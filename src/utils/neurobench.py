import sys
import os
import math
import time
import json
import struct
import random
import threading
import queue
from pathlib import Path
from datetime import datetime
from PySide6 import QtCore, QtWidgets, QtGui
import pyqtgraph as pg
import numpy as np

# Optional: serial backend
try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

APP_NAME = "SignalForge (mock device)"
# Fix path to be relative to this script location
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "sensor_config.json"
SYNC1 = 0xC7
SYNC2 = 0x7C
END_BYTE = 0x01
ADC_BITS = 14
ADC_MAX = (1 << ADC_BITS) - 1

# -------------------------
# Signal generation helpers
# -------------------------
def clamp(v, a=-1.0, b=1.0):
    return max(a, min(b, v))

class ChannelGenerator:
    """Generates normalized [-1..1] samples for a single logical channel."""
    def __init__(self, role="EMG"):
        self.role = role  # "EMG" | "EEG" | "EOG" | "NONE"
        self.lock = threading.Lock()
        # dynamic state
        self.events = []  # queued transient events (tuples)
        self.ssv_ep_on = False
        self.ssv_freq = None
        self.sampling_rate = 512.0
        self.scale = 1.0
        self.random = random.Random(12345)

    def set_role(self, role):
        with self.lock:
            self.role = role

    def set_rate(self, rate):
        with self.lock:
            self.sampling_rate = float(rate)

    def set_scale(self, scale):
        with self.lock:
            self.scale = float(scale)

    def trigger_emg(self, intensity="light"):
        """Intensity: light | medium | strong -> enqueue burst event"""
        with self.lock:
            dur = {"light": 0.12, "medium": 0.25, "strong": 0.45}.get(intensity, 0.12)
            amp = {"light": 0.35, "medium": 0.75, "strong": 1.25}.get(intensity, 0.35)
            ev = {"type": "emg_burst", "t0": None, "dur": dur, "amp": amp}
            self.events.append(ev)

    def trigger_eog(self, dir_name="blink"):
        with self.lock:
            dur = 0.18 if dir_name != "blink" else 0.08
            amp = 0.8 if dir_name != "blink" else 1.2
            ev = {"type": "eog_pulse", "t0": None, "dur": dur, "amp": amp, "dir": dir_name}
            self.events.append(ev)

    def toggle_ssvep(self, freq=None, enabled=False):
        with self.lock:
            if enabled:
                self.ssv_ep_on = True
                self.ssv_freq = freq
            else:
                self.ssv_ep_on = False
                self.ssv_freq = None

    def synth_now(self, t_seconds):
        """Return value at a given continuous time (seconds)."""
        with self.lock:
            role = self.role
            ssv_on = self.ssv_ep_on
            ssv_freq = self.ssv_freq
            scale = self.scale
            events = list(self.events)  # shallow copy
        val = 0.0
        # continuous components
        if role == "EEG":
            # SSVEP if toggled
            if ssv_on and ssv_freq:
                # fundamental + small harmonic
                val += 0.25 * math.sin(2 * math.pi * ssv_freq * t_seconds)
                val += 0.08 * math.sin(2 * math.pi * (2 * ssv_freq) * t_seconds)
                val += 0.02 * self.random.gauss(0, 1)
            # background alpha rhythm + slow drift
            val += 0.06 * math.sin(2 * math.pi * 10.0 * t_seconds) + 0.01 * math.sin(2 * math.pi * 0.2 * t_seconds)
        elif role == "EMG":
            # noisy baseline
            noise = self.random.gauss(0, 0.06)
            env = 0.05 * (1 + 0.5 * math.sin(2 * math.pi * 0.15 * t_seconds))
            val += env * noise
        elif role == "EOG":
            val += 0.005 * self.random.gauss(0, 1)
        else:
            val += 0.0

        # event processing (bursts / pulses) — events store t0 when first used
        with self.lock:
            remaining = []
            for ev in self.events:
                if ev.get("t0") is None:
                    ev["t0"] = t_seconds
                dt = t_seconds - ev["t0"]
                if ev["type"] == "emg_burst":
                    dur = ev["dur"]
                    amp = ev["amp"]
                    if dt <= dur:
                        # triangular-ish burst * noise
                        env = (1.0 - abs((dt / dur) * 2 - 1))  # triangle
                        val += amp * env * (0.6 * self.random.gauss(0, 1))
                        remaining.append(ev)
                    # else: event ends (don't re-add)
                elif ev["type"] == "eog_pulse":
                    dur = ev["dur"]
                    amp = ev["amp"]
                    if dt <= dur:
                        # simple decaying step shaped pulse depending on dir
                        pulse = amp * (1.0 - (dt / dur))
                        # direction mapping: up/down/left/right/blink -> sign/offset
                        if ev.get("dir") == "up":
                            val += pulse * 0.6
                        elif ev.get("dir") == "down":
                            val -= pulse * 0.6
                        elif ev.get("dir") == "left":
                            val -= pulse * 0.4
                        elif ev.get("dir") == "right":
                            val += pulse * 0.4
                        else:  # blink
                            val += pulse * 1.0
                        remaining.append(ev)
                    # else finished
            # commit remaining events back (thread-safe)
            self.events = remaining

        # final scale and clamp
        out = clamp(val * scale)
        return out

