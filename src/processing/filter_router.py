"""
src/processing/filter_router.py

Filter Router
- Subscribe to "BioSignals-Raw"
- Inspect channel metadata (label & type) and map channels to categories (EMG/EOG/EEG)
- Preserve channels as-is: each EMG raw channel -> EMG output channel (same for EOG/EEG)
- Design per-category streaming filters using config/sensor_config.json
- Publish filtered outputs:
    - BioSignals-EMG-Filtered
    - BioSignals-EOG-Filtered
    - BioSignals-EEG-Filtered

Usage:
    python -m src.processing.filter_router
or
    python src/processing/filter_router.py
"""

from pathlib import Path
import time
import json
import threading
from typing import List, Tuple, Dict, Optional

# third-party imports (optional)
try:
    import numpy as np
except Exception as e:
    raise RuntimeError("numpy is required") from e

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

# Config path (project root / config)
CONFIG_PATH = Path("config/sensor_config.json")
RAW_STREAM_NAME = "BioSignals-Raw-uV"
RELOAD_INTERVAL = 2.0  # seconds for config watcher and remap checks
DEFAULT_SR = 512


def load_config() -> dict:
    """Load sensor_config.json, return fallback defaults if missing / invalid."""
    defaults = {
        "sampling_rate": DEFAULT_SR,
        "filters": {
            "EMG": {"cutoff": 70.0, "order": 4},
            "EOG": {"cutoff": 10.0, "order": 4},
            "EEG": {
                "filters": [
                    {"type": "notch", "freq": 50.0, "Q": 30},
                    {"type": "bandpass", "low": 0.5, "high": 45.0, "order": 4}
                ]
            }
        }
    }
    if not CONFIG_PATH.exists():
        return defaults
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        # basic sanity
        if "sampling_rate" not in cfg:
            cfg["sampling_rate"] = defaults["sampling_rate"]
        if "filters" not in cfg:
            cfg["filters"] = defaults["filters"]
        return cfg
    except Exception as e:
        print(f"[Router] Failed to load config ({CONFIG_PATH}): {e} — using defaults")
        return defaults


def parse_channel_map(info: pylsl.StreamInfo) -> List[Tuple[int, str, str]]:
    """
    Inspect an LSL StreamInfo's channel metadata and return a list:
    [(index, label, type_str), ...]
    If metadata missing, fall back to ('ch{i}', '').
    """
    idx_map = []
    try:
        ch_count = int(info.channel_count())
        desc = info.desc()
        channels = desc.child("channels")
        
        # Iterate through channels using first_child() and next_sibling()
        ch = channels.first_child()
        i = 0
        while ch.empty() == False and i < ch_count:
            label = f"ch{i}"
            type_str = ""
            
            try:
                lab = ch.child_value("label")
                typ = ch.child_value("type")
                if lab:
                    label = lab
                if typ:
                    type_str = typ
            except Exception:
                pass
            
            idx_map.append((i, label, type_str))
            ch = ch.next_sibling()
            i += 1
            
    except Exception as e:
        print(f"[Router] parse_channel_map error: {e}")
    
    return idx_map


class CategoryOutlet:
    """Container for an output LSL stream and per-channel filter state"""

    def __init__(self, name: str, type_name: str, indices: List[int], sr: int):
        self.name = name
        self.type_name = type_name  # e.g., "EMG"
        self.indices = list(indices)  # raw indices in BioSignals-Raw
        self.sr = int(sr)
        self.sos = None  # combined sos for the category
        self.zi = []  # list of per-channel zi arrays
        self.outlet = None  # pylsl.StreamOutlet or None

    def create_outlet(self):
        if not LSL_AVAILABLE:
            print(f"[Router] LSL not available - cannot create outlet '{self.name}'")
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
            chans = info.desc().append_child("channels")
            for idx in self.indices:
                ch = chans.append_child("channel")
                ch.append_child_value("label", f"{self.type_name}_{idx}")
                ch.append_child_value("type", self.type_name)
            self.outlet = pylsl.StreamOutlet(info)
            print(f"[Router] Created outlet '{self.name}' (channels={len(self.indices)})")
        except Exception as e:
            print(f"[Router] Failed to create outlet {self.name}: {e}")
            self.outlet = None

    def push(self, samples: List[float], ts: Optional[float]):
        if not LSL_AVAILABLE or self.outlet is None:
            return
        try:
            if ts is not None:
                self.outlet.push_sample(samples, ts)
            else:
                self.outlet.push_sample(samples)
        except Exception as e:
            print(f"[Router] LSL push error ({self.name}): {e}")


