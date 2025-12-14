
# import sys
# import os
# import json
# import time
# import math
# import struct
# import threading
# import queue
# import logging
# from logging.handlers import RotatingFileHandler
# from pathlib import Path
# from datetime import datetime
# import numpy as np

# from PySide6 import QtCore, QtWidgets
# import pyqtgraph as pg

# # Project imports
# PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# SRC = PROJECT_ROOT / "src"

# if str(SRC) not in sys.path:
#     sys.path.insert(0, str(SRC))

# try:
#     from acquisition.serial_reader import SerialPacketReader
#     from acquisition.packet_parser import PacketParser
#     from acquisition.lsl_streams import LSLStreamer, LSL_AVAILABLE
#     from src.utils.config import config 
# except Exception as e:
#     raise SystemExit(f"Failed to import modules: {e}")

# # File paths
# CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
# DEFAULT_SAVE_FOLDER = PROJECT_ROOT / "data" / "sessions"
# LOG_DIR = PROJECT_ROOT / "logs"
# LOG_DIR.mkdir(parents=True, exist_ok=True)
# PACKET_STATS_LOG = LOG_DIR / "packet_stats.log"

# # ADC constants
# ADC_BITS = 14
# ADC_MAX = (1 << ADC_BITS) - 1
# VREF = 3300.0

# # Packet constants
# SYNC1 = 0xC7
# SYNC2 = 0x7C
# END_BYTE = 0x01

# # Logging setup
# logger = logging.getLogger("packet_stats")
# logger.setLevel(logging.INFO)
# handler = RotatingFileHandler(str(PACKET_STATS_LOG), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
# formatter = logging.Formatter("%(asctime)s %(message)s")
# handler.setFormatter(formatter)
# logger.addHandler(handler)

# def adc_to_uv(adc_val, bits=ADC_BITS, vref=VREF):
#     """Map ADC integer to voltage units."""
#     volts = ((adc_val / (2 ** bits)) * vref) - (vref / 2.0)
#     return volts

# def ensure_dir(p: Path):
#     p.mkdir(parents=True, exist_ok=True)

# # ========== Main GUI Window ==========

# class AcquisitionWindow(QtWidgets.QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("AcqQT — PySide6 Acquisition (ConfigWatcher v1.0)")
#         self.resize(1300, 800)
        
#         # ✅ Get config from ConfigWatcher (always fresh!)
#         self.config = config.get_all()
#         self.sampling_rate = float(self.config.get("sampling_rate", 512))
#         self.window_seconds = float(self.config.get("display", {}).get("window_seconds", 5.0))
#         self.buffer_size = int(self.sampling_rate * self.window_seconds)
        
#         # Paths
#         self.save_path = DEFAULT_SAVE_FOLDER
#         self.config_path = CONFIG_PATH
        
#         # Buffers
#         self.ch0_buffer = np.zeros(self.buffer_size, dtype=float)
#         self.ch1_buffer = np.zeros(self.buffer_size, dtype=float)
#         self.buf_ptr = 0
        
#         # Pipeline objects
#         self.serial_thread = None
#         self.serial_worker = None
#         self.lsl_raw_uV = None
        
#         # Recording state
#         self.is_connected = False
#         self.is_acquiring = False
#         self.is_recording = False
#         self.session_data = []
#         self.save_folder = Path(self.config.get("save_folder", str(DEFAULT_SAVE_FOLDER)))
#         ensure_dir(self.save_folder)
#         self.save_on_stop = True
#         self.packet_count = 0
#         self.last_counter = None
        
#         # Diagnostics
#         self._last_diag_log_time = 0.0
#         self._diag_log_interval = 1.0
        
#         # Build UI
#         self._build_ui()
#         self._init_plotting()
        
#         # UI timer
#         self.ui_timer = QtCore.QTimer()
#         self.ui_timer.setInterval(50)
#         self.ui_timer.timeout.connect(self._on_ui_timer)
#         self.ui_timer.start()
        
#         # Start config monitoring thread
#         self._start_config_monitor()
    
#     def _start_config_monitor(self):
#         """Monitor config changes and update UI."""
#         def monitor():
#             last_sr = self.sampling_rate
#             while True:
#                 try:
#                     current_sr = config.get("sampling_rate", 512)
#                     if current_sr != last_sr:
#                         print(f"🔄 Config changed! Sampling rate: {last_sr}Hz → {current_sr}Hz")
#                         self.sampling_rate = float(current_sr)
#                         self.buffer_size = int(self.sampling_rate * self.window_seconds)
#                         self.ch0_buffer = np.zeros(self.buffer_size, dtype=float)
#                         self.ch1_buffer = np.zeros(self.buffer_size, dtype=float)
#                         self.buf_ptr = 0
#                         last_sr = current_sr
#                         self._log(f"✅ Config updated: sampling_rate={current_sr}Hz")
                    
#                     time.sleep(1)
#                 except Exception as e:
#                     print(f"Config monitor error: {e}")
#                     time.sleep(1)
        
#         t = threading.Thread(target=monitor, daemon=True)
#         t.start()
    
#     def _build_ui(self):
#         """Build UI layout."""
#         central = QtWidgets.QWidget()
#         self.setCentralWidget(central)
#         hl = QtWidgets.QHBoxLayout(central)
        
#         # Left panel
#         left_scroll = QtWidgets.QScrollArea()
#         left_scroll.setWidgetResizable(True)
#         left = QtWidgets.QWidget()
#         left_layout = QtWidgets.QVBoxLayout(left)
#         left_layout.setContentsMargins(10, 10, 10, 10)
        
#         # Serial controls
#         left_layout.addWidget(QtWidgets.QLabel("Serial / Stream"))
#         self.port_combo = QtWidgets.QComboBox()
#         left_layout.addWidget(self.port_combo)
        
