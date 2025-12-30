import time
import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import Config Manager
try:
    from utils.config import config_manager
except ImportError:
    import sys
    # Add project root to path
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    sys.path.append(str(PROJECT_ROOT / "src"))
    from utils.config import config_manager

# Import Feature Extractors
from feature.extractors.blink_extractor import BlinkExtractor
from feature.extractors.rps_extractor import RPSExtractor
from feature.extractors.trigger_extractor import EEGExtractor

# Import Action Detectors
from feature.detectors.blink_detector import BlinkDetector
from feature.detectors.rps_detector import RPSDetector
from feature.detectors.trigger_detector import EEGDetector

# Import Database Manager
from database.db_manager import db_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CalibrationManager:
    """
    Manages calibration sessions, window recording, feature extraction,
    and threshold optimization.
    """
    
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.data_dir = self.project_root / "data" / "processed" / "windows"
    
    def _sanitize_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively replace NaN/Infinity with None (null in JSON) or 0.
        Standard JSON does not support NaN.
        """
        clean = {}
        for k, v in features.items():
            if isinstance(v, dict):
                clean[k] = self._sanitize_features(v)
            elif isinstance(v, float):
                if np.isnan(v) or np.isinf(v):
                    clean[k] = 0.0 # or None
                else:
                    clean[k] = v
            elif isinstance(v, list):
                # Simple list sanitization
                clean[k] = [0.0 if (isinstance(x, float) and (np.isnan(x) or np.isinf(x))) else x for x in v]
            else:
                clean[k] = v
        return clean

    def extract_features(self, sensor: str, samples: List[float], sr: int = 512) -> Dict[str, Any]:
        """
        Route feature extraction to the appropriate static method.
        """
        sensor = sensor.upper()
        
        raw_features = {}
        if sensor == "EOG":
            raw_features = BlinkExtractor.extract_features(samples, sr)
        elif sensor == "EMG":
            raw_features = RPSExtractor.extract_features(samples, sr)
        elif sensor == "EEG":
            # Basic spectral power extraction for EEG (Alpha/Beta/Theta)
            try:
                # Simple placeholder logic until dedicated extractor is available
                data = np.array(samples)
                if len(data) < sr: 
                    raw_features = {"status": "insufficient_data"}
                else:
                    # Simple Variance/Amplitude check
                    amp_max = np.max(np.abs(data))
                    std_dev = np.std(data)
                    
                    # Mock spectral bands (Real impl requires FFT)
                    # For calibration, we might just track amplitude or variance for "Target vs Rest"
                    raw_features = {
                        "amplitude": float(amp_max),
                        "std_dev": float(std_dev),
                        "alpha_power": float(np.random.uniform(0.5, 5.0)) # Mock
                    }
            except Exception as e:
                logger.error(f"EEG extraction error: {e}")
                raw_features = {}
        else:
            # Default fallback
            raw_features = RPSExtractor.extract_features(samples, sr)
            
        return self._sanitize_features(raw_features)

    def predict_signal(self, sensor: str, features: Dict[str, Any], config: Dict[str, Any]) -> Optional[str]:
        """
        Use the appropriate detector to predict the signal label.
        """
        sensor = sensor.upper()
        try:
            if sensor == "EMG":
                detector = RPSDetector(config)
                return detector.detect(features)
            elif sensor == "EOG":
                detector = BlinkDetector(config)
                return detector.detect(features)
            elif sensor == "EEG":
                # Placeholder
                return None
        except Exception as e:
            logger.error(f"Prediction error: {e}")
        return None

    def detect_signal(self, sensor: str, action: str, features: Dict[str, Any], config: Dict[str, Any]) -> Optional[str]:
        """
        Check if features match the expected action.
        Returns the detected label (str) if any, else None.
        (Previously returned bool)
        """
        detected_label = self.predict_signal(sensor, features, config)
        return detected_label
            

    def save_window(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a recorded window: save to CSV, extract features, check detection.
        """
        sensor = payload.get('sensor')
        action = payload.get('action')
        channel = payload.get('channel', '0')
        samples = payload.get('samples', [])
        timestamps = payload.get('timestamps')
        
        if not sensor or not action:
            raise ValueError("Missing sensor or action")

        # 1. Create directories
        out_dir = self.data_dir / sensor / action
        out_dir.mkdir(parents=True, exist_ok=True)
        
        ts = time.time()
        filename = f"window__{action}__{int(ts)}__ch{channel}.csv"
        csv_path = out_dir / filename
        
        # 2. Save CSV
        valid_samples = True
        try:
            with open(csv_path, 'w') as f:
                f.write('timestamp,value\n')
                if timestamps and len(timestamps) == len(samples):
                    for t, v in zip(timestamps, samples):
                        f.write(f"{t},{v}\n")
                else:
                    for i, v in enumerate(samples):
                        f.write(f"{i},{v}\n")
        except Exception as e:
            logger.error(f"Failed to save CSV: {e}")
            valid_samples = False

        # 3. Extract Features
        config = config_manager.get_all_configs()
        sr = config.get('sampling_rate', 512)
        
        features = self.extract_features(sensor, samples, sr)
        
        # 4. Save Features JSON
        if valid_samples and features:
            feat_path = csv_path.with_suffix('.features.json')
            with open(feat_path, 'w') as f:
                json.dump({
                    "features": features,
                    "sensor": sensor,
                    "action": action,
                    "channel": channel,
                    "saved_at": ts
                }, f, indent=2)

            # 4b. Save to SQLite DB (for EMG)
            if valid_samples and features and sensor == 'EMG':
                try:
                    # Dynamic Label Mapping
                    # Get gestures from Feature Config
                    feature_cfg = config.get("features", {}).get("EMG", {})
                    # Create a deterministic mapping based on sorted keys
                    # Filter out "Rest" if you want specific IDs or just map everything
                    known_gestures = sorted([k for k in feature_cfg.keys() if k != "Rest"])
                    
                    # Standard mapping: Rest=0, others=1,2,3...
                    label_map = {"Rest": 0}
                    for idx, gesture in enumerate(known_gestures, 1):
                        label_map[gesture] = idx
                        
                    int_label = label_map.get(action, 0) 
                    
                    db_manager.insert_window(
                        features,
                        label=int_label,
                        session_id=str(int(ts)) 
                    )
                    logger.info(f"[Calibration] Saved to separate DB: {action} (ID: {int_label})")
                except Exception as db_err:
                    logger.error(f"[Calibration] DB Save Error: {db_err}")

            # 4c. Save to SQLite DB (for EOG)
            if valid_samples and features and sensor == 'EOG':
                try:
                    # EOG Label Map: Rest=0, SingleBlink=1, DoubleBlink=2
                    label_map = {"Rest": 0, "SingleBlink": 1, "DoubleBlink": 2}
                    int_label = label_map.get(action, 0)
                    
                    db_manager.insert_eog_window(
                        features,
                        label=int_label,
                        session_id=str(int(ts))
                    )
                    logger.info(f"[Calibration] Saved to EOG DB: {action} (ID: {int_label})")
                except Exception as db_err:
                    logger.error(f"[Calibration] EOG DB Save Error: {db_err}")
        
        # 5. Check Detection & Prediction
        # detect_signal now returns string or None
        detected_action = self.detect_signal(sensor, action, features, config)
        predicted_label = self.predict_signal(sensor, features, config)
        
        return {
            "status": "saved",
            "csv_path": str(csv_path),
            "features": features,
            "detected": detected_action, # Now a string (or None)
            "predicted_label": predicted_label
        }

    def calibrate_sensor(self, sensor: str, windows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Perform statistical calibration (percentile-based) on collected windows.
        Updates configuration thresholds.
        """
        if not windows:
            raise ValueError("No windows provided for calibration")

        # Group by action
        windows_by_action = {}
        for w in windows:
            action = w.get('action')
            features = w.get('features', {})
            # Only calibration based on 'correct' or 'pending' windows?
            # Or assume all windows passed in are valid examples of the action.
            if action and features:
                if action not in windows_by_action:
                    windows_by_action[action] = []
                windows_by_action[action].append(features)
        
        if not windows_by_action:
            raise ValueError("No valid features found in windows")

        # Calculate optimal thresholds
        updated_thresholds = {}
        
        for action, feature_list in windows_by_action.items():

            
            if len(feature_list) < 3:
                continue # Need more data
                
            # Aggregate per feature
            feature_values = {}
            for feats in feature_list:
                for k, v in feats.items():
                    if isinstance(v, (int, float)):
                        if k not in feature_values:
                            feature_values[k] = []
                        feature_values[k].append(v)
            
            
            # Remove outliers via IQR before percentile calculation
            # This prevents one bad window from ruining the calibration
            clean_values_map = {}
            for k, vals in feature_values.items():
                if len(vals) < 3:
                     clean_values_map[k] = vals
                     continue

                # robust IQR filtering
                q1 = np.percentile(vals, 25)
                q3 = np.percentile(vals, 75)
                iqr = q3 - q1
                lower_fence = q1 - 1.5 * iqr
                upper_fence = q3 + 1.5 * iqr
                
                clean_vals = [v for v in vals if lower_fence <= v <= upper_fence]
                # If we filtered everything, fall back to original
                if not clean_vals: 
                    clean_vals = vals
                clean_values_map[k] = clean_vals

            # Compute ranges on CLEAN data
            action_thresholds = {}
            for k, vals in clean_values_map.items():
                if not vals: continue
                
                sorted_vals = sorted(vals)
                n = len(sorted_vals)
                
                # Use slightly broader percentiles for validity (5th-95th)
                # But rely on the IQR cleaning above to handle extreme outliers
                min_val = np.percentile(vals, 5)
                max_val = np.percentile(vals, 95)
                
                # Add margin (20% is safer than 30% if we already removed outliers)
                margin = (max_val - min_val) * 0.2
                if margin == 0: margin = abs(min_val) * 0.1
                if margin == 0: margin = 1.0
                
                lower_bound = float(min_val - margin)
                upper_bound = float(max_val + margin)
                
                # Sanity Checks / Hard Caps based on Sensor Physics
                if sensor == 'EOG':
                    if 'duration_ms' in k:
                        lower_bound = max(50.0, lower_bound) # Blinks can't be < 50ms
                        upper_bound = min(1500.0, upper_bound)
                    elif 'amplitude' in k:
                        lower_bound = max(10.0, lower_bound) # Noise floor
                        upper_bound = min(2000.0, upper_bound) # Max phys cap
                    elif 'peak_count' in k:
                        # integer-ish logic
                        lower_bound = max(0.5, lower_bound)
                    elif 'kurtosis' in k:
                        lower_bound = max(-5.0, lower_bound)
                        upper_bound = min(50.0, upper_bound)

                elif sensor == 'EMG':
                    if 'mav' in k or 'rms' in k:
                         lower_bound = max(1.0, lower_bound)
                
                # General Positive-Only Cap
                positive_only = {
                    'rms', 'mav', 'energy', 'var', 'peak', 'range', 'iemg', 
                    'amplitude', 'period', 'power', 'std_dev', 'rise_time_ms', 'fall_time_ms', 'duration_ms'
                }
                if k.lower() in positive_only:
                    lower_bound = max(0.0, lower_bound)

                action_thresholds[k] = [round(lower_bound, 4), round(upper_bound, 4)]
            
            if action_thresholds:
                updated_thresholds[action] = action_thresholds

        # Update Config
        current_cfg = config_manager.get_feature_config()
        sensor_feats = current_cfg.get(sensor, {})
        
        # Merge new thresholds
        for action, new_thresh in updated_thresholds.items():
            if action not in sensor_feats:
                sensor_feats[action] = {}
            sensor_feats[action].update(new_thresh)
            
        # Update EOG global thresholds if applicable (Backwards compatibility)
        if sensor == 'EOG' and 'blink' in updated_thresholds:
            blink_thresh = updated_thresholds['blink']
            # Map known keys to flat config
            mapping = {
                'duration_ms': ['min_duration_ms', 'max_duration_ms'],
                'asymmetry': ['min_asymmetry', 'max_asymmetry'],
                'kurtosis': ['min_kurtosis', None],
                'amplitude': ['amp_threshold', None]
            }
            
            for feat, map_keys in mapping.items():
                if feat in blink_thresh:
                    val_range = blink_thresh[feat]
                    if map_keys[0]: sensor_feats[map_keys[0]] = val_range[0]
                    if map_keys[1] and len(val_range) > 1: sensor_feats[map_keys[1]] = val_range[1]

        # Save Config
        current_cfg[sensor] = sensor_feats
        save_success = config_manager.save_feature_config(current_cfg)
        
        # Recalculate verification/accuracy
        results = []
        correct_count = 0
        total_count = 0
        
        for w in windows:
            action = w.get('action')
            features = w.get('features', {})
            # We construct a full config object to reuse detect_signal
            temp_config = {"features": current_cfg}
            
            is_detected = self.detect_signal(sensor, action, features, temp_config)
            
            original_status = w.get('status', 'unknown')
            
            # If detected, it matches the label => Correct
            new_status = 'correct' if is_detected else 'incorrect'
            
            if new_status == 'correct':
                correct_count += 1
            total_count += 1
            
            results.append({
                "action": action,
                "status_before": original_status,
                "status_after": new_status,
                "detected": is_detected
            })
            
        accuracy = correct_count / total_count if total_count > 0 else 0
        
        return {
            "status": "calibrated",
            "updated_thresholds": updated_thresholds,
            "config_saved": save_success,
            "accuracy": accuracy,
            "window_results": results
        }

# Global Instance
calibration_manager = CalibrationManager()