class FilterRouter:
    def __init__(self):
        self.config = load_config()
        self.sr = int(self.config.get("sampling_rate", DEFAULT_SR))
        self.inlet = None  # pylsl.StreamInlet
        self.index_map: List[Tuple[int, str, str]] = []  # (index,label,type)
        self.categories: Dict[str, CategoryOutlet] = {}
        self.running = False
        self._config_lock = threading.Lock()
        self._start_config_watcher()

    def _start_config_watcher(self):
        t = threading.Thread(target=self._config_watcher, daemon=True)
        t.start()

    def _config_watcher(self):
        """Reload config periodically so filter parameters can change live."""
        while True:
            try:
                new_cfg = load_config()
                with self._config_lock:
                    self.config = new_cfg
                    self.sr = int(self.config.get("sampling_rate", self.sr))
                time.sleep(RELOAD_INTERVAL)
            except Exception as e:
                print(f"[Router] config watcher error: {e}")
                time.sleep(RELOAD_INTERVAL)

    def resolve_raw_stream(self, timeout: float = 3.0) -> bool:
        """
        Robust discovery of the raw/conversion stream. Attempts:
        1) exact name match of RAW_STREAM_NAME
        2) fallback heuristics: look for names containing 'raw', 'uV', or starting with 'BioSignals'
        Returns True if inlet attached and categories configured.
        """
        if not LSL_AVAILABLE:
            print("[Router] pylsl not installed — cannot resolve raw stream")
            return False

        try:
            # Enumerate streams using the most portable API available
            try:
                all_streams = pylsl.resolve_streams()
            except Exception:
                try:
                    all_streams = pylsl.lsl_resolve_all()
                except Exception:
                    all_streams = []

            # Build a list of (name, StreamInfo)
            available = []
            for s in all_streams:
                try:
                    sname = s.name() if callable(getattr(s, "name", None)) else ""
                    suid = s.uid() if callable(getattr(s, "uid", None)) else ""
                except Exception:
                    try:
                        sname = getattr(s, "name", lambda: "")()
                        suid = getattr(s, "uid", lambda: "")()
                    except Exception:
                        sname = str(s)
                        suid = ""
                available.append((sname, suid, s))

            if not available:
                print("[Router] No LSL streams discovered. Retrying later.")
                return False

            # 1) Try exact name match first
            exact_matches = [s for (n, u, s) in available if n == RAW_STREAM_NAME]
            if exact_matches:
                info = exact_matches[0]
                self.inlet = pylsl.StreamInlet(info, max_buflen=1.0, recover=True)
                self.index_map = parse_channel_map(info)
                print(f"[Router] Resolved (exact) {RAW_STREAM_NAME}: {self.index_map}")
                self._configure_categories()
                return True

            # 2) Heuristic fallback: look for names with 'raw' / 'uV' / 'pure' or starting with 'BioSignals'
            lowered = [(n.lower(), u, s) for (n, u, s) in available]
            heur_matches = []
            for name_low, uid, sinfo in lowered:
                if "raw" in name_low or "uv" in name_low or "pure" in name_low or name_low.startswith("biosignals"):
                    heur_matches.append((name_low, uid, sinfo))

            if heur_matches:
                # Prefer those that contain 'raw' or 'uv' first
                heur_matches_sorted = sorted(
                    heur_matches,
                    key=lambda x: (("raw" not in x[0]), ("uv" not in x[0]), x[0])
                )
                chosen = heur_matches_sorted[0][2]
                try:
                    name_chosen = chosen.name()
                except Exception:
                    name_chosen = "<unknown>"
                self.inlet = pylsl.StreamInlet(chosen, max_buflen=1.0, recover=True)
                self.index_map = parse_channel_map(chosen)
                print(f"[Router] Resolved (heuristic) stream '{name_chosen}' -> indices: {self.index_map}")
                self._configure_categories()
                return True

            # 3) No matches: print available streams for debugging
            print("[Router] No matching raw stream found. Available streams:")
            for n, u, _ in available:
                print(f"  - name: '{n}', uid: '{u}'")
            print(f"[Router] Looking for RAW_STREAM_NAME='{RAW_STREAM_NAME}' or names containing 'raw'/'uV'/'pure' or starting with 'BioSignals'.")
            return False

        except Exception as e:
            print(f"[Router] resolve_raw_stream unexpected error: {e}")
            return False


    def _configure_categories(self):
        """Group raw indices by category using channel type (fallback to label prefix)."""
        # mapping buckets
        buckets = {"EMG": [], "EOG": [], "EEG": [], "OTHER": []}
        for idx, label, typ in self.index_map:
            t = (typ or "").strip().upper()
            if not t:
                # fallback: take label prefix before '_' or whole label
                t = (label.split("_")[0] if "_" in label else label).strip().upper()
            if t in buckets:
                buckets[t].append(idx)
            else:
                buckets["OTHER"].append(idx)

        # Create CategoryOutlet for each present category
        self.categories = {}
        cfg_filters = self.config.get("filters", {})

        # Helper to design filters per category
        def design_for(category: str, indices: List[int]):
            co = CategoryOutlet(f"BioSignals-{category}-Filtered", category, indices, self.sr)
            # design sos depending on category and config
            if not SCIPY_AVAILABLE:
                co.sos = None
            else:
                if category == "EMG":
                    sec = cfg_filters.get("EMG", {})
                    cutoff = float(sec.get("cutoff", 70.0))
                    order = int(sec.get("order", 4))
                    try:
                        nyq = 0.5 * co.sr
                        wn = cutoff / nyq
                        co.sos = butter(order, wn, btype="highpass", output="sos")
                    except Exception as e:
                        print(f"[Router] EMG design error: {e}"); co.sos = None
                elif category == "EOG":
                    sec = cfg_filters.get("EOG", {})
                    cutoff = float(sec.get("cutoff", 10.0))
                    order = int(sec.get("order", 4))
                    try:
                        nyq = 0.5 * co.sr
                        wn = cutoff / nyq
                        co.sos = butter(order, wn, btype="lowpass", output="sos")
                    except Exception as e:
                        print(f"[Router] EOG design error: {e}"); co.sos = None
                elif category == "EEG":
                    sec = cfg_filters.get("EEG", {})
                    filters = sec.get("filters", [])
                    sos_blocks = []
                    try:
                        for f in filters:
                            if f.get("type") == "notch":
                                freq = float(f.get("freq", 50.0))
                                q = float(f.get("Q", 30.0))
                                b, a = iirnotch(freq, q, fs=co.sr)
                                sos_blocks.append(tf2sos(b, a))
                        for f in filters:
                            if f.get("type") == "bandpass":
                                low = float(f.get("low", 0.5)); high = float(f.get("high", 45.0))
                                order = int(f.get("order", 4))
                                nyq = 0.5 * co.sr
                                wn = [low / nyq, high / nyq]
                                sos_blocks.append(butter(order, wn, btype="bandpass", output="sos"))
                    except Exception as e:
                        print(f"[Router] EEG design error: {e}")
                    if sos_blocks:
                        try:
                            co.sos = np.vstack(sos_blocks)
                        except Exception:
                            co.sos = sos_blocks[-1]
                    else:
                        co.sos = None
                else:
                    co.sos = None

            # initialize per-channel zi arrays for this category
            if SCIPY_AVAILABLE and co.sos is not None:
                try:
                    co.zi = [sosfilt_zi(co.sos) * 0.0 for _ in co.indices]
                except Exception as e:
                    print(f"[Router] zi init error for {co.name}: {e}")
                    co.zi = [None for _ in co.indices]
            else:
                co.zi = [None for _ in co.indices]

            co.create_outlet()
            return co

        if buckets["EMG"]:
            self.categories["EMG"] = design_for("EMG", buckets["EMG"])
        if buckets["EOG"]:
            self.categories["EOG"] = design_for("EOG", buckets["EOG"])
        if buckets["EEG"]:
            self.categories["EEG"] = design_for("EEG", buckets["EEG"])

        print(f"[Router] category mapping: {{k: [v.indices for v in self.categories.values()]}}")
        # (log friendly mapping)
        for k, v in self.categories.items():
            print(f"[Router] {k} -> indices {v.indices} (outlet: {v.name})")

    def run(self):
        if not LSL_AVAILABLE:
            print("[Router] pylsl not installed — router cannot run. Install pylsl to enable LSL streams.")
            return
        self.running = True
        print("[Router] Starting: resolving raw stream...")
        # wait until we resolve the raw stream
        while self.running and not self.resolve_raw_stream(timeout=2.0):
            time.sleep(0.5)
        print("[Router] Entering processing loop")

        while self.running:
            try:
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                if sample is None:
                    continue
                arr = list(sample)

                # For each category, extract relevant indices in order, apply per-channel filtering and push
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
                                # filter failed for this sample -> fallback to raw
                                print(f"[Router] filter error cat={cat_name} idx={raw_idx}: {e}")
                                out_vals.append(raw_val)
                        else:
                            out_vals.append(raw_val)
                    # push sample downstream
                    co.push(out_vals, ts)
            except KeyboardInterrupt:
                print("[Router] KeyboardInterrupt received. Stopping.")
                self.running = False
            except Exception as e:
                print(f"[Router] processing loop exception: {e}")
                # attempt to recover: re-resolve stream if inlet closed/unavailable
                try:
                    # Some pylsl StreamInlet implementations have .is_open() or similar; test for exceptions
                    if self.inlet is None:
                        self.resolve_raw_stream(timeout=2.0)
                except Exception:
                    pass
                time.sleep(0.05)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    router = FilterRouter()
    try:
        router.run()
    except KeyboardInterrupt:
        router.stop()
        print("Exited filter_router")
