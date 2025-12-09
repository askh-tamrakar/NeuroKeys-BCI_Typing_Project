"""
src/processing/filter_router.py

IMPROVED FILTER ROUTER with Mapping Updates & Processor Integration

Features:
- Monitors channel mapping changes in config (updates in real-time)
- Spawns EMG/EOG/EEG processor threads
- Routes channels to appropriate processors
- Aggregates filtered outputs
- Broadcasts mapping + filtered data to web clients
- Coordinates all bio-signal processing

Architecture:
    Raw Stream → Filter Router → Spawns Processor Threads → Aggregates → Web Broadcast
                                ↓
                    EMG/EOG/EEG processors (threaded)
"""

from pathlib import Path
import time
import json
import threading
import queue
from typing import List, Tuple, Dict, Optional
import hashlib

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

# Resolve project root: src/processing -> src -> root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
RAW_STREAM_NAME = "BioSignals-Raw-uV"
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
    """
    Parse channel metadata from LSL StreamInfo.
    Returns: [(index, label, type_str), ...]
    """
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
                    if lab:
                        label = lab
                    if typ:
                        type_str = typ
                except:
                    pass
                idx_map.append((i, label, type_str))
                ch = ch.next_sibling()
                i += 1
        
        if idx_map:
            print(f"[Router] Parsed {len(idx_map)} channels from XML metadata")
            return idx_map
    except Exception as e:
        print(f"[Router] XML parsing warning: {e}")
    
    # FALLBACK: Use config-based mapping
    try:
        ch_count = int(info.channel_count())
        print(f"[Router] Using config-based channel mapping (ch_count={ch_count})")
        return [(i, f"ch{i}", f"ch{i}") for i in range(ch_count)]
    except:
        return idx_map


class ProcessorThread:
    """Wrapper for running a processor as a thread."""
    
    def __init__(self, proc_type: str, channel_indices: List[int], sr: int, config: dict):
        self.proc_type = proc_type  # "EMG", "EOG", "EEG"
        self.channel_indices = list(channel_indices)
        self.sr = sr
        self.config = config
        self.running = False
        self.thread = None
        self.processor_obj = None
        
    def start(self):
        """Start processor thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print(f"[Router] Started {self.proc_type} processor thread for channels {self.channel_indices}")
    
    def _run(self):
        """Run the processor in thread context."""
        try:
            # Dynamically import and instantiate processor
            if self.proc_type == "EMG":
                try:
                    from .emg_processor import EMGFilterProcessor
                    self.processor_obj = EMGFilterProcessor()
                    if self.processor_obj:
                        self.processor_obj.process()
                except ImportError:
                    print(f"[Router] Could not import EMGFilterProcessor - running without processor")
                    return
                    
            elif self.proc_type == "EOG":
                try:
                    from .eog_processor import EOGFilterProcessor
                    self.processor_obj = EOGFilterProcessor()
                    if self.processor_obj:
                        self.processor_obj.process()
                except ImportError:
                    print(f"[Router] Could not import EOGFilterProcessor - running without processor")
                    return
                    
            elif self.proc_type == "EEG":
                try:
                    from .eeg_processor import EEGFilterProcessor
                    self.processor_obj = EEGFilterProcessor()
                    if self.processor_obj:
                        self.processor_obj.process()
                except ImportError:
                    print(f"[Router] Could not import EEGFilterProcessor - running without processor")
                    return
            else:
                print(f"[Router] Unknown processor type: {self.proc_type}")
                return
                
        except Exception as e:
            print(f"[Router] {self.proc_type} processor error: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop processor thread."""
        self.running = False
        if self.processor_obj:
            try:
                self.processor_obj.stop()
            except:
                pass


