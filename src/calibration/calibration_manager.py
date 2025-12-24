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
    
    def extract_features(self, sensor: str, samples: List[float], sr: int = 512) -> Dict[str, Any]:
        """
        Route feature extraction to the appropriate static method.
        """
        sensor = sensor.upper()
        
        if sensor == "EOG":
            return BlinkExtractor.extract_features(samples, sr)
        elif sensor == "EMG":
            return RPSExtractor.extract_features(samples, sr)
        elif sensor == "EEG":
            # For now, EEG extraction logic isn't refactored into a class yet, 
            # or we can assume a similar pattern if we had EEGExtractor.
            # Using basic extraction or returns empty if not available
            return {} 
        else:
            # Default to generic/EMG stats if unknown
            return RPSExtractor.extract_features(samples, sr)

    def detect_signal(self, sensor: str, action: str, features: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """
        Check if features match the current detection thresholds in config.
        """
        sensor = sensor.upper()
        sensor_cfg = config.get("features", {}).get(sensor, {})
        
        if sensor == "EOG":
            # Blink logic
            min_duration = sensor_cfg.get("min_duration_ms", 100.0)
            max_duration = sensor_cfg.get("max_duration_ms", 600.0)
            min_asymmetry = sensor_cfg.get("min_asymmetry", 0.05)
            max_asymmetry = sensor_cfg.get("max_asymmetry", 2.5)
            min_kurtosis = sensor_cfg.get("min_kurtosis", -3.0)
            amp_thresh = sensor_cfg.get("amp_threshold", 10.0)
            
            dur = features.get("duration_ms", 0)
            asym = features.get("asymmetry", 0)
            kurt = features.get("kurtosis", 0)
            amp = features.get("amplitude", 0)
            
            is_valid_duration = min_duration <= dur <= max_duration
            is_valid_asymmetry = min_asymmetry <= asym <= max_asymmetry
            is_valid_shape = kurt >= min_kurtosis
            is_valid_amp = amp >= amp_thresh
            
            return is_valid_duration and is_valid_asymmetry and is_valid_shape and is_valid_amp

        elif sensor == "EMG":
            # RPS logic - compare against action profile
            action_profile = sensor_cfg.get(action, {})
            if not action_profile:
                return False
            
            match_count = 0
            total_features = 0
            
            for feat_name, range_val in action_profile.items():
                if feat_name in features and isinstance(range_val, list) and len(range_val) == 2:
                    total_features += 1
                    val = features[feat_name]
                    if range_val[0] <= val <= range_val[1]:
                        match_count += 1
            
            if total_features > 0:
                score = match_count / total_features
                return score >= 0.6
            return False
            
        return False

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
        
        # 5. Check Detection
        detected = self.detect_signal(sensor, action, features, config)
        
        return {
            "status": "saved",
            "csv_path": str(csv_path),
            "features": features,
            "detected": detected
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
            
            # Compute 5th-95th percentile ranges
            action_thresholds = {}
            for k, vals in feature_values.items():
                if len(vals) < 3:
                    continue
                
                sorted_vals = sorted(vals)
                n = len(sorted_vals)
                idx_lo = max(0, int(n * 0.05))
                idx_hi = min(n - 1, int(n * 0.95))
                
                min_val = sorted_vals[idx_lo]
                max_val = sorted_vals[idx_hi]
                
                # Add 5% margin
                margin = (max_val - min_val) * 0.05 if max_val != min_val else abs(min_val) * 0.1
                
                action_thresholds[k] = [
                    round(min_val - margin, 4), 
                    round(max_val + margin, 4)
                ]
            
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
            
        # Update EOG global thresholds if applicable
        if sensor == 'EOG' and 'blink' in updated_thresholds:
            blink_thresh = updated_thresholds['blink']
            if 'duration_ms' in blink_thresh:
                sensor_feats['min_duration_ms'] = blink_thresh['duration_ms'][0]
                sensor_feats['max_duration_ms'] = blink_thresh['duration_ms'][1]
            if 'asymmetry' in blink_thresh:
                sensor_feats['min_asymmetry'] = blink_thresh['asymmetry'][0]
                sensor_feats['max_asymmetry'] = blink_thresh['asymmetry'][1]
            if 'kurtosis' in blink_thresh:
                sensor_feats['min_kurtosis'] = blink_thresh['kurtosis'][0]
            if 'amplitude' in blink_thresh:
                sensor_feats['amp_threshold'] = blink_thresh['amplitude'][0]

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
            # This is a bit inefficient but safe
            temp_config = {"features": current_cfg}
            
            is_detected = self.detect_signal(sensor, action, features, temp_config)
            
            # Original status
            original_status = w.get('status', 'unknown')
            
            # If detected, it matches the label => Correct
            # If not detected, it's missed or Incorrect
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
