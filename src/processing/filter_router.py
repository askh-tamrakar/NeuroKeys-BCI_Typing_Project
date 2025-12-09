"""
src/processing/filter_router.py

IMPROVED FILTER ROUTER with Passive Processors

Features:
- Monitors channel mapping changes in config
- Instantiates per-channel passive processors (EMG/EOG/EEG)
- Routes data through processors sample-by-sample
- Publishes single unified "BioSignals-Processed" stream
"""

from pathlib import Path
import time
import json
import threading
import hashlib
from typing import List, Tuple, Dict, Optional

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

# Import passive processors
try:
    from .emg_processor import EMGFilterProcessor
    from .eog_processor import EOGFilterProcessor
    from .eeg_processor import EEGFilterProcessor
except ImportError:
    print("[Router] Running from different context, using local imports")
    # Add project root to sys.path to allow 'src' imports
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from src.processing.emg_processor import EMGFilterProcessor
    from src.processing.eog_processor import EOGFilterProcessor
    from src.processing.eeg_processor import EEGFilterProcessor

# Resolve project root: src/processing -> src -> root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
RAW_STREAM_NAME = "BioSignals-Raw-uV"
PROCESSED_STREAM_NAME = "BioSignals-Processed"
RELOAD_INTERVAL = 2.0
DEFAULT_SR = 512


