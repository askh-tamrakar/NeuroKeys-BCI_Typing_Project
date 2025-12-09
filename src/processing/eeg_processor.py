#!/usr/bin/env python3
"""
EEG filter processor

- Reads raw stream "BioSignals-Raw" (supports multi-channel)
- Applies configurable notch filter (default 50 Hz) and bandpass (default 0.5-45 Hz)
- Publishes filtered EEG to "BioSignals-EEG-Filtered"
- Handles per-channel filter state (zi) and config reloading every 2s
- This processor is intended to be used by multi-channel EEG setups.
"""

import json
import time
import threading
from pathlib import Path

import numpy as np
import pylsl
from scipy.signal import iirnotch, butter, lfilter, lfilter_zi

CONFIG_PATH = Path("config/sensor_config.json")


class EEGFilterProcessor:
    def __init__(self):
        self.config = self.load_config()
        self.sr = int(self.config.get("sampling_rate", 512))

        # default EEG filter specs from config
        eeg_filters = self.config["filters"].get("EEG", {}).get("filters", [])
        # extract notch and bandpass specs safely
        notch_cfg = next((f for f in eeg_filters if f.get("type") == "notch"), {"freq": 50.0, "Q": 30})
        band_cfg = next((f for f in eeg_filters if f.get("type") == "bandpass"),
                        {"low": 0.5, "high": 45.0, "order": 4})

        self.notch_freq = float(notch_cfg.get("freq", 50.0))
        self.notch_q = float(notch_cfg.get("Q", 30.0))
        self.bp_low = float(band_cfg.get("low", 0.5))
        self.bp_high = float(band_cfg.get("high", 45.0))
        self.bp_order = int(band_cfg.get("order", 4))

        self.inlet = None
        self.outlet = None
        self.is_running = False

        self.num_channels = 1  # updated when inlet is found
        self.zi_notch = []
        self.zi_band = []

        self._design_filters()
        self._setup_lsl()

        self._watcher_thread = threading.Thread(target=self._config_watcher, daemon=True)
        self._watcher_thread.start()

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {
                "sampling_rate": 512,
                "filters": {
                    "EEG": {
                        "filters": [
                            {"type": "notch", "freq": 50.0, "Q": 30},
                            {"type": "bandpass", "low": 0.5, "high": 45.0, "order": 4}
                        ]
                    }
                }
            }

    def _design_filters(self):
        # Notch design (SciPy iirnotch signature: w0, Q, fs)
        self.b_notch, self.a_notch = iirnotch(self.notch_freq, self.notch_q, fs=self.sr)
        # Bandpass normalized
        nyq = self.sr / 2.0
        low = self.bp_low / nyq
        high = self.bp_high / nyq
        self.b_band, self.a_band = butter(self.bp_order, [low, high], btype="band")
        print(f"[EEG] Designed notch {self.notch_freq}Hz Q={self.notch_q} and bandpass {self.bp_low}-{self.bp_high}Hz (order {self.bp_order})")

    def _setup_lsl(self):
        streams = pylsl.resolve_bypred("name='BioSignals-Raw'", timeout=5)
        if not streams:
            print("⚠️ EEG: BioSignals-Raw not found (will retry).")
        else:
            self.inlet = pylsl.StreamInlet(streams[0])
            info = self.inlet.info()
            self.num_channels = int(info.channel_count())
            print(f"✓ EEG: connected to BioSignals-Raw (channels={self.num_channels})")

        # create outlet: match channel_count so downstream can read multi-channel filtered EEG
        info_out = pylsl.StreamInfo(
            name="BioSignals-EEG-Filtered",
            type="EEG",
            channel_count=max(1, self.num_channels),
            nominal_srate=self.sr,
            channel_format="float32",
            source_id="EEG-Filter-Processor"
        )
        self.outlet = pylsl.StreamOutlet(info_out)
        print("✓ EEG: created outlet BioSignals-EEG-Filtered")

        # initialize per-channel filter state
        self.zi_notch = [lfilter_zi(self.b_notch, self.a_notch) * 0.0 for _ in range(max(1, self.num_channels))]
        self.zi_band = [lfilter_zi(self.b_band, self.a_band) * 0.0 for _ in range(max(1, self.num_channels))]

    def _config_watcher(self):
        while True:
            try:
                cfg = self.load_config()
                eeg_filters = cfg["filters"].get("EEG", {}).get("filters", [])
                notch_cfg = next((f for f in eeg_filters if f.get("type") == "notch"), None)
                band_cfg = next((f for f in eeg_filters if f.get("type") == "bandpass"), None)

                changed = False
                if notch_cfg:
                    new_notch_freq = float(notch_cfg.get("freq", self.notch_freq))
                    new_notch_q = float(notch_cfg.get("Q", self.notch_q))
                    if new_notch_freq != self.notch_freq or new_notch_q != self.notch_q:
                        self.notch_freq = new_notch_freq
                        self.notch_q = new_notch_q
                        changed = True

                if band_cfg:
                    new_low = float(band_cfg.get("low", self.bp_low))
                    new_high = float(band_cfg.get("high", self.bp_high))
                    new_order = int(band_cfg.get("order", self.bp_order))
                    if new_low != self.bp_low or new_high != self.bp_high or new_order != self.bp_order:
                        self.bp_low = new_low
                        self.bp_high = new_high
                        self.bp_order = new_order
                        changed = True

                if int(cfg.get("sampling_rate", self.sr)) != self.sr:
                    self.sr = int(cfg.get("sampling_rate", self.sr))
                    changed = True

                if changed:
                    print("[EEG] Config changed -> redesigning filters")
                    self._design_filters()
                    # re-init filter states (fresh)
                    self.zi_notch = [lfilter_zi(self.b_notch, self.a_notch) * 0.0 for _ in range(self.num_channels)]
                    self.zi_band = [lfilter_zi(self.b_band, self.a_band) * 0.0 for _ in range(self.num_channels)]
                time.sleep(2.0)
            except Exception as e:
                print(f"[EEG] watcher error: {e}")
                time.sleep(2.0)

    def process(self):
        self.is_running = True
        print("▶️ EEG filter processor started")
        while self.is_running:
            try:
                if not self.inlet:
                    streams = pylsl.resolve_bypred("name='BioSignals-Raw'", timeout=5)
                    if streams:
                        self.inlet = pylsl.StreamInlet(streams[0])
                        info = self.inlet.info()
                        self.num_channels = int(info.channel_count())
                        # re-create outlet to reflect channel count
                        self._setup_lsl()
                        print("✓ EEG: reconnected and reconfigured")
                    else:
                        time.sleep(0.5)
                        continue

                sample, ts = self.inlet.pull_sample(timeout=0.1)
                if sample is None:
                    continue

                # Ensure sample length >= num_channels; if not, pad/trim
                arr = np.asarray(sample, dtype=float)
                if arr.size < self.num_channels:
                    # pad with zeros
                    arr = np.pad(arr, (0, self.num_channels - arr.size))
                elif arr.size > self.num_channels:
                    arr = arr[:self.num_channels]

                filtered_out = []
                # apply notch then bandpass per channel using per-channel zi
                for ch in range(self.num_channels):
                    raw_val = float(arr[ch])
                    notch_res, self.zi_notch[ch] = lfilter(self.b_notch, self.a_notch, [raw_val], zi=self.zi_notch[ch])
                    band_res, self.zi_band[ch] = lfilter(self.b_band, self.a_band, notch_res, zi=self.zi_band[ch])
                    filtered_out.append(float(band_res[0]))

                # push multi-channel filtered sample
                if self.outlet:
                    self.outlet.push_sample(filtered_out, ts)

            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                print(f"[EEG] processing error: {e}")
                time.sleep(0.05)

    def stop(self):
        self.is_running = False
        print("⏹️ EEG filter processor stopped")


if __name__ == "__main__":
    p = EEGFilterProcessor()
    p.process()
