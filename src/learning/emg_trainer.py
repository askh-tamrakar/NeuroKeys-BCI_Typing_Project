import pandas as pd
import numpy as np
import sqlite3
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix

import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Now we can import from src
from src.learning.tree_utils import tree_to_json
from src.database.db_manager import db_manager

# Paths
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "emg_rf.joblib"
SCALER_PATH = MODELS_DIR / "emg_scaler.joblib"

def train_emg_model(n_estimators=100, max_depth=None, test_size=0.2):
    """
    Trains a Random Forest classifier on EMG data from the database.
    
    Returns:
        dict: Training results including accuracy, confusion matrix, and tree structure.
    """
    conn = db_manager.connect()
    
    # Load data from DB
    # Note: Using 'range' column as per DB schema, and new columns entropy/energy
    try:
        df = pd.read_sql_query("SELECT * FROM emg_windows", conn)
    except Exception as e:
        conn.close()
        return {"error": f"Database read error: {str(e)}"}
    
    conn.close()

    if df.empty:
        return {"error": "Database is empty. Collect data first."}

    # Prepare Features and Labels
    # DB Columns: rms, mav, zcr, var, wl, peak, range, iemg, entropy, energy
    feature_cols = ['rms', 'mav', 'zcr', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy']
    
    # Check if columns exist (handle legacy naming if necessary)
    missing_cols = [c for c in feature_cols if c not in df.columns]
    if missing_cols:
         # Try to be robust: if 'range' is missing but 'rng' exists (legacy), rename it
         if 'range' in missing_cols and 'rng' in df.columns:
             df.rename(columns={'rng': 'range'}, inplace=True)
         
         # If entropy/energy missing, fill 0 (less ideal but prevents crash)
         for col in ['entropy', 'energy']:
             if col not in df.columns:
                 df[col] = 0.0

    X = df[feature_cols]
    y = df['label']

    # Test/Train Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, stratify=y, random_state=42)

    # Scale Features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train Random Forest
    rf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
    rf.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = rf.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred).tolist()
    
    # Feature Importance
    importances = dict(zip(feature_cols, rf.feature_importances_.tolist()))

    # Save Model
    joblib.dump(rf, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"Model saved to {MODEL_PATH}")

    # Tree Visualization (First Estimator)
    tree_struct = tree_to_json(rf.estimators_[0], feature_cols)

    return {
        "status": "success",
        "accuracy": acc,
        "confusion_matrix": cm,
        "feature_importances": importances,
        "tree_structure": tree_struct,
        "n_samples": len(df),
        "model_path": str(MODEL_PATH)
    }

if __name__ == "__main__":
    # Test run
    result = train_emg_model()
    print(result)