#         refresh_btn = QtWidgets.QPushButton("Refresh ports")
#         refresh_btn.clicked.connect(self.refresh_ports)
#         left_layout.addWidget(refresh_btn)
        
#         row = QtWidgets.QHBoxLayout()
#         row.addWidget(QtWidgets.QLabel("Baud"))
#         self.baud_edit = QtWidgets.QLineEdit("230400")
#         row.addWidget(self.baud_edit)
#         left_layout.addLayout(row)
        
#         # Channel mapping
#         grp_map = QtWidgets.QGroupBox("Channel Mapping")
#         gmap_layout = QtWidgets.QFormLayout(grp_map)
#         self.ch0_combo = QtWidgets.QComboBox()
#         self.ch0_combo.addItems(["EMG", "EOG", "EEG"])
#         self.ch1_combo = QtWidgets.QComboBox()
#         self.ch1_combo.addItems(["EMG", "EOG", "EEG"])
        
#         ch_mapping = self.config.get("channel_mapping", {})
#         self.ch0_combo.setCurrentText(ch_mapping.get("ch0", {}).get("sensor", "EMG"))
#         self.ch1_combo.setCurrentText(ch_mapping.get("ch1", {}).get("sensor", "EEG"))
        
#         # ===== WIRING COMBO BOXES TO SAVE =====
#         self.ch0_combo.currentTextChanged.connect(self._on_ch0_changed)
#         self.ch1_combo.currentTextChanged.connect(self._on_ch1_changed)

#         # Mark that we need to save on next button click
#         self._pending_mapping_changes = False

#         gmap_layout.addRow("Channel 0:", self.ch0_combo)
#         gmap_layout.addRow("Channel 1:", self.ch1_combo)
#         left_layout.addWidget(grp_map)
        
#         # Connect buttons
#         self.btn_connect = QtWidgets.QPushButton("Connect")
#         self.btn_connect.clicked.connect(self.connect_serial)
#         self.btn_disconnect = QtWidgets.QPushButton("Disconnect")
#         self.btn_disconnect.clicked.connect(self.disconnect_serial)
#         self.btn_disconnect.setEnabled(False)
#         left_layout.addWidget(self.btn_connect)
#         left_layout.addWidget(self.btn_disconnect)
#         left_layout.addSpacing(8)
        
#         # Acquisition controls
#         left_layout.addWidget(QtWidgets.QLabel("Acquisition"))
#         self.btn_start = QtWidgets.QPushButton("Start Acquisition")
#         self.btn_start.setEnabled(False)
#         self.btn_start.clicked.connect(self.start_acquisition)
        
#         btn_save_cfg = QtWidgets.QPushButton("Save Mapping to Config")
#         btn_save_cfg.clicked.connect(self.save_config)
#         left_layout.addWidget(btn_save_cfg)
        
#         self.btn_stop = QtWidgets.QPushButton("Stop Acquisition")
#         self.btn_stop.clicked.connect(self.stop_acquisition)
#         left_layout.addWidget(self.btn_start)
#         left_layout.addWidget(self.btn_stop)
        
#         # Recording
#         left_layout.addWidget(QtWidgets.QLabel("Recording"))
#         rec_h = QtWidgets.QHBoxLayout()
#         self.btn_record = QtWidgets.QPushButton("Start Recording")
#         self.btn_record.setEnabled(False)
#         self.btn_record.clicked.connect(self._toggle_record)
#         rec_h.addWidget(self.btn_record)
        
#         self.btn_save_now = QtWidgets.QPushButton("Save Session Now")
#         self.btn_save_now.clicked.connect(self._save_session_now)
#         rec_h.addWidget(self.btn_save_now)
#         left_layout.addLayout(rec_h)
        
#         # Save folder
#         sf_h = QtWidgets.QHBoxLayout()
#         self.folder_label = QtWidgets.QLineEdit(str(self.save_folder))
#         self.folder_label.setReadOnly(True)
#         sf_h.addWidget(self.folder_label)
#         choose = QtWidgets.QPushButton("Choose")
#         choose.clicked.connect(self._choose_folder)
#         sf_h.addWidget(choose)
#         left_layout.addLayout(sf_h)
        
#         self.autosave_chk = QtWidgets.QCheckBox("Save on stop (auto)")
#         self.autosave_chk.setChecked(self.save_on_stop)
#         left_layout.addWidget(self.autosave_chk)
        
#         left_layout.addStretch()
#         left_scroll.setWidget(left)
#         left_scroll.setMinimumWidth(320)
#         hl.addWidget(left_scroll, 0)
        
#         # Right panel: plots + diagnostics
#         right = QtWidgets.QWidget()
#         rlay = QtWidgets.QVBoxLayout(right)
        
#         pg.setConfigOptions(antialias=True)
#         self.plot0 = pg.PlotWidget(title="Channel 0 (µV)")
#         self.plot1 = pg.PlotWidget(title="Channel 1 (µV)")
#         self.curve0 = self.plot0.plot(pen=pg.mkPen('c', width=1.4))
#         self.curve1 = self.plot1.plot(pen=pg.mkPen('y', width=1.4))
#         rlay.addWidget(self.plot0, 1)
#         rlay.addWidget(self.plot1, 1)
        
#         # Diagnostics
#         self.diag_box = QtWidgets.QPlainTextEdit()
#         self.diag_box.setReadOnly(True)
#         self.diag_box.setMaximumHeight(160)
#         rlay.addWidget(self.diag_box)
        
#         hl.addWidget(right, 1)
#         self.refresh_ports()
#         self.plot0.setYRange(-1000, 1000)
#         self.plot1.setYRange(-1000, 1000)
    
