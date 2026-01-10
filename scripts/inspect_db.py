import sqlite3
import pandas as pd
import os

db_path = r"i:\Neuroscience\Brain-To-Brain-Telepathic-Communication-System\data\processed\EMG\emg_data.db"

def inspect_db():
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    for table in tables:
        table_name = table[0]
        print(f"\n--- Checking table: {table_name} ---")
        try:
            # Get columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]
            print("Columns:", columns)
            
            # Count rows
            cursor.execute(f"SELECT count(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"Total rows: {count}")
            
            # Check for label distribution if 'label' column exists
            if 'label' in columns:
                df = pd.read_sql_query(f"SELECT label, count(*) as count FROM {table_name} GROUP BY label", conn)
                print("Label distribution:")
                print(df)
                
            # Check for session_id distribution if 'session_id' column exists
            if 'session_id' in columns:
                 df_sess = pd.read_sql_query(f"SELECT session_id, count(*) as count FROM {table_name} GROUP BY session_id", conn)
                 print("Session distribution:")
                 print(df_sess)

            # Sample data
            if count > 0:
                print("Sample row:")
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
                print(cursor.fetchone())

        except Exception as e:
            print(f"Error inspecting table {table_name}: {e}")

    conn.close()

if __name__ == "__main__":
    inspect_db()
