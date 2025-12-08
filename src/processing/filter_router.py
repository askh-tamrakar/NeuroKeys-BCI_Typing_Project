#!/usr/bin/env python3
"""
filter_router.py

- Subscribes to LSL stream "BioSignals-Raw"
- Inspects channel metadata to map channels to types (EMG/EOG/EEG)
- Applies per-channel streaming filters according to sensor_config.json
- Publishes filtered outputs to:
    - "BioSignals-EMG-Filtered"  (all EMG channels, preserved order)
    - "BioSignals-EOG-Filtered"  (all EOG channels)
    - "BioSignals-EEG-Filtered"  (all EEG channels)
- Auto-reloads sensor_config.json every 2s (live tuning)
- Maintains per-channel zi states for continuous filtering
"""

import time
import json
import threading
from pathlib import Path
from typing import List, Dict, Tuple, Optional

try:
    import numpy as np
except Exception:
    raise RuntimeError("numpy required")

# LSL and SciPy are optional at import time: we warn later if absent
try:
    import pylsl
    LSL_AVAILABLE = True
except Exception:
    pylsl = None
    LSL_AVAILABLE = False

try:
    from scipy.signal import butter, iirnotch, tf2sos, sosfilt, sosfilt_zi
    SCIPY_AVAILABLE = True
except Exception:
    butter = iirnotch = tf2sos = sosfilt = sosfilt_zi = None
    SCIPY_AVAILABLE = False

CONFIG_PATH = Path("sensor_config.json")
RELOAD_INTERVAL = 2.0  # seconds
RAW_STREAM_NAME = "BioSignals-Raw"


def load_config():
    if not CONFIG_PATH.exists():
        # sensible defaults
        return {
            "sampling_rate": 512,
            "filters": {
                "EMG": {"type": "highpass", "cutoff": 70.0, "order": 4},
                "EOG": {"type": "lowpass", "cutoff": 10.0, "order": 4},
                "EEG": {"filters": [{"type": "notch", "freq": 50.0, "Q": 30},
                                    {"type": "bandpass", "low": 0.5, "high": 45.0, "order": 4}]}
            }
        }
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return load_config()


def parse_channel_map(stream_info) -> List[Tuple[int, str, str]]:
    """
    Return list of (index, label, type_str) for each channel in the stream info.
    If channel metadata missing, default to label 'ch{i}' and type ''.
    """
    idx_map = []
    try:
        info = stream_info
        ch_count = int(info.channel_count())
        desc = info.desc()
        channels = desc.child("channels")
        # channels may not be present; handle safely
        for i in range(ch_count):
            label = f"ch{i}"
            type_str = ""
            try:
                ch = channels.child("channel", i)
                lab = ch.child_value("label")
                typ = ch.child_value("type")
                if lab:
                    label = lab
                if typ:
                    type_str = typ
            except Exception:
                pass
            idx_map.append((i, label, type_str))
    except Exception:
        # fallback
        return idx_map
    return idx_map


class CategoryOutlet:
    """Holds LSL outlet and per-channel filter state for a signal category"""

    def __init__(self, name: str, types: List[str], channel_indices: List[int], sr: int):
        self.name = name
        self.types = types
        self.channel_indices = channel_indices
        self.sr = sr
        self.outlet = None  # pylsl.StreamOutlet
        self.sos = None     # combined sos for this category (applied to all channels of this category)
        self.zi = []        # per-channel zi arrays (matching channel_indices order)

    def create_outlet(self):
        if not LSL_AVAILABLE:
            return
        # channel labels: use type + index for clarity
        info = pylsl.StreamInfo(
            name=self.name,
            type=self.types[0] if self.types else "Signal",
            channel_count=max(1, len(self.channel_indices)),
            nominal_srate=self.sr,
            channel_format='float32',
            source_id=self.name
        )
        channels = info.desc().append_child("channels")
        for idx in self.channel_indices:
            channels.append_child("channel").append_child_value("label", f"{self.name}_{idx}").append_child_value("type", self.types[0] if self.types else "Signal")
        self.outlet = pylsl.StreamOutlet(info)
        print(f"[Router] Created LSL outlet '{self.name}' ch={len(self.channel_indices)}")

    def push(self, sample: List[float], ts: Optional[float]):
        if not LSL_AVAILABLE or self.outlet is None:
            return
        try:
            if ts is not None:
                self.outlet.push_sample(sample, ts)
            else:
                self.outlet.push_sample(sample)
        except Exception as e:
            print(f"[Router] LSL push error ({self.name}): {e}")


