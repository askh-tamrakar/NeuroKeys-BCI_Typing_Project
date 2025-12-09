#!/usr/bin/env python3
"""
EMG filter processor

- Reads raw stream "BioSignals-Raw" (assumes ch0/ch1 ordering)
- Applies configurable high-pass filter (default 70 Hz, order 4)
- Publishes filtered EMG to "BioSignals-EMG-Filtered"
- Auto-reloads sensor_config.json every 2 seconds
"""

import json
import time
import queue
import threading
from pathlib import Path

import numpy as np
import pylsl
from scipy.signal import butter, lfilter, lfilter_zi

CONFIG_PATH = Path("config/sensor_config.json")


class EMGFilterProcessor:
    def __init__(self):
        self.config = self.load_config()
        self.sr = int(self.config.get("sampling_rate", 512))
        self.cutoff = float(self.config["filters"]["EMG"].get("cutoff", 70.0))
        self.order = int(self.config["filters"]["EMG"].get("order", 4))
        self.inlet = None
        self.outlet = None
        self.is_running = False

        self._design_filter()
        self._setup_lsl()

        # state for lfilter
        self.zi = lfilter_zi(self.b, self.a) * 0.0

        # config watcher
        self._watcher_thread = threading.Thread(target=self._config_watcher, daemon=True)
        self._watcher_thread.start()

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            # fallback default (matches project defaults)
            return {
                "sampling_rate": 512,
                "filters": {"EMG": {"cutoff": 70.0, "order": 4}}
            }

    def _design_filter(self):
        nyq = self.sr / 2.0
        wn = self.cutoff / nyq
        # design high-pass Butterworth
        self.b, self.a = butter(self.order, wn, btype="high", analog=False)
        print(f"[EMG] Designed high-pass: cutoff={self.cutoff} Hz order={self.order}")

    def _setup_lsl(self):
        # find raw LSL stream
        streams = pylsl.resolve_bypred("name='BioSignals-Raw'", timeout=5)
        if not streams:
            print("⚠️ EMG: BioSignals-Raw not found (will retry on process loop)")
        else:
            self.inlet = pylsl.StreamInlet(streams[0])
            print("✓ EMG: connected to BioSignals-Raw")

        # create filtered outlet (single channel)
        info = pylsl.StreamInfo(
            name="BioSignals-EMG-Filtered",
            type="EMG",
            channel_count=1,
            nominal_srate=self.sr,
            channel_format="float32",
            source_id="EMG-Filter-Processor"
        )
        self.outlet = pylsl.StreamOutlet(info)
        print("✓ EMG: created outlet BioSignals-EMG-Filtered")

    def _config_watcher(self):
        prev = None
        while True:
            try:
                cfg = self.load_config()
                # detect cutoff or order change
                new_cutoff = float(cfg["filters"]["EMG"].get("cutoff", 70.0))
                new_order = int(cfg["filters"]["EMG"].get("order", 4))
                if new_cutoff != self.cutoff or new_order != self.order or int(cfg.get("sampling_rate", 512)) != self.sr:
                    print(f"[EMG] Config changed -> redesigning filter (cutoff {new_cutoff} order {new_order})")
                    self.config = cfg
                    self.cutoff = new_cutoff
                    self.order = new_order
                    self.sr = int(cfg.get("sampling_rate", self.sr))
                    self._design_filter()
                    self.zi = lfilter_zi(self.b, self.a) * 0.0
                time.sleep(2.0)
            except Exception as e:
                print(f"[EMG] config watcher error: {e}")
                time.sleep(2.0)

    def process(self):
        self.is_running = True
        print("▶️ EMG filter processor started")
        while self.is_running:
            try:
                if not self.inlet:
                    # try reconnecting
                    streams = pylsl.resolve_bypred("name='BioSignals-Raw'", timeout=5)
                    if streams:
                        self.inlet = pylsl.StreamInlet(streams[0])
                        print("✓ EMG: reconnected to BioSignals-Raw")
                    else:
                        time.sleep(0.5)
                        continue

                sample, ts = self.inlet.pull_sample(timeout=0.1)
                if sample is None:
                    continue

                # EMG usually ch0 by convention — but config/route may change; we take ch0 here
                raw_val = float(sample[0])

                # filter the single sample (use lfilter with zi)
                filtered, self.zi = lfilter(self.b, self.a, [raw_val], zi=self.zi)
                filtered_value = float(filtered[0])

                # push filtered value
                if self.outlet:
                    self.outlet.push_sample([filtered_value], ts)
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                print(f"[EMG] processing error: {e}")
                time.sleep(0.05)

    def stop(self):
        self.is_running = False
        print("⏹️ EMG filter processor stopped")


if __name__ == "__main__":
    p = EMGFilterProcessor()
    p.process()
