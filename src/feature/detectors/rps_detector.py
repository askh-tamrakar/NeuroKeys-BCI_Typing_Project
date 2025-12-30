import joblib
import pandas as pd
import numpy as np
import os
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
        self.feature_cols = ['rms', 'mav', 'zcr', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy']
        self._load_model()
        
    def _load_model(self):
        """
        Load the trained model and scaler.
        """
        try:
            # Path relative to this file: src/feature/detectors/ -> data/models
            # This file: .../src/feature/detectors/rps_detector.py
            # Root: .../
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            models_dir = project_root / "data" / "models"
            
            model_path = models_dir / "emg_rf.joblib"
            scaler_path = models_dir / "emg_scaler.joblib"
            
            if model_path.exists() and scaler_path.exists():
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                print(f"[RPSDetector] ✅ Loaded Random Forest Model from {model_path}")
            else:
                print(f"[RPSDetector] ⚠️ Model not found at {model_path}. Detection disabled until trained.")
        except Exception as e:
            print(f"[RPSDetector] ❌ Error loading model: {e}")

    def detect(self, features: dict) -> str | None:
        """
        Classify gesture based on ML model.
        """
        if not features:
            return None
            
        if self.model is None or self.scaler is None:
            # Try to reload if missing (maybe trained recently)
            self._load_model()
            if self.model is None:
                return None

        try:
            # 1. Prepare feature vector in correct order
            # Ensure all features exist, default to 0.0
            feature_vector = []
            for col in self.feature_cols:
                val = features.get(col, 0.0)
                # Handle potential rename like 'rng' -> 'range' if extraction used different key
                if col == 'range' and 'range' not in features and 'rng' in features:
                   val = features['rng']
                feature_vector.append(val)
            
            # 2. Reshape for sklearn (DataFrame to preserve feature names)
            X = pd.DataFrame([feature_vector], columns=self.feature_cols)
            
            # 3. Scale
            X_scaled = self.scaler.transform(X)
            
            # 4. Predict
            # Determine class probabilities for confidence thresholding
            probs = self.model.predict_proba(X_scaled)[0]
            pred_class_idx = np.argmax(probs)
            confidence = probs[pred_class_idx]
            
            # Map index to label (0=Rest, 1=Rock, 2=Paper, 3=Scissors, or however trained)
            # IMPORTANT: Matches the order in seed_data.py / training data
            label_map = {0: "Rest", 1: "Rock", 2: "Paper", 3: "Scissors"}
            
            predicted_label = label_map.get(pred_class_idx, "Unknown")
            
            # Confidence threshold
            CONFIDENCE_THRESHOLD = 0.6
            
            if confidence >= CONFIDENCE_THRESHOLD:
                if predicted_label != "Rest":
                    print(f"[RPSDetector] 🤖 Detected: {predicted_label} ({confidence:.2f})")
                    return predicted_label
            else:
                # print(f"[RPSDetector] Low confidence: {predicted_label} ({confidence:.2f})")
                pass

            return None

        except Exception as e:
            print(f"[RPSDetector] Prediction error: {e}")
            return None

    def update_config(self, config: dict):
        self.config = config
        # Re-load model if needed, or if config contained model paths (not currently true)
        pass
