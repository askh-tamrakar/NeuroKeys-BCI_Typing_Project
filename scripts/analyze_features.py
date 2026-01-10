import sqlite3
import pandas as pd
import os

db_path = r"i:\Neuroscience\Brain-To-Brain-Telepathic-Communication-System\data\processed\EMG\emg_data.db"

def analyze_features():
    conn = sqlite3.connect(db_path)
    
    print("--- emg_windows Stats ---")
    df_win = pd.read_sql_query("SELECT label, rms, mav FROM emg_windows", conn)
    print(df_win.groupby('label').describe())

    print("\n--- emg_session_lucifer Stats ---")
    df_luc = pd.read_sql_query("SELECT label, rms, mav FROM emg_session_lucifer", conn)
    print(df_luc.groupby('label').describe())
    
    conn.close()

if __name__ == "__main__":
    analyze_features()