#     def _on_ch0_changed(self, sensor_type):
#         """Called when channel 0 dropdown changes."""
#         self._pending_mapping_changes = True
#         self._log(f"📝 Channel 0 mapping changed to: {sensor_type} (pending save...)")

#     def _on_ch1_changed(self, sensor_type):
#         """Called when channel 1 dropdown changes."""
#         self._pending_mapping_changes = True
#         self._log(f"📝 Channel 1 mapping changed to: {sensor_type} (pending save...)")

#     def _init_plotting(self):
#         self.plot_len = self.buffer_size
#         self.plot0.setYRange(-500, 500)
#         self.plot1.setYRange(-500, 500)
    
#     def refresh_ports(self):
#         try:
#             import serial.tools.list_ports as lp
#             ports = [p.device for p in lp.comports()]
#         except:
#             ports = []
#         self.port_combo.clear()
#         self.port_combo.addItems(ports or ["No ports"])
    
#     def connect_serial(self):
#         port = self.port_combo.currentText()
#         baud = int(self.baud_edit.text().strip() or 230400)

#         if not port or port.startswith("No"):
#             self._log("No COM port selected")
#             return

#         self.serial_thread = QtCore.QThread()
#         self.serial_worker = SerialWorker(port, baud)

#         self.serial_worker.moveToThread(self.serial_thread)
#         self.serial_thread.started.connect(self.serial_worker.start)
#         self.serial_worker.packet_ready.connect(self._on_packet_block)
#         self.serial_worker.error.connect(self._log)

#         self.serial_thread.start()

#         self.is_connected = True
#         self.btn_connect.setEnabled(False)
#         self.btn_disconnect.setEnabled(True)
#         self.btn_start.setEnabled(True)

#         self._log(f"Serial connected on {port}")
  
#     def disconnect_serial(self):
#         if self.serial_worker:
#             self.serial_worker.stop()

#         if self.serial_thread:
#             self.serial_thread.quit()
#             self.serial_thread.wait()

#         self.serial_worker = None
#         self.serial_thread = None

#         self.is_connected = False
#         self.btn_connect.setEnabled(True)
#         self.btn_disconnect.setEnabled(False)
#         self.btn_start.setEnabled(False)

#         self._log("Serial disconnected")
    
#     def start_acquisition(self):
#         if not self.is_connected:
#             self._log("Not connected")
#             return
#         self.is_acquiring = True
        
#         self.serial_worker.reader.send_command("START")
#         self.btn_start.setEnabled(False)
#         self.btn_stop.setEnabled(True)
#         self.btn_record.setEnabled(True)
        
#         # ONE LSL STREAM ONLY (µV)
#         if LSL_AVAILABLE:
#             labels = ["ch0", "ch1"]
#             self.lsl_raw_uV = LSLStreamer(
#                 "Bio-Raw-uV",
#                 channel_types=["uV", "uV"],
#                 channel_labels=labels,
#                 channel_count=2,
#                 nominal_srate=self.sampling_rate
#             )

#         self._log("Acquisition started")
    
#     def stop_acquisition(self):
#         self.is_acquiring = False
#         self.serial_worker.reader.send_command("STOP")    
#         self.btn_start.setEnabled(True)
#         self.btn_stop.setEnabled(False)
#         self._log("Acquisition stopped")
        
#         if self.autosave_chk.isChecked() and self.is_recording:
#             self._log("Auto-saving session on stop")
#             self._save_session_now()
        
#         self.is_recording = False
#         self.btn_record.setText("Start Recording")
#         self.btn_record.setEnabled(False)
    
#     def _toggle_record(self):
#         if not self.is_acquiring:
#             self._log("Start acquisition first")
#             return
        
#         self.is_recording = not self.is_recording
#         self.btn_record.setText("Stop Recording" if self.is_recording else "Start Recording")
#         self._log("Recording: " + ("ON" if self.is_recording else "OFF"))
        
#         if self.is_recording:
#             self.session_data = []
    
#     def _choose_folder(self):
#         dlg = QtWidgets.QFileDialog(self, "Select folder to save sessions")
#         dlg.setFileMode(QtWidgets.QFileDialog.Directory)
#         if dlg.exec():
#             path = dlg.selectedFiles()[0]
#             self.save_folder = Path(path)
#             self.folder_label.setText(str(self.save_folder))
#             ensure_dir(self.save_folder)
#             self._log(f"Save folder set to {self.save_folder}")
    
#     def _save_session_now(self):
#         if not self.session_data:
#             self._log("No session data to save")
#             return
        
#         ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#         ensure_dir(self.save_folder)
#         out_json = self.save_folder / f"session_{ts}.json"
#         out_csv = self.save_folder / f"session_{ts}.csv"
        
#         try:
#             with open(out_json, "w") as f:
#                 json.dump({
#                     "meta": {
#                         "saved_at": datetime.now().isoformat(),
#                         "packets": len(self.session_data)
#                     },
#                     "data": self.session_data
#                 }, f, indent=2)
            
#             import csv
#             keys = list(self.session_data[0].keys())
#             with open(out_csv, "w", newline="") as cf:
#                 writer = csv.DictWriter(cf, fieldnames=keys)
#                 writer.writeheader()
#                 writer.writerows(self.session_data)
            
#             self._log(f"Session saved: {out_json} and {out_csv}")
#         except Exception as e:
#             self._log(f"Failed to save session: {e}")
    
#     def save_config(self):
#         try:
#             cfg = config.get_all()

#             cfg["channel_mapping"] = {
#                 "ch0": {
#                     "sensor": self.ch0_combo.currentText(),
#                     "enabled": True
#                 },
#                 "ch1": {
#                     "sensor": self.ch1_combo.currentText(),
#                     "enabled": True
#                 }
#             }

#             CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
#             CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
            
#             self._log("✅ Channel mapping saved to config!")
#             self._pending_mapping_changes = False

