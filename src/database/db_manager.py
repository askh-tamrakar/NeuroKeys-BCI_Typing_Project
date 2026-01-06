
import sqlite3
import re
from pathlib import Path
from typing import Dict, Optional, List

class DatabaseManager:
    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent.parent
        data_dir = project_root / "data" / "processed"
        
        self.db_paths = {
            'EMG': data_dir / "EMG" / "emg_data.db",
            'EOG': data_dir / "EOG" / "eog_data.db",
            'EEG': data_dir / "EEG" / "eeg_data.db"
        }
        
        # Ensure directories exist
        for path in self.db_paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_dbs()
        
    def connect(self, sensor_type: str):
        """Get database connection for specific sensor."""
        sensor = sensor_type.upper()
        if sensor not in self.db_paths:
            raise ValueError(f"Unknown sensor type: {sensor}")
        return sqlite3.connect(self.db_paths[sensor])

    def _init_dbs(self):
        """Initialize all databases."""
        # EMG
        conn = self.connect('EMG')
        self._create_emg_table(conn.cursor(), "emg_windows")
        conn.commit()
        conn.close()

        # EOG
        conn = self.connect('EOG')
        self._create_eog_table(conn.cursor(), "eog_windows")
        conn.commit()
        conn.close()

    def _create_emg_table(self, cursor, table_name):
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
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
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_label ON {table_name}(label)')

    def _create_eog_table(self, cursor, table_name):
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
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
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_{table_name}_label ON {table_name}(label)')

    def sanitize_table_name(self, name: str) -> str:
        safe = re.sub(r'[^a-zA-Z0-9]', '_', name)
        return safe.strip('_')

    def create_session_table(self, sensor_type: str, session_name: str) -> str:
        safe_suffix = self.sanitize_table_name(session_name)
        if not safe_suffix: safe_suffix = "default"
        
        sensor = sensor_type.upper()
        table_name = f"{sensor.lower()}_session_{safe_suffix}"
        
        conn = self.connect(sensor)
        cursor = conn.cursor()
        
        if sensor == "EMG":
            self._create_emg_table(cursor, table_name)
        elif sensor == "EOG":
            self._create_eog_table(cursor, table_name)
            
        conn.commit()
        conn.close()
        return table_name

    def get_session_tables(self, sensor_type: str) -> List[str]:
        sensor = sensor_type.upper()
        conn = self.connect(sensor)
        cursor = conn.cursor()
        prefix = f"{sensor.lower()}_session_"
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?", (f"{prefix}%",))
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]

    # --- Session Management ---
    def delete_session_table(self, sensor_type: str, session_name: str) -> bool:
        """Drop a session table."""
        try:
            # Reconstruct table name logic
            safe_suffix = self.sanitize_table_name(session_name)
            
            sensor = sensor_type.upper()
            prefix = f"{sensor.lower()}_session_"
            
            if session_name.startswith(prefix):
                 table_name = session_name
            else:
                 if not safe_suffix: safe_suffix = "default"
                 table_name = f"{prefix}{safe_suffix}"
            
            conn = self.connect(sensor)
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            conn.close()
            print(f"[DB] Dropped table: {table_name}")
            return True
        except Exception as e:
            print(f"[DB] Error dropping table {session_name}: {e}")
            return False

    def get_session_data(self, sensor_type: str, session_name: str) -> List[Dict]:
        """Fetch all rows from a specific session table."""
        try:
            sensor = sensor_type.upper()
            
            # Validate table name strictly to prevent injection
            # Although sanitize_table_name does some, ensure it matches expected pattern
            prefix = f"{sensor.lower()}_session_"
            if not session_name.startswith(prefix):
                 # Try to see if it's the short name?
                 # Assume it's the full table name passed from frontend
                 return []
            
            # Additional safety verify it exists in list?
            if session_name not in self.get_session_tables(sensor):
                return []

            conn = self.connect(sensor)
            conn.row_factory = sqlite3.Row # Access columns by name
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {session_name}")
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                r_dict = dict(row)
                # Pack features into list/dict if needed for consistency with frontend expectations
                # Frontend expects: { label: ..., features: [...] }
                # But here we have raw columns.
                # Let's verify what columns we have.
                # EMG: rms, mav, zcr...
                # EOG: amplitude, duration...
                
                # We can group features dynamically
                item = {
                    "id": r_dict.get('id'),
                    "label": r_dict.get('label'),
                    "timestamp": r_dict.get('timestamp')
                }
                
                # Collect remaining columns as features for display
                # Exclude metadata
                excluded = {'id', 'label', 'session_id', 'timestamp', 'created_at'}
                features = {k: v for k, v in r_dict.items() if k not in excluded}
                
                # Flatten features to array or keep object? 
                # Frontend does: row.features.map... implying array OR object handling in table?
                # Frontend code: `Array.isArray(row.features) ? ... : JSON.stringify(...)`
                # Let's return features as object values for simplified display or just the object
                # But for a cleaner table, detailed structure is better.
                # Let's just put the feature dict in 'features' key.
                item['features'] = features # Return dict with keys
                
                # Or better, list of objects or formatted string?
                # Frontend truncates. List of floats is fine.
                
                results.append(item)
                
            conn.close()
            conn.close()
            return results
        except Exception as e:
            print(f"[DB] Error fetching session data {session_name}: {e}")
            return []

    def delete_session_row(self, sensor_type: str, session_name: str, row_id: int) -> bool:
        """Delete a specific row from a session table."""
        try:
            sensor = sensor_type.upper()
            
            # Validate table name similar to get_session_data
            prefix = f"{sensor.lower()}_session_"
            if not session_name.startswith(prefix):
                 # Try sanitize/lookup if needed, but stick to strict matching for safety like get_session_data
                 # Or allow if it's in the known table list (expensive?)
                 # For now, strict prefix check as frontend sends full name
                 if session_name not in self.get_session_tables(sensor):
                     return False

            conn = self.connect(sensor)
            cursor = conn.cursor()
            
            # Use parameterized query for ID, but table name must be injected (safe due to check above)
            cursor.execute(f"DELETE FROM {session_name} WHERE id = ?", (row_id,))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                print(f"[DB] Deleted row {row_id} from {session_name}")
                return True
            else:
                print(f"[DB] Row {row_id} not found in {session_name}")
                return False
                
        except Exception as e:
            print(f"[DB] Error deleting row {row_id} from {session_name}: {e}")
            return False

    # --- EMG Methods ---
    def insert_window(self, features: Dict[str, float], label: int, session_id: str = None, table_name: str = "emg_windows") -> bool:
        try:
            conn = self.connect('EMG')
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO {table_name} (
                    rms, mav, zcr, var, wl, peak, range, iemg, entropy, energy,
                    label, session_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                features.get('rms', 0), features.get('mav', 0), features.get('zcr', 0),
                features.get('var', 0), features.get('wl', 0), features.get('peak', 0),
                features.get('range', 0), features.get('iemg', 0), features.get('entropy', 0),
                features.get('energy', 0), label, session_id, features.get('timestamp', 0)
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB] EMG Insert Error: {e}")
            return False

    def get_counts_by_label(self, table_name: str = "emg_windows") -> Dict[str, int]:
        try:
            conn = self.connect('EMG')
            cursor = conn.cursor()
            cursor.execute(f'SELECT label, COUNT(*) FROM {table_name} GROUP BY label')
            rows = cursor.fetchall()
            counts = { "0": 0, "1": 0, "2": 0, "3": 0 }
            for l, c in rows: counts[str(l)] = c
            conn.close()
            return counts
        except: return { "0": 0, "1": 0, "2": 0, "3": 0 }
        
    def clear_table(self, sensor_type: str, table_name: str):
        try:
            conn = self.connect(sensor_type)
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {table_name}')
            conn.commit()
            conn.close()
            return {"status": "success"}
        except Exception as e:
            return {"error": str(e)}

    # --- EOG Methods ---
    def insert_eog_window(self, features: Dict[str, float], label: int, session_id: str = None, table_name: str = "eog_windows") -> bool:
        try:
            conn = self.connect('EOG')
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO {table_name} (
                    amplitude, duration_ms, rise_time_ms, fall_time_ms, 
                    asymmetry, peak_count, kurtosis, skewness,
                    label, session_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                features.get('amplitude', 0), features.get('duration_ms', 0), features.get('rise_time_ms', 0),
                features.get('fall_time_ms', 0), features.get('asymmetry', 0), int(features.get('peak_count', 0)),
                features.get('kurtosis', 0), features.get('skewness', 0), label, session_id, features.get('timestamp', 0)
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB] EOG Insert Error: {e}")
            return False

    def get_eog_counts(self, table_name: str = "eog_windows") -> Dict[str, int]:
        try:
            conn = self.connect('EOG')
            cursor = conn.cursor()
            cursor.execute(f'SELECT label, COUNT(*) FROM {table_name} GROUP BY label')
            rows = cursor.fetchall()
            counts = {"0": 0, "1": 0, "2": 0}
            for l, c in rows: counts[str(l)] = c
            conn.close()
            return counts
        except: return {"0": 0, "1": 0, "2": 0}

db_manager = DatabaseManager()
