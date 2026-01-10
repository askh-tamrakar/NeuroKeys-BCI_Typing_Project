import sqlite3
import pandas as pd

db_path = r"i:\Neuroscience\Brain-To-Brain-Telepathic-Communication-System\data\processed\EMG\emg_data.db"

def check_columns():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables = ["emg_windows", "emg_session_lucifer"]
    
    for table in tables:
        print(f"\n--- {table} ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            for col in columns:
                print(col)
                
            # Try reading one row with pandas
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 1", conn)
                print("Pandas read sample:")
                print(df.columns)
            except Exception as e:
                print(f"Pandas read error: {e}")
                
        except Exception as e:
            print(f"Error checking {table}: {e}")

    conn.close()

if __name__ == "__main__":
    check_columns()