#             self._log(
#                 f"Config saved | ch0 → {self.ch0_combo.currentText()} | "
#                 f"ch1 → {self.ch1_combo.currentText()}"
#             )

#         except Exception as e:
#             self._log(f"Save config error: {e}")

#     def _start_config_monitor(self):
#         """Monitor config changes and update UI."""
#         def monitor():
#             last_sr = self.sampling_rate
#             last_ch0 = None
#             last_ch1 = None
            
#             while True:
#                 try:
#                     current_sr = config.get("sampling_rate", 512)
#                     current_mapping = config.get("channel_mapping", {})
#                     current_ch0 = current_mapping.get("ch0", {}).get("sensor", "EMG")
#                     current_ch1 = current_mapping.get("ch1", {}).get("sensor", "EEG")
                    
#                     # Check if sampling rate changed
#                     if current_sr != last_sr:
#                         print(f"🔄 Config changed! Sampling rate: {last_sr}Hz → {current_sr}Hz")
#                         self.sampling_rate = float(current_sr)
#                         self.buffer_size = int(self.sampling_rate * self.window_seconds)
#                         self.ch0_buffer = np.zeros(self.buffer_size, dtype=float)
#                         self.ch1_buffer = np.zeros(self.buffer_size, dtype=float)
#                         self.buf_ptr = 0
#                         last_sr = current_sr
#                         self._log(f"✅ Config updated: sampling_rate={current_sr}Hz")
                    
#                     # ===== CRITICAL: Update UI combos if mapping changed =====
#                     if current_ch0 != last_ch0:
#                         self._log(f"🔄 Ch0 mapping updated: {last_ch0} → {current_ch0}")
#                         self.ch0_combo.blockSignals(True)  # Don't trigger save
#                         self.ch0_combo.setCurrentText(current_ch0)
#                         self.ch0_combo.blockSignals(False)
#                         last_ch0 = current_ch0
                    
#                     if current_ch1 != last_ch1:
#                         self._log(f"🔄 Ch1 mapping updated: {last_ch1} → {current_ch1}")
#                         self.ch1_combo.blockSignals(True)  # Don't trigger save
#                         self.ch1_combo.setCurrentText(current_ch1)
#                         self.ch1_combo.blockSignals(False)
#                         last_ch1 = current_ch1
                    
#                     time.sleep(0.5)  # Check every 500ms (faster than 2s for responsiveness)
                    
#                 except Exception as e:
#                     print(f"Config monitor error: {e}")
#                     time.sleep(1)
        
#         t = threading.Thread(target=monitor, daemon=True)
#         t.start()

#     def _on_ui_timer(self):
#         # if self.is_acquiring and self.serial_reader:
#         #     while True:
#         #         try:
#         #             pkt_bytes = self.serial_reader.get_packet(timeout=0.001)
#         #         except:
#         #             pkt_bytes = None
                
#         #         if not pkt_bytes:
#         #             break
                
#         #         try:
#         #             pkt = self.packet_parser.parse(pkt_bytes)
#         #         except Exception as e:
#         #             self._log(f"Parse error: {e}")
#         #             continue
                
#         #         if self.last_counter is not None and pkt.counter == self.last_counter:
#         #             continue
                
#         #         self.last_counter = pkt.counter
#         #         self.packet_count += 1
                
#         #         ch0_uv = adc_to_uv(pkt.ch0_raw)
#         #         ch1_uv = adc_to_uv(pkt.ch1_raw)
                
#         #         if LSL_AVAILABLE and self.lsl_raw:
#         #             try:
#         #                 self.lsl_raw_uV.push_sample([ch0_uv, ch1_uv], None)
#         #             except:
#         #                 pass
                
#         #         self.ch0_buffer[self.buf_ptr] = ch0_uv
#         #         self.ch1_buffer[self.buf_ptr] = ch1_uv
#         #         self.buf_ptr = (self.buf_ptr + 1) % self.buffer_size
                
#         #         if self.is_recording:
#         #             entry = {
#         #                 "timestamp": pkt.timestamp.isoformat(),
#         #                 "counter": int(pkt.counter),
#         #                 "ch0_raw": int(pkt.ch0_raw),
#         #                 "ch1_raw": int(pkt.ch1_raw),
#         #                 "ch0_uv": float(ch0_uv),
#         #                 "ch1_uv": float(ch1_uv),
#         #                 "ch0_type": self.ch0_combo.currentText(),
#         #                 "ch1_type": self.ch1_combo.currentText()
#         #             }
#         #             self.session_data.append(entry)
        
#         self._refresh_plots()
#         self._update_diagnostics()
    
#     @QtCore.Slot(object)
#     def _on_packet_block(self, pkt):
#         sensor0 = self.ch0_combo.currentText()
#         sensor1 = self.ch1_combo.currentText()

#         if not self.is_acquiring:
#             return

#         if self.last_counter is not None and pkt.counter == self.last_counter:
#             return

#         self.last_counter = pkt.counter
#         self.packet_count += 1
        
#         ch0_uv = adc_to_uv(pkt.ch0_raw)
#         ch1_uv = adc_to_uv(pkt.ch1_raw)
        
#         if LSL_AVAILABLE and self.lsl_raw_uV:
#             try:
#                 self.lsl_raw_uV.push_sample([ch0_uv, ch1_uv], None)
#             except:
#                 pass
        
#         self.ch0_buffer[self.buf_ptr] = ch0_uv
#         self.ch1_buffer[self.buf_ptr] = ch1_uv
#         self.buf_ptr = (self.buf_ptr + 1) % self.buffer_size
        
