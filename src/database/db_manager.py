
import sqlite3
import json
from pathlib import Path
from typing import Dict, Optional, List

class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Default to data/processed/EMG/emg_data.db
            project_root = Path(__file__).resolve().parent.parent.parent
            self.db_path = project_root / "data" / "processed" / "EMG" / "emg_data.db"
        else:
            self.db_path = db_path
            
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        
    def _init_db(self):
        """Initialize database tables."""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Create emg_windows table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emg_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rms REAL NOT NULL,
                mav REAL NOT NULL,
                zcr REAL NOT NULL,
                var REAL NOT NULL,
                wl REAL NOT NULL,
                peak REAL NOT NULL,
                range REAL NOT NULL,
                iemg REAL NOT NULL,
                entropy REAL NOT NULL,
                energy REAL NOT NULL,
                label INTEGER NOT NULL,
                session_id TEXT,
                timestamp REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index on label for faster counting
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_label ON emg_windows(label)')
        
        conn.commit()
        conn.close()
        
    def connect(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
        
    def insert_window(self, features: Dict[str, float], label: int, session_id: str = None) -> bool:
        """Insert a feature window into the database."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO emg_windows (
                    rms, mav, zcr, var, wl, peak, range, iemg, 
                    entropy, energy,
                    label, session_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                features.get('rms', 0),
                features.get('mav', 0),
                features.get('zcr', 0),
                features.get('var', 0),
                features.get('wl', 0),
                features.get('peak', 0),
                features.get('range', 0),  
                features.get('iemg', 0),
                features.get('entropy', 0),
                features.get('energy', 0),
                label,
                session_id,
                features.get('timestamp', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DatabaseManager] ❌ Error inserting window: {e}")
            return False
            
    def get_counts_by_label(self) -> Dict[str, int]:
        """Get count of samples per label."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            cursor.execute('SELECT label, COUNT(*) FROM emg_windows GROUP BY label')
            rows = cursor.fetchall()
            
            counts = {
                "0": 0, "1": 0, "2": 0, "3": 0
            }
            
            for label, count in rows:
                counts[str(label)] = count
                
            conn.close()
            return counts
        except Exception as e:
            print(f"[DatabaseManager] ❌ Error getting counts: {e}")
            return {}

# Singleton instance
db_manager = DatabaseManager()
