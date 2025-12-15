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

from .extractors.eog import EOGExtractor

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
        
        # Map channel_index -> Extractor Instance
        self.extractors = {} 
        self.channel_labels = []

    def resolve_stream(self):
        if not LSL_AVAILABLE:
            print("[FeatureRouter] ❌ pylsl not installed")
            return False

        print(f"[FeatureRouter] 🔍 Searching for {INPUT_STREAM_NAME}...")
        streams = pylsl.resolve_stream('name', INPUT_STREAM_NAME)
        if not streams:
            print("[FeatureRouter] ❌ Stream not found")
            return False
            
        self.inlet = pylsl.StreamInlet(streams[0])
        info = self.inlet.info()
        self.sr = int(info.nominal_srate())
        self.parse_channels(info)
        
        print(f"[FeatureRouter] ✅ Connected to {INPUT_STREAM_NAME} ({len(self.channel_labels)} ch @ {self.sr} Hz)")
        
        # Create Event Outlet
        self.create_outlet()
        
        # Initialize Extractors based on mapping
        self.configure_pipeline()
        
        return True

    def create_outlet(self):
        info = pylsl.StreamInfo(OUTPUT_STREAM_NAME, 'Markers', 1, 0, 'string', 'BioEvents123')
        self.outlet = pylsl.StreamOutlet(info)
        print(f"[FeatureRouter] 📤 Created Event Outlet: {OUTPUT_STREAM_NAME}")

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
        
        print(f"[FeatureRouter] ⚙️ Configuring features for {self.num_channels} channels...")
        
        for i in range(self.num_channels):
            ch_key = f"ch{i}"
            if ch_key in mapping:
                info = mapping[ch_key]
                if not info.get("enabled", True):
                    continue
                    
                sensor = info.get("sensor", "UNKNOWN")
                
                if sensor == "EOG":
                    print(f" [{i}] → EOG Extractor (Blink Detection)")
                    self.extractors[i] = EOGExtractor(i, self.config, self.sr)
                # Add EEG/EMG extractors here later

    def run(self):
        self.running = True
        print("[FeatureRouter] ▶️ Loop started")
        
        while self.running:
            try:
                # Pull chunk for better performance? For low latency events, sample by sample is okay or small chunks
                # pull_sample blocks
                sample, ts = self.inlet.pull_sample(timeout=1.0)
                
                if sample:
                    # Route to extractors
                    for ch_idx, val in enumerate(sample):
                        if ch_idx in self.extractors:
                            event = self.extractors[ch_idx].process(val)
                            
                            if event:
                                # emit event
                                formatted_event = json.dumps({
                                    "event": event,
                                    "channel": f"ch{ch_idx}",
                                    "timestamp": ts 
                                })
                                print(f"[FeatureRouter] ⚡ Event: {formatted_event}")
                                self.outlet.push_sample([formatted_event])

            except Exception as e:
                print(f"[FeatureRouter] ⚠️ Error: {e}")
                time.sleep(0.1)

if __name__ == "__main__":
    router = FeatureRouter()
    if router.resolve_stream():
        router.run()
