import sqlite3
import pandas as pd

db_path = r"i:\Neuroscience\Brain-To-Brain-Telepathic-Communication-System\data\processed\EMG\emg_data.db"

def check_schema():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    table = "emg_windows"
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        print(f"Columns in {table}:")
        for col in columns:
            print(col)
            
        print("\nSkipping empty dataframe check for now, getting raw data...")
        df = pd.read_sql_query(f"SELECT label, rms, mav FROM {table} LIMIT 10", conn)
        print(df)
        
    except Exception as e:
        print(f"Error: {e}")

    conn.close()

if __name__ == "__main__":
    check_schema()
