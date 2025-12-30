import sys
import os

# UTF-8 encoding for standard output to avoid UnicodeEncodeError in some terminals
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional
import math
import statistics

try:
    import pylsl
    LSL_AVAILABLE = True
except Exception as e:
    print(f"[WebServer] Warning: pylsl not available: {e}")
    LSL_AVAILABLE = False


from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room

# Feature extraction and detection imports
import numpy as np
# scipy imports removed as they are now handled in calibration_manager

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Database and Extractor
try:
    from database.db_manager import db_manager
    from feature.extractors.rps_extractor import RPSExtractor
except ImportError:
    import sys
    sys.path.append(str(PROJECT_ROOT / "src"))
    from database.db_manager import db_manager
    from feature.extractors.rps_extractor import RPSExtractor



# ========== Configuration ==========
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
TEMPLATES_DIR = PROJECT_ROOT / "src" / "web" / "templates"
DEFAULT_SR = 512

RAW_STREAM_NAME = "BioSignals-Processed"
EVENT_STREAM_NAME = "BioSignals-Events"


# ========== Flask App Setup ==========

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR) if TEMPLATES_DIR.exists() else None,
    static_folder=str(TEMPLATES_DIR / "static") if (TEMPLATES_DIR / "static").exists() else None
)

# CORS configuration
CORS(app, resources={r"/*": {"origins": "*"}})

# SocketIO configuration  
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=10,
    ping_interval=5,
    engineio_logger=False,
    logger=False
)


class WebServerState:
    def __init__(self):
        self.inlet = None
        self.event_inlet = None  # NEW: Event Stream Inlet
        self.channel_mapping = {}
        self.running = False
        self.connected = False
        self.sample_count = 0
        self.clients = 0
        self.sr = DEFAULT_SR
        self.num_channels = 0
        self.config = {}
        
        # Recording State
        self.recording = {
            "active": False,
            "label": 0,
            "session_id": None,
            "start_time": 0,
            "extractor": None
        }
        
        self.prediction = {
            "active": False,
            "mode": "EOG", 
            "extractor": None,
            "detector": None
        }


state = WebServerState()


# ========== CONFIG MANAGEMENT ==========

# Import centralized config manager
# Assuming sibling package import setup is correct or adjustment needed
try:
    from utils.config import config_manager
except ImportError:
    # Try relative import if running from src/web
    import sys
    sys.path.append(str(PROJECT_ROOT / "src"))
    from utils.config import config_manager


def load_config() -> dict:
    """Load config facade from ConfigManager."""
    return config_manager.get_all_configs()

# Import Calibration Manager
try:
    from calibration.calibration_manager import calibration_manager
except ImportError:
    import sys
    sys.path.append(str(PROJECT_ROOT / "src"))
    from calibration.calibration_manager import calibration_manager


def save_config(config: dict) -> bool:
    """
    Save config facade: SPLIT the monolithic dict into component parts
    and save them individually.
    """
    try:
        # 1. Extract and Save SENSOR Config
        # We need to filter only sensor keys to avoid polluting sensor_config.json with other stuff
        # Ideally, we get current sensor config and update it
        current_sensor = config_manager.sensor_config.get_all()
        
        # Valid keys for sensor config
        valid_keys = ["sampling_rate", "channel_mapping", "adc_settings", "ui_settings", "num_channels", "serial_port", "baidu", "display"]
        
        new_sensor = {k: config.get(k, current_sensor.get(k)) for k in valid_keys if k in config or k in current_sensor}
        
        # Merge channel_mapping deep to be safe? 
        # For now, simple replacement from the monolithic dict is likely what the frontend expects
        if "channel_mapping" in config:
             new_sensor["channel_mapping"] = config["channel_mapping"]

        if not config_manager.save_sensor_config(new_sensor):
            print("[WebServer] ❌ Failed to save Sensor Config")
            return False

        # 2. Extract and Save FILTER Config
        if "filters" in config:
            if not config_manager.save_filter_config(config["filters"]):
                print("[WebServer] ❌ Failed to save Filter Config")
                return False

        # 3. Extract and Save FEATURE Config
        if "features" in config:
            if not config_manager.save_feature_config(config["features"]):
                print("[WebServer] ❌ Failed to save Feature Config")
                return False

        print(f"[WebServer] 💾 Config saved (Modular split)")
        state.config = config
        return True

    except Exception as e:
        print(f"[WebServer] ❌ Error saving config: {e}")
        return False