def load_config() -> dict:
    """Load sensor_config.json with safe fallback defaults."""
    defaults = {
        "sampling_rate": DEFAULT_SR,
        "channel_mapping": {
            "ch0": {"sensor": "EMG", "enabled": True},
            "ch1": {"sensor": "EOG", "enabled": True}
        },
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
        if "sampling_rate" not in cfg:
            cfg["sampling_rate"] = defaults["sampling_rate"]
        if "filters" not in cfg:
            cfg["filters"] = defaults["filters"]
        if "channel_mapping" not in cfg:
            cfg["channel_mapping"] = defaults["channel_mapping"]
        return cfg
    except Exception as e:
        print(f"[Router] Failed to load config ({CONFIG_PATH}): {e} — using defaults")
        return defaults


def get_config_hash(cfg: dict) -> str:
    """Create hash of config to detect changes."""
    try:
        return hashlib.md5(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    except:
        return ""


def parse_channel_map(info: pylsl.StreamInfo) -> List[Tuple[int, str, str]]:
    """Parse channel metadata from LSL StreamInfo."""
    idx_map = []
    try:
        ch_count = int(info.channel_count())
        desc = info.desc()
        channels = desc.child("channels")
        
        if not channels.empty():
            ch = channels.first_child()
            i = 0
            while not ch.empty() and i < ch_count:
                label = f"ch{i}"
                type_str = ""
                try:
                    lab = ch.child_value("label")
                    typ = ch.child_value("type")
                    if lab: label = lab
                    if typ: type_str = typ
                except:
                    pass
                idx_map.append((i, label, type_str))
                ch = ch.next_sibling()
                i += 1
        
        if idx_map:
            return idx_map
    except Exception as e:
        print(f"[Router] XML parsing warning: {e}")
    
    # Fallback
    try:
        ch_count = int(info.channel_count())
        return [(i, f"ch{i}", f"ch{i}") for i in range(ch_count)]
    except:
        return []


class FilterRouter:
    def __init__(self):
        self.config = load_config()
        self.sr = int(self.config.get("sampling_rate", DEFAULT_SR))
        self.inlet = None
        self.outlet = None
        
        self.raw_index_map: List[Tuple[int, str, str]] = []  # From LSL stream
        self.channel_processors: Dict[int, object] = {} # ch_idx -> ProcessorInstance
        self.channel_mapping: Dict[int, str] = {} # ch_idx -> "EMG"/"EOG"/"EEG"
        
        self.running = False
        self._config_lock = threading.Lock()
        self._start_config_watcher()

    def _start_config_watcher(self):
        t = threading.Thread(target=self._config_watcher, daemon=True)
        t.start()
    
    def _config_watcher(self):
        last_cfg_hash = ""
        last_map_hash = ""
        
        while True:
            try:
                new_cfg = load_config()
                cfg_hash = get_config_hash(new_cfg.get("filters", {}))
                map_hash = get_config_hash(new_cfg.get("channel_mapping", {}))
                
                with self._config_lock:
                    self.config = new_cfg
                    self.sr = int(self.config.get("sampling_rate", self.sr))
                    
                    # 1. Mapping changed? Reconfigure everything (including LSL outlet)
                    if map_hash != last_map_hash:
                        print("[Router] Channel mapping changed - reconfiguring pipeline...")
                        self._configure_pipeline()
                        last_map_hash = map_hash
                        last_cfg_hash = cfg_hash # Reset config hash too since we reloaded
                    
                    # 2. Only Params changed? Update existing processors
                    elif cfg_hash != last_cfg_hash:
                        print("[Router] Filter params updated - updating processors...")
                        for p in self.channel_processors.values():
                            if hasattr(p, 'update_config'):
                                p.update_config(self.config, self.sr)
                        last_cfg_hash = cfg_hash
                
                time.sleep(RELOAD_INTERVAL)
            except Exception as e:
                print(f"[Router] config watcher error: {e}")
                time.sleep(RELOAD_INTERVAL)

    def resolve_raw_stream(self, timeout: float = 3.0) -> bool:
        if not LSL_AVAILABLE:
            print("[Router] pylsl not installed.")
            return False
        
        try:
            streams = pylsl.resolve_streams(wait_time=0.5)
            target = None
            
            # 1. Exact match
            for s in streams:
                if s.name() == RAW_STREAM_NAME:
                    target = s
                    break
            
            # 2. Heuristic
            if not target:
                for s in streams:
                    if "raw" in s.name().lower() or "uv" in s.name().lower():
                        target = s
                        break
            
            if target:
                self.inlet = pylsl.StreamInlet(target, max_buflen=1, recover=True)
                self.raw_index_map = parse_channel_map(self.inlet.info())
                print(f"[Router] Connected to raw stream: {target.name()}")
                self._configure_pipeline()
                return True
            
            return False
        except Exception as e:
            print(f"[Router] resolve error: {e}")
            return False

    def _configure_pipeline(self):
        """Create processors and output stream based on current mapping."""
        # Clean up old
        self.channel_processors = {}
        self.channel_mapping = {}
        self.outlet = None
        
        mapping_cfg = self.config.get("channel_mapping", {})
        
        # 1. Map raw indices to processors
        # raw_index_map might be [(0, 'ch0', 'EMG'), (1, 'ch1', 'EOG')]
        num_channels = len(self.raw_index_map)
        
        print(f"[Router] Configuring pipeline for {num_channels} channels...")
        
        for i in range(num_channels):
            # Check config for this channel index (ch0, ch1)
            ch_key = f"ch{i}"
            mapped_type = "RAW" # default if not in config
            
            if ch_key in mapping_cfg:
                cinfo = mapping_cfg[ch_key]
                if cinfo.get("enabled", True):
                    mapped_type = cinfo.get("sensor", "RAW").upper()
            
            self.channel_mapping[i] = mapped_type
            
            # Instantiate processor
            if mapped_type == "EMG":
                self.channel_processors[i] = EMGFilterProcessor(self.config, self.sr)
            elif mapped_type == "EOG":
                self.channel_processors[i] = EOGFilterProcessor(self.config, self.sr)
            elif mapped_type == "EEG":
                self.channel_processors[i] = EEGFilterProcessor(self.config, self.sr)
            else:
                self.channel_processors[i] = None # Pass-through
            
            # Log
            proc_status = "Pass-through" if self.channel_processors[i] is None else f"{mapped_type} Processor"
            print(f"  [{i}] -> {mapped_type} ({proc_status})")

        # 2. Create Unified LSL Outlet
        if LSL_AVAILABLE and num_channels > 0:
            info = pylsl.StreamInfo(
                name=PROCESSED_STREAM_NAME,
                type="BioSignals",
                channel_count=num_channels,
                nominal_srate=self.sr,
                channel_format='float32',
                source_id="BioSignals-Processed-Source"
            )
            
            # Add metadata
            chans = info.desc().append_child("channels")
            for i in range(num_channels):
                ctype = self.channel_mapping.get(i, "RAW")
                ch = chans.append_child("channel")
                ch.append_child_value("label", f"{ctype}_{i}")
                ch.append_child_value("type", ctype)
            
            self.outlet = pylsl.StreamOutlet(info)
            print(f"[Router] Created outlet '{PROCESSED_STREAM_NAME}'")

    def run(self):
        if not LSL_AVAILABLE:
            return
            
        print("[Router] Waiting for stream...")
        while self.running and not self.resolve_raw_stream():
            time.sleep(1.0)
            
        print("[Router] Processing loop started.")
        self.running = True
        
        while self.running:
            try:
                # 1. Pull
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                if sample is None:
                    continue
                
                # 2. Process
                out_sample = []
                for i, val in enumerate(sample):
                    proc = self.channel_processors.get(i)
                    if proc:
                        try:
                            val = proc.process_sample(float(val))
                        except Exception as e:
                            # print(f"Proc error ch{i}: {e}") # noisy
                            pass
                    out_sample.append(val)
                
                # 3. Push
                if self.outlet:
                    self.outlet.push_sample(out_sample, ts)
                    
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                print(f"[Router] Loop error: {e}")
                # Reconnect logic could go here
                if self.inlet is None: # simplified
                     self.resolve_raw_stream()
                time.sleep(0.1)

    def stop(self):
        self.running = False
        print("[Router] Stopped.")

if __name__ == "__main__":
    router = FilterRouter()
    router.running = True
    try:
        router.run()
    except KeyboardInterrupt:
        router.stop()
