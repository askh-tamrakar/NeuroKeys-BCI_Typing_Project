import pandas as pd
import numpy as np
import joblib
import json
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

MODEL_PATH = MODELS_DIR / "eog_rf.joblib"
SCALER_PATH = MODELS_DIR / "eog_scaler.joblib"
META_PATH = MODELS_DIR / "eog_rf_meta.json"

EOG_FEATURES = [
    'amplitude', 'duration_ms', 'rise_time_ms', 'fall_time_ms',
    'asymmetry', 'peak_count', 'kurtosis', 'skewness'
]

def train_eog_model(n_estimators=100, max_depth=None, test_size=0.2, table_name="eog_windows"):
    """
    Trains a Random Forest classifier on EOG data from the database.
    """
    conn = db_manager.connect('EOG') # Fixed: Explicit sensor type
    
    # Load data from DB
    # Load data from DB
    try:
        if not table_name: table_name = "eog_windows"
        if table_name == "undefined" or table_name == "null": table_name = "eog_windows"

        # Check if table exists first
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
             conn.close()
             return {"error": f"Table {table_name} does not exist. Collect data first."}

        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    except Exception as e:
        conn.close()
        return {"error": f"Database read error: {str(e)}"}
    
    conn.close()

    if df.empty:
        return {"error": "EOG Database is empty. Collect data first."}

    # Prepare Features and Labels
    # Check completeness
    missing = [c for c in EOG_FEATURES if c not in df.columns]
    if missing:
        return {"error": f"Missing columns in DB: {missing}"}

    X = df[EOG_FEATURES]
    y = df['label']

    # Test/Train Split
    try:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, stratify=y, random_state=42)
    except ValueError as e:
         return {"error": f"Split error (not enough data per class?): {str(e)}"}

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
    importances = dict(zip(EOG_FEATURES, rf.feature_importances_.tolist()))

    # Save Model
    joblib.dump(rf, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    
    # Save Metadata
    with open(META_PATH, 'w') as f:
        json.dump({
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "test_size": test_size,
            "table_name": table_name
        }, f)

    print(f"EOG Model saved to {MODEL_PATH}")

    # Tree Visualization (First Estimator)
    tree_struct = tree_to_json(rf.estimators_[0], EOG_FEATURES)

    return {
        "status": "success",
        "accuracy": acc,
        "confusion_matrix": cm,
        "feature_importances": importances,
        "tree_structure": tree_struct,
        "n_samples": len(y_test),
        "model_path": str(MODEL_PATH)
    }

def evaluate_saved_eog_model(table_name="eog_windows"):
    """
    Evaluates the currently saved EOG model against the specified database table.
    """
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        return {"error": "EOG Model not found. Train one first."}

    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
    except Exception as e:
        return {"error": f"Failed to load EOG model: {str(e)}"}

    # Prepare base response
    # Load Metadata if available
    hyperparameters = {}
    if META_PATH.exists():
        try:
            with open(META_PATH, 'r') as f:
                hyperparameters = json.load(f)
        except Exception:
            pass

    # Prepare base response
    base_response = {
        "status": "success",
        "model_path": str(MODEL_PATH),
        "feature_importances": dict(zip(EOG_FEATURES, model.feature_importances_.tolist())),
        "tree_structure": tree_to_json(model.estimators_[0], EOG_FEATURES),
        "hyperparameters": hyperparameters
    }

    if not table_name:
        table_name = "eog_windows"

    conn = db_manager.connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
             conn.close()
             return {
                 **base_response,
                 "accuracy": None,
                 "confusion_matrix": None,
                 "n_samples": 0,
                 "warning": f"Table {table_name} not found."
             }

        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    except Exception as e:
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

    X = df[EOG_FEATURES]
    y = df['label']

    # Inference on FULL dataset
    try:
        X_scaled = scaler.transform(X)
        y_pred = model.predict(X_scaled)
        
        acc = accuracy_score(y, y_pred)
        cm = confusion_matrix(y, y_pred).tolist()
        
        return {
            **base_response,
            "accuracy": acc,
            "confusion_matrix": cm,
            "n_samples": len(df)
        }
    except Exception as e:
        return {"error": f"Inference error: {str(e)}"}

if __name__ == "__main__":
    # Test run
    print(train_eog_model())