# ========== HELPER FUNCTIONS ==========


def create_channel_mapping(lsl_info) -> Dict:
    """Create channel mapping from LSL stream info."""
    mapping = {}
    # Use facade
    config = config_manager.get_all_configs()
    config_mapping = config.get("channel_mapping", {})

    try:
        ch_count = int(lsl_info.channel_count())
        state.sr = int(lsl_info.nominal_srate())
        state.num_channels = ch_count

        for i in range(ch_count):
            ch_key = f"ch{i}"
            
            # Get from config or use defaults
            if ch_key in config_mapping:
                ch_info = config_mapping[ch_key]
                sensor_type = ch_info.get("sensor", "UNKNOWN").upper()
                enabled = ch_info.get("enabled", True)
            else:
                sensor_type = "UNKNOWN"
                enabled = True

            mapping[i] = {
                "type": sensor_type,
                "label": f"{sensor_type}_{i}",
                "enabled": enabled
            }

    except Exception as e:
        print(f"[WebServer] ⚠️  Error creating mapping: {e}")

    return mapping


def resolve_lsl_stream() -> bool:
    """Resolve and connect to LSL stream."""
    if not LSL_AVAILABLE:
        print("[WebServer] ❌ pylsl not available")
        return False

    try:
        print("[WebServer] 🔍 Searching for LSL stream...")
        streams = pylsl.resolve_streams(wait_time=1.0)
        
        target = None

        # Exact match first
        for s in streams:
            if s.name() == RAW_STREAM_NAME:
                target = s
                break

        # Heuristic match
        if not target:
            for s in streams:
                if "processed" in s.name().lower():
                    target = s
                    break

        if target:
            state.inlet = pylsl.StreamInlet(target, max_buflen=1, recover=True)
            state.channel_mapping = create_channel_mapping(state.inlet.info())
            state.connected = True
            print(f"[WebServer] ✅ Connected to: {target.name()}")
            print(f"[WebServer] Channels: {state.num_channels} @ {state.sr} Hz")
            return True

        print("[WebServer] ❌ Could not find LSL stream")
        print("[WebServer] Make sure filter_router is running!")
        return False

    except Exception as e:
        print(f"[WebServer] ❌ Error resolving stream: {e}")
        return False


def resolve_event_stream() -> bool:
    """Resolve and connect to LSL Event stream."""
    if not LSL_AVAILABLE:
        return False
        
    try:
        print(f"[WebServer] 🔍 Searching for Event stream: {EVENT_STREAM_NAME}...")
        streams = pylsl.resolve_streams()
        # Filter manually if needed, or use resolve_byprop if available. 
        # Actually resolve_stream('name', 'foo') works in standard pylsl, but maybe version diff.
        # Let's try resolve_byprop
        streams = pylsl.resolve_byprop('name', EVENT_STREAM_NAME)
        
        if streams:
            state.event_inlet = pylsl.StreamInlet(streams[0])
            print(f"[WebServer] ✅ Connected to Event Stream: {EVENT_STREAM_NAME}")
            return True
            
        print("[WebServer] ℹ️  Event stream not found")
        return False
    except Exception as e:
        print(f"[WebServer] ❌ Error resolving event stream: {e}")
        return False

