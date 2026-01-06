import sys
import os
import sqlite3
import random
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from src.database.db_manager import DatabaseManager

def generate_data():
    db = DatabaseManager()
    
    # Create the session table
    # This will create 'emg_session_synthetic'
    session_name = "synthetic" 
    table_name = db.create_session_table("EMG", session_name)
    print(f"Created table: {table_name}")
    
    # Connect directly to perform batch inserts efficiently
    # insert_window opens/closes connection per call, which is slow for 4000 rows
    conn = db.connect("EMG")
    cursor = conn.cursor()
    
    # Define features to generate
    feature_keys = ['rms', 'mav', 'zcr', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy']
    
    samples_per_label = 1000
    
    print("Generating data...")
    
    for label in range(4):
        print(f"Generating for label {label}...")
        # Create slightly distinct distributions for each label
        # This makes the synthetic data somewhat separable for testing ML models
        # Label 0: Low values
        # Label 1: Medium values
        # Label 2: High values
        # Label 3: Variable/Mixed
        
        base_mean = (label + 1) * 10.0
        
        for i in range(samples_per_label):
            features = {}
            for key in feature_keys:
                # Random value centered around base_mean with noise
                # Ensure positive values for most EMG features
                val = random.gauss(base_mean, 5.0)
                features[key] = abs(val) 
            
            timestamp = i * 0.1 # Mock timestamp
            
            cursor.execute(f'''
                INSERT INTO {table_name} (
                    rms, mav, zcr, var, wl, peak, range, iemg, entropy, energy,
                    label, session_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                features['rms'], features['mav'], features['zcr'],
                features['var'], features['wl'], features['peak'],
                features['range'], features['iemg'], features['entropy'],
                features['energy'], label, "synthetic_batch_1", timestamp
            ))
            
    conn.commit()
    conn.close()
    
    print(f"Successfully inserted {samples_per_label * 4} samples into {table_name}.")

if __name__ == "__main__":
    generate_data()
