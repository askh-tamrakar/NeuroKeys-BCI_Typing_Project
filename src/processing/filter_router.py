"""

Usage:
    python -m src.processing.filter_router_modified

"""

from pathlib import Path
import time
import json
import threading
import hashlib
import sys
import os
from typing import List, Tuple, Dict, Optional

# UTF-8 encoding for standard output to avoid UnicodeEncodeError in some terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

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
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from src.processing.emg_processor import EMGFilterProcessor
    from src.processing.eog_processor import EOGFilterProcessor
    from src.processing.eeg_processor import EEGFilterProcessor

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
FILTER_CONFIG_PATH = PROJECT_ROOT / "config" / "filter_config.json"
RAW_STREAM_NAME = "BioSignals-Raw-uV"
PROCESSED_STREAM_NAME = "BioSignals-Processed"
RELOAD_INTERVAL = 2.0
DEFAULT_SR = 512


def load_config() -> dict:
    """Load config from sensor_config.json and filter_config.json with safe fallback defaults."""
    defaults = {
        "sampling_rate": DEFAULT_SR,
        "channel_mapping": {
            "ch0": {"sensor": "EMG", "enabled": True},
            "ch1": {"sensor": "EOG", "enabled": True}
        },
        "filters": {
            "EMG": {"cutoff": 70.0, "order": 4, "notch_enabled": False, "notch_freq": 50, "bandpass_enabled": False, "bandpass_low": 20, "bandpass_high": 250, "envelope_enabled": True, "envelope_cutoff": 10.0, "envelope_order": 4},
            "EOG": {"cutoff": 10.0, "order": 4},
            "EEG": {
                "filters": [
                    {"type": "notch", "freq": 50.0, "Q": 30},
                    {"type": "bandpass", "low": 0.5, "high": 45.0, "order": 4}
                ]
            }
        }
    }
    
    cfg = defaults.copy()

    # 1. Load Sensor Config
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                sensor_cfg = json.load(f)
            
            if "sampling_rate" in sensor_cfg:
                cfg["sampling_rate"] = sensor_cfg["sampling_rate"]
            if "channel_mapping" in sensor_cfg:
                cfg["channel_mapping"] = sensor_cfg["channel_mapping"]
        except Exception as e:
            print(f"[Router] Failed to load sensor config ({CONFIG_PATH}): {e} — using defaults")

    # 2. Load Filter Config
    if FILTER_CONFIG_PATH.exists():
        try:
            with open(FILTER_CONFIG_PATH, "r") as f:
                filter_cfg = json.load(f)
            
            if "filters" in filter_cfg:
                cfg["filters"] = filter_cfg["filters"]
        except Exception as e:
            print(f"[Router] Failed to load filter config ({FILTER_CONFIG_PATH}): {e} — using defaults")
    else:
        print(f"[Router] Filter config not found ({FILTER_CONFIG_PATH}) — using defaults")

    return cfg


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
            return idx_map
    except Exception as e:
        print(f"[Router] ⚠️ XML parsing warning: {e}")
    
    # Fallback
    try:
        ch_count = int(info.channel_count())
        return [(i, f"ch{i}", f"ch{i}") for i in range(ch_count)]
    except:
        return []


