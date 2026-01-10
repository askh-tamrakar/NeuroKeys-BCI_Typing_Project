"""
Feature Router
- Listens to: BioSignals-Processed (LSL)
- Routing: Based on channel_mapping
- Processing: Runs Extractors (EOG -> Blink)
- Output: BioSignals-Events (LSL Markers)
"""

import sys
import os

# UTF-8 encoding for standard output to avoid UnicodeEncodeError in some terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import time
import json
import threading
import hashlib
from pathlib import Path
try:
    import pylsl
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False

from .extractors.blink_extractor import BlinkExtractor
from .detectors.blink_detector import BlinkDetector
from .extractors.rps_extractor import RPSExtractor
from .detectors.rps_detector import RPSDetector
from .extractors.trigger_extractor import EEGExtractor
from .detectors.trigger_detector import EEGDetector

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"

INPUT_STREAM_NAME = "BioSignals-Processed"
OUTPUT_STREAM_NAME = "BioSignals-Events"

try:
    from ..utils.config import config_manager
except ImportError:
    # Try relative path if running as script
    sys.path.append(str(PROJECT_ROOT / "src"))
    from utils.config import config_manager

def load_config():
    # Use the facade to get merged config (Sensor + Features)
    # This ensures Detectors find their 'features' key
    return config_manager.get_all_configs()

