from flask import Blueprint, jsonify, request
import time
import numpy as np
from src.web.server.state import state
from src.web.server.config_manager import load_config, save_config
from src.web.server.extensions import socketio
from src.database.db_manager import db_manager
from src.web.server.lsl_service import extract_emg_features, extract_emg_features as extract_features_for_sensor
# Note: original code routed `extract_features_for_sensor` to specific functions.
# We need to reimplement that routing or import it.
# EOG features are also needed.
from src.web.server.lsl_service import extract_eog_features
from scipy import stats as scipy_stats

# Imports for ML logic
from src.learning.emg_trainer import train_emg_model, evaluate_saved_model
from src.learning.eog_trainer import train_eog_model, evaluate_saved_eog_model

training_bp = Blueprint('training', __name__)

def extract_features_wrapper(sensor: str, samples: list, sr: int = 512) -> dict:
    """Route to sensor-specific feature extraction."""
    sensor = sensor.upper()
    if sensor == "EMG":
        return extract_emg_features(samples, sr)
    elif sensor == "EOG":
        return extract_eog_features(samples, sr)
    elif sensor == "EEG":
         # Assume EEG support might be added later or copied from original if present
         return {}
    else:
        return extract_emg_features(samples, sr)

@training_bp.route('/api/train-emg-rf', methods=['POST'])
def api_train_emg():
    try:
        params = request.get_json() or {}
        target_table = params.get('table_name', 'emg_windows')
        
        try:
            conn = db_manager.connect('EMG') # Need connect method exposed or access raw path?
            # db_manager exposes connect(sensor).
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (target_table,))
            if not cursor.fetchone():
                 return jsonify({"error": f"Table {target_table} not found"}), 404
                 
            n = conn.execute(f"SELECT COUNT(*) FROM {target_table}").fetchone()[0]
            conn.close()
            
            print(f"[Training] Train Request on {target_table}. Contains {n} samples.")
            if n == 0:
                return jsonify({"error": "Database is empty (0 samples). Please Record Data and hit Stop."}), 400
        except Exception as e:
            print(f"[Training] DB Check failed: {e}")

        n_est = int(params.get('n_estimators', 100))
        max_d = params.get('max_depth')
        if max_d == 'None' or max_d is None: max_d = None
        else: max_d = int(max_d)
        
        result = train_emg_model(n_estimators=n_est, max_depth=max_d, table_name=target_table)
        if "error" in result:
             return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@training_bp.route('/api/train-eog-rf', methods=['POST'])
def api_train_eog():
    try:
        params = request.get_json() or {}
        n_est = int(params.get('n_estimators', 100))
        max_d = params.get('max_depth')
        if max_d == 'None' or max_d is None: max_d = None
        else: max_d = int(max_d)
        
        result = train_eog_model(n_estimators=n_est, max_depth=max_d)
        if "error" in result:
             return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@training_bp.route('/api/model/evaluate', methods=['POST'])
def api_eval_emg():
    res = evaluate_saved_model()
    if "error" in res:
        return jsonify(res), 400
    return jsonify(res)

@training_bp.route('/api/model/evaluate/eog', methods=['POST'])
def api_eval_eog():
    res = evaluate_saved_eog_model()
    if "error" in res:
        return jsonify(res), 400
    return jsonify(res)


@training_bp.route('/api/window', methods=['POST'])
def api_save_window():
    """Accept a recorded window, save as CSV/DB, compute features and update config thresholds."""
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No payload provided"}), 400

        sensor = payload.get('sensor')
        action = payload.get('action')
        samples = payload.get('samples')
        timestamps = payload.get('timestamps', None)

        if sensor is None or action is None or samples is None:
            return jsonify({"error": "Missing required fields: sensor, action, samples"}), 400

        # Compute features
        sr = state.config.get('sampling_rate', 512) if state.config else 512
        features = extract_features_wrapper(sensor, samples, sr)

        ts = time.time()

        # Load config and update thresholds
        cfg = state.config or load_config()
        cfg_features = cfg.setdefault('features', {})
        sensor_features = cfg_features.setdefault(sensor, {})
        
        # Session handling
        session_name = payload.get('session_name', 'Manual_Windows')
        if not session_name: session_name = 'Manual_Windows'
        
        table_name = db_manager.create_session_table(sensor, session_name)
        
        label_map = {'Rest': 0, 'Rock': 1, 'Paper': 2, 'Scissors': 3}
        label_int = label_map.get(action, -1)
        if label_int == -1 and action.isdigit():
             label_int = int(action)
        if label_int == -1: label_int = 0
        
        if sensor.upper() == 'EMG':
            db_manager.insert_window(features, label_int, session_id=str(int(ts)), table_name=table_name)
        elif sensor.upper() == 'EOG':
            db_manager.insert_eog_window(features, label_int, session_id=str(int(ts)), table_name=table_name)

        # Update Config Logic (Auto-Calibration on fly)
        action_entry = sensor_features.setdefault(action, {})
        updated = {}

        for k, val in features.items():
            old_range = action_entry.get(k)
            if isinstance(old_range, list) and len(old_range) == 2:
                lo, hi = float(old_range[0]), float(old_range[1])
                new_lo = min(lo, val)
                new_hi = max(hi, val)
                action_entry[k] = [new_lo, new_hi]
                updated[k] = [new_lo, new_hi]
            else:
                if val == 0:
                    new_lo, new_hi = 0.0, 0.0
                else:
                    new_lo = val * 0.9
                    new_hi = val * 1.1
                action_entry[k] = [new_lo, new_hi]
                updated[k] = [new_lo, new_hi]

        save_success = save_config(cfg)

        result = {
            "status": "saved",
            "features": features,
            "config_updated": save_success,
            "db_table": table_name
        }

        try:
            socketio.emit('window_saved', {"sensor": sensor, "action": action, "features": features})
        except Exception:
            pass

        print(f"[Training] 💾 Window saved to DB: {table_name}")
        return jsonify(result)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[Training] ❌ Error saving window: {tb}")
        return jsonify({"error": str(e), "traceback": tb}), 500