def broadcast_events():
    """Broadcast events to all connected clients."""
    print("[WebServer] 📡 Starting event broadcast thread...")
    
    while state.running:
        if state.event_inlet is None:
            # Try to reconnect occasionally
            if not resolve_event_stream():
                time.sleep(2.0)
                continue

        try:
            # Pull sample (blocking for short time)
            sample, ts = state.event_inlet.pull_sample(timeout=0.1)
            
            if sample:
                # LSL Markers are usually strings or lists of strings
                # The router sends a JSON string inside a list: ['{"event": "BLINK", ...}']
                raw_event = sample[0]
                try:
                    event_data = json.loads(raw_event)
                    print(f"[WebServer] ⚡ Event Received: {event_data.get('event')}")
                    # Broadcast to socket
                    socketio.emit('bio_event', event_data)
                except json.JSONDecodeError:
                    print(f"[WebServer] ⚠️  Failed to parse event JSON: {raw_event}")

        except Exception as e:
             # If connection lost, reset inlet
             if "timeout" not in str(e).lower():
                 print(f"[WebServer] ⚠️  Event Loop Error: {e}")
                 state.event_inlet = None
             time.sleep(0.01)

        # Recording State
        self.recording = {
            "active": False,
            "mode": "EMG", # "EMG" or "EOG"
            "label": 0,
            "session_id": None,
            "start_time": 0,
            "extractor": None
        }
        
        # Prediction State
        self.prediction = {
            "active": False,
            "mode": "EOG",
            "extractor": None,
            "detector": None
        }


