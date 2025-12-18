"""
Feature Router
- Listens to: BioSignals-Processed (LSL)
- Routing: Based on channel_mapping
- Processing: Runs Extractors (EOG -> Blink)
- Output: BioSignals-Events (LSL Markers)
"""

import time
import json
import threading
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"

INPUT_STREAM_NAME = "BioSignals-Processed"
OUTPUT_STREAM_NAME = "BioSignals-Events"

def load_config():
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

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
                    self.pipeline[i] = (extractor, detector)
                elif sensor == "EMG":
                    print(f" [{i}] -> EMG RPS Pipeline (Extractor + Detector)")
                    extractor = RPSExtractor(i, self.config, self.sr)
                    detector = RPSDetector(self.config)
                    self.pipeline[i] = (extractor, detector)

    def run(self):
        self.running = True
        print("[FeatureRouter] [START] Loop started")
        
        while self.running:
            try:
                # Pull chunk for better performance? For low latency events, sample by sample is okay or small chunks
                # pull_sample blocks
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                
                if sample:
                    # Route to pipeline
                    for ch_idx, val in enumerate(sample):
                        if ch_idx in self.pipeline:
                            extractor, detector = self.pipeline[ch_idx]
                            features = extractor.process(val)
                            
                            if features:
                                is_blink = detector.detect(features)
                                
                                if is_blink:
                                    # emit event
                                    event_data = {
                                        "event": "BLINK",
                                        "channel": f"ch{ch_idx}",
                                        "timestamp": ts,
                                        "features": features
                                    }
                                    formatted_event = json.dumps(event_data)
                                    print(f"[FeatureRouter] [EVENT] {formatted_event}")
                                    self.outlet.push_sample([formatted_event])

            except Exception as e:
                print(f"[FeatureRouter] [WARNING] Error: {e}")
                time.sleep(0.1)

if __name__ == "__main__":
    router = FeatureRouter()
    if router.resolve_stream():
        router.run()
