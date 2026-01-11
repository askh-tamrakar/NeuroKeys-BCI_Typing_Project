import sys
import os
from pathlib import Path
import json

# Add src to path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root / "src"))

try:
    from feature.detectors.rps_detector import RPSDetector
    from utils.config import config_manager
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

def test_rps_detector():
    print("--- Testing RPS Detector Initialization ---")
    config = config_manager.get_all_configs()
    
    # Check if features.RPS exists
    if "features" not in config or "RPS" not in config["features"]:
        print("WARNING: 'features.RPS' config missing!")
    else:
        print("Config 'features.RPS' found.")

    detector = RPSDetector(config)
    
    if detector.model is None:
        print("FAIL: Model failed to load.")
        return
    else:
        print("SUCCESS: Model loaded.")
        print(f"Classes: {detector.model.classes_}")

    print("\n--- Testing Prediction (Dummy Data) ---")
    # Feature columns from rps_detector.py
    # ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
    dummy_features = {
        'rms': 0.5, 'mav': 0.5, 'var': 100.0, 'wl': 50.0, 'peak': 1.0, 
        'range': 2.0, 'iemg': 50.0, 'entropy': 3.0, 'energy': 1000.0, 
        'kurtosis': 0.1, 'skewness': 0.1, 'ssc': 5, 'wamp': 10
    }
    
    # Run detect multiple times to test state machine
    # We need to simulate 'Active' then 'Rest'
    
    # 1. Prediction on dummy data (Random Forest might predict anything)
    label, confidence = detector._predict_instant(dummy_features)
    print(f"Instant Prediction: Label={label}, Confidence={confidence:.4f}")
    
    result = detector.detect(dummy_features)
    print(f"Detect Result (1): {result}")
    
    # If confidence is low, it returns None.
    # To properly test state machine, we might need to mock predict_proba
    # but let's see what the real model says for this dummy vector.

if __name__ == "__main__":
    test_rps_detector()
