import sys
import time
import json
import numpy as np
from pathlib import Path
import pylsl

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

from feature.extractors.blink_extractor import BlinkExtractor
from utils.config import config_manager

def main():
    print("="*60)
    print("   BLINK DATA COLLECTOR & THRESHOLD OPTIMIZER")
    print("="*60)
    
    # 1. Load Config
    config = config_manager.get_all_configs()
    sr = config.get("sampling_rate", 512)
    
    # Identify EOG Channel
    mapping = config.get("channel_mapping", {})
    eog_channel = None
    for ch_key, info in mapping.items():
        if info.get("sensor") == "EOG" and info.get("enabled", True):
            eog_channel = int(ch_key.replace("ch", ""))
            print(f"[*] Found EOG Channel: {ch_key} (Index {eog_channel})")
            break
            
    if eog_channel is None:
        print("[!] No enabled EOG channel found in sensor_config.json")
        return

    # 2. Connect LSL
    print("[*] Looking for LSL stream 'BioSignals-Processed'...")
    streams = pylsl.resolve_byprop('name', 'BioSignals-Processed')
    if not streams:
        print("[!] Stream not found. Make sure the main app is running.")
        return
    inlet = pylsl.StreamInlet(streams[0])
    print("[*] Connected to LSL Stream.")

    # 3. Initialize Extractor
    extractor = BlinkExtractor(eog_channel, config, sr)
    
    collected_features = []
    
    # Mode Selection
    print("\n[?] Select recording mode:")
    print("    1. Blink (Positive Class - Detect This)")
    print("    2. Rest (Negative Class - Ignore This)")
    mode_input = input("    Choice (1/2): ").strip()
    
    label = "SingleBlink" if mode_input == "1" else "Rest"
    print(f"\n[*] Mode Selected: {label.upper()}")

    try:
        while True:
            chunk, timestamps = inlet.pull_chunk()
            if chunk:
                for sample in chunk:
                    # Extract EOG channel value
                    val = sample[eog_channel]
                    
                    # Process
                    features = extractor.process(val)
                    
                    if features:
                        print(f" [!] Event Detected ({label}): Dur={features['duration_ms']:.1f}ms Amp={features['amplitude']:.1f}")
                        collected_features.append(features)
                        
    except KeyboardInterrupt:
        print("\n\n[*] Recording stopped.")
        
    if not collected_features:
        print(f"[!] No {label} events collected. Exiting.")
        return

    # 4. Analysis
    print(f"\n[*] Analyzing {len(collected_features)} events for {label}...")
    
    keys = ["amplitude", "duration_ms", "asymmetry", "kurtosis", "peak_count", "rise_time_ms", "fall_time_ms"]
    stats = {}
    
    new_profile = {}
    
    for k in keys:
        values = [f[k] for f in collected_features if k in f]
        if not values: continue
        
        # Calculate stats
        v_min = np.min(values)
        v_max = np.max(values)
        v_mean = np.mean(values)
        v_std = np.std(values)
        
        # Simple Margin Logic (Min - 20%, Max + 20% or +/- 2 StdDev?)
        # StdDev is better for outliers, but Min/Max captures the full recorded range.
        # Let's use robust range: 5th percentile to 95th percentile with 20% margin
        p5 = np.percentile(values, 5)
        p95 = np.percentile(values, 95)
        
        iqr = p95 - p5
        margin = max(iqr * 0.2, abs(p5)*0.1, 1.0) # Ensure some margin
        
        thresh_min = p5 - margin
        thresh_max = p95 + margin
        
        # Sanity caps
        if k == "amplitude" or k == "duration_ms":
            thresh_min = max(thresh_min, 0)
        
        stats[k] = {
            "min": v_min, "max": v_max, "mean": v_mean, 
            "new_range": [round(thresh_min, 4), round(thresh_max, 4)]
        }
        
        new_profile[k] = [round(thresh_min, 4), round(thresh_max, 4)]
        
        print(f"   > {k:12}: Mean={v_mean:7.2f} | Range=[{v_min:7.2f}, {v_max:7.2f}] -> New Threshold: {new_profile[k]}")

    # 5. Save/Update
    print(f"\n[?] Do you want to update 'feature_config.json' [{label}] with these thresholds? (y/n)")
    try:
        choice = input().strip().lower()
    except EOFError:
        choice = 'n'
        
    if choice == 'y':
        current_config = config_manager.get_feature_config()
        if "EOG" not in current_config: current_config["EOG"] = {}
        
        # Update specific profile
        current_config["EOG"][label] = new_profile
        
        # Only auto-tune amp_threshold if we are calibrating Blinks
        if label == "SingleBlink":
            min_amp = stats["amplitude"]["new_range"][0]
            suggested_amp_thresh = max(10, min_amp * 0.5)
            current_config["EOG"]["amp_threshold"] = round(suggested_amp_thresh, 2)
            print(f"   > Updated amp_threshold to {suggested_amp_thresh:.2f}")

        config_manager.save_feature_config(current_config)
        print("[*] Configuration saved successfully!")
    else:
        print("[*] Discarded changes.")

if __name__ == "__main__":
    main()
