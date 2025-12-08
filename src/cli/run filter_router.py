#!/usr/bin/env python3
"""
run_filter_router.py

Usage:
    python src/processing/run_filter_router.py

Description:
    - Loads routing/filter config from config/filter_router_integrated.json
    - Resolves BioSignals-Raw LSL stream
    - Maps channels by metadata (type/label) to categories EMG/EOG/EEG
    - Designs streaming SOS filters per category (hot-reloads config)
    - Applies filters per-channel preserving streaming state (zi)
    - Publishes filtered channels to category outputs:
        BioSignals-EMG-Filtered, BioSignals-EOG-Filtered, BioSignals-EEG-Filtered
"""

import time
import json
import threading
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# external deps: numpy, pylsl, scipy
try:
    import numpy as np
except Exception:
    raise RuntimeError("numpy is required. Install with: pip install numpy")

try:
    import pylsl
    LSL_AVAILABLE = True
except Exception:
    pylsl = None
    LSL_AVAILABLE = False
    print("⚠️ pylsl not available. Install pylsl to enable LSL functionality (pip install pylsl).")

try:
    from scipy.signal import butter, iirnotch, tf2sos, sosfilt, sosfilt_zi
    SCIPY_AVAILABLE = True
except Exception:
    butter = iirnotch = tf2sos = sosfilt = sosfilt_zi = None
    SCIPY_AVAILABLE = False
    print("⚠️ scipy not available. Filtering will be disabled (pip install scipy).")

CONFIG_PATH = Path("config/filter_router_integrated.json")
RELOAD_INTERVAL = 2.0  # seconds


def load_json_config(path: Path) -> dict:
    if not path.exists():
        print(f"[Router] Config {path} not found. Using built-in defaults.")
        return {
            "router": {
                "sampling_rate_hz": 512,
                "channels": {"0": {"default_type": "EMG"}, "1": {"default_type": "EOG"}},
                "filters": {
                    "EMG": {"type": "highpass", "cutoff": 70.0, "order": 4},
                    "EOG": {"type": "lowpass", "cutoff": 10.0, "order": 4},
                    "EEG": {"chain": [{"type": "notch", "freq": 50.0, "Q": 30}, {"type": "bandpass", "low": 0.5, "high": 45.0, "order": 4}]}
                }
            }
        }
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Router] Failed to read config {path}: {e}")
        return {}


def parse_channel_map(info: "pylsl.StreamInfo") -> List[Tuple[int, str, str]]:
    """
    Return list of (index, label, type) for each channel in a StreamInfo.
    Fallback label 'ch{i}', type '' when not present.
    """
    mapping = []
    try:
        ch_count = int(info.channel_count())
        desc = info.desc()
        channels = desc.child("channels")
        for i in range(ch_count):
            label = f"ch{i}"
            typ = ""
            try:
                ch = channels.child("channel", i)
                lab = ch.child_value("label")
                tt = ch.child_value("type")
                if lab:
                    label = lab
                if tt:
                    typ = tt
            except Exception:
                pass
            mapping.append((i, label, typ))
    except Exception as e:
        print(f"[Router] parse_channel_map error: {e}")
    return mapping


class CategoryOutlet:
    def __init__(self, name: str, type_name: str, indices: List[int], sr: int):
        self.name = name
        self.type_name = type_name
        self.indices = list(indices)
        self.sr = int(sr)
        self.sos = None
        self.zi = []  # per-channel zi
        self.outlet = None

    def create_outlet(self):
        if not LSL_AVAILABLE:
            return
        try:
            info = pylsl.StreamInfo(
                name=self.name,
                type=self.type_name,
                channel_count=max(1, len(self.indices)),
                nominal_srate=self.sr,
                channel_format='float32',
                source_id=self.name
            )
            channels = info.desc().append_child("channels")
            for idx in self.indices:
                ch = channels.append_child("channel")
                ch.append_child_value("label", f"{self.type_name}_{idx}")
                ch.append_child_value("type", self.type_name)
            self.outlet = pylsl.StreamOutlet(info)
            print(f"[Router] Created outlet '{self.name}' with {len(self.indices)} channels")
        except Exception as e:
            print(f"[Router] Failed to create outlet {self.name}: {e}")
            self.outlet = None

    def push(self, sample: List[float], ts: Optional[float] = None):
        if not LSL_AVAILABLE or self.outlet is None:
            return
        try:
            if ts is not None:
                self.outlet.push_sample(sample, ts)
            else:
                self.outlet.push_sample(sample)
        except Exception as e:
            print(f"[Router] push error ({self.name}): {e}")


class FilterRouter:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.config = load_json_config(self.config_path)
        self.sr = int(self._cfg_get("router.sampling_rate_hz", 512))
        self.inlet = None
        self.index_map = []
        self.categories: Dict[str, CategoryOutlet] = {}
        self.running = False
        self._config_lock = threading.Lock()
        self._start_config_watcher()

    def _cfg_get(self, key_path: str, default=None):
        parts = key_path.split(".")
        cur = self.config
        try:
            for p in parts:
                cur = cur[p]
            return cur
        except Exception:
            return default

    def _start_config_watcher(self):
        t = threading.Thread(target=self._config_watcher_loop, daemon=True)
        t.start()

    def _config_watcher_loop(self):
        last_mtime = None
        while True:
            try:
                if self.config_path.exists():
                    mtime = self.config_path.stat().st_mtime
                    if last_mtime is None or mtime != last_mtime:
                        new_cfg = load_json_config(self.config_path)
                        with self._config_lock:
                            self.config = new_cfg
                            self.sr = int(self._cfg_get("router.sampling_rate_hz", self.sr))
                        last_mtime = mtime
                        print("[Router] Config reloaded")
                        # re-design filters if already resolved
                        if self.inlet is not None:
                            self._configure_categories()
                time.sleep(RELOAD_INTERVAL)
            except Exception as e:
                print(f"[Router] config watcher error: {e}")
                time.sleep(RELOAD_INTERVAL)

    def resolve_raw_stream(self, timeout: float = 3.0) -> bool:
        if not LSL_AVAILABLE:
            print("[Router] pylsl not installed.")
            return False
        try:
            streams = pylsl.resolve_bypred(f"name='BioSignals-Raw'", timeout=timeout)
            if not streams:
                print("[Router] BioSignals-Raw not found (retrying)...")
                return False
            info = streams[0]
            self.inlet = pylsl.StreamInlet(info, max_buflen=1.0, recover=True)
            self.index_map = parse_channel_map(info)
            print(f"[Router] Resolved raw stream: {self.index_map}")
            self._configure_categories()
            return True
        except Exception as e:
            print(f"[Router] resolve_raw_stream error: {e}")
            return False

    def _configure_categories(self):
        # bucket indices by inferred type
        buckets = {"EMG": [], "EOG": [], "EEG": [], "OTHER": []}
        for idx, label, typ in self.index_map:
            t = (typ or "").strip().upper()
            if not t:
                t = (label.split("_")[0] if "_" in label else label).strip().upper()
            if t in buckets:
                buckets[t].append(idx)
            else:
                buckets["OTHER"].append(idx)

        cfg_filters = self._cfg_get("router.filters", {})
        # helper to design per category
        def design(category: str, indices: List[int]):
            co = CategoryOutlet(f"BioSignals-{category}-Filtered", category, indices, self.sr)
            if not SCIPY_AVAILABLE:
                co.sos = None
            else:
                try:
                    if category == "EMG":
                        sec = cfg_filters.get("EMG", {})
                        cutoff = float(sec.get("cutoff", 70.0))
                        order = int(sec.get("order", 4))
                        nyq = 0.5 * co.sr
                        wn = cutoff / nyq
                        co.sos = butter(order, wn, btype="highpass", output="sos")
                    elif category == "EOG":
                        sec = cfg_filters.get("EOG", {})
                        cutoff = float(sec.get("cutoff", 10.0))
                        order = int(sec.get("order", 4))
                        nyq = 0.5 * co.sr
                        wn = cutoff / nyq
                        co.sos = butter(order, wn, btype="lowpass", output="sos")
                    elif category == "EEG":
                        sec = cfg_filters.get("EEG", {})
                        filters = sec.get("filters", [])
                        sos_blocks = []
                        for f in filters:
                            if f.get("type") == "notch":
                                freq = float(f.get("freq", 50.0))
                                q = float(f.get("Q", 30.0))
                                # use iirnotch with fs parameter, convert to sos via tf2sos
                                b, a = iirnotch(freq, q, fs=co.sr)
                                sos_blocks.append(tf2sos(b, a))
                        for f in filters:
                            if f.get("type") == "bandpass":
                                low = float(f.get("low", 0.5)); high = float(f.get("high", 45.0))
                                order = int(f.get("order", 4))
                                nyq = 0.5 * co.sr
                                wn = [low / nyq, high / nyq]
                                sos_blocks.append(butter(order, wn, btype="bandpass", output="sos"))
                        if sos_blocks:
                            try:
                                co.sos = np.vstack(sos_blocks)
                            except Exception:
                                co.sos = sos_blocks[-1]
                        else:
                            co.sos = None
                    else:
                        co.sos = None
                except Exception as e:
                    print(f"[Router] design error for {category}: {e}")
                    co.sos = None

            # init zi per channel
            if SCIPY_AVAILABLE and co.sos is not None:
                try:
                    co.zi = [sosfilt_zi(co.sos) * 0.0 for _ in co.indices]
                except Exception as e:
                    print(f"[Router] zi init error {category}: {e}")
                    co.zi = [None for _ in co.indices]
            else:
                co.zi = [None for _ in co.indices]

            co.create_outlet()
            return co

        # rebuild categories
        self.categories = {}
        if buckets["EMG"]:
            self.categories["EMG"] = design("EMG", buckets["EMG"])
        if buckets["EOG"]:
            self.categories["EOG"] = design("EOG", buckets["EOG"])
        if buckets["EEG"]:
            self.categories["EEG"] = design("EEG", buckets["EEG"])

        print("[Router] Categories configured:", {k: v.indices for k, v in self.categories.items()})

    def run(self):
        if not LSL_AVAILABLE:
            print("[Router] pylsl is required to run the router. Exiting.")
            return
        self.running = True
        # resolve stream first
        while self.running and not self.resolve_raw_stream(timeout=2.0):
            time.sleep(1.0)

        print("[Router] Running processing loop.")
        while self.running:
            try:
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                if sample is None:
                    continue
                arr = list(sample)
                # for each category, extract and filter
                for cat_name, co in self.categories.items():
                    if not co.indices:
                        continue
                    out_vals = []
                    for local_idx, raw_idx in enumerate(co.indices):
                        raw_val = float(arr[raw_idx]) if raw_idx < len(arr) else 0.0
                        if SCIPY_AVAILABLE and co.sos is not None:
                            zi = co.zi[local_idx] if local_idx < len(co.zi) else None
                            if zi is None:
                                try:
                                    zi = sosfilt_zi(co.sos) * 0.0
                                except Exception:
                                    zi = None
                            try:
                                y, zf = sosfilt(co.sos, [raw_val], zi=zi)
                                co.zi[local_idx] = zf
                                out_vals.append(float(y[0]))
                            except Exception as e:
                                print(f"[Router] filter apply error cat={cat_name} idx={raw_idx}: {e}")
                                out_vals.append(raw_val)
                        else:
                            out_vals.append(raw_val)
                    co.push(out_vals, ts)
            except KeyboardInterrupt:
                print("\n[Router] KeyboardInterrupt - stopping.")
                self.running = False
            except Exception as e:
                print(f"[Router] main loop error: {e}")
                # attempt to re-resolve on critical errors
                try:
                    if self.inlet is None:
                        self.resolve_raw_stream(timeout=2.0)
                except Exception:
                    pass
                time.sleep(0.05)

    def stop(self):
        self.running = False


def main():
    router = FilterRouter()
    try:
        router.run()
    except KeyboardInterrupt:
        router.stop()
        print("Exiting.")

if __name__ == "__main__":
    main()
