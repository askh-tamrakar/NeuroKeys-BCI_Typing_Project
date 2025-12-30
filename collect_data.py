import sys
import os
import time
import pylsl
import sqlite3
from pathlib import Path

# Add src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT / "src"))

from feature.extractors.rps_extractor import RPSExtractor
from database.db_manager import db_manager

# Hardcoded config for collection
EMG_CHANNEL_INDEX = 1 

def get_db_connection():
    return db_manager.connect()

def collect_class_data(label_name, label_id, duration_sec=10):
    print(f"\n--- Recording {label_name} (Label: {label_id}) ---")
    input(f"Press ENTER to start recording {duration_sec}s of data...")
    
    print("Searching for stream...")
    streams = pylsl.resolve_byprop('name', 'BioSignals-Processed', timeout=5.0)
    if not streams:
        print("Error: Could not find 'BioSignals-Processed' LSL stream.")
        return
    
    inlet = pylsl.StreamInlet(streams[0])
    sr = int(inlet.info().nominal_srate())
    
    # Initialize Extractor
    dummy_config = {
        "features": {
            "EMG": {
                 "window_size_ms": 250, 
                 "step_size_ms": 50
            }
        }
    }
    
    extractor = RPSExtractor(EMG_CHANNEL_INDEX, dummy_config, sr)
    
    print(f"Recording started! Perform {label_name} gesture...")
    
    start_time = time.time()
    feature_list = []
    
    while time.time() - start_time < duration_sec:
        chunk, ts = inlet.pull_chunk(timeout=1.0)
        if chunk:
            for sample in chunk:
                if EMG_CHANNEL_INDEX < len(sample):
                    val = sample[EMG_CHANNEL_INDEX]
                    feats = extractor.process(val)
                    if feats:
                        feature_list.append(feats)
    
    print(f"Recording finished. Captured {len(feature_list)} windows.")
    
    if not feature_list:
        print("No features extracted. Check signal quality or channel index.")
        return

    # Save to DB via DB Manager
    count = 0
    for f in feature_list:
        db_manager.insert_window(f, label_id, f"cli_session_{int(time.time())}")
        count += 1
        
    print(f"Saved {count} samples to database.")

def main():
    print("=== EMG Data Collection Tool (Fixed) ===")
    print(f"Database: {db_manager.db_path}")
    print(f"Listening to Channel: {EMG_CHANNEL_INDEX}")
    
    while True:
        print("\nSelect Action to Record:")
        print("0. Rest")
        print("1. Rock")
        print("2. Paper")
        print("3. Scissors")
        print("4. Clear Database")
        print("q. Quit")
        
        choice = input("Choice: ")
        
        if choice == 'q':
            break
        elif choice == '4':
            confirm = input("Are you sure? (yes/no): ")
            if confirm.lower() == 'yes':
                conn = db_manager.connect()
                conn.execute("DELETE FROM emg_windows")
                conn.commit()
                conn.close()
                print("Database cleared.")
        elif choice in ['0', '1', '2', '3']:
             labels = ['Rest', 'Rock', 'Paper', 'Scissors']
             try:
                 dur_str = input("Duration in seconds (default 10): ")
                 dur = float(dur_str) if dur_str.strip() else 10.0
             except:
                 dur = 10.0
             
             collect_class_data(labels[int(choice)], int(choice), dur)
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