class FilterRouter:
    def __init__(self):
        self.config = load_config()
        self.sr = int(self.config.get("sampling_rate", DEFAULT_SR))
        self.inlet = None
        self.index_map: List[Tuple[int, str, str]] = []
        self.channel_mapping: Dict[str, Dict] = {}  # {ch_index: {type, label, processor_ref}}
        self.processor_threads: Dict[str, ProcessorThread] = {}  # {type: thread}
        self.running = False
        self._config_lock = threading.Lock()
        self._last_mapping_hash = ""
        self._start_config_watcher()
    
    def _start_config_watcher(self):
        """Start config watcher thread."""
        t = threading.Thread(target=self._config_watcher, daemon=True)
        t.start()
    
    def _config_watcher(self):
        """Monitor config and channel mapping for changes."""
        last_cfg_hash = ""
        last_map_hash = ""
        
        while True:
            try:
                new_cfg = load_config()
                cfg_hash = get_config_hash(new_cfg)
                
                with self._config_lock:
                    self.config = new_cfg
                    self.sr = int(self.config.get("sampling_rate", self.sr))
                    
                    # Detect config changes (filters)
                    if cfg_hash != last_cfg_hash:
                        print("[Router] ⚠️ Config changed - filter parameters updated")
                        last_cfg_hash = cfg_hash
                    
                    # Detect mapping changes (channels)
                    mapping_data = self.config.get("channel_mapping", {})
                    map_hash = get_config_hash(mapping_data)
                    
                    if map_hash != last_map_hash:
                        print("[Router] 🔄 Channel mapping changed - reconfiguring...")
                        self._configure_categories()
                        last_map_hash = map_hash
                        self._last_mapping_hash = map_hash
                
                time.sleep(RELOAD_INTERVAL)
            except Exception as e:
                print(f"[Router] config watcher error: {e}")
                time.sleep(RELOAD_INTERVAL)
    
    def resolve_raw_stream(self, timeout: float = 3.0) -> bool:
        """Discover and connect to raw bio-signal stream."""
        if not LSL_AVAILABLE:
            print("[Router] pylsl not installed — cannot resolve raw stream")
            return False
        
        try:
            try:
                all_streams = pylsl.resolve_streams()
            except:
                try:
                    all_streams = pylsl.lsl_resolve_all()
                except:
                    all_streams = []
            
            available = []
            for s in all_streams:
                try:
                    sname = s.name() if callable(getattr(s, "name", None)) else ""
                except:
                    try:
                        sname = getattr(s, "name", lambda: "")()
                    except:
                        sname = str(s)
                available.append((sname, s))
            
            if not available:
                print("[Router] No LSL streams discovered. Retrying later.")
                return False
            
            # Try exact name match first
            exact_matches = [s for (n, s) in available if n == RAW_STREAM_NAME]
            if exact_matches:
                self.inlet = pylsl.StreamInlet(exact_matches[0], max_buflen=1, recover=True)
                self.index_map = parse_channel_map(self.inlet.info())
                print(f"[Router] Resolved (exact) {RAW_STREAM_NAME}")
                self._configure_categories()
                return True
            
            # Heuristic fallback
            lowered = [(n.lower(), s) for (n, s) in available]
            heur_matches = [s for (n, s) in lowered if "raw" in n or "uv" in n or "biosignals" in n]
            
            if heur_matches:
                self.inlet = pylsl.StreamInlet(heur_matches[0], max_buflen=1, recover=True)
                self.index_map = parse_channel_map(self.inlet.info())
                print(f"[Router] Resolved (heuristic) raw stream")
                self._configure_categories()
                return True
            
            print("[Router] No matching raw stream found.")
            return False
        except Exception as e:
            print(f"[Router] resolve_raw_stream error: {e}")
            return False
    
    def _configure_categories(self):
        """Configure which channels go to which processor based on mapping."""
        old_mapping = dict(self.channel_mapping)
        self.channel_mapping = {}
        
        mapping_cfg = self.config.get("channel_mapping", {})
        
        # Build mapping from config
        for ch_key, ch_info in mapping_cfg.items():
            try:
                ch_idx = int(ch_key.replace("ch", ""))
                sensor_type = ch_info.get("sensor", "EMG").upper()
                enabled = ch_info.get("enabled", True)
                
                if enabled and ch_idx < len(self.index_map):
                    self.channel_mapping[ch_idx] = {
                        "type": sensor_type,
                        "label": f"{sensor_type}_{ch_idx}",
                        "enabled": True
                    }
                    print(f"[Router] Mapped ch{ch_idx} → {sensor_type}")
            except:
                pass
        
        # Spawn processor threads if needed
        self._spawn_processors()
        
        if old_mapping != self.channel_mapping:
            print(f"[Router] 📊 Mapping changed: {self.channel_mapping}")
        else:
            print(f"[Router] Channel mapping: {self.channel_mapping}")
    
    def _spawn_processors(self):
        """Spawn processor threads for each sensor type."""
        processor_types = set(ch["type"] for ch in self.channel_mapping.values())
        
        for ptype in processor_types:
            if ptype not in self.processor_threads:
                # Get channel indices for this type
                channel_indices = [
                    ch_idx for ch_idx, info in self.channel_mapping.items()
                    if info["type"] == ptype
                ]
                
                # Create and start processor thread
                proc = ProcessorThread(ptype, channel_indices, self.sr, self.config)
                proc.start()
                self.processor_threads[ptype] = proc
                print(f"[Router] Spawned {ptype} processor for channels {channel_indices}")
        
        # Stop processors for types no longer needed
        for ptype in list(self.processor_threads.keys()):
            if ptype not in processor_types:
                self.processor_threads[ptype].stop()
                del self.processor_threads[ptype]
                print(f"[Router] Stopped {ptype} processor")
    
    def run(self):
        """Main processing loop."""
        if not LSL_AVAILABLE:
            print("[Router] pylsl not installed — router cannot run.")
            return
        
        self.running = True
        print("[Router] Starting: resolving raw stream...")
        
        while self.running and not self.resolve_raw_stream(timeout=2.0):
            time.sleep(0.5)
        
        print("[Router] Entering processing loop")
        
        while self.running:
            try:
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                if sample is None:
                    continue
                
                # Log mapping and data for web display
                mapping_info = self.get_mapping()
                
                # TODO: Aggregate processor outputs and broadcast to web
                # Current flow: Raw → Processors → Filter Router → Web
                
            except KeyboardInterrupt:
                print("[Router] KeyboardInterrupt received. Stopping.")
                self.running = False
            except Exception as e:
                print(f"[Router] processing loop exception: {e}")
                try:
                    if self.inlet is None:
                        self.resolve_raw_stream(timeout=2.0)
                except:
                    pass
                time.sleep(0.05)
    
    def stop(self):
        """Stop router and all processors."""
        self.running = False
        for proc in self.processor_threads.values():
            proc.stop()
        print("[Router] Router stopped")
    
    def get_mapping(self) -> Dict:
        """Get current channel mapping for web display."""
        return {
            "mapping": self.channel_mapping,
            "sample_rate": self.sr,
            "timestamp": time.time(),
            "config_hash": self._last_mapping_hash
        }


if __name__ == "__main__":
    router = FilterRouter()
    try:
        router.run()
    except KeyboardInterrupt:
        router.stop()
        print("Exited filter_router")
