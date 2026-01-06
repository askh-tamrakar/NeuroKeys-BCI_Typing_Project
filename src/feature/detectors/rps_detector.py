import joblib
import pandas as pd
import numpy as np
from pathlib import Path

class RPSDetector:
    """
    Classifies EMG features into Rock, Paper, or Scissors gestures.
    Uses a pre-trained Random Forest model.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.scaler = None
        self._load_model()
        
    def _load_model(self):
        try:
            # Locate model paths relative to project root (assuming this file is in src/feature/detectors)
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            models_dir = project_root / "data" / "models"
            
            model_path = models_dir / "emg_rf.joblib"
            scaler_path = models_dir / "emg_scaler.joblib"
            
            if model_path.exists() and scaler_path.exists():
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                print(f"[RPSDetector] ✅ Loaded ML Model from {model_path}")
            else:
                print(f"[RPSDetector] ⚠️ Model not found at {model_path}")
                
        except Exception as e:
            print(f"[RPSDetector] ❌ Error loading model: {e}")
        
    def detect(self, features: dict) -> str | None:
        """
        Classify gesture based on ML model.
        """
        if not self.model or not self.scaler:
             return None
             
        try:
            # 1. Prepare Feature Vector (Must match training order)
            # ['rms', 'mav', 'zcr', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy']
            feature_cols = ['rms', 'mav', 'zcr', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy']
            
            row = []
            for col in feature_cols:
                val = features.get(col, 0.0)
                # handle potential missing 'range' vs 'rng' if any (though standard extraction has 'range')
                if col == 'range' and 'range' not in features and 'rng' in features:
                   val = features['rng']
                row.append(val)
            
            # 2. Scale
            X = pd.DataFrame([row], columns=feature_cols)
            X_scaled = self.scaler.transform(X)
            
            # 3. Predict PROBABILITY first to check confidence
            probs = self.model.predict_proba(X_scaled)[0]
            pred_idx = np.argmax(probs)
            confidence = probs[pred_idx]
            
            # Labels match model classes. 
            # If using standard sklearn, classes_ attribute holds labels.
            # Assuming labels are Ints 0,1,2,3 mapped to Rest, Rock, Paper, Scissors?
            # Or Strings if trained on strings.
            # emg_trainer.py uses db data. 
            # web_server saves labels as INTEGERS (0,1,2,3).
            # So model predicts integers.
            
            pred_label_int = self.model.classes_[pred_idx]
            
            # Map back to String
            # 0: Rest, 1: Rock, 2: Paper, 3: Scissors
            label_map = {0: 'Rest', 1: 'Rock', 2: 'Paper', 3: 'Scissors'}
            
            # Handle potential string classes if model was trained on strings
            if isinstance(pred_label_int, str):
                 pred_label_str = pred_label_int
            else:
                 pred_label_str = label_map.get(int(pred_label_int), 'Unknown')

            # Threshold
            if confidence > 0.6:
                # print(f"[RPSDetector] 🧠 Predicted: {pred_label_str} ({confidence:.2f})")
                return pred_label_str
                
            return None

        except Exception as e:
            print(f"[RPSDetector] Prediction Error: {e}")
            return None

    def update_config(self, config: dict):
        self.config = config
        # Heuristics rely on config, but ML relies on model file.
        # Maybe reload model if config points to new path? 
        # For now, do nothing or attempt reload.
        self._load_model()
