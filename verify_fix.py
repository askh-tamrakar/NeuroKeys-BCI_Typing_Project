import pandas as pd
import numpy as np
import sqlite3
import json
from pathlib import Path
from src.learning.emg_trainer import train_emg_model, STANDARD_LABELS

# Setup test DB
TEST_DB = "test_emg.db"
TABLE_NAME = "emg_test_rock_only"

def create_mock_data():
    conn = sqlite3.connect(TEST_DB)
    
    feature_cols = ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
    
    columns = ", ".join([f"{c} REAL" for c in feature_cols])
    # Label is INTEGER now
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} (id INTEGER PRIMARY KEY, {columns}, label INTEGER, timestamp REAL)")
    
    data = []
    # 50 Rock samples (Label 1)
    for i in range(50):
        row = [np.random.random() for _ in feature_cols]
        row.append(1) # Label 1
        row.append(0.0)
        data.append(tuple(row))
        
    # 50 Rest samples (Label 0)
    for i in range(50):
        row = [np.random.random() for _ in feature_cols]
        row.append(0) # Label 0
        row.append(0.0)
        data.append(tuple(row))

    placeholders = ", ".join(["?"] * (len(feature_cols) + 2))
    conn.executemany(f"INSERT INTO {TABLE_NAME} ({', '.join(feature_cols)}, label, timestamp) VALUES ({placeholders})", data)
    conn.commit()
    conn.close()
    print(f"Created {TABLE_NAME} with Rock (1) and Rest (0) samples.")

def verify_fix():
    # Monkeypatch db_manager
    from src.database.db_manager import db_manager
    original_connect = db_manager.connect
    db_manager.connect = lambda name: sqlite3.connect(TEST_DB)
    
    print("\nRunning Training...")
    result = train_emg_model(table_name=TABLE_NAME)
    
    db_manager.connect = original_connect
    
    if "error" in result:
        print(f"FAILED: {result['error']}")
        return

    cm = result.get("confusion_matrix")
    labels = result.get("labels")
    
    print(f"\nLabels used: {labels}")
    print(f"Confusion Matrix: {cm}")
    
    if len(cm) != 4:
        print("FAILED: Confusion Matrix is not 4x4.")
    elif labels != [0, 1, 2, 3]:
        print(f"FAILED: Labels mismatch. Got {labels}, expected [0, 1, 2, 3]")
    elif cm[0][0] > 0 and cm[1][1] > 0:
         print("SUCCESS: 4x4 Matrix with correct data indices.")
    else:
         print("FAILED: Data alignment seems wrong.")

if __name__ == "__main__":
    create_mock_data()
    verify_fix()
    try:
        Path(TEST_DB).unlink()
    except:
        pass
