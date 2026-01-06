import pandas as pd
import numpy as np
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

MODEL_PATH = MODELS_DIR / "eog_rf.joblib"
SCALER_PATH = MODELS_DIR / "eog_scaler.joblib"

EOG_FEATURES = [
    'amplitude', 'duration_ms', 'rise_time_ms', 'fall_time_ms',
    'asymmetry', 'peak_count', 'kurtosis', 'skewness'
]

def train_eog_model(n_estimators=100, max_depth=None, test_size=0.2):
    """
    Trains a Random Forest classifier on EOG data from the database.
    """
    conn = db_manager.connect()
    
    # Load data from DB
    try:
        # Check if table exists first prevents crash if called before any EOG data collection
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='eog_windows'")
        if not cursor.fetchone():
             conn.close()
             return {"error": "EOG table does not exist. Collect data first."}

        df = pd.read_sql_query("SELECT * FROM eog_windows", conn)
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
    print(f"EOG Model saved to {MODEL_PATH}")

    # Tree Visualization (First Estimator)
    tree_struct = tree_to_json(rf.estimators_[0], EOG_FEATURES)

    return {
        "status": "success",
        "accuracy": acc,
        "confusion_matrix": cm,
        "feature_importances": importances,
        "tree_structure": tree_struct,
        "n_samples": len(df),
        "model_path": str(MODEL_PATH)
    }

def evaluate_saved_eog_model():
    """
    Evaluates the currently saved EOG model against the FULL database.
    """
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        return {"error": "EOG Model not found. Train one first."}

    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
    except Exception as e:
        return {"error": f"Failed to load EOG model: {str(e)}"}

    conn = db_manager.connect()
    try:
        df = pd.read_sql_query("SELECT * FROM eog_windows", conn)
    except Exception as e:
        conn.close()
        return {"error": f"Database read error: {str(e)}"}
    conn.close()

    if df.empty:
        return {"error": "EOG Database is empty."}

    X = df[EOG_FEATURES]
    y = df['label']

    # Inference on FULL dataset
    try:
        X_scaled = scaler.transform(X)
        y_pred = model.predict(X_scaled)
        
        acc = accuracy_score(y, y_pred)
        cm = confusion_matrix(y, y_pred).tolist()
        
        return {
            "status": "success",
            "accuracy": acc,
            "confusion_matrix": cm,
            "n_samples": len(df),
            "model_path": str(MODEL_PATH),
            "feature_importances": dict(zip(EOG_FEATURES, model.feature_importances_.tolist())),
            "tree_structure": tree_to_json(model.estimators_[0], EOG_FEATURES)
        }
    except Exception as e:
        return {"error": f"Inference error: {str(e)}"}

if __name__ == "__main__":
    # Test run
    print(train_eog_model())