# -------------------------
# Serial writer thread
# -------------------------
class SerialWriter(threading.Thread):
    def __init__(self, port_name, baud, sample_rate, channels, data_queue, binary=True, quiet=False):
        super().__init__(daemon=True)
        self.port_name = port_name
        self.baud = baud
        self.sample_rate = sample_rate
        self.channels = channels
        self.data_queue = data_queue  # receives tuples (adc0, adc1, timestamp)
        self._stop = threading.Event()
        self.binary = binary
        self.quiet = quiet
        self.counter = 0
        self.ser = None

    def open_port(self):
        if serial is None:
            print("[SerialWriter] pyserial missing; running in loopback-only mode")
            return False
        try:
            self.ser = serial.Serial(self.port_name, baudrate=self.baud, timeout=1, write_timeout=1)
            return True
        except Exception as e:
            print(f"[SerialWriter] Failed to open {self.port_name}: {e}")
            self.ser = None
            return False

    def stop(self):
        self._stop.set()

    def run(self):
        opened = self.open_port()
        interval = 1.0 / float(self.sample_rate)
        while not self._stop.is_set():
            try:
                adc0, adc1, ts = self.data_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            # Build packet according to the expected layout
            ctr = self.counter & 0xFF
            ch0 = int(adc0) & 0xFFFF
            ch1 = int(adc1) & 0xFFFF
            # packet bytes indices: sync1 sync2 counter ch0_hi ch0_lo ch1_hi ch1_lo end
            packet = bytes([SYNC1, SYNC2, ctr,
                            (ch0 >> 8) & 0xFF, ch0 & 0xFF,
                            (ch1 >> 8) & 0xFF, ch1 & 0xFF,
                            END_BYTE])
            # write
            if opened and self.ser:
                try:
                    self.ser.write(packet)
                except Exception as e:
                    print("[SerialWriter] write error:", e)
            # show console print (parsed)
            # if not self.quiet:
            # uncomment to enable logging of data sent to serial port
            # print(f"[SerialWriter] sent ctr={ctr:03d} ch0={ch0} ch1={ch1} time={datetime.fromtimestamp(ts).isoformat()}")
            self.counter += 1

        # close serial
        if self.ser:
            try:
                self.ser.close()
            except:
                pass