class FeatureRouter:
    def __init__(self):
        self.config = load_config()
        self.sr = self.config.get("sampling_rate", 512)
        
        self.inlet = None
        self.outlet = None
        self.running = False
        
        # Map channel_index -> (Extractor Instance, Detector Instance)
        self.pipeline = {} 
        self.channel_labels = []
        
        # State tracking
        self.sample_counter = 0
        self.detection_active = False # Start disabled/passive
        self.last_event_state = {} # Key: ch_idx_type -> event_name

        self._config_lock = threading.Lock()
        self._start_config_watcher()

    def get_config_hash(self, cfg: dict) -> str:
        try:
            return hashlib.md5(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
        except:
            return ""

    def _start_config_watcher(self):
        t = threading.Thread(target=self._config_watcher, daemon=True)
        t.start()
        
    def _config_watcher(self):
        """Monitor config file for changes and update pipeline."""
        last_feat_hash = ""
        last_map_hash = ""
        
        while True:
            try:
                new_cfg = load_config()
                feat_hash = self.get_config_hash(new_cfg.get("features", {}))
                map_hash = self.get_config_hash(new_cfg.get("channel_mapping", {}))
                
                with self._config_lock:
                    # 1. Mapping changed? Reconfigure everything
                    if map_hash != last_map_hash and last_map_hash != "":
                        print("[FeatureRouter] [CONFIG] Channel mapping changed - reconfiguring...")
                        self.config = new_cfg
                        self.configure_pipeline()
                        last_map_hash = map_hash
                        last_feat_hash = feat_hash 
                    
                    # 2. Features changed? Update existing components
                    elif feat_hash != last_feat_hash:
                        if last_feat_hash != "": 
                             print("[FeatureRouter] [CONFIG] Features updated - updating detectors...")
                        
                        self.config = new_cfg
                        for ch_idx, (extractor, detector, _) in self.pipeline.items():
                            if hasattr(extractor, 'update_config'):
                                extractor.update_config(self.config)
                            if hasattr(detector, 'update_config'):
                                detector.update_config(self.config)
                        
                        last_feat_hash = feat_hash
                        if last_map_hash == "": last_map_hash = map_hash
                
                time.sleep(2.0)
            except Exception as e:
                print(f"[FeatureRouter] ⚠️ Config watcher error: {e}")
                time.sleep(2.0)

    def resolve_stream(self):
        if not LSL_AVAILABLE:
            print("[FeatureRouter] ❌ pylsl not installed")
            return False

        print(f"[FeatureRouter] [SEARCH] Searching for {INPUT_STREAM_NAME}...")
        streams = pylsl.resolve_byprop('name', INPUT_STREAM_NAME, timeout=5.0)
        if not streams:
            print("[FeatureRouter] [ERROR] Stream not found")
            return False
            
        self.inlet = pylsl.StreamInlet(streams[0])
        info = self.inlet.info()
        self.sr = int(info.nominal_srate())
        self.parse_channels(info)
        
        print(f"[FeatureRouter] [OK] Connected to {INPUT_STREAM_NAME} ({len(self.channel_labels)} ch @ {self.sr} Hz)")
        
        # Create Event Outlet
        self.create_outlet()
        
        # Initialize Extractors based on mapping
        self.configure_pipeline()
        
        return True

    def create_outlet(self):
        info = pylsl.StreamInfo(OUTPUT_STREAM_NAME, 'Markers', 1, 0, 'string', 'BioEvents123')
        self.outlet = pylsl.StreamOutlet(info)
        print(f"[FeatureRouter] [OUTLET] Created Event Outlet: {OUTPUT_STREAM_NAME}")

    def parse_channels(self, info):
        # Simplistic parsing - relying on config mostly, but let's see what stream says
        # Ideally, reading the layout from the StreamInfo desc if available
        # But we will rely on strict index mapping from config for now as requested
        self.num_channels = info.channel_count()
        # For logging
        self.channel_labels = [f"ch{i}" for i in range(self.num_channels)]

    def configure_pipeline(self):
        """
        Instantiate extractors for channels based on config.
        """
        self.extractors = {}
        self.pipeline = {} # Clear existing pipeline!
        mapping = self.config.get("channel_mapping", {})
        
        print(f"[FeatureRouter] [CONFIG] Configuring features for {self.num_channels} channels...")
        
        for i in range(self.num_channels):
            ch_key = f"ch{i}"
            if ch_key in mapping:
                info = mapping[ch_key]
                if not info.get("enabled", True):
                    continue
                    
                sensor = info.get("sensor", "UNKNOWN")
                
                if sensor == "EOG":
                    print(f" [{i}] -> EOG Blink Pipeline (Extractor + Detector)")
                    extractor = BlinkExtractor(i, self.config, self.sr)
                    detector = BlinkDetector(self.config)
                    self.pipeline[i] = (extractor, detector, "EOG")
                elif sensor == "EMG":
                    print(f" [{i}] -> EMG RPS Pipeline (Extractor + Detector)")
                    extractor = RPSExtractor(i, self.config, self.sr)
                    detector = RPSDetector(self.config)
                    self.pipeline[i] = (extractor, detector, "EMG")
                elif sensor == "EEG":
                    print(f" [{i}] -> EEG Pipeline (Mean Band Power)")
                    extractor = EEGExtractor(i, self.config, self.sr)
                    detector = EEGDetector(self.config)
                    self.pipeline[i] = (extractor, detector, "EEG")

    def run(self):
        self.running = True
        print("[FeatureRouter] [START] Loop started")
        
        last_blink_time = 0.0
        
        while self.running:
            try:
                # Pull chunk for better performance features like timestamp precision
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                
                if sample:
<<<<<<< HEAD
                    current_time = time.time()
                    
                    # 1. Processing Loop
                    # We need to process all channels first, then handle events?
                    # Actually, processing is sequential here.
                    # Ideally, if EOG is Ch1 and EMG is Ch0, Ch0 computes first.
                    # If Ch0 detects Rock (Artifact), we verify it.
                    # But we don't know if a blink is coming in Ch1 yet!
                    # BUT, usually Blinks are detected at the END of the wave (post-peak).
                    # The artifact on EMG (spike) is simultaneous.
                    # This simple inhibition only blocks EMG *after* a blink is detected.
                    # Better than nothing: Prevents "Double triggering" or trailing artifacts.
                    
=======
                    # Check detection state (cached for performance?)
                    # For now we check every time; file I/O on tmpfs/OS cache is fast enough for 512Hz?
                    # Maybe throttle check to 5Hz (every ~100 samples) or just rely on OS.
                    # Let's add simple throttling to be safe.
                    self.sample_counter += 1
                    if self.sample_counter % 50 == 0: # Check every ~0.1s
                         self.detection_active = config_manager.get_detection_state()

                    # Route to pipeline
>>>>>>> rps-implement
                    for ch_idx, val in enumerate(sample):
                        if ch_idx in self.pipeline:
                            extractor, detector, sensor_type = self.pipeline[ch_idx]
                            features = extractor.process(val)
                            
                            if features:
                                # Feature Extractor produced a window -> Run Detector
                                detection_result = detector.detect(features)
                                
                                if detection_result:
                                    # --- Global Inhibition Logic ---
                                    # Update Blink Time
                                    if sensor_type == "EOG" and "Blink" in detection_result:
                                        last_blink_time = current_time
                                        # Pass through the blink event
                                    
                                    # Block EMG if recent blink
                                    if sensor_type == "EMG":
                                        # If blink happened in last 600ms, ignore EMG
                                        if current_time - last_blink_time < 0.6:
                                            print(f"[FeatureRouter] 🛡️ Inhibited EMG {detection_result} (Recent Blink)")
                                            continue
                                    # --------------------------------

                                    # Determine event name
                                    if sensor_type == "EOG":
                                        event_name = detection_result # SingleBlink/DoubleBlink
                                    elif sensor_type == "EMG":
                                        # Only emit RPS events if game is active!
                                        if not self.detection_active:
                                            # If not active, we still get 'Rest' or gestures, but we ignore them
                                            # UNLESS it's something critical? No.
                                            continue
                                        event_name = detection_result 
                                    elif sensor_type == "EEG":
                                        event_name = detection_result 
                                    else:
                                        event_name = "UNKNOWN_EVENT"

                                    # De-duplication for continuous states (like Rest)
                                    # Make a unique key for channel+event
                                    state_key = f"{ch_idx}_{sensor_type}"
                                    last_event = self.last_event_state.get(state_key)

                                    # If it's a "state" type event (like Rest), dedup.
                                    # Blinks are discrete events, so always emit.
                                    is_discrete = sensor_type == "EOG" 
                                    
                                    if not is_discrete and event_name == last_event:
                                         # Skip duplicate log/emit
                                         continue
                                    
                                    self.last_event_state[state_key] = event_name

                                    # emit event
                                    event_data = {
                                        "event": event_name,
                                        "channel": f"ch{ch_idx}",
                                        "timestamp": ts,
                                        "features": features
                                    }
                                    formatted_event = json.dumps(event_data)
<<<<<<< HEAD
=======
                                    print(f"[Feature Router] [EVENT] {event_name} created")
>>>>>>> rps-implement
                                    self.outlet.push_sample([formatted_event])

            except Exception as e:
                print(f"[FeatureRouter] [WARNING] Error: {e}")
                time.sleep(0.1)

if __name__ == "__main__":
    router = FeatureRouter()
    if router.resolve_stream():
        router.run()


