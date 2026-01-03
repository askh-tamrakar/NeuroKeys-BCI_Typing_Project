
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

        # Initialize EOG table
        self._init_eog_table(cursor)
        
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

    # --- EOG Support ---

    def _init_eog_table(self, cursor):
        """Create eog_windows table."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eog_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amplitude REAL NOT NULL,
                duration_ms REAL NOT NULL,
                rise_time_ms REAL NOT NULL,
                fall_time_ms REAL NOT NULL,
                asymmetry REAL NOT NULL,
                peak_count INTEGER NOT NULL,
                kurtosis REAL NOT NULL,
                skewness REAL NOT NULL,
                label INTEGER NOT NULL,
                session_id TEXT,
                timestamp REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_eog_label ON eog_windows(label)')

    def insert_eog_window(self, features: Dict[str, float], label: int, session_id: str = None) -> bool:
        """Insert an EOG feature window."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO eog_windows (
                    amplitude, duration_ms, rise_time_ms, fall_time_ms, 
                    asymmetry, peak_count, kurtosis, skewness,
                    label, session_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                features.get('amplitude', 0),
                features.get('duration_ms', 0),
                features.get('rise_time_ms', 0),
                features.get('fall_time_ms', 0),
                features.get('asymmetry', 0),
                int(features.get('peak_count', 0)),
                features.get('kurtosis', 0),
                features.get('skewness', 0),
                label,
                session_id,
                features.get('timestamp', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DatabaseManager] ❌ Error inserting EOG window: {e}")
            return False

    def get_eog_counts(self) -> Dict[str, int]:
        """Get count of EOG samples per label."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # Ensure table exists (deferred init if needed)
            self._init_eog_table(cursor)
            
            cursor.execute('SELECT label, COUNT(*) FROM eog_windows GROUP BY label')
            rows = cursor.fetchall()
            
            # Map labels to 0 (Rest), 1 (Single), 2 (Double)
            counts = {"0": 0, "1": 0, "2": 0}
            for label, count in rows:
                counts[str(label)] = count
                
            conn.close()
            return counts
        except Exception as e:
            print(f"[DatabaseManager] ❌ Error getting EOG counts: {e}")
            return {}

    def clear_eog_data(self):
        """Delete all records from eog_windows table."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM eog_windows')
            conn.commit()
            conn.close()
            print("[DatabaseManager] 🗑️  Cleared all EOG data")
            return {"status": "success"}
        except Exception as e:
            msg = f"Error clearing EOG data: {e}"
            print(f"[DatabaseManager] ❌ {msg}")
            return {"error": msg}

# Singleton instance
db_manager = DatabaseManager()
