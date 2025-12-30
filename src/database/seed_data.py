import numpy as np
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

from database.db_manager import db_manager

def seed_db():
    print(f"Seeding database at {db_manager.db_path}")
    conn = db_manager.connect()
    cursor = conn.cursor()
    
    # Check if data exists
    try:
        cursor.execute("SELECT COUNT(*) FROM emg_windows")
        count = cursor.fetchone()[0]
    except Exception:
        # Table might not exist if db_manager didn't auto-init (it does in __init__)
        count = 0
    
    if count > 0:
        print("Clearing existing data to insert structured seed data...")
        cursor.execute("DELETE FROM emg_windows")
        conn.commit()
    
    print("Generating structured seed data...")
    n_samples_per_class = 200
    
    data = []
    
    # Feature order matches db_manager insert: 
    # rms, mav, zcr, var, wl, peak, range, iemg, entropy, energy, label, session_id, timestamp
    
    # Class 0: Rest (Low activity)
    for _ in range(n_samples_per_class):
        features = [
            np.random.normal(5, 2),    # rms
            np.random.normal(4, 2),    # mav
            np.random.normal(10, 5),   # zcr
            np.random.normal(10, 5),   # var
            np.random.normal(20, 10),  # wl
            np.random.normal(10, 3),   # peak
            np.random.normal(15, 5),   # range
            np.random.normal(50, 20),  # iemg
            np.random.normal(0.5, 0.1),# entropy (low)
            np.random.normal(200, 50)  # energy (low)
        ]
        data.append(tuple(abs(x) for x in features) + (0, "seed_data", 0))

    # Class 1: Rock (High isometric tension -> High RMS/Energy, Low Entropy)
    for _ in range(n_samples_per_class):
        features = [
            np.random.normal(50, 10),  # rms (High)
            np.random.normal(45, 10),  # mav
            np.random.normal(50, 15),  # zcr
            np.random.normal(200, 50), # var
            np.random.normal(300, 50), # wl
            np.random.normal(80, 15),  # peak
            np.random.normal(100, 20), # range
            np.random.normal(500, 100),# iemg
            np.random.normal(0.8, 0.1),# entropy (med-low)
            np.random.normal(5000, 1000) # energy (high)
        ]
        data.append(tuple(abs(x) for x in features) + (1, "seed_data", 0))

    # Class 2: Paper (Dynamic open hand -> Med RMS, High ZCR/WL/Entropy)
    for _ in range(n_samples_per_class):
        features = [
            np.random.normal(25, 8),   # rms (Medium)
            np.random.normal(22, 8),   # mav
            np.random.normal(90, 20),  # zcr (High)
            np.random.normal(100, 30), # var
            np.random.normal(400, 60), # wl
            np.random.normal(40, 10),  # peak
            np.random.normal(60, 15),  # range
            np.random.normal(250, 50), # iemg
            np.random.normal(1.5, 0.2),# entropy (high)
            np.random.normal(1500, 300) # energy (med)
        ]
        data.append(tuple(abs(x) for x in features) + (2, "seed_data", 0))

    # Class 3: Scissors (Specific muscle -> Med-High RMS, Distinctive)
    for _ in range(n_samples_per_class):
        features = [
            np.random.normal(35, 8),   # rms
            np.random.normal(30, 8),   # mav
            np.random.normal(60, 15),  # zcr
            np.random.normal(150, 40), # var
            np.random.normal(250, 40), # wl
            np.random.normal(95, 10),  # peak
            np.random.normal(90, 15),  # range
            np.random.normal(350, 60), # iemg
            np.random.normal(1.2, 0.2),# entropy (med)
            np.random.normal(2500, 500)# energy (med-high)
        ]
        data.append(tuple(abs(x) for x in features) + (3, "seed_data", 0))
        
    cursor.executemany('''
        INSERT INTO emg_windows (
            rms, mav, zcr, var, wl, peak, range, iemg, entropy, energy, label, session_id, timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', data)
    print(f"Inserted {len(data)} structured seed records.")
    conn.commit()    
    conn.close()

if __name__ == "__main__":
    seed_db()