def broadcast_data():
    """
    Broadcast stream data to all connected clients.
    Optimized: Batches samples to ~30Hz (33ms) to prevent frontend overload.
    """
    print("[WebServer] 📡 Starting broadcast thread (BATCHED)...")
    
    # Batch settings
    BATCH_INTERVAL = 0.033  # 33ms target (approx 30Hz)
    last_batch_time = time.time()
    batch_buffer = []

    while state.running:
        if state.inlet is None:
            time.sleep(0.1)
            continue

        try:
            # Pull sample with short timeout (was 1.0, shorter is fine for loop responsiveness)
            sample, ts = state.inlet.pull_sample(timeout=1.0)
            
            # --- RECORDING LOGIC ---
            if state.recording["active"] and sample:
                try:
                    # Initialize extractor if needed
                    if state.recording["extractor"] is None:
                        mode = state.recording.get("mode", "EMG")
                        target_type = "EMG" if mode == "EMG" else "EOG"
                        
                        # Determine correct channel
                        requested_idx = state.recording.get("channel_index")
                        target_channel = 0
                        
                        if requested_idx is not None:
                             target_channel = requested_idx
                        else:
                            # Auto-find
                            found = False
                            for idx, info in state.channel_mapping.items():
                                 if info.get("type", "").upper() == target_type:
                                     target_channel = idx
                                     found = True
                                     break
                                     
                            # Fallback if specific sensor not found (use ch0)
                            if not found and mode == "EOG":
                                target_channel = 0

                        if mode == "EMG":
                            state.recording["extractor"] = RPSExtractor(
                                channel_index=target_channel, 
                                config={}, 
                                sr=state.sr
                            )
                        else: # EOG
                            # Import here to ensure availability
                            from feature.extractors.blink_extractor import BlinkExtractor
                            state.recording["extractor"] = BlinkExtractor(
                                channel_index=target_channel,
                                config=config_manager.get_all_configs(), # Needs config for thresholds
                                sr=state.sr
                            )
                    
                    # Process sample - this handles buffering and windowing internally
                    target_ch = state.recording["extractor"].channel_index
                    if target_ch < len(sample):
                        val = sample[target_ch] 
                    else:
                        val = 0 # Safety fallback
                    
                    features = state.recording["extractor"].process(val)
                    
                    if features:
                        # Save to DB
                        if state.recording["mode"] == "EMG":
                            db_manager.insert_window(
                                features, 
                                state.recording["label"], 
                                state.recording["session_id"]
                            )
                        else: # EOG
                            db_manager.insert_eog_window(
                                features,
                                state.recording["label"],
                                state.recording["session_id"]
                            )

                except Exception as rec_e:
                    print(f"[WebServer] ⚠️ Recording Error: {rec_e}")
            
            # --- PREDICTION LOGIC ---
            if state.prediction["active"] and sample:
                try:
                    if state.prediction["extractor"] is None:
                        from feature.extractors.blink_extractor import BlinkExtractor
                        from feature.detectors.blink_detector import BlinkDetector
                        
                        target_channel = 0
                        requested_idx = state.prediction.get("channel_index")
                        if requested_idx is not None:
                            target_channel = requested_idx
                        else:
                            for idx, info in state.channel_mapping.items():
                                 if info.get("type", "").upper() == "EOG":
                                     target_channel = idx
                                     break
                        
                        cfg = config_manager.get_all_configs()
                        state.prediction["extractor"] = BlinkExtractor(channel_index=target_channel, config=cfg, sr=state.sr)
                        state.prediction["detector"] = BlinkDetector(config=cfg)
                        print(f"[WebServer] 🔮 Prediction Init on Ch {target_channel}")

                    target_ch = state.prediction["extractor"].channel_index
                    val = sample[target_ch] if target_ch < len(sample) else 0
                    features = state.prediction["extractor"].process(val)
                    
                    if features:
                        label = state.prediction["detector"].detect(features)
                        if label:
                            # Use bio_event to utilize existing frontend hooks
                            socketio.emit('bio_event', {
                                'event': 'prediction',
                                'type': 'EOG', 
                                'label': label, 
                                'timestamp': ts
                            })
                            print(f"[WebServer] 🔮 Prediction: {label}")

                except Exception as pred_e:
                    print(f"[WebServer] ⚠️ Prediction Error: {pred_e}")
            # -----------------------

            if sample is not None and len(sample) == state.num_channels:
                state.sample_count += 1
                
                # ... (rest of broadcast logic unchanged, abbreviated for replacement)
                channels_data = {}
                for ch_idx in range(state.num_channels):
                    ch_mapping = state.channel_mapping.get(ch_idx, {})
                    if not ch_mapping.get("enabled", True): continue
                    channels_data[ch_idx] = {
                        "label": ch_mapping.get("label", f"ch{ch_idx}"),
                        "type": ch_mapping.get("type", "UNKNOWN"),
                        "value": float(sample[ch_idx]),
                        "timestamp": ts
                    }
                batch_buffer.append({
                    "channels": channels_data,
                    "timestamp": ts,
                    "sample_count": state.sample_count
                })

                now = time.time()
                if now - last_batch_time >= BATCH_INTERVAL and len(batch_buffer) > 0:
                    batch_payload = {
                        "stream_name": RAW_STREAM_NAME,
                        "type": "batch",
                        "samples": batch_buffer,
                        "sample_rate": state.sr,
                        "batch_size": len(batch_buffer),
                        "timestamp": now
                    }
                    socketio.emit('bio_data_batch', batch_payload)
                    batch_buffer = []
                    last_batch_time = now
                    if state.sample_count % 512 == 0:
                         print(f"[WebServer] ✅ {state.sample_count} samples broadcast")

        except Exception as e:
            if "timeout" not in str(e).lower():
                print(f"[WebServer] ⚠️  Error broadcasting: {e}")
            time.sleep(0.01)


# ========== FLASK ROUTES ==========


@app.route('/')
def index():
    """Serve main dashboard."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Get server status."""
    return jsonify({
        "status": "ok" if state.connected else "disconnected",
        "connected": state.connected,
        "stream_name": RAW_STREAM_NAME,
        "channels": state.num_channels,
        "sample_rate": state.sr,
        "samples_broadcast": state.sample_count,
        "connected_clients": state.clients,
        "channel_mapping": state.channel_mapping
    })


@app.route('/api/channels')
def api_channels():
    """Get channel information."""
    return jsonify({
        "count": state.num_channels,
        "rate": state.sr,
        "mapping": state.channel_mapping
    })


