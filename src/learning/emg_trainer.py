import pandas as pd
import numpy as np
import sqlite3
import joblib
import json
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix
import sys
from pathlib import Path

# Standard Labels for Confusion Matrix alignment (Indices)
# 0=Rest, 1=Rock, 2=Paper, 3=Scissors (Assumed based on usage)
STANDARD_LABELS = [0, 1, 2, 3]

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
META_PATH = MODELS_DIR / "emg_rf_meta.json"

def train_emg_model(n_estimators=100, max_depth=None, test_size=0.2, table_name="emg_windows"):
    """
    Trains a Random Forest classifier on EMG data from the specified table.
    
    Returns:
        dict: Training results including accuracy, confusion matrix, and tree structure.
    """
    conn = db_manager.connect('EMG')
    
    # Load data from DB
    try:
        # Validate table name basic safety (alphanumeric + underscore only)
        # In prod we should use params, but table names can't be parameterized easily in all drivers.
        # Since table_name comes from our internal API which validates it, it's relatively safe.
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    except Exception as e:
        conn.close()
        return {"error": f"Database read error from {table_name}: {str(e)}"}
    
    conn.close()

    if df.empty:
        return {"error": "Database is empty. Collect data first."}

    # Prepare Features and Labels
    # DB Columns: rms, mav, var, wl, peak, range, iemg, entropy, energy, kurtosis, skewness, ssc, wamp
    feature_cols = ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
    
    # Check if columns exist (handle legacy naming if necessary)
    missing_cols = [c for c in feature_cols if c not in df.columns]
    if missing_cols:
         # Try to be robust: if 'range' is missing but 'rng' exists (legacy), rename it
         if 'range' in missing_cols and 'rng' in df.columns:
             df.rename(columns={'rng': 'range'}, inplace=True)
         
         # If entropy/energy/new_feats missing, fill 0 (less ideal but prevents crash)
         for col in ['entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']:
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
    # Use standard labels to ensure matrix is always 4x4 and aligned with frontend
    cm = confusion_matrix(y_test, y_pred, labels=STANDARD_LABELS).tolist()
    
    # Feature Importance
    importances = dict(zip(feature_cols, rf.feature_importances_.tolist()))

    # Save Model
    joblib.dump(rf, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    
    # Save Metadata (Hyperparameters)
    with open(META_PATH, 'w') as f:
        json.dump({
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "test_size": test_size,
            "table_name": table_name
        }, f)
        
    print(f"Model saved to {MODEL_PATH}")

    # Tree Visualization (First Estimator)
    tree_struct = tree_to_json(rf.estimators_[0], feature_cols)

    return {
        "status": "success",
        "accuracy": acc,
        "accuracy": acc,
        "confusion_matrix": cm,
        "labels": STANDARD_LABELS,
        "feature_importances": importances,
        "tree_structure": tree_struct,
        "n_samples": len(y_test),
        "model_path": str(MODEL_PATH)
    }

def evaluate_saved_model(table_name="emg_windows"):
    """
    Evaluates the currently saved model against the specified database table.
    Used to verify how well the persisted model performs on all available data.
    """
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        return {"error": "Model not found. Train a model first."}

    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
    except Exception as e:
        return {"error": f"Failed to load model: {str(e)}"}

    # Prepare base response with model structure
    feature_cols = ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
    
    # Load Metadata if available
    hyperparameters = {}
    if META_PATH.exists():
        try:
            with open(META_PATH, 'r') as f:
                hyperparameters = json.load(f)
        except Exception:
            pass

    base_response = {
        "status": "success",
        "model_path": str(MODEL_PATH),
        "feature_importances": dict(zip(feature_cols, model.feature_importances_.tolist())),
        "tree_structure": tree_to_json(model.estimators_[0], feature_cols),
        "hyperparameters": hyperparameters
    }

    # If no table specified or table is None, default to emg_windows
    if not table_name:
        table_name = "emg_windows"
    
    print(f"[DEBUG] evaluate_saved_model - Using table: {table_name}")

    conn = db_manager.connect('EMG')
    try:
        # Check if table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
             print(f"[DEBUG] Table {table_name} NOT FOUND in sqlite_master")
             conn.close()
             # Return partial response if table missing
             return {
                 **base_response,
                 "accuracy": None,
                 "confusion_matrix": None,
                 "n_samples": 0,
                 "warning": f"Table {table_name} not found. Evaluation skipped."
             }

        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        print(f"[DEBUG] Loaded {len(df)} rows from {table_name}")
    except Exception as e:
        print(f"[DEBUG] DB Error: {e}")
        conn.close()
        return {
             **base_response,
             "accuracy": None,
             "confusion_matrix": None,
             "n_samples": 0,
             "warning": f"Database read error: {str(e)}"
        }
    conn.close()

    if df.empty:
         return {
             **base_response,
             "accuracy": None,
             "confusion_matrix": None,
             "n_samples": 0,
             "warning": f"Table {table_name} is empty."
         }

    # Prepare Features
    # Check/Fix columns
    missing_cols = [c for c in feature_cols if c not in df.columns]
    if missing_cols:
         if 'range' in missing_cols and 'rng' in df.columns:
             df.rename(columns={'rng': 'range'}, inplace=True)
         for col in ['entropy', 'energy']:
             if col not in df.columns:
                 df[col] = 0.0

    X = df[feature_cols]
    y = df['label']

    # Inference on FULL dataset
    try:
        X_scaled = scaler.transform(X)
        y_pred = model.predict(X_scaled)
        
        acc = accuracy_score(y, y_pred)
        # Use standard labels
        cm = confusion_matrix(y, y_pred, labels=STANDARD_LABELS).tolist()
        
        return {
            **base_response,
            "accuracy": acc,
            "confusion_matrix": cm,
            "labels": STANDARD_LABELS,
            "n_samples": len(df)
        }
    except Exception as e:
        return {"error": f"Inference error: {str(e)}"}

if __name__ == "__main__":
    # Test run
    # result = train_emg_model()
    # print(result)
    print("Testing Evaluation...")
    print(evaluate_saved_model())
