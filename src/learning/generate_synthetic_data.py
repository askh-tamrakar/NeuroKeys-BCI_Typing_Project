import sys
import time
import random
import numpy as np
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Fix encoding for potential print issues
sys.stdout.reconfigure(encoding='utf-8')

from src.database.db_manager import db_manager

def clear_data():
    conn = db_manager.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emg_windows")
    cursor.execute("DELETE FROM eog_windows")
    conn.commit()
    conn.close()
    print("Cleared existing training data.")

def generate_emg_data(n_samples=1000):
    print(f"Generating {n_samples} EMG samples per class...")
    
    # Define feature means for each class to make them separable
    # Features: rms, mav, zcr, var, wl, peak, range, iemg, entropy, energy
    
    classes = {
        0: "Rest",
        1: "Rock",
        2: "Paper",
        3: "Scissors"
    }
    
    # Synthetic "profiles" for each gesture (mean values for features)
    profiles = {
        0: {'rms': 5, 'mav': 4, 'zcr': 10, 'energy': 50, 'entropy': 0.5},       # Rest: Low energy
        1: {'rms': 150, 'mav': 120, 'zcr': 80, 'energy': 5000, 'entropy': 1.5}, # Rock: High energy, high tension
        2: {'rms': 80, 'mav': 70, 'zcr': 50, 'energy': 2000, 'entropy': 1.2},   # Paper: Medium energy
        3: {'rms': 100, 'mav': 90, 'zcr': 120, 'energy': 3000, 'entropy': 1.8}  # Scissors: Medium-High energy, distinct ZCR
    }
    
    session_id = f"synth_emg_{int(time.time())}"
    
    count = 0
    for label, name in classes.items():
        prof = profiles[label]
        
        for _ in range(n_samples):
            # Generate features with some noise
            features = {
                'rms': np.random.normal(prof['rms'], prof['rms']*0.1),
                'mav': np.random.normal(prof['mav'], prof['mav']*0.1),
                'zcr': np.random.normal(prof['zcr'], prof['zcr']*0.1),
                'var': np.random.normal(prof['rms']**2, (prof['rms']**2)*0.1), # var approx rms^2
                'wl': np.random.normal(prof['mav']*2, prof['mav']*0.2),
                'peak': np.random.normal(prof['rms']*1.5, prof['rms']*0.1),
                'range': np.random.normal(prof['rms']*3, prof['rms']*0.2),
                'iemg': np.random.normal(prof['mav']*50, prof['mav']*5), # Integrated over hypothetical window
                'entropy': np.random.normal(prof['entropy'], 0.1),
                'energy': np.random.normal(prof['energy'], prof['energy']*0.1),
                'timestamp': time.time()
            }
            
            # Clamp non-negative
            for k in features:
                if k != 'timestamp':
                    features[k] = max(0.0, features[k])
            
            db_manager.insert_window(features, label, session_id)
            count += 1
            
    print(f"Inserted {count} EMG records.")

def generate_eog_data(n_samples=1000):
    print(f"Generating {n_samples} EOG samples per class...")
    
    # Labels: 0=Rest, 1=Single Blink, 2=Double Blink
    classes = {
        0: "Rest",
        1: "Single Blink",
        2: "Double Blink"
    }
    
    # DB Columns: amplitude, duration_ms, rise_time_ms, fall_time_ms, asymmetry, peak_count, kurtosis, skewness
    
    profiles = {
        0: {'amp': 20, 'dur': 100, 'peaks': 0},      # Rest: Noise
        1: {'amp': 400, 'dur': 250, 'peaks': 1},     # Single: High amp, short duration, 1 peak
        2: {'amp': 450, 'dur': 600, 'peaks': 2},     # Double: High amp, longer duration, 2 peaks
    }
    
    session_id = f"synth_eog_{int(time.time())}"
    count = 0
    
    for label, name in classes.items():
        prof = profiles[label]
        
        for _ in range(n_samples):
            features = {
                'amplitude': np.random.normal(prof['amp'], 30),
                'duration_ms': np.random.normal(prof['dur'], 50),
                'rise_time_ms': np.random.normal(prof['dur']*0.4, 20),
                'fall_time_ms': np.random.normal(prof['dur']*0.4, 20),
                'asymmetry': np.random.normal(0, 0.5),
                'peak_count': prof['peaks'], # Keep peaks exact mostly, maybe mostly exact
                'kurtosis': np.random.normal(3, 1),
                'skewness': np.random.normal(0, 1),
                'timestamp': time.time()
            }
            
            # Ensure logical constraints
            if label == 0: features['peak_count'] = 0
            if label == 1: features['peak_count'] = 1
            if label == 2: features['peak_count'] = random.choice([2, 2, 2, 3]) # Occasional noise
            
            features['amplitude'] = max(0, features['amplitude'])
            features['duration_ms'] = max(20, features['duration_ms'])
            
            db_manager.insert_eog_window(features, label, session_id)
            count += 1
            
    print(f"Inserted {count} EOG records.")

if __name__ == "__main__":
    try:
        clear_data()
        generate_emg_data(1000)
        generate_eog_data(1000)
        print("Data generation complete.")
    except Exception as e:
        print(f"Error: {e}")