# ========== CONFIG ENDPOINTS (CRITICAL) ==========


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration."""
    # Force reload from ConfigManager to get latest file changes
    config = load_config()
    state.config = config
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def api_save_config():
    """Save configuration to disk."""
    try:
        config = request.get_json()
        if not config:
            return jsonify({"error": "No config provided"}), 400

        # Validate structure
        if "channel_mapping" not in config:
            config["channel_mapping"] = load_config().get("channel_mapping", {})

        # Save to disk
        success = save_config(config)
        
        # Broadcast to all connected clients
        socketio.emit('config_updated', {
            "status": "saved",
            "config": config
        })

        return jsonify({
            "status": "ok",
            "saved": success,
            "config": config
        })
    except Exception as e:
        print(f"[WebServer] ❌ Error saving config: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/config', methods=['DELETE'])
def api_delete_config():
    """Reset to default configuration."""
    try:
        defaults = load_config()
        save_config(defaults)
        socketio.emit('config_updated', {"status": "reset"})
        return jsonify({"status": "ok", "message": "Config reset to defaults"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/record', methods=['POST'])
def api_record_session():
    """Save a recorded session to disk."""
    try:
        data = request.get_json()
        if not data or 'filename' not in data or 'payload' not in data:
            return jsonify({"error": "Invalid request payload"}), 400

        filename = data['filename']
        payload = data['payload']

        # Path protection: ensure filename is safe
        safe_filename = os.path.basename(filename)
        if not safe_filename.endswith('.json'):
            safe_filename += '.json'

        processed_dir = PROJECT_ROOT / "data" / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = processed_dir / safe_filename

        with open(filepath, 'w') as f:
            json.dump(payload, f, indent=2)

        print(f"[WebServer] 💾 Session saved: {filepath}")
        return jsonify({
            "status": "success",
            "message": f"Session saved to {safe_filename}",
            "path": str(filepath)
        })
    except Exception as e:
        print(f"[WebServer] ❌ Error recording session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/recordings', methods=['GET'])
def api_list_recordings():
    """List all available recordings in data/processed."""
    try:
        processed_dir = PROJECT_ROOT / "data" / "processed"
        if not processed_dir.exists():
            print("[WebServer] 📂 No processed data found")
            return jsonify([])

        recordings = []
        for file in processed_dir.glob('*.json'):
            stat = file.stat()
            print(file.name)
            recordings.append({
                "name": file.name,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "type": file.name.split('__')[0]
            })
            
        # Sort by creation time (newest first)
        recordings.sort(key=lambda x: x['created'], reverse=True)
        return jsonify(recordings)
    except Exception as e:
        print(f"[WebServer] ❌ Error listing recordings: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/recordings/<filename>', methods=['GET'])
def api_get_recording(filename):
    """Get the content of a specific recording."""
    try:
        # Path protection: ensure filename is safe
        safe_filename = os.path.basename(filename)
        processed_dir = PROJECT_ROOT / "data" / "processed"
        filepath = processed_dir / safe_filename

        if not filepath.exists():
            return jsonify({"error": "Recording not found"}), 404

        with open(filepath, 'r') as f:
            data = json.load(f)

        return jsonify(data)
    except Exception as e:
        print(f"[WebServer] ❌ Error getting recording: {e}")
        return jsonify({"error": str(e)}), 500


# ========== WINDOW SAVING & FEATURE EXTRACTION ==========

def extract_eog_features(samples: list, sr: int = 512) -> dict:
    """
    Extract EOG features using BlinkExtractor.
    Restored for compatibility with master logic.
    """
    try:
        from feature.extractors.blink_extractor import BlinkExtractor
        return BlinkExtractor.extract_features(samples, sr)
    except ImportError:
        # Fallback if imports fail (circular dependency risk)
        return {}

def detect_for_sensor(sensor: str, action: str, features: dict, config: dict) -> bool:
    """
    Detect signal using CalibrationManager's unified pipeline.
    Restored for compatibility with master logic.
    """
    detected = calibration_manager.detect_signal(sensor, action, features, config)
    return detected == action or (detected and detected == action)

# Logic moved to CalibrationManager



@app.route('/api/window', methods=['POST'])
def api_save_window():
    """Accept a recorded window, save as CSV, compute features and update config thresholds.

    Expected JSON:
    {
      "sensor": "EMG",
      "channel": 0,
      "action": "Rock",
      "samples": [ ... ],
      "timestamps": [ ... ] (optional)
    }
    """
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No payload provided"}), 400

        result = calibration_manager.save_window(payload)

        # Broadcast via socket for live UI updates
        try:
            socketio.emit('window_saved', {
                "sensor": payload.get('sensor'),
                "action": payload.get('action'),
                "features": result.get("features"),
                "detected": result.get("detected")
            })
        except Exception:
            pass

        print(f"[WebServer] 💾 Window saved: {result.get('csv_path')} (detected={result.get('detected')})")
        return jsonify(result)

    except Exception as e:
        print(f"[WebServer] ❌ Error saving window: {e}")
        return jsonify({"error": str(e)}), 500

# ========== CALIBRATION THRESHOLD OPTIMIZATION ==========


@app.route('/api/calibrate', methods=['POST'])
def api_calibrate():
    """
    Calibrate detection thresholds based on collected windows.
    Delegates to CalibrationManager.
    """
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No payload provided"}), 400
        
        sensor = payload.get('sensor')
        windows = payload.get('windows', [])
        
        if not sensor or not windows:
            return jsonify({"error": "Missing sensor or windows"}), 400
            
        result = calibration_manager.calibrate_sensor(sensor, windows)
        
        # Broadcast config update
        try:
            socketio.emit('config_updated', {"sensor": sensor})
        except Exception:
            pass
        
        print(f"[WebServer] 🎯 Calibration complete for {sensor}")
        return jsonify(result)
    
    except Exception as e:
        print(f"[WebServer] ❌ Calibration error: {e}")
        return jsonify({"error": str(e)}), 500


# ========== TRAINING ENDPOINTS ==========

@app.route('/api/train-emg-rf', methods=['POST'])
def api_train_emg():
    """Train Random Forest Model."""
    try:
        data = request.get_json() or {}
        n_estimators = data.get('n_estimators', 100)
        max_depth = data.get('max_depth', None)
        test_size = data.get('test_size', 0.2)
        
        # Import here to avoid circular dependencies if any
        try:
            from learning.emg_trainer import train_emg_model
        except ImportError:
             import sys
             sys.path.append(str(PROJECT_ROOT / "src"))
             from learning.emg_trainer import train_emg_model

        result = train_emg_model(n_estimators=n_estimators, max_depth=max_depth, test_size=test_size)
        
        if "error" in result:
             return jsonify(result), 400
             
        return jsonify(result)
        
    except Exception as e:
        print(f"[WebServer] ❌ Training error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/model/evaluate', methods=['POST'])
def api_evaluate_emg():
    """Evaluate Saved Model on Full Database."""
    try:
         # Import locally
        try:
            from learning.emg_trainer import evaluate_saved_model
        except ImportError:
             import sys
             sys.path.append(str(PROJECT_ROOT / "src"))
             from learning.emg_trainer import evaluate_saved_model

        result = evaluate_saved_model()
        
        if "error" in result:
             return jsonify(result), 400
             
        return jsonify(result)
    except Exception as e:
        print(f"[WebServer] ❌ Evaluation error: {e}")
        return jsonify({"error": str(e)}), 500


# ========== EMG DATA COLLECTION ENDPOINTS ==========


@app.route('/api/emg/start', methods=['POST'])
def api_start_emg_recording():
    """Start recording EMG data for a specific label."""
    try:
        data = request.get_json()
        label = data.get('label')
        
        if label is None:
            return jsonify({"error": "Label is required"}), 400
            
        label = int(label)
        session_id = f"sess_{int(time.time())}"
        
        # Reset extractor to clear old buffer
        state.recording["extractor"] = None
        
        state.recording.update({
            "active": True,
            "label": label,
            "session_id": session_id,
            "start_time": time.time()
        })
        
        print(f"[WebServer] 🔴 Started EMG Recording: Label {label}, Session {session_id}")
        return jsonify({"status": "started", "session_id": session_id})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/emg/stop', methods=['POST'])
def api_stop_emg_recording():
    """Stop EMG recording."""
    try:
        state.recording["active"] = False
        print(f"[WebServer] ⏹️  Stopped EMG Recording")
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/emg/status', methods=['GET'])
def api_emg_status():
    """Get recording status and database counts."""
    from database.db_manager import db_manager # Ensure import
    
    counts = db_manager.get_counts_by_label()
    
    return jsonify({
        "recording": state.recording["active"],
        "current_label": state.recording["label"],
        "counts": counts
    })


# ========== EOG ENDPOINTS ==========

@app.route('/api/train-eog-rf', methods=['POST'])
def api_train_eog():
    """Train EOG Random Forest Model."""
    try:
        data = request.get_json() or {}
        n_estimators = data.get('n_estimators', 100)
        max_depth = data.get('max_depth', None)
        test_size = data.get('test_size', 0.2)
        
        try:
            from learning.eog_trainer import train_eog_model
        except ImportError:
             import sys
             sys.path.append(str(PROJECT_ROOT / "src"))
             from learning.eog_trainer import train_eog_model

        result = train_eog_model(n_estimators=n_estimators, max_depth=max_depth, test_size=test_size)
        
        if "error" in result:
             return jsonify(result), 400
             
        return jsonify(result)
        
    except Exception as e:
        print(f"[WebServer] ❌ EOG Training error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/model/evaluate/eog', methods=['POST'])
def api_evaluate_eog():
    """Evaluate Saved EOG Model."""
    try:
        try:
            from learning.eog_trainer import evaluate_saved_eog_model
        except ImportError:
             import sys
             sys.path.append(str(PROJECT_ROOT / "src"))
             from learning.eog_trainer import evaluate_saved_eog_model

        result = evaluate_saved_eog_model()
        if "error" in result:
             return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/eog/data', methods=['DELETE'])
def api_clear_eog_data():
    """Clear all EOG data."""
    try:
        from database.db_manager import db_manager
        result = db_manager.clear_eog_data()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/eog/start', methods=['POST'])
def api_start_eog_recording():
    """Start recording EOG data."""
    try:
        data = request.get_json()
        label = data.get('label')
        channel = data.get('channel')
        
        if label is None: return jsonify({"error": "Label required"}), 400
            
        label = int(label)
        session_id = f"sess_eog_{int(time.time())}"
        
        state.recording["extractor"] = None # Reset
        state.recording.update({
            "active": True,
            "mode": "EOG",
            "label": label,
            "channel_index": int(channel) if channel is not None else None,
            "session_id": session_id,
            "start_time": time.time()
        })
        
        print(f"[WebServer] 👁️ Started EOG Recording: Label {label} (Ch {channel})")
        return jsonify({"status": "started", "session_id": session_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/eog/stop', methods=['POST'])
def api_stop_eog_recording():
    """Stop EOG recording."""
    try:
        state.recording["active"] = False
        print(f"[WebServer] ⏹️  Stopped EOG Recording")
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/eog/status', methods=['GET'])
def api_eog_status():
    """Get EOG recording status and counts."""
    from database.db_manager import db_manager
    counts = db_manager.get_eog_counts()
    return jsonify({
        "recording": state.recording["active"] and state.recording.get("mode") == "EOG",
        "current_label": state.recording["label"],
        "channel_index": state.recording.get("channel_index"),
        "counts": counts
    })


@app.route('/api/eog/predict/start', methods=['POST'])
def api_start_eog_predict():
    """Start live EOG prediction."""
    try:
        data = request.get_json() or {}
        channel = data.get('channel')
        
        state.prediction["extractor"] = None # Reset
        state.prediction["detector"] = None  # Reset to force model reload
        state.prediction.update({
            "active": True,
            "mode": "EOG",
            "channel_index": int(channel) if channel is not None else None
        })
        print(f"[WebServer] 🔮 Started EOG Prediction Mode (Ch {channel}) - Model Reload Triggered")
        return jsonify({"status": "started"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/eog/predict/stop', methods=['POST'])
def api_stop_eog_predict():
    """Stop live EOG prediction."""
    try:
        state.prediction["active"] = False
        print(f"[WebServer] ⏹️  Stopped EOG Prediction Mode")
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========== SOCKETIO EVENTS ==========


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    state.clients += 1
    print(f"[WebServer] 🔗 Client connected (total: {state.clients})")
    emit('response', {'data': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    state.clients = max(0, state.clients - 1)
    print(f"[WebServer] 🔗 Client disconnected (total: {state.clients})")


@socketio.on('request_status')
def handle_status_request():
    """Handle status request from client."""
    emit('status', {
        'connected': state.connected,
        'channels': state.num_channels,
        'rate': state.sr,
        'mapping': state.channel_mapping
    })


@socketio.on('ping')
def handle_ping():
    """Handle ping from client for latency measurement."""
    emit('pong')


# ========== CONFIG MESSAGE HANDLER (CRITICAL) ==========


@socketio.on('message')
def handle_message(data):
    """Handle messages from client."""
    try:
        msg_type = data.get('type')
        
        if msg_type == 'SAVE_CONFIG':
            config = data.get('config')
            if config:
                print("[WebServer] 💾 Received SAVE_CONFIG message")
                success = save_config(config)
                emit('config_response', {
                    "status": "saved" if success else "failed",
                    "config": config
                })
            else:
                print("[WebServer] ⚠️  No config in SAVE_CONFIG message")
        
        elif msg_type == 'REQUEST_CONFIG':
            print("[WebServer] 📡 Received REQUEST_CONFIG message")
            config = state.config or load_config()
            emit('config_response', {"status": "ok", "config": config})
        
        else:
            print(f"[WebServer] ℹ️  Unknown message type: {msg_type}")
            
    except Exception as e:
        print(f"[WebServer] ❌ Error handling message: {e}")


# ========== MAIN ==========


def main():
    """Main entry point."""
    print("=" * 70)
    print(" 🧬 BioSignals WebSocket Server - FIXED VERSION")
    print(" Real-time Multi-Channel Signal Streaming")
    print(" Config Persistence Enabled")
    print("=" * 70)
    print()

    # Load config from disk first
    state.config = load_config()

    # Resolve LSL stream
    if not resolve_lsl_stream():
        print("[WebServer] ❌ Failed to connect to LSL stream")
        print("[WebServer] Starting server anyway (will wait for stream)")

    # Start broadcast thread
    state.running = True
    broadcast_thread = threading.Thread(target=broadcast_data, daemon=True)
    broadcast_thread.start()
    
    # Start Event listener thread
    event_thread = threading.Thread(target=broadcast_events, daemon=True)
    event_thread.start()

    print("[WebServer] ✅ Background threads started")
    print()

    port = state.config.get("server_port", 5000)

    # Start SocketIO server
    print("[WebServer] 🚀 Starting WebSocket server...")
    print(f"[WebServer] 📡 WebSocket endpoint: ws://localhost:{port}")
    print(f"[WebServer] 🌐 Dashboard: http://localhost:{port}")
    print(f"[WebServer] 📊 API: http://localhost:{port}/api/status")
    print(f"[WebServer] ⚙️  Config: http://localhost:{port}/api/config")
    print()

    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n[WebServer] ⏹️  Shutting down...")
    finally:
        state.running = False
        if state.inlet:
            try:
                state.inlet.close_stream()
            except:
                pass
        print("[WebServer] ✅ Cleanup complete")


if __name__ == "__main__":
    main()

