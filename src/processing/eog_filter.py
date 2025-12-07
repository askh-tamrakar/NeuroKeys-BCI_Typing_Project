#!/usr/bin/env python3
"""
EOG filter processor

- Reads raw stream "BioSignals-Raw"
- Applies configurable low-pass filter (default 10 Hz, order 4)
- Publishes filtered EOG to "BioSignals-EOG-Filtered"
- Auto-reloads sensor_config.json every 2 seconds
"""

import json
import time
import threading
from pathlib import Path

import pylsl
from scipy.signal import butter, lfilter, lfilter_zi

CONFIG_PATH = Path("sensor_config.json")


class EOGFilterProcessor:
    def __init__(self):
        self.config = self.load_config()
        self.sr = int(self.config.get("sampling_rate", 512))
        self.cutoff = float(self.config["filters"]["EOG"].get("cutoff", 10.0))
        self.order = int(self.config["filters"]["EOG"].get("order", 4))
        self.inlet = None
        self.outlet = None
        self.is_running = False

        self._design_filter()
        self._setup_lsl()
        self.zi = lfilter_zi(self.b, self.a) * 0.0

        self._watcher_thread = threading.Thread(target=self._config_watcher, daemon=True)
        self._watcher_thread.start()

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {
                "sampling_rate": 512,
                "filters": {"EOG": {"cutoff": 10.0, "order": 4}}
            }

    def _design_filter(self):
        nyq = self.sr / 2.0
        wn = self.cutoff / nyq
        self.b, self.a = butter(self.order, wn, btype="low", analog=False)
        print(f"[EOG] Designed low-pass: cutoff={self.cutoff} Hz order={self.order}")

    def _setup_lsl(self):
        streams = pylsl.resolve_bypred("name='BioSignals-Raw'", timeout=5)
        if not streams:
            print("⚠️ EOG: BioSignals-Raw not found (will retry)")
        else:
            self.inlet = pylsl.StreamInlet(streams[0])
            print("✓ EOG: connected to BioSignals-Raw")

        info = pylsl.StreamInfo(
            name="BioSignals-EOG-Filtered",
            type="EOG",
            channel_count=1,
            nominal_srate=self.sr,
            channel_format="float32",
            source_id="EOG-Filter-Processor"
        )
        self.outlet = pylsl.StreamOutlet(info)
        print("✓ EOG: created outlet BioSignals-EOG-Filtered")

    def _config_watcher(self):
        while True:
            try:
                cfg = self.load_config()
                new_cutoff = float(cfg["filters"]["EOG"].get("cutoff", 10.0))
                new_order = int(cfg["filters"]["EOG"].get("order", 4))
                if new_cutoff != self.cutoff or new_order != self.order or int(cfg.get("sampling_rate", 512)) != self.sr:
                    print(f"[EOG] Config changed -> redesigning filter (cutoff {new_cutoff} order {new_order})")
                    self.config = cfg
                    self.cutoff = new_cutoff
                    self.order = new_order
                    self.sr = int(cfg.get("sampling_rate", self.sr))
                    self._design_filter()
                    self.zi = lfilter_zi(self.b, self.a) * 0.0
                time.sleep(2.0)
            except Exception as e:
                print(f"[EOG] watcher error: {e}")
                time.sleep(2.0)

    def process(self):
        self.is_running = True
        print("▶️ EOG filter processor started")
        while self.is_running:
            try:
                if not self.inlet:
                    streams = pylsl.resolve_bypred("name='BioSignals-Raw'", timeout=5)
                    if streams:
                        self.inlet = pylsl.StreamInlet(streams[0])
                        print("✓ EOG: reconnected to BioSignals-Raw")
                    else:
                        time.sleep(0.5)
                        continue

                sample, ts = self.inlet.pull_sample(timeout=0.1)
                if sample is None:
                    continue

                # EOG typically ch1 (but depends on mapping); this implementation uses sample[1] if available, else sample[0]
                raw_val = float(sample[1]) if len(sample) > 1 else float(sample[0])

                filtered, self.zi = lfilter(self.b, self.a, [raw_val], zi=self.zi)
                filtered_value = float(filtered[0])

                if self.outlet:
                    self.outlet.push_sample([filtered_value], ts)
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                print(f"[EOG] processing error: {e}")
                time.sleep(0.05)

    def stop(self):
        self.is_running = False
        print("⏹️ EOG filter processor stopped")


if __name__ == "__main__":
    p = EOGFilterProcessor()
    p.process()
