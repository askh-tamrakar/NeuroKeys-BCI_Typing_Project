import sqlite3
import os

db_path = r"i:\Neuroscience\Brain-To-Brain-Telepathic-Communication-System\data\processed\EMG\emg_data.db"

def debug_raw():
    print(f"Opening {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Count(*):")
    cursor.execute("SELECT count(*) FROM emg_windows")
    print(cursor.fetchone())

    print("Select one row:")
    cursor.execute("SELECT * FROM emg_windows LIMIT 1")
    row = cursor.fetchone()
    print(row)
    
    conn.close()

if __name__ == "__main__":
    debug_raw()