class FilterRouter:
    """Main filter router class - processes multi-channel biomedical signals."""
    
    def __init__(self):
        self.config = load_config()
        self.sr = int(self.config.get("sampling_rate", DEFAULT_SR))
        self.inlet = None
        self.outlet = None
        self.raw_index_map: List[Tuple[int, str, str]] = []
        self.channel_processors: Dict[int, object] = {}
        self.channel_mapping: Dict[int, Dict] = {}
        self.num_channels = 0
        self.running = False
        self._config_lock = threading.Lock()
        self._start_config_watcher()
    
    def _start_config_watcher(self):
        """Start background thread to monitor config changes."""
        t = threading.Thread(target=self._config_watcher, daemon=True)
        t.start()
    
    def _config_watcher(self):
        """Background thread: Monitor config file for changes."""
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
                    
                    # 1. Channel mapping changed? Reconfigure pipeline
                    if map_hash != last_map_hash:
                        print("[Router] [CONFIG] Channel mapping changed - reconfiguring pipeline...")
                        self._configure_pipeline()
                        last_map_hash = map_hash
                        last_cfg_hash = cfg_hash
                    
                    # 2. Only filter params changed? Update processors
                    elif cfg_hash != last_cfg_hash:
                        print("[Router] [CONFIG] Filter parameters updated - updating processors...")
                        for p in self.channel_processors.values():
                            if p and hasattr(p, 'update_config'):
                                p.update_config(self.config, self.sr)
                        last_cfg_hash = cfg_hash
                
                time.sleep(RELOAD_INTERVAL)
            
            except Exception as e:
                print(f"[Router] ⚠️ Config watcher error: {e}")
                time.sleep(RELOAD_INTERVAL)
    
    def resolve_raw_stream(self, timeout: float = 3.0) -> bool:
        """Resolve and connect to raw LSL stream."""
        if not LSL_AVAILABLE:
            print("[Router] ❌ pylsl not installed.")
            return False
        
        try:
            print("[Router] 🔍 Searching for raw LSL stream...")
            streams = pylsl.resolve_streams(wait_time=0.5)
            target = None
            
            # 1. Exact name match
            for s in streams:
                if s.name() == RAW_STREAM_NAME:
                    target = s
                    break
            
            # 2. Heuristic match (contains "raw" or "uv")
            if not target:
                for s in streams:
                    if "raw" in s.name().lower() or "uv" in s.name().lower():
                        target = s
                        break
            
            if target:
                self.inlet = pylsl.StreamInlet(target, max_buflen=1, recover=True)
                self.raw_index_map = parse_channel_map(self.inlet.info())
                print(f"[Router] [OK] Connected to raw stream: {target.name()}")
                print(f"[Router]    Channels: {len(self.raw_index_map)} @ {target.nominal_srate()} Hz")
                self._configure_pipeline()
                return True
            
            print("[Router] [ERROR] Could not find raw stream")
            return False
        
        except Exception as e:
            print(f"[Router] [ERROR] Resolution error: {e}")
            return False
    
    def _configure_pipeline(self):
        """
        Configure processing pipeline based on current config.
        
        This is the IMPROVED version that handles all cases:
        - Both channels different sensors (EMG + EOG) ✅
        - Both channels same sensor (EMG + EMG) ✅
        - Disabled channels (pass-through with metadata) ✅
        - Missing channel config (defaults applied) ✅
        """
        
        # Clean up old configuration
        self.channel_processors = {}
        self.channel_mapping = {}
        
        # ========== IMPROVED: Explicitly close old outlet ==========
        if self.outlet is not None:
            print("[Router] 🔄 Closing old LSL outlet...")
            del self.outlet
            self.outlet = None
            time.sleep(0.2)  # Small delay to let LSL unregister from network
        
        mapping_cfg = self.config.get("channel_mapping", {})
        num_channels = len(self.raw_index_map)
        
        if num_channels == 0:
            print("[Router] [WARNING] No channels found in raw stream!")
            return
        
        self.num_channels = num_channels
        print(f"[Router] 📍 Configuring pipeline for {num_channels} channels...")
        
        # ========== IMPROVED: Handle all mapping cases ==========
        try:
            for i in range(num_channels):
                ch_key = f"ch{i}"
                
                # CASE 1: Channel in config
                if ch_key in mapping_cfg:
                    cinfo = mapping_cfg[ch_key]
                    enabled = cinfo.get("enabled", True)
                    sensor_type = cinfo.get("sensor", "UNKNOWN").upper()
                    
                    # CASE 2: Channel disabled
                    if not enabled:
                        print(f" [{i}] → {sensor_type} (DISABLED - Pass-through)")
                        self.channel_mapping[i] = {
                            "sensor": sensor_type,
                            "enabled": False,
                            "label": f"RAW_{i}",
                            "processor": None
                        }
                        self.channel_processors[i] = None
                        continue
                    
                    # CASE 3: Channel enabled with processor
                    self.channel_mapping[i] = {
                        "sensor": sensor_type,
                        "enabled": True,
                        "label": f"{sensor_type}_{i}",
                        "processor": sensor_type
                    }
                    
                    # Create processor instance for this channel
                    if sensor_type == "EMG":
                        self.channel_processors[i] = EMGFilterProcessor(self.config, self.sr, channel_key=ch_key)
                        print(f" [{i}] → EMG (EMG Processor) | Key: {ch_key}")
                    
                    elif sensor_type == "EOG":
                        self.channel_processors[i] = EOGFilterProcessor(self.config, self.sr, channel_key=ch_key)
                        print(f" [{i}] → EOG (EOG Processor) | Key: {ch_key}")
                    
                    elif sensor_type == "EEG":
                        self.channel_processors[i] = EEGFilterProcessor(self.config, self.sr, channel_key=ch_key)
                        print(f" [{i}] → EEG (EEG Processor) | Key: {ch_key}")
                    
                    else:
                        # Unknown type - pass-through
                        self.channel_processors[i] = None
                        print(f" [{i}] → {sensor_type} (Unknown - Pass-through)")
                
                # CASE 4: Channel NOT in config - Apply default
                else:
                    print(f" [{i}] → UNMAPPED (applying default: pass-through)")
                    self.channel_mapping[i] = {
                        "sensor": "UNMAPPED",
                        "enabled": True,
                        "label": f"RAW_{i}",
                        "processor": None
                    }
                    self.channel_processors[i] = None
        except Exception as e:
            print(f"[Router] [ERROR] Pipeline configuration error: {e}")
            return
        
        # ========== Create Unified LSL Outlet ==========
        
        if LSL_AVAILABLE and num_channels > 0:
            try:
                info = pylsl.StreamInfo(
                    name=PROCESSED_STREAM_NAME,
                    type="BioSignals",
                    channel_count=num_channels,
                    nominal_srate=self.sr,
                    channel_format='float32',
                    source_id="BioSignals-Processed-Source"
                )
                
                # Add channel descriptions
                chns = info.desc().append_child("channels")
                for i in range(num_channels):
                    ch_info = self.channel_mapping.get(i, {})
                    ch = chns.append_child("channel")
                    ch.append_child_value("label", ch_info.get("label", f"ch{i}"))
                    ch.append_child_value("type", ch_info.get("sensor", "UNKNOWN"))
                    ch.append_child_value("enabled", "true" if ch_info.get("enabled", True) else "false")
                
                self.outlet = pylsl.StreamOutlet(info)
                print(f"[Router] [OUTLET] Publishing unified stream: {PROCESSED_STREAM_NAME}")
                print(f"[Router]    Channels: {num_channels} @ {self.sr} Hz")
                print(f"[Router] [OK] Pipeline configured successfully")
                
            except Exception as e:
                print(f"[Router] [ERROR] Error creating outlet: {e}")
    
    def run(self):
        """Main processing loop."""
        if not self.inlet or not self.outlet:
            print("[Router] [ERROR] Error: Inlet or outlet not ready!")
            return
        
        self.running = True
        print("[Router] [START] Starting processing loop...")
        print("[Router] Press Ctrl+C to stop\n")
        
        sample_count = 0
        error_count = 0
        
        try:
            while self.running:
                # Pull raw sample
                raw_sample, ts = self.inlet.pull_sample(timeout=1.0)
                
                if raw_sample is not None and len(raw_sample) == self.num_channels:
                    try:
                        with self._config_lock:
                            # Process each channel through its processor
                            processed_sample = []
                            
                            for ch_idx in range(self.num_channels):
                                raw_val = raw_sample[ch_idx]
                                processor = self.channel_processors.get(ch_idx)
                                
                                if processor:
                                    # ✅ Channel has processor - apply it
                                    filtered_val = processor.process_sample(raw_val)
                                else:
                                    # ✅ Channel disabled or unmapped - pass through
                                    print(f"[Router] [WARNING] Channel {ch_idx} disabled or unmapped - passing through")
                                    filtered_val = raw_val
                                
                                processed_sample.append(filtered_val)
                            
                            # ✅ Push ALL channels in single sample with same timestamp
                            self.outlet.push_sample(processed_sample, ts)
                            sample_count += 1
                            
                            # Log progress every 512 samples (1 second at 512 Hz)
                            if sample_count % 512 == 0:
                                print(f"[Router] ✅ {sample_count} samples processed")
                    
                    except Exception as e:
                        error_count += 1
                        if error_count <= 5:  # Only log first 5 errors
                            print(f"[Router] [WARNING] Error processing sample: {e}")
                        if error_count == 6:
                            print(f"[Router] [WARNING] (suppressing further error messages)")
        
        except KeyboardInterrupt:
            print("\n[Router] [STOP] Stopping...")
        
        finally:
            self.running = False
            print(f"[Router] 📊 Total samples processed: {sample_count}")
            
            if self.inlet:
                try:
                    self.inlet.close_stream()
                except:
                    pass
            
            if self.outlet:
                try:
                    # StreamOutlet is closed on destruction in pylsl
                    del self.outlet
                    self.outlet = None
                except:
                    pass
            
            print("[Router] [OK] Cleanup complete")
    
    def stop(self):
        """Stop the processing loop."""
        self.running = False


def main():
    """Main entry point."""
    print("=" * 60)
    print("  🧬 BioSignals Filter Router")
    print("  Processing multi-channel biosignals with independent filtering")
    print("=" * 60)
    print()
    
    router = FilterRouter()
    
    if router.resolve_raw_stream(timeout=3.0):
        print("[Router] ✅ Raw stream resolved, starting processor...\n")
        router.run()
    else:
        print("[Router] ❌ Could not resolve raw stream")
        print("[Router] Make sure acquisition_app is running first")


if __name__ == "__main__":
    main()