# -------------------------
# GUI Application
# -------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)
        self.config = self.load_config()
        # state

        
        self.sample_rate = self.config.get("sampling_rate", 512.0)
        self.baud = self.config.get("baud", 230400)
        self.port = self.config.get("serial_port", "")
        self.streaming = False
        self.binary = self.config.get("binary", True)

        # two channel generators
        self.ch_gens = [ChannelGenerator(), ChannelGenerator()]
        # apply config mapping if exist
        mapping = self.config.get("channel_mapping", {})
        for i in range(2):
            role = mapping.get(f"ch{i}", {}).get("sensor", "EMG")
            self.ch_gens[i].set_role(role)

        # queue for inter-thread samples
        self.sample_queue = queue.Queue(maxsize=4096)
        # Bounded queue for plotting to prevent UI freeze if main thread falls behind
        self.plot_queue = queue.Queue(maxsize=1024) 
        self.serial_writer = None
        
        print(f"[{datetime.now()}] Building UI...")
        self._build_ui()
        print(f"[{datetime.now()}] Building Plot...")
        self._build_plot()
        print(f"[{datetime.now()}] Initial port update...")
        self.update_port_list()
        print(f"[{datetime.now()}] Port update done. Starting timer...")
        self.timer = QtCore.QTimer()
        self.timer.setInterval(100)  # UI refresh ~10 Hz (relaxed)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start()

        # generator loop in background
        print(f"[{datetime.now()}] Starting generator thread...")
        self.gen_thread = threading.Thread(target=self._generator_loop, daemon=True)
        self._gen_stop = threading.Event()
        self.gen_thread.start()
        print(f"[{datetime.now()}] Init complete.")

    def load_config(self):
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
        # default
        return {
            "sampling_rate": 512.0,
            "baud": 230400,
            "serial_port": "",
            "binary": True,
            "channel_mapping": {
                "ch0": {"sensor": "EMG"},
                "ch1": {"sensor": "EEG"}
            },
            "display": {
                "manualZoom": False,
                "yMin": -1,
                "yMax": 1
            }
        }

    def save_config(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.config["sampling_rate"] = self.sample_rate
            self.config["baud"] = self.baud
            self.config["serial_port"] = self.port
            self.config["binary"] = self.binary
            # channel mapping read from UI
            self.config["channel_mapping"] = {
                "ch0": {"sensor": self.ch0_map.currentText()},
                "ch1": {"sensor": self.ch1_map.currentText()}
            }
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2))
            print("[Main] Config saved to", CONFIG_PATH)
        except Exception as e:
            print("[Main] Failed to save config:", e)

    def _build_ui(self):
        w = QtWidgets.QWidget()
        self.setCentralWidget(w)
        layout = QtWidgets.QHBoxLayout(w)

        # Left pane: controls (use a scroll area so controls never disappear on resize/fullscreen)
        left_content = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_content)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        # mapping
        left_layout.addWidget(QtWidgets.QLabel("<b>Channel Mapping</b>"))
        self.ch0_map = QtWidgets.QComboBox()
        self.ch0_map.addItems(["EMG", "EEG", "EOG", "NONE"])
        self.ch0_map.setCurrentText(self.config.get("channel_mapping", {}).get("ch0", {}).get("sensor", "EMG"))
        self.ch0_map.currentTextChanged.connect(lambda v: self._on_map_change(0, v))
        left_layout.addWidget(QtWidgets.QLabel("Channel 0"))
        left_layout.addWidget(self.ch0_map)

        self.ch1_map = QtWidgets.QComboBox()
        self.ch1_map.addItems(["EMG", "EEG", "EOG", "NONE"])
        self.ch1_map.setCurrentText(self.config.get("channel_mapping", {}).get("ch1", {}).get("sensor", "EEG"))
        self.ch1_map.currentTextChanged.connect(lambda v: self._on_map_change(1, v))
        left_layout.addWidget(QtWidgets.QLabel("Channel 1"))
        left_layout.addWidget(self.ch1_map)

        left_layout.addSpacing(6)

        # dynamic per-channel controls container
        left_layout.addWidget(QtWidgets.QLabel("<b>Channel Controls</b>"))
        # controls for each channel
        self.controls_ch0 = self._build_channel_controls(0)
        self.controls_ch1 = self._build_channel_controls(1)
        ctrl_wrapper = QtWidgets.QWidget()
        ctrl_layout = QtWidgets.QVBoxLayout(ctrl_wrapper)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(6)
        ctrl_layout.addWidget(QtWidgets.QLabel("Channel 0 controls"))
        ctrl_layout.addWidget(self.controls_ch0)
        ctrl_layout.addSpacing(8)
        ctrl_layout.addWidget(QtWidgets.QLabel("Channel 1 controls"))
        ctrl_layout.addWidget(self.controls_ch1)
        left_layout.addWidget(ctrl_wrapper)

        left_layout.addSpacing(12)

        # Serial / Streaming controls
        left_layout.addWidget(QtWidgets.QLabel("<b>Streaming</b>"))
        form = QtWidgets.QFormLayout()
        # port
        self.port_combo = QtWidgets.QComboBox()
        form.addRow("COM Port", self.port_combo)
        # baud
        self.baud_input = QtWidgets.QLineEdit(str(self.baud))
        form.addRow("Baud", self.baud_input)
        # sample rate
        self.rate_input = QtWidgets.QLineEdit(str(self.sample_rate))
        form.addRow("Sample rate (Hz)", self.rate_input)
        left_layout.addLayout(form)

        h = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("Refresh ports")
        self.btn_refresh.clicked.connect(self.update_port_list)
        h.addWidget(self.btn_refresh)
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_start.clicked.connect(self.start_stream)
        h.addWidget(self.btn_start)
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_stream)
        h.addWidget(self.btn_stop)
        left_layout.addLayout(h)

        # plotting options
        left_layout.addSpacing(10)
        left_layout.addWidget(QtWidgets.QLabel("<b>Display</b>"))
        self.autoscale_chk = QtWidgets.QCheckBox("Autoscale Y")
        self.autoscale_chk.setChecked(True)
        left_layout.addWidget(self.autoscale_chk)
        left_layout.addWidget(QtWidgets.QLabel("Y min / max (manual)"))
        ymin_layout = QtWidgets.QHBoxLayout()
        self.ylim_min = QtWidgets.QLineEdit("-1")
        self.ylim_max = QtWidgets.QLineEdit("1")
        ymin_layout.addWidget(self.ylim_min)
        ymin_layout.addWidget(self.ylim_max)
        left_layout.addLayout(ymin_layout)

        left_layout.addStretch()
        # save config button
        save_btn = QtWidgets.QPushButton("Save config")
        save_btn.clicked.connect(self.save_config)
        left_layout.addWidget(save_btn)

        # Put left_content into a QScrollArea so controls remain accessible at all sizes.
        left_scroll = QtWidgets.QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_content)
        left_scroll.setMinimumWidth(320)   # nice starting width but not fixed
        left_scroll.setMaximumWidth(520)   # prevents it from taking too much space on ultra-wide screens

        # Right pane: plots + console
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(8)
        # plots
        self.plot0 = pg.PlotWidget(title="Channel 0")
        self.plot1 = pg.PlotWidget(title="Channel 1")
        self.plot0.showGrid(x=True, y=True)
        self.plot1.showGrid(x=True, y=True)
        self.curve0 = self.plot0.plot(pen=pg.mkPen('c', width=1.4))
        self.curve1 = self.plot1.plot(pen=pg.mkPen('y', width=1.4))
        right_layout.addWidget(self.plot0, 1)
        right_layout.addWidget(self.plot1, 1)

        # console log
        self.console = QtWidgets.QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(160)
        right_layout.addWidget(self.console)

        # Add both panes to main layout. Right pane gets stretch weight so it expands more.
        layout.addWidget(left_scroll, 0)
        layout.addWidget(right, 1)

    def _build_channel_controls(self, ch_index):
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        # EMG buttons
        emg_box = QtWidgets.QGroupBox("EMG actions")
        emg_layout = QtWidgets.QHBoxLayout()
        b_light = QtWidgets.QPushButton("Light")
        b_med = QtWidgets.QPushButton("Medium")
        b_str = QtWidgets.QPushButton("Strong")
        emg_layout.addWidget(b_light); emg_layout.addWidget(b_med); emg_layout.addWidget(b_str)
        emg_box.setLayout(emg_layout)
        b_light.clicked.connect(lambda: self._emg_action(ch_index, "light"))
        b_med.clicked.connect(lambda: self._emg_action(ch_index, "medium"))
        b_str.clicked.connect(lambda: self._emg_action(ch_index, "strong"))
        v.addWidget(emg_box)

        # EEG SSVEP buttons (toggle)
        ssvep_box = QtWidgets.QGroupBox("SSVEP (EEG) - toggle to simulate gaze")
        ssvep_layout = QtWidgets.QGridLayout()
        freqs = [6, 8, 10, 12, 15, 20]
        self.ssvep_buttons = getattr(self, "ssvep_buttons_" + str(ch_index), {})
        self.ssvep_buttons = {}
        for i, f in enumerate(freqs):
            btn = QtWidgets.QPushButton(f"{f} Hz")
            btn.setCheckable(True)
            btn.toggled.connect(lambda checked, ch=ch_index, freq=f: self._ssvep_toggle(ch, freq, checked))
            ssvep_layout.addWidget(btn, i//3, i%3)
            self.ssvep_buttons[f] = btn
        ssvep_box.setLayout(ssvep_layout)
        v.addWidget(ssvep_box)

        # EOG controls
        eog_box = QtWidgets.QGroupBox("EOG actions")
        eog_layout = QtWidgets.QHBoxLayout()
        for name in ["Left", "Right", "Up", "Down", "Blink"]:
            b = QtWidgets.QPushButton(name)
            b.clicked.connect(lambda _checked, ch=ch_index, n=name.lower(): self._eog_action(ch, n))
            eog_layout.addWidget(b)
        eog_box.setLayout(eog_layout)
        v.addWidget(eog_box)

        return widget

    def _on_map_change(self, ch, text):
        self.log(f"Mapping ch{ch} -> {text}")
        self.ch_gens[ch].set_role(text)

    def _emg_action(self, ch, intensity):
        self.log(f"EMG trigger ch{ch} intensity={intensity}")
        self.ch_gens[ch].trigger_emg(intensity)

    def _eog_action(self, ch, name):
        self.log(f"EOG trigger ch{ch} dir={name}")
        self.ch_gens[ch].trigger_eog(name)

    def _ssvep_toggle(self, ch, freq, checked):
        self.log(f"SSVEP ch{ch} freq={freq}Hz {'ON' if checked else 'OFF'}")
        self.ch_gens[ch].toggle_ssvep(freq if checked else None, enabled=checked)

    def update_port_list(self):
        self.port_combo.clear()
        ports = []
        if list_ports:
            try:
                print(f"[{datetime.now()}] calling list_ports.comports()...")
                ports = [p.device for p in list_ports.comports()]
                print(f"[{datetime.now()}] list_ports.comports() returned {len(ports)} ports")
            except Exception as e:
                print(f"[{datetime.now()}] Error listing ports: {e}")
                ports = []
        self.port_combo.addItems([""] + ports)

    def _build_plot(self):
        # rolling buffers for plotting
        self.plot_len = int(self.sample_rate * 4)  # 4 seconds buffer
        self.buf0 = np.zeros(self.plot_len, dtype=float)
        self.buf1 = np.zeros(self.plot_len, dtype=float)
        self.ptr = 0

    def _on_timer(self):
        # update plots from buffers
        if not getattr(self, "_timer_logged", False):
            print(f"[{datetime.now()}] First _on_timer call")
            self._timer_logged = True

        # drain queue
        new_data0 = []
        new_data1 = []
        while True:
            try:
                v0, v1 = self.plot_queue.get_nowait()
                new_data0.append(v0)
                new_data1.append(v1)
            except queue.Empty:
                break
        
        n = len(new_data0)
        if n > 0:
            # Shift buffers and append new data
            # Doing this in main thread is safe
            if n >= self.plot_len:
                self.buf0 = np.array(new_data0[-self.plot_len:], dtype=float)
                self.buf1 = np.array(new_data1[-self.plot_len:], dtype=float)
            else:
                self.buf0 = np.roll(self.buf0, -n)
                self.buf1 = np.roll(self.buf1, -n)
                self.buf0[-n:] = new_data0
                self.buf1[-n:] = new_data1
        
        self.curve0.setData(self.buf0)
        self.curve1.setData(self.buf1)
        
        # apply manual Y limits if needed
        if not self.autoscale_chk.isChecked():
            try:
                ymin = float(self.ylim_min.text()); ymax = float(self.ylim_max.text())
                self.plot0.setYRange(ymin, ymax, padding=0)
                self.plot1.setYRange(ymin, ymax, padding=0)
            except Exception:
                pass

    def start_stream(self):
        if self.streaming:
            return
        # get values
        self.port = self.port_combo.currentText().strip()
        try:
            self.baud = int(self.baud_input.text().strip())
            self.sample_rate = float(self.rate_input.text().strip())
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Invalid", "Please enter valid baud and sample rate")
            return

        # re-initialize plot buffers with new sample rate if it changed
        self._build_plot()

        # update generator rates
        for g in self.ch_gens:
            g.set_rate(self.sample_rate)
            g.set_scale(1.0)

        # prepare serial writer
        self.sample_queue = queue.Queue(maxsize=8192)
        self.serial_writer = SerialWriter(self.port, self.baud, self.sample_rate, channels=2,
                                          data_queue=self.sample_queue, binary=self.binary, quiet=False)
        self.serial_writer.start()
        self.streaming = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log(f"Streaming started on {self.port if self.port else 'LOOPBACK'}")
        # start pushing samples from generator loop (already running)

    def stop_stream(self):
        if not self.streaming:
            return
        if self.serial_writer:
            self.serial_writer.stop()
            self.serial_writer.join(timeout=1.0)
            self.serial_writer = None
        self.streaming = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log("Streaming stopped")

    def _generator_loop(self):
        """Background loop that produces samples at sample_rate and enqueues them for serial writer."""
        last_t = time.perf_counter()
        frame = 0
        while True:
            if self._gen_stop.is_set():
                break
            t_target = frame / max(1.0, self.sample_rate)
            t_now = time.perf_counter()
            # Use a monotonic origin per run to feed channel gens
            origin = getattr(self, "_gen_origin", None)
            if origin is None:
                self._gen_origin = time.perf_counter()
                origin = self._gen_origin
            t_seconds = time.perf_counter() - origin

            # synth values for both channels
            v0 = self.ch_gens[0].synth_now(t_seconds)
            v1 = self.ch_gens[1].synth_now(t_seconds)

            # map normalized [-1..1] -> 14-bit ADC
            a0 = int(round(((v0 + 1.0) / 2.0) * ADC_MAX))
            a1 = int(round(((v1 + 1.0) / 2.0) * ADC_MAX))
            
            # push to plot buffers (scale back to -1..1 for plot)
            self._append_plot(v0, v1)
            
            # enqueue for serial writer if streaming
            if self.streaming and self.serial_writer:
                try:
                    self.sample_queue.put_nowait((a0, a1, time.time()))
                except queue.Full:
                    # drop if writer is slow
                    pass

            if frame % 100 == 0:
                print(f"[{datetime.now()}] Gen loop frame {frame}")
            frame += 1
            # sleep until next sample
            next_target = origin + frame / max(1.0, self.sample_rate)
            sleep_time = next_target - time.perf_counter()
            if sleep_time > 0:
                # If sleep_time is large, sleep in small increments to maintain responsiveness
                # or just sleep if it's small enough.
                time.sleep(sleep_time)
            else:
                # behind — continue without sleeping to catch up
        # but limit catch-up to avoid freezing if real-time is impossible
                if frame % 100 == 0:
                    time.sleep(0.001)

    def _append_plot(self, v0, v1):
        # Enqueue for main thread to handle
        try:
            self.plot_queue.put_nowait((v0, v1))
        except queue.Full:
            # If main thread gets stuck, drop visual frames rather than blocking or OOM
            pass
        self.buf1[self.ptr] = v1
        self.ptr = (self.ptr + 1) % self.plot_len

    def log(self, s):
        now = datetime.now().strftime("%H:%M:%S")
        self.console.appendPlainText(f"[{now}] {s}")
        # also print to stdout
        print(f"[{now}] {s}")

    def closeEvent(self, event):
        # stop threads
        self._gen_stop.set()
        if self.serial_writer:
            self.serial_writer.stop()
            self.serial_writer.join(timeout=0.5)
        event.accept()

# -------------------------
# Run
# -------------------------
def main():
    try:
        print(f"[{datetime.now()}] Starting {APP_NAME}...")
        print(f"[{datetime.now()}] Config path: {CONFIG_PATH.resolve()}")
        app = QtWidgets.QApplication(sys.argv)
        win = MainWindow()
        win.show()
        print(f"[{datetime.now()}] Window shown, entering event loop.")
        ret = app.exec()
        print(f"[{datetime.now()}] Event loop exited with {ret}")
        sys.exit(ret)
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"CRITICAL ERROR: {err_msg}")
        try:
            with open("error.log", "w") as f:
                f.write(err_msg)
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