class FilterRouter:
    def __init__(self):
        self.config = load_config()
        self.sr = int(self.config.get("sampling_rate", 512))
        self.inlet = None  # raw inlet
        self.index_map = []  # list of (idx, label, type_str)
        self.categories: Dict[str, CategoryOutlet] = {}  # keys: "EMG","EOG","EEG"
        self.running = False
        self.config_lock = threading.Lock()
        self.last_config_mtime = None
        self._start_config_watcher()

    def _start_config_watcher(self):
        t = threading.Thread(target=self._config_watcher, daemon=True)
        t.start()

    def _config_watcher(self):
        while True:
            try:
                cfg = load_config()
                with self.config_lock:
                    self.config = cfg
                    self.sr = int(self.config.get("sampling_rate", self.sr))
                time.sleep(RELOAD_INTERVAL)
            except Exception as e:
                print("[Router] Config watcher error:", e)
                time.sleep(RELOAD_INTERVAL)

    def resolve_raw(self, timeout=5.0) -> bool:
        if not LSL_AVAILABLE:
            print("⚠️ LSL not available: router cannot resolve BioSignals-Raw")
            return False
        streams = pylsl.resolve_bypred(f"name='{RAW_STREAM_NAME}'", timeout=timeout)
        if not streams:
            print(f"[Router] Raw stream '{RAW_STREAM_NAME}' not found (will retry)")
            return False
        self.inlet = pylsl.StreamInlet(streams[0], max_buflen=1.0, recover=True)
        info = streams[0]
        self.index_map = parse_channel_map(info)
        print(f"[Router] Resolved {RAW_STREAM_NAME} with channels:", self.index_map)
        self._configure_categories()
        return True

    def _configure_categories(self):
        # Map indices by type. Types may be blank; fallback rules: prefer 'type' then label prefix.
        mapping: Dict[str, List[int]] = {"EMG": [], "EOG": [], "EEG": [], "OTHER": []}
        for idx, label, typ in self.index_map:
            t = (typ or "").strip().upper()
            if not t:
                # infer from label prefix
                t = (label.split("_")[0] if "_" in label else label).strip().upper()
            if t in mapping:
                mapping[t].append(idx)
            else:
                mapping["OTHER"].append(idx)

        # Build CategoryOutlet objects for EMG, EOG, EEG (preserve channel order)
        self.categories = {}
        cfg = self.config.get("filters", {})
        # EMG
        emg_idxs = mapping.get("EMG", [])
        if emg_idxs:
            co = CategoryOutlet("BioSignals-EMG-Filtered", ["EMG"], emg_idxs, self.sr)
            self._design_category_filter(co, "EMG", cfg.get("EMG", {}))
            co.create_outlet()
            self.categories["EMG"] = co
        # EOG
        eog_idxs = mapping.get("EOG", [])
        if eog_idxs:
            co = CategoryOutlet("BioSignals-EOG-Filtered", ["EOG"], eog_idxs, self.sr)
            self._design_category_filter(co, "EOG", cfg.get("EOG", {}))
            co.create_outlet()
            self.categories["EOG"] = co
        # EEG
        eeg_idxs = mapping.get("EEG", [])
        if eeg_idxs:
            co = CategoryOutlet("BioSignals-EEG-Filtered", ["EEG"], eeg_idxs, self.sr)
            self._design_category_filter(co, "EEG", cfg.get("EEG", {}))
            co.create_outlet()
            self.categories["EEG"] = co

        # initialize zi arrays per channel for each category
        for cat in self.categories.values():
            if SCIPY_AVAILABLE and cat.sos is not None:
                cat.zi = [sosfilt_zi(cat.sos) * 0.0 for _ in cat.channel_indices]
            else:
                cat.zi = [None for _ in cat.channel_indices]

        print(f"[Router] Category mapping: { {k: v.channel_indices for k,v in self.categories.items()} }")

    def _design_category_filter(self, co: CategoryOutlet, category: str, cfg_section):
        # Design filters for category: produce combined SOS assigned to co.sos
        if not SCIPY_AVAILABLE:
            co.sos = None
            return
        fs = int(self.sr)
        nyq = 0.5 * fs

        if category == "EMG":
            # High-pass default 70Hz
            cutoff = float(cfg_section.get("cutoff", 70.0))
            order = int(cfg_section.get("order", 4))
            wn = cutoff / nyq
            try:
                sos = butter(order, wn, btype="highpass", output="sos")
                co.sos = sos
            except Exception as e:
                print(f"[Router] EMG filter design failed: {e}")
                co.sos = None

        elif category == "EOG":
            cutoff = float(cfg_section.get("cutoff", 10.0))
            order = int(cfg_section.get("order", 4))
            wn = cutoff / nyq
            try:
                sos = butter(order, wn, btype="lowpass", output="sos")
                co.sos = sos
            except Exception as e:
                print(f"[Router] EOG filter design failed: {e}")
                co.sos = None

        elif category == "EEG":
            # expect cfg_section to contain 'filters' list with notch and bandpass
            filters = cfg_section.get("filters", [])
            sos_blocks = []
            # notch first
            for f in filters:
                try:
                    if f.get("type") == "notch":
                        f_freq = float(f.get("freq", 50.0))
                        fQ = float(f.get("Q", 30.0))
                        # scipy iirnotch expects w0 (Hz) and Q with fs parameter
                        b, a = iirnotch(f_freq, fQ, fs=fs)
                        notch_sos = tf2sos(b, a)
                        sos_blocks.append(notch_sos)
                except Exception as e:
                    print(f"[Router] EEG notch design error: {e}")
            # bandpass
            for f in filters:
                try:
                    if f.get("type") == "bandpass":
                        low = float(f.get("low", 0.5))
                        high = float(f.get("high", 45.0))
                        order = int(f.get("order", 4))
                        wn = [low / nyq, high / nyq]
                        band_sos = butter(order, wn, btype="bandpass", output="sos")
                        sos_blocks.append(band_sos)
                except Exception as e:
                    print(f"[Router] EEG bandpass design error: {e}")
            if sos_blocks:
                # stack blocks vertically
                try:
                    co.sos = np.vstack(sos_blocks)
                except Exception:
                    co.sos = sos_blocks[-1]
            else:
                co.sos = None
        else:
            co.sos = None

    def run(self):
        if not LSL_AVAILABLE:
            print("LSL not installed — router cannot run. Install pylsl.")
            return
        self.running = True
        print("[Router] Starting main loop. Resolving raw stream...")
        # try to resolve initially
        while self.running and not self.resolve_raw(timeout=2.0):
            time.sleep(1.0)

        print("[Router] Entering processing loop")
        while self.running:
            try:
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                if sample is None:
                    continue
                # sample is list-like containing raw ADC channels in LSL order
                arr = list(sample)
                # For each category, extract the raw values for the assigned indices, apply per-channel filtering, push outlet
                for cat_name, co in self.categories.items():
                    if not co.channel_indices:
                        continue
                    out_vals = []
                    for i_local, ch_idx in enumerate(co.channel_indices):
                        raw_val = float(arr[ch_idx]) if ch_idx < len(arr) else 0.0
                        # Filtering
                        if SCIPY_AVAILABLE and co.sos is not None:
                            zi = co.zi[i_local] if i_local < len(co.zi) else None
                            if zi is None:
                                # initialize
                                zi = sosfilt_zi(co.sos) * 0.0
                            y, zf = sosfilt(co.sos, [raw_val], zi=zi)
                            co.zi[i_local] = zf
                            out_vals.append(float(y[0]))
                        else:
                            out_vals.append(raw_val)
                    # push multi-channel sample
                    co.push(out_vals, ts)
            except KeyboardInterrupt:
                print("[Router] KeyboardInterrupt — stopping")
                self.running = False
            except Exception as e:
                print("[Router] processing error:", e)
                # attempt to re-resolve if inlet lost
                try:
                    if self.inlet.closed():
                        print("[Router] inlet closed — resolving again")
                        self.resolve_raw(timeout=2.0)
                except Exception:
                    pass
                time.sleep(0.05)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    r = FilterRouter()
    try:
        r.run()
    except KeyboardInterrupt:
        r.stop()
        print("Exited")