@training_bp.route('/api/calibrate', methods=['POST'])
def api_calibrate():
    """Calibrate detection thresholds based on collected windows."""
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No payload provided"}), 400
        
        sensor = payload.get('sensor')
        windows = payload.get('windows', [])
        
        if not sensor or not windows:
            return jsonify({"error": "Missing sensor or windows"}), 400
        
        windows_by_action = {}
        for w in windows:
            action = w.get('action') or w.get('label') # Support both
            features = w.get('features', {})
            if action and features:
                if action not in windows_by_action:
                    windows_by_action[action] = []
                windows_by_action[action].append({
                    'features': features,
                    'status': w.get('status', 'unknown')
                })
        
        if not windows_by_action:
            return jsonify({"error": "No valid windows with features found"}), 400
        
        total_before = len(windows)
        correct_before = sum(1 for w in windows if w.get('status') == 'correct')
        accuracy_before = correct_before / total_before if total_before > 0 else 0
        
        updated_thresholds = {}
        samples_per_action = {}
        
        for action, action_windows in windows_by_action.items():
            samples_per_action[action] = len(action_windows)
            
            if len(action_windows) < 3:
                continue
            
            feature_values = {}
            for w in action_windows:
                for feat_name, feat_val in w['features'].items():
                    if isinstance(feat_val, (int, float)):
                        if feat_name not in feature_values:
                            feature_values[feat_name] = []
                        feature_values[feat_name].append(feat_val)
            
            action_thresholds = {}
            for feat_name, values in feature_values.items():
                if len(values) >= 3:
                    sorted_vals = sorted(values)
                    n = len(sorted_vals)
                    idx_lo = max(0, int(n * 0.05))
                    idx_hi = min(n - 1, int(n * 0.95))
                    
                    min_val = sorted_vals[idx_lo]
                    max_val = sorted_vals[idx_hi]
                    
                    margin = (max_val - min_val) * 0.05 if max_val != min_val else abs(min_val) * 0.1
                    action_thresholds[feat_name] = [
                        round(min_val - margin, 4),
                        round(max_val + margin, 4)
                    ]
            
            if action_thresholds:
                updated_thresholds[action] = action_thresholds
        
        cfg = state.config or load_config()
        cfg_features = cfg.setdefault('features', {})
        sensor_features = cfg_features.setdefault(sensor, {})
        
        for action, thresholds in updated_thresholds.items():
            if action not in sensor_features:
                sensor_features[action] = {}
            sensor_features[action].update(thresholds)
        
        # EOG Specific
        if sensor == 'EOG' and 'blink' in updated_thresholds:
            blink_thresh = updated_thresholds['blink']
            if 'duration_ms' in blink_thresh:
                sensor_features['min_duration_ms'] = blink_thresh['duration_ms'][0]
                sensor_features['max_duration_ms'] = blink_thresh['duration_ms'][1]
            if 'asymmetry' in blink_thresh:
                sensor_features['min_asymmetry'] = blink_thresh['asymmetry'][0]
                sensor_features['max_asymmetry'] = blink_thresh['asymmetry'][1]
            if 'kurtosis' in blink_thresh:
                sensor_features['min_kurtosis'] = blink_thresh['kurtosis'][0]
            if 'amplitude' in blink_thresh:
                sensor_features['amp_threshold'] = blink_thresh['amplitude'][0]
        
        save_success = save_config(cfg)
        
        # Simulate after accuracy
        correct_after = 0
        for w in windows:
            action = w.get('action') or w.get('label')
            features = w.get('features', {})
            if action in updated_thresholds:
                match_count = 0
                total_feats = 0
                for feat_name, range_val in updated_thresholds[action].items():
                    if feat_name in features:
                        total_feats += 1
                        if range_val[0] <= features[feat_name] <= range_val[1]:
                            match_count += 1
                if total_feats > 0 and (match_count / total_feats) >= 0.6:
                    correct_after += 1
        
        accuracy_after = correct_after / total_before if total_before > 0 else 0
        
        recommended_samples = {'EOG': 20, 'EMG': 30, 'EEG': 25}.get(sensor, 20)
        
        result = {
            "status": "calibrated",
            "updated_thresholds": updated_thresholds,
            "accuracy_before": round(accuracy_before, 4),
            "accuracy_after": round(accuracy_after, 4),
            "samples_per_action": samples_per_action,
            "recommended_samples": recommended_samples,
            "config_saved": save_success
        }
        
        try:
            socketio.emit('config_updated', {"sensor": sensor})
        except Exception:
            pass
        
        print(f"[Training] 🎯 Calibration complete: {sensor} | Acc: {accuracy_before:.1%} -> {accuracy_after:.1%}")
        return jsonify(result)
    
    except Exception as e:
        print(f"[Training] ❌ Calibration error: {e}")
        return jsonify({"error": str(e)}), 500