#         if self.is_recording:
#             entry = {
#                 "timestamp": pkt.timestamp.isoformat(),
#                 "counter": int(pkt.counter),
#                 "ch0_raw": int(pkt.ch0_raw),
#                 "ch1_raw": int(pkt.ch1_raw),
#                 "ch0_uv": float(ch0_uv),
#                 "ch1_uv": float(ch1_uv),
#                 "ch0_type": self.ch0_combo.currentText(),
#                 "ch1_type": self.ch1_combo.currentText()
#             }
#             self.session_data.append(entry)

#     def _refresh_plots(self):
#         try:
#             if self.buf_ptr == 0:
#                 self.curve0.setData(self.ch0_buffer)
#                 self.curve1.setData(self.ch1_buffer)
#             else:
#                 self.curve0.setData(
#                     np.concatenate((self.ch0_buffer[self.buf_ptr:], self.ch0_buffer[:self.buf_ptr]))
#                 )
#                 self.curve1.setData(
#                     np.concatenate((self.ch1_buffer[self.buf_ptr:], self.ch1_buffer[:self.buf_ptr]))
#                 )
#         except Exception as e:
#             self._log(f"Plot update error: {e}")
    
#     def _update_diagnostics(self):
#         try:
#             if not self.serial_worker:
#                 return

#             stats = {}

#             # read known fields from worker.stats dict
#             for name in ("bytes_read", "packets_read", "sync_errors",
#                         "read_errors", "queue_size", "packets_total",
#                         "packets", "parse_errors", "queue_empty"):
#                 val = self.serial_worker.stats.get(name, None)
#                 if val is not None:
#                     stats[name] = val

#             # internal counters
#             stats["last_counter"] = int(self.last_counter) if self.last_counter is not None else None
#             stats["packet_count_total"] = int(self.packet_count)

#             # update GUI
#             lines = [f"{k}: {v}" for k, v in stats.items()]
#             self.diag_box.setPlainText("\n".join(lines[-200:]))

#             # log every second
#             nowt = time.time()
#             if nowt - self._last_diag_log_time >= self._diag_log_interval:
#                 logger.info(json.dumps(stats))
#                 self._last_diag_log_time = nowt

#         except Exception as e:
#             self._log(f"Diag error: {e}")
    
#     def _log(self, s: str):
#         ts = datetime.now().strftime("%H:%M:%S")
#         line = f"[{ts}] {s}"
#         print(line)
#         cur = self.diag_box.toPlainText()
#         if cur:
#             cur = cur + "\n" + line
#         else:
#             cur = line
#         lines = cur.splitlines()[-500:]
#         self.diag_box.setPlainText("\n".join(lines))
    
#     def closeEvent(self, event):
#         try:
#             if self.serial_worker:
#                 self.serial_worker.stop()
#             if self.serial_thread:
#                 self.serial_thread.quit()
#                 self.serial_thread.wait()
#         except Exception as e:
#             print(e)

#         if self.is_recording and self.autosave_chk.isChecked():
#             self._save_session_now()

#         event.accept()

# class SerialWorker(QtCore.QObject):
#     packet_ready = QtCore.Signal(object)
#     error = QtCore.Signal(str)

#     def __init__(self, port, baud):
#         super().__init__()
#         self.port = port
#         self.baud = baud
#         self.reader = SerialPacketReader(port=self.port, baud=self.baud)
#         self.parser = PacketParser()
#         self.running = False
#         self.stats = {
#             "packets": 0,
#             "parse_errors": 0,
#             "queue_empty": 0
#         }

#     @QtCore.Slot()
#     def start(self):
#         try:
#             if not self.reader.connect():
#                 self.error.emit("Failed to open serial port")
#                 return

#             self.reader.start()
#             self.running = True

#             while self.running:
#                 pkt_bytes = self.reader.get_packet(timeout=0.1)
#                 if not pkt_bytes:
#                     self.stats["queue_empty"] += 1
#                     continue

#                 try:
#                     pkt = self.parser.parse(pkt_bytes)
#                     self.stats["packets"] += 1
#                     self.packet_ready.emit(pkt)
#                 except Exception as e:
#                     self.stats["parse_errors"] += 1
#                     self.error.emit(f"Parse error: {e}")

#         except Exception as e:
#             self.error.emit(str(e))

#     @QtCore.Slot()
#     def stop(self):
#         self.running = False
#         try:
#             if self.reader:
#                 self.reader.disconnect()
#         except:
#             pass

# def main():
#     app = QtWidgets.QApplication(sys.argv)
#     win = AcquisitionWindow()
#     win.show()
#     sys.exit(app.exec())

# if __name__ == "__main__":
#     main()




import sys
import os
import json
import time
import math
import struct
import threading
import queue
from pathlib import Path
from datetime import datetime

import numpy as np
from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

# Project imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = PROJECT_ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from acquisition.serial_reader import SerialPacketReader
    from acquisition.packet_parser import PacketParser
    from acquisition.lsl_streams import LSLStreamer, LSL_AVAILABLE
    from src.utils.config import config
except Exception as e:
    raise SystemExit(f"Failed to import modules: {e}")

# File paths
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
DEFAULT_SAVE_FOLDER = PROJECT_ROOT / "data" / "sessions"

# ADC constants
ADC_BITS = 14
ADC_MAX = (1 << ADC_BITS) - 1
VREF = 3300.0

# Packet constants
SYNC1 = 0xC7
SYNC2 = 0x7C
END_BYTE = 0x01

def adc_to_uv(adc_val, bits=ADC_BITS, vref=VREF):
    """Map ADC integer to voltage units."""
    volts = ((adc_val / (2 ** bits)) * vref) - (vref / 2.0)
    return volts

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

# ========== Main GUI Window ==========

class AcquisitionWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AcqQT — Optimized (Lag-Free)")
        self.resize(1300, 800)

        # Get config
        self.config = config.get_all()
        self.sampling_rate = float(self.config.get("sampling_rate", 512))
        self.window_seconds = float(self.config.get("display", {}).get("window_seconds", 5.0))
        self.buffer_size = int(self.sampling_rate * self.window_seconds)

        self.x_axis = np.arange(self.buffer_size)

        # Paths
        self.save_path = DEFAULT_SAVE_FOLDER
        self.config_path = CONFIG_PATH

        # Buffers
        self.ch0_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.ch1_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.buf_ptr = 0

        # Pipeline objects
        self.serial_thread = None
        self.serial_worker = None
        self.lsl_raw_uV = None

        # Recording state
        self.is_connected = False
        self.is_acquiring = False
        self.is_recording = False
        self.session_data = []
        self.save_folder = Path(self.config.get("save_folder", str(DEFAULT_SAVE_FOLDER)))
        ensure_dir(self.save_folder)
        self.save_on_stop = True
        self.packet_count = 0
        self.last_counter = None

        # Build UI
        self._build_ui()
        self._init_plotting()

        # ===== OPTIMIZED: Reduced UI refresh rate =====
        # Update plots only every 100ms instead of 50ms
        self.ui_timer = QtCore.QTimer()
        self.ui_timer.setInterval(150)  # 100ms update interval
        self.ui_timer.timeout.connect(self._on_ui_timer)
        self.ui_timer.start()

        # Start config monitoring thread
        #self._start_config_monitor()

    def _start_config_monitor(self):
        """Monitor config changes and update UI."""
        def monitor():
            last_sr = self.sampling_rate
            last_ch0 = None
            last_ch1 = None
            while True:
                try:
                    current_sr = config.get("sampling_rate", 512)
                    current_mapping = config.get("channel_mapping", {})
                    current_ch0 = current_mapping.get("ch0", {}).get("sensor", "EMG")
                    current_ch1 = current_mapping.get("ch1", {}).get("sensor", "EEG")

                    # Check if sampling rate changed
                    if current_sr != last_sr:
                        print(f"🔄 Sampling rate: {last_sr}Hz → {current_sr}Hz")
                        self.sampling_rate = float(current_sr)
                        self.buffer_size = int(self.sampling_rate * self.window_seconds)
                        self.ch0_buffer = np.zeros(self.buffer_size, dtype=np.float32)
                        self.ch1_buffer = np.zeros(self.buffer_size, dtype=np.float32)
                        self.buf_ptr = 0
                        last_sr = current_sr
                        self._log(f"✅ Sampling rate updated: {current_sr}Hz")

                    # Update UI combos if mapping changed
                    if current_ch0 != last_ch0:
                        self._log(f"🔄 Ch0: {last_ch0} → {current_ch0}")
                        self.ch0_combo.blockSignals(True)
                        self.ch0_combo.setCurrentText(current_ch0)
                        self.ch0_combo.blockSignals(False)
                        last_ch0 = current_ch0

                    if current_ch1 != last_ch1:
                        self._log(f"🔄 Ch1: {last_ch1} → {current_ch1}")
                        self.ch1_combo.blockSignals(True)
                        self.ch1_combo.setCurrentText(current_ch1)
                        self.ch1_combo.blockSignals(False)
                        last_ch1 = current_ch1

                    time.sleep(0.5)
                except Exception as e:
                    print(f"Config monitor error: {e}")
                    time.sleep(1)

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    def _build_ui(self):
        """Build UI layout."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        hl = QtWidgets.QHBoxLayout(central)

        # Left panel
        left_scroll = QtWidgets.QScrollArea()
        left_scroll.setWidgetResizable(True)
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Serial controls
        left_layout.addWidget(QtWidgets.QLabel("Serial / Stream"))
        self.port_combo = QtWidgets.QComboBox()
        left_layout.addWidget(self.port_combo)

        refresh_btn = QtWidgets.QPushButton("Refresh ports")
        refresh_btn.clicked.connect(self.refresh_ports)
        left_layout.addWidget(refresh_btn)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Baud"))
        self.baud_edit = QtWidgets.QLineEdit("230400")
        row.addWidget(self.baud_edit)
        left_layout.addLayout(row)

        # Channel mapping
        grp_map = QtWidgets.QGroupBox("Channel Mapping")
        gmap_layout = QtWidgets.QFormLayout(grp_map)

        self.ch0_combo = QtWidgets.QComboBox()
        self.ch0_combo.addItems(["EMG", "EOG", "EEG"])
        self.ch1_combo = QtWidgets.QComboBox()
        self.ch1_combo.addItems(["EMG", "EOG", "EEG"])

        ch_mapping = self.config.get("channel_mapping", {})
        self.ch0_combo.setCurrentText(ch_mapping.get("ch0", {}).get("sensor", "EMG"))
        self.ch1_combo.setCurrentText(ch_mapping.get("ch1", {}).get("sensor", "EEG"))

        # Wire combos
        self.ch0_combo.currentTextChanged.connect(self._on_ch0_changed)
        self.ch1_combo.currentTextChanged.connect(self._on_ch1_changed)

        self._pending_mapping_changes = False

        gmap_layout.addRow("Channel 0:", self.ch0_combo)
        gmap_layout.addRow("Channel 1:", self.ch1_combo)
        left_layout.addWidget(grp_map)

        # Connect buttons
        self.btn_connect = QtWidgets.QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_serial)
        self.btn_disconnect = QtWidgets.QPushButton("Disconnect")
        self.btn_disconnect.clicked.connect(self.disconnect_serial)
        self.btn_disconnect.setEnabled(False)

        left_layout.addWidget(self.btn_connect)
        left_layout.addWidget(self.btn_disconnect)
        left_layout.addSpacing(8)

        # Acquisition controls
        left_layout.addWidget(QtWidgets.QLabel("Acquisition"))
        self.btn_start = QtWidgets.QPushButton("Start Acquisition")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_acquisition)

        btn_save_cfg = QtWidgets.QPushButton("Save Mapping to Config")
        btn_save_cfg.clicked.connect(self.save_config)

        left_layout.addWidget(btn_save_cfg)

        self.btn_stop = QtWidgets.QPushButton("Stop Acquisition")
        self.btn_stop.clicked.connect(self.stop_acquisition)

        left_layout.addWidget(self.btn_start)
        left_layout.addWidget(self.btn_stop)

        # Recording
        left_layout.addWidget(QtWidgets.QLabel("Recording"))
        rec_h = QtWidgets.QHBoxLayout()

        self.btn_record = QtWidgets.QPushButton("Start Recording")
        self.btn_record.setEnabled(False)
        self.btn_record.clicked.connect(self._toggle_record)
        rec_h.addWidget(self.btn_record)

        self.btn_save_now = QtWidgets.QPushButton("Save Session Now")
        self.btn_save_now.clicked.connect(self._save_session_now)
        rec_h.addWidget(self.btn_save_now)

        left_layout.addLayout(rec_h)

        # Save folder
        sf_h = QtWidgets.QHBoxLayout()
        self.folder_label = QtWidgets.QLineEdit(str(self.save_folder))
        self.folder_label.setReadOnly(True)
        sf_h.addWidget(self.folder_label)

        choose = QtWidgets.QPushButton("Choose")
        choose.clicked.connect(self._choose_folder)
        sf_h.addWidget(choose)

        left_layout.addLayout(sf_h)

        self.autosave_chk = QtWidgets.QCheckBox("Save on stop (auto)")
        self.autosave_chk.setChecked(self.save_on_stop)
        left_layout.addWidget(self.autosave_chk)

        left_layout.addStretch()
        left_scroll.setWidget(left)
        left_scroll.setMinimumWidth(320)

        hl.addWidget(left_scroll, 0)

        # Right panel: plots only (NO DIAGNOSTICS)
        right = QtWidgets.QWidget()
        rlay = QtWidgets.QVBoxLayout(right)

        pg.setConfigOptions(antialias=False)

        self.plot0 = pg.PlotWidget(title="Channel 0 (µV)")
        self.plot1 = pg.PlotWidget(title="Channel 1 (µV)")

        self.curve0 = self.plot0.plot(pen=pg.mkPen('c', width=1.4))
        self.curve1 = self.plot1.plot(pen=pg.mkPen('y', width=1.4))

        rlay.addWidget(self.plot0, 1)
        rlay.addWidget(self.plot1, 1)

        # ===== REMOVED: Diagnostics box =====
        # This was causing major lag! Removed completely

        hl.addWidget(right, 1)

        self.refresh_ports()
        self.plot0.setYRange(-1000, 1000)
        self.plot1.setYRange(-1000, 1000)

    def _on_ch0_changed(self, sensor_type):
        """Called when channel 0 dropdown changes."""
        self._pending_mapping_changes = True
        self._log(f"📝 Channel 0 → {sensor_type}")

    def _on_ch1_changed(self, sensor_type):
        """Called when channel 1 dropdown changes."""
        self._pending_mapping_changes = True
        self._log(f"📝 Channel 1 → {sensor_type}")

    def _init_plotting(self):
        self.plot_len = self.buffer_size
        self.plot0.setYRange(-500, 500)
        self.plot1.setYRange(-500, 500)

    def refresh_ports(self):
        try:
            import serial.tools.list_ports as lp
            ports = [p.device for p in lp.comports()]
        except:
            ports = []

        self.port_combo.clear()
        self.port_combo.addItems(ports or ["No ports"])

    def connect_serial(self):
        port = self.port_combo.currentText()
        baud = int(self.baud_edit.text().strip() or 230400)

        if not port or port.startswith("No"):
            self._log("No COM port selected")
            return

        self.serial_thread = QtCore.QThread()
        self.serial_worker = SerialWorker(port, baud)
        self.serial_worker.moveToThread(self.serial_thread)

        self.serial_thread.started.connect(self.serial_worker.start)
        self.serial_worker.packet_ready.connect(self._on_packet_block)
        self.serial_worker.error.connect(self._log)

        self.serial_thread.start()

        self.is_connected = True
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.btn_start.setEnabled(True)

        self._log(f"Serial connected on {port}")

    def disconnect_serial(self):
        if self.serial_worker:
            self.serial_worker.stop()
        if self.serial_thread:
            self.serial_thread.quit()
            self.serial_thread.wait()

        self.serial_worker = None
        self.serial_thread = None

        self.is_connected = False
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_start.setEnabled(False)

        self._log("Serial disconnected")

    def start_acquisition(self):
        if not self.is_connected:
            self._log("Not connected")
            return

        self.is_acquiring = True
        self.serial_worker.reader.send_command("START")

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_record.setEnabled(True)

        # ONE LSL STREAM ONLY (µV)
        if LSL_AVAILABLE:
            labels = ["ch0", "ch1"]
            self.lsl_raw_uV = LSLStreamer(
                "Bio-Raw-uV",
                channel_types=["uV", "uV"],
                channel_labels=labels,
                channel_count=2,
                nominal_srate=self.sampling_rate
            )

        self._log("Acquisition started")

    def stop_acquisition(self):
        self.is_acquiring = False
        self.serial_worker.reader.send_command("STOP")

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        self._log("Acquisition stopped")

        if self.autosave_chk.isChecked() and self.is_recording:
            self._log("Auto-saving session on stop")
            self._save_session_now()

        self.is_recording = False
        self.btn_record.setText("Start Recording")
        self.btn_record.setEnabled(False)

    def _toggle_record(self):
        if not self.is_acquiring:
            self._log("Start acquisition first")
            return

        self.is_recording = not self.is_recording
        self.btn_record.setText("Stop Recording" if self.is_recording else "Start Recording")

        self._log("Recording: " + ("ON" if self.is_recording else "OFF"))

        if self.is_recording:
            self.session_data = []

    def _choose_folder(self):
        dlg = QtWidgets.QFileDialog(self, "Select folder to save sessions")
        dlg.setFileMode(QtWidgets.QFileDialog.Directory)

        if dlg.exec():
            path = dlg.selectedFiles()[0]
            self.save_folder = Path(path)
            self.folder_label.setText(str(self.save_folder))
            ensure_dir(self.save_folder)
            self._log(f"Save folder set to {self.save_folder}")

    def _save_session_now(self):
        if not self.session_data:
            self._log("No session data to save")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ensure_dir(self.save_folder)

        out_json = self.save_folder / f"session_{ts}.json"
        out_csv = self.save_folder / f"session_{ts}.csv"

        try:
            with open(out_json, "w") as f:
                json.dump({
                    "meta": {
                        "saved_at": datetime.now().isoformat(),
                        "packets": len(self.session_data)
                    },
                    "data": self.session_data
                }, f, indent=2)

            import csv
            keys = list(self.session_data[0].keys())
            with open(out_csv, "w", newline="") as cf:
                writer = csv.DictWriter(cf, fieldnames=keys)
                writer.writeheader()
                writer.writerows(self.session_data)

            self._log(f"Session saved: {out_json} and {out_csv}")
        except Exception as e:
            self._log(f"Failed to save session: {e}")

    def save_config(self):
        try:
            cfg = config.get_all()
            cfg["channel_mapping"] = {
                "ch0": {
                    "sensor": self.ch0_combo.currentText(),
                    "enabled": True
                },
                "ch1": {
                    "sensor": self.ch1_combo.currentText(),
                    "enabled": True
                }
            }

            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

            self._log("✅ Channel mapping saved!")
            self._pending_mapping_changes = False
            self._log(
                f"Ch0 → {self.ch0_combo.currentText()} | "
                f"Ch1 → {self.ch1_combo.currentText()}"
            )
        except Exception as e:
            self._log(f"Save config error: {e}")

    def _on_ui_timer(self):
        """FrameDropping: Only update plot every 100ms"""
        self._refresh_plots()

    @QtCore.Slot(object)
    def _on_packet_block(self, packets):
        """Process incoming packet block (minimal work)"""
        if not self.is_acquiring:
            return

        lsl_chunk = []

        for counter, timestamp, ch0_raw, ch1_raw in packets:
            if self.last_counter is not None and counter == self.last_counter:
                continue

            self.last_counter = counter
            self.packet_count += 1

            ch0_uv = adc_to_uv(ch0_raw)
            ch1_uv = adc_to_uv(ch1_raw)

            self.ch0_buffer[self.buf_ptr] = ch0_uv
            self.ch1_buffer[self.buf_ptr] = ch1_uv
            self.buf_ptr = (self.buf_ptr + 1) % self.buffer_size

            if self.is_recording:
                self.session_data.append({
                    "timestamp": timestamp.isoformat(),
                    "counter": counter,
                    "ch0_uV": ch0_uv,
                    "ch1_uV": ch1_uv
                })

            lsl_chunk.append([ch0_uv, ch1_uv])

        # Push to LSL ONCE per block
        if LSL_AVAILABLE and self.lsl_raw_uV and lsl_chunk:
            try:
                self.lsl_raw_uV.push_chunk(lsl_chunk)
            except Exception as e:
                pass

    def _refresh_plots(self):
        """Update plots efficiently"""
        try:
            idx = self.buf_ptr
            self.curve0.setData(self.ch0_buffer, skipFiniteCheck=True)
            self.curve1.setData(self.ch1_buffer, skipFiniteCheck=True)
        except Exception as e:
            self._log(f"Plot error: {e}")

    def _log(self, s: str):
        """Simple logging to console only"""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {s}"
        print(line)

    def closeEvent(self, event):
        try:
            if self.serial_worker:
                self.serial_worker.stop()
            if self.serial_thread:
                self.serial_thread.quit()
                self.serial_thread.wait()
        except Exception as e:
            print(e)

        if self.is_recording and self.autosave_chk.isChecked():
            self._save_session_now()

        event.accept()

class SerialWorker(QtCore.QObject):
    packet_ready = QtCore.Signal(list)
    error = QtCore.Signal(str)

    def __init__(self, port, baud):
        super().__init__()
        self.reader = SerialPacketReader(port=port, baud=baud)
        self.parser = PacketParser()
        self.running = False

    @QtCore.Slot()
    def start(self):
        BLOCK_SIZE = 16
        block = []

        try:
            if not self.reader.connect():
                self.error.emit("Failed to open serial port")
                return

            self.reader.start()
            self.running = True

            while self.running:
                pkt_bytes = self.reader.get_packet(timeout=0.05)
                if not pkt_bytes:
                    continue

                try: 
                    pkt = self.parser.parse(pkt_bytes)

                    block.append((
                            pkt.counter,
                            pkt.timestamp,
                            pkt.ch0_raw,
                            pkt.ch1_raw
                    ))

                    if len(block) >= BLOCK_SIZE:
                        self.packet_ready.emit(block)
                        block = []

                except Exception as e:
                    self.error.emit(f"Parse error: {e}")

        except Exception as e:
            self.error.emit(str(e))

    @QtCore.Slot()
    def stop(self):
        self.running = False
        try:
            if self.reader:
                self.reader.disconnect()
        except:
            pass

class ConfigSignals(QtCore.QObject):
    update_mapping = QtCore.Signal(str, str)
    update_sr = QtCore.Signal(float)

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = AcquisitionWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()