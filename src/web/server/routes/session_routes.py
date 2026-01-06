from flask import Blueprint, jsonify, request
import uuid
import uuid
import numpy as np
import time
from src.web.server.state import state
from src.database.db_manager import db_manager
# from src.web.server.lsl_service import extract_emg_features # If needed for saving EMG buffer
# Import extract_emg_features from lsl_service to avoid duplication if possible, 
# but lsl_service.py has it.
from src.web.server.lsl_service import extract_emg_features, extract_eog_features # Assume we export this

session_bp = Blueprint('session', __name__)

@session_bp.route('/api/sessions/<sensor_type>', methods=['GET'])
def api_list_sessions(sensor_type):
    """List available session tables."""
    tables = db_manager.get_session_tables(sensor_type)
    
    # FIX: Frontend expects {"tables": ["table1", "table2", ...]}
    # Previously it returned just list of objects or strings, but frontend checked data.tables
    
    # We return the full table names as strings, as frontend parser handles `_session_` split.
    # We return the full table names as strings, as frontend parser handles `_session_` split.
    return jsonify({"tables": tables})


@session_bp.route('/api/sessions/<sensor_type>/<session_name>', methods=['GET'])
def api_get_session_data(sensor_type, session_name):
    """Get data rows for a specific session."""
    try:
        data = db_manager.get_session_data(sensor_type, session_name)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@session_bp.route('/api/sessions/<sensor_type>/<session_name>', methods=['DELETE'])
