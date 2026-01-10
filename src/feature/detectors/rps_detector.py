import joblib
import pandas as pd
import numpy as np
<<<<<<< HEAD
import os
from pathlib import Path
=======
from pathlib import Path
from collections import Counter
>>>>>>> rps-implement

class RPSDetector:
    """
    Classifies EMG features into Rock, Paper, or Scissors gestures.
    Uses a pre-trained Random Forest model.
<<<<<<< HEAD
=======
    
    Refactored to use a Candidate/State-based approach:
    - Buffers predictions while the gesture is active (not Rest).
    - Emits the most frequent prediction when the gesture returns to Rest.
>>>>>>> rps-implement
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.scaler = None
<<<<<<< HEAD
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
=======
        
        # State tracking for candidate-based detection
        self.collecting_candidates = False
        self.candidates = []
        self.last_active_ts = 0.0
        
        # Configuration for state machine
        rps_cfg = config.get("features", {}).get("RPS", {})
        self.confidence_threshold = rps_cfg.get("confidence_threshold", 0.6)
        
        self._load_model()
        
    def _load_model(self):
        try:
            # Locate model paths relative to project root (assuming this file is in src/feature/detectors)
>>>>>>> rps-implement
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            models_dir = project_root / "data" / "models"
            
            model_path = models_dir / "emg_rf.joblib"
            scaler_path = models_dir / "emg_scaler.joblib"
            
            if model_path.exists() and scaler_path.exists():
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
<<<<<<< HEAD
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
=======
                print(f"[RPSDetector] ✅ Loaded ML Model from {model_path}")
            else:
                print(f"[RPSDetector] ⚠️ Model not found at {model_path}")
                
        except Exception as e:
            print(f"[RPSDetector] ❌ Error loading model: {e}")
        
    def _predict_instant(self, features: dict) -> tuple[str, float]:
        """
        Helper: Make a single instant prediction from features.
        Returns: (Label, Confidence)
        """
        if not self.model or not self.scaler:
             return "Unknown", 0.0
             
        try:
            # 1. Prepare Feature Vector (Must match training order)
            # ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
            feature_cols = ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
            
            row = []
            for col in feature_cols:
                val = features.get(col, 0.0)
                # handle potential missing 'range' vs 'rng' if any
                if col == 'range' and 'range' not in features and 'rng' in features:
                   val = features['rng']
                row.append(val)
            
            # 2. Scale
            X = pd.DataFrame([row], columns=feature_cols)
            X_scaled = self.scaler.transform(X)
            
            # 3. Predict PROBABILITY
            probs = self.model.predict_proba(X_scaled)[0]
            pred_idx = np.argmax(probs)
            confidence = probs[pred_idx]
            
            pred_label_int = self.model.classes_[pred_idx]
            
            # Map back to String
            # 0: Rest, 1: Rock, 2: Paper, 3: Scissors
            label_map = {0: 'Rest', 1: 'Rock', 2: 'Paper', 3: 'Scissors'}
            
            if isinstance(pred_label_int, str):
                 pred_label_str = pred_label_int
            else:
                 pred_label_str = label_map.get(int(pred_label_int), 'Unknown')

            return pred_label_str, confidence

        except Exception as e:
            print(f"[RPSDetector] Prediction Error: {e}")
            return "Error", 0.0

    def detect(self, features: dict) -> str | None:
        """
        Stateful detection logic:
        - If Rest -> Resolve any pending candidates.
        - If Gesture -> Add to candidates.
        """
        label, confidence = self._predict_instant(features)
        
        # Determine if this instant frame is "Active" (valid gesture) or "Rest"
        is_confident = confidence > self.confidence_threshold
        is_active = is_confident and label in ['Rock', 'Paper', 'Scissors']
        is_rest = is_confident and label == 'Rest'
        
        # State Machine
        if is_active:
            if not self.collecting_candidates:
                self.collecting_candidates = True
                self.candidates = []
                # print(f"[RPS] Starting gesture candidate collection... ({label})")
            
            self.candidates.append(label)
            return None # Don't emit yet
            
        elif is_rest:
            if self.collecting_candidates:
                # End of a gesture, resolve it!
                if self.candidates:
                    # Logic: Most frequent label
                    # Could also weigh by confidence if we stored it, but Mode is usually robust enough
                    counts = Counter(self.candidates)
                    most_common = counts.most_common(1)[0][0] # (Label, Count)
                    
                    # print(f"[RPS] Gesture Finished. Candidates: {counts}. Final: {most_common}")
                    
                    self.collecting_candidates = False
                    self.candidates = []
                    return most_common
                else:
                    self.collecting_candidates = False
                    return "Rest"
            else:
                # Already resting, ensure system knows
                return "Rest"
                
        else:
            # Low confidence or Unknown
            # If we are collecting, maybe tolerate a few dropped frames? 
            # For now, treat as noise/continue current state or ignore.
            # If we treat as "Rest", we might chop gestures too aggressively.
            # If we ignore, we rely on the next strong frame.
            return None
            
        return None

    def update_config(self, config: dict):
        self.config = config
        rps_cfg = config.get("features", {}).get("RPS", {})
        self.confidence_threshold = rps_cfg.get("confidence_threshold", 0.6)
        self._load_model()
>>>>>>> rps-implement
