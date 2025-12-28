import joblib
import pandas as pd
import numpy as np
from pathlib import Path

# Constants for project root (adjusted for where this file is: src/feature/detectors/blink_detector.py)
# Root is ../../../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "data" / "models"
MODEL_PATH = MODELS_DIR / "eog_rf.joblib"
SCALER_PATH = MODELS_DIR / "eog_scaler.joblib"

EOG_FEATURES = [
    'amplitude', 'duration_ms', 'rise_time_ms', 'fall_time_ms',
    'asymmetry', 'peak_count', 'kurtosis', 'skewness'
]

class BlinkDetector:
    """
    Classifies an event as a blink using a trained Random Forest model.
    Falls back to heuristic rules if model is not found.
    """
    
    def __init__(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        if not eog_cfg:
             eog_cfg = config.get("EOG", {})
        
        # Heuristic Thresholds (Fallback)
        self.min_duration = eog_cfg.get("min_duration_ms", 100.0)
        self.max_duration = eog_cfg.get("max_duration_ms", 600.0)
        self.min_asymmetry = eog_cfg.get("min_asymmetry", 0.05) 
        self.max_asymmetry = eog_cfg.get("max_asymmetry", 2.5) 
        self.min_kurtosis = eog_cfg.get("min_kurtosis", -3.0) 
        
        # Load Model
        self.model = None
        self.scaler = None
        try:
            if MODEL_PATH.exists() and SCALER_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
                self.scaler = joblib.load(SCALER_PATH)
                print(f"[BlinkDetector] 🧠 Loaded EOG Random Forest Model")
        except Exception as e:
            print(f"[BlinkDetector] ⚠️ Failed to load model: {e}")

    def detect(self, features: dict) -> str | None:
        """
        Classify event.
        """
        if not features:
            return None
        
        # 1. Model-based Inference
        if self.model and self.scaler:
            try:
                # Prepare input vector (must match training order)
                # Use DataFrame to avoid sklearn warning about feature names
                input_df = pd.DataFrame([features])[EOG_FEATURES]
                
                # Scale
                input_scaled = self.scaler.transform(input_df)
                
                # Predict
                pred_label = self.model.predict(input_scaled)[0] # 0, 1, 2
                
                # Map to string
                label_map = {0: "Rest", 1: "SingleBlink", 2: "DoubleBlink"}
                result = label_map.get(pred_label, "Rest")
                
                if result == "Rest":
                    return None
                    
                print(f"[BlinkDetector] 🧠 Model Pred: {result}")
                return result
                
            except Exception as e:
                print(f"[BlinkDetector] ❌ Inference Error: {e}")
                # Fallthrough to heuristic
        
        # 2. Heuristic Fallback
        dur = features.get("duration_ms", 0)
        asym = features.get("asymmetry", 0)
        kurt = features.get("kurtosis", 0)
        
        is_valid_duration = self.min_duration <= dur <= self.max_duration
        is_valid_asymmetry = self.min_asymmetry <= asym <= self.max_asymmetry
        is_valid_shape = kurt >= self.min_kurtosis

        if is_valid_duration and is_valid_asymmetry and is_valid_shape:
            # Simple heuristic for Double Blink based on peak count or duration
            # (If model is missing, we use basic fallback)
            p_count = features.get("peak_count", 1)
            if p_count >= 2:
                print("[BlinkDetector] 📏 Heauristic: DoubleBlink")
                return "DoubleBlink"
            else:
                print("[BlinkDetector] 📏 Heuristic: SingleBlink")
                return "SingleBlink"
            
        return None

    def update_config(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        if not eog_cfg:
             eog_cfg = config.get("EOG", {})
             
        self.min_duration = eog_cfg.get("min_duration_ms", self.min_duration)
        self.max_duration = eog_cfg.get("max_duration_ms", self.max_duration)
        self.min_asymmetry = eog_cfg.get("min_asymmetry", self.min_asymmetry)
        self.max_asymmetry = eog_cfg.get("max_asymmetry", self.max_asymmetry)
        self.min_kurtosis = eog_cfg.get("min_kurtosis", self.min_kurtosis)
        
        # Attempt reload if config changes (optional, but good practice)
        try:
            if MODEL_PATH.exists() and SCALER_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
                self.scaler = joblib.load(SCALER_PATH)
        except:
            pass