def api_delete_session(sensor_type, session_name):
    """Delete a session table."""
    try:
        if db_manager.delete_session_table(sensor_type, session_name):
            # If active session was this one, reset it?
            # The UI should handle clearing local state, server state reset is tricky if it's currently recording.
            # We assume user won't delete ACTIVE recording session without stopping it first.
            return jsonify({"status": "deleted", "session": session_name})
        else:
            return jsonify({"error": "Failed to delete"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@session_bp.route('/api/sessions/<sensor_type>/<session_name>/rows/<row_id>', methods=['DELETE'])
def api_delete_session_row(sensor_type, session_name, row_id):
    """Delete a specific row from a session."""
    try:
        # Convert row_id to int
        try:
            r_id = int(row_id)
        except ValueError:
            return jsonify({"error": "Invalid row ID"}), 400

        if db_manager.delete_session_row(sensor_type, session_name, r_id):
            return jsonify({"status": "deleted", "row_id": r_id})
        else:
            return jsonify({"error": "Failed to delete row (not found or DB error)"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- EMG ENDPOINTS ---

@session_bp.route('/api/emg/start', methods=['POST'])
def api_emg_start():
    try:
        data = request.get_json()
        label = data.get('label', 0) # Default to Rest (0)
        session_name = data.get('session_name', 'DefaultSession')
        
        label_map = {0: 'Rest', 1: 'Rock', 2: 'Paper', 3: 'Scissors'}
        label_str = label_map.get(int(label), f"Unknown_{label}")
        
        state.session.start_recording('EMG', label_str, session_name=session_name)
        return jsonify({"status": "started", "label": label_str, "table": state.session.current_table_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@session_bp.route('/api/emg/stop', methods=['POST'])
def api_emg_stop():
    # Capture table name BEFORE stopping
    target_table = state.session.current_table_name or "emg_windows"
    
    state.session.is_recording = False # Stop adding samples
    # We allow processing the buffer now
    # Process and save collected data to DB
    try:
        session_id = str(uuid.uuid4())
        data_store = state.session.data_store['EMG']
        
        saved_count = 0
        
        for label_str, samples in data_store.items():
            # Paranoid check: ensure we don't do 'if samples'
            if samples is None:
                continue
            if len(samples) < 64:  # Relaxed from 100 to 64 (~0.125s) just to capture *something*
                continue
                
            # Convert label string to int if possible (for DB efficiency/schema)
            label_map = {'Rest': 0, 'Rock': 1, 'Paper': 2, 'Scissors': 3}
            label_int = label_map.get(label_str, -1)
            
            if label_int == -1:
                # 1. Try case-insensitive matching
                label_map_lower = {k.lower(): v for k, v in label_map.items()}
                label_int = label_map_lower.get(label_str.lower(), -1)
                
            if label_int == -1:
                try:
                    label_int = int(label_str)
                except:
                    label_int = -1
                    
            # Convert samples to numpy array
            raw_data = np.array(samples)
            if raw_data.ndim > 1 and raw_data.shape[1] == 1:
                raw_data = raw_data.flatten()
            
            # Windowing parameters
            sr = state.sr or 512
            window_size = int(sr * 0.5)  # 0.5s window
            step_size = int(window_size * 0.5) # 50% overlap
            
            # Slice and dice
            num_samples = len(raw_data)
            if num_samples < window_size:
                continue
                
            for i in range(0, num_samples - window_size, step_size):
                window = raw_data[i : i + window_size]
                
                # Extract features
                feats = extract_emg_features(window, sr)
                feats['timestamp'] = time.time()
                
                # Save to DB (Specific Table)
                if db_manager.insert_window(feats, label_int, session_id, table_name=target_table):
                    saved_count += 1
                    
        print(f"[Session_Routes] 💾 Saved {saved_count} EMG windows to {target_table}")
        
        # Finally reset session state
        state.session.reset_recording_state()
        
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        print(f"[Session_Routes] ❌ Error processing EMG session: {tb_str}")
        return jsonify({"status": "stopped", "error": str(e), "traceback": tb_str, "saved_windows": 0})

    return jsonify({"status": "stopped", "saved_windows": saved_count if 'saved_count' in locals() else 0})

@session_bp.route('/api/emg/status', methods=['GET'])
def api_emg_status():
    status = state.session.get_status('EMG')
    
    # Remap counts to frontend keys
    label_map_inv = {'Rest': '0', 'Rock': '1', 'Paper': '2', 'Scissors': '3'}
    mapped_counts = {}
    for k, v in status['counts'].items():
        if k in label_map_inv:
            mapped_counts[label_map_inv[k]] = v
        else:
            mapped_counts[k] = v 
            
    # Also map current_label
    curr = status['current_label']
    if curr in label_map_inv:
        status['current_label'] = int(label_map_inv[curr])
        
    status['counts'] = mapped_counts
    return jsonify(status)

@session_bp.route('/api/emg/data', methods=['DELETE'])
def api_emg_clear():
    state.session.clear_data('EMG')
    try:
        db_manager.connect('EMG').execute("DELETE FROM emg_windows").connection.commit()
    except Exception as e:
        print(f"Failed to clear DB: {e}")
    return jsonify({"status": "cleared"})

@session_bp.route('/api/emg/predict/<action>', methods=['POST'])
def api_emg_predict_toggle(action):
    if action == 'start':
        state.session.prediction_active['EMG'] = True
    elif action == 'stop':
        state.session.prediction_active['EMG'] = False
    return jsonify({"status": "ok", "predicting": state.session.prediction_active['EMG']})


# --- EOG ENDPOINTS ---

@session_bp.route('/api/eog/start', methods=['POST'])
def api_eog_start():
    try:
        data = request.get_json()
        label = data.get('label', 0)
        session_name = data.get('session_name', 'DefaultSession')
        
        state.session.start_recording('EOG', str(label), session_name=session_name)
        return jsonify({"status": "started", "label": label, "table": state.session.current_table_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@session_bp.route('/api/eog/stop', methods=['POST'])
def api_eog_stop():
    target_table = state.session.current_table_name or "eog_windows"
    state.session.is_recording = False 
    
    # Process and save EOG data
    try:
        session_id = str(uuid.uuid4())
        data_store = state.session.data_store['EOG']
        saved_count = 0
        
        for label_str, samples in data_store.items():
            if len(samples) < 50:
                continue

            try:
                label_int = int(label_str)
            except:
                continue
                
            raw_data = np.array(samples)
            if raw_data.ndim > 1:
                raw_data = raw_data.flatten()
                
            sr = state.sr or 512
            window_size = int(sr * 0.6) # 600ms to capture full blink
            step_size = int(window_size * 0.5)
            
            for i in range(0, len(raw_data) - window_size, step_size):
                window = raw_data[i : i + window_size]
                
                # Extract
                feats = extract_eog_features(window, sr)
                feats['timestamp'] = time.time()
                
                if db_manager.insert_eog_window(feats, label_int, session_id, table_name=target_table):
                    saved_count += 1

        print(f"[Session_Routes] 💾 Saved {saved_count} EOG windows to {target_table}")
        state.session.reset_recording_state()
        
    except Exception as e:
        print(f"[Session_Routes] ❌ Error processing EOG session: {e}")

    return jsonify({"status": "stopped", "saved_windows": saved_count if 'saved_count' in locals() else 0})

@session_bp.route('/api/eog/status', methods=['GET'])
def api_eog_status():
    return jsonify(state.session.get_status('EOG'))

@session_bp.route('/api/eog/data', methods=['DELETE'])
def api_eog_clear():
    state.session.clear_data('EOG')
    return jsonify({"status": "cleared"})

@session_bp.route('/api/eog/predict/<action>', methods=['POST'])
def api_eog_predict_toggle(action):
    if action == 'start':
        state.session.prediction_active['EOG'] = True
    elif action == 'stop':
        state.session.prediction_active['EOG'] = False
    return jsonify({"status": "ok", "predicting": state.session.prediction_active['EOG']})
