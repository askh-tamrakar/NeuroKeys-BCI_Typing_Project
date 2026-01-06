
import sys
import sqlite3
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from src.database.db_manager import DatabaseManager

def verify():
    db = DatabaseManager()
    conn = db.connect("EMG")
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM emg_session_synthetic")
        total = cursor.fetchone()[0]
        print(f"Total rows: {total}")
        
        cursor.execute("SELECT label, COUNT(*) FROM emg_session_synthetic GROUP BY label")
        counts = cursor.fetchall()
        print("Counts by label:")
        for label, count in counts:
            print(f"Label {label}: {count}")
            
    except Exception as e:
        print(f"Verification failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify()
