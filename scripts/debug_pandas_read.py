import sqlite3
import pandas as pd

db_path = r"i:\Neuroscience\Brain-To-Brain-Telepathic-Communication-System\data\processed\EMG\emg_data.db"

def debug_read():
    conn = sqlite3.connect(db_path)
    
    print("Trying to read label only...")
    try:
        df = pd.read_sql_query("SELECT label FROM emg_windows LIMIT 5", conn)
        print(df)
    except Exception as e:
        print(e)
        
    print("\nTrying to read rms only...")
    try:
        df = pd.read_sql_query("SELECT rms FROM emg_windows LIMIT 5", conn)
        print(df)
    except Exception as e:
        print(e)

    print("\nTrying to read all...")
    try:
        df = pd.read_sql_query("SELECT * FROM emg_windows LIMIT 5", conn)
        print(df)
        print("Columns:", df.columns)
    except Exception as e:
        print(e)

    conn.close()

if __name__ == "__main__":
    debug_read()
