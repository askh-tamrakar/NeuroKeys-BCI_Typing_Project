import pandas as pd
import sqlite3
from src.database.db_manager import db_manager

def check_labels():
    for sensor in ['EMG', 'EOG']:
        try:
            conn = db_manager.connect(sensor)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"\n--- {sensor} Tables ---")
            for table in tables:
                t_name = table[0]
                print(f"Table: {t_name}")
                try:
                    df = pd.read_sql_query(f"SELECT DISTINCT label FROM {t_name}", conn)
                    labels = df['label'].tolist()
                    print(f"  Labels: {labels}")
                except Exception as e:
                    print(f"  Error reading labels: {e}")
            conn.close()
        except Exception as e:
            print(f"Error checking {sensor} DB: {e}")

if __name__ == "__main__":
    check_labels()
