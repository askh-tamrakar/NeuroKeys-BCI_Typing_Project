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


# ========== Configuration ==========


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
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

state = WebServerState()


# ========== CONFIG MANAGEMENT ==========


def load_config() -> dict:
    """Load channel mapping from disk or return defaults."""
    defaults = {
        "sampling_rate": DEFAULT_SR,
        "channel_mapping": {
            "ch0": {
                "sensor": "EMG", 
                "enabled": True
            },
            "ch1": {
                "sensor": "EEG", 
                "enabled": True
            }
        },
        "filters": {
            "EMG": {
                "type": "high_pass",
                "cutoff": 70.0,
                "order": 4
            },
            "EOG": {
                "type": "low_pass",
                "cutoff": 10.0,
                "order": 4
            },
            "EEG": {
                "filters": [ 
                    {
                        "type": "notch",
                        "freq": 50,
                        "Q": 30
                    },  
                    {
                        "type": "bandpass",
                        "low": 0.5,
                        "high": 45,
                        "order": 4
                    }
                ]
            }
        },
        "display": {
            "timeWindowMs": 10000,
            "showGrid": True,
            "scannerX": 0
        },
        "num_channels": 2
    }

    if not CONFIG_PATH.exists():
        print(f"[WebServer] Config file not found at {CONFIG_PATH}")
        return defaults

    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        print(f"[WebServer] Loaded config from {CONFIG_PATH}")
        
        # Convert new sensor-based format to legacy format for compatibility
        if "sensors" in cfg:
            # New format: sensors.EEG.filters, sensors.EMG.filters, etc.
            filters = {}
            features = {}
            
            for sensor_name, sensor_cfg in cfg.get("sensors", {}).items():
                # Extract filters
                if "filters" in sensor_cfg:
                    sensor_filters = sensor_cfg["filters"]
                    if len(sensor_filters) == 1:
                        # Single filter - flatten it
                        filters[sensor_name] = sensor_filters[0]
                    else:
                        # Multiple filters - keep as list
                        filters[sensor_name] = {"filters": sensor_filters}
                
                # Extract features
                if "features" in sensor_cfg:
                    features[sensor_name] = sensor_cfg["features"]
            
            cfg["filters"] = filters
            cfg["features"] = features
        
        # Merge with defaults to ensure all keys present
        merged = {**defaults, **cfg}
        # Deep merge for nested objects
        if 'channel_mapping' in cfg:
            merged['channel_mapping'] = {**defaults.get('channel_mapping', {}), **cfg['channel_mapping']}
        return merged
    except Exception as e:
        print(f"[WebServer] Error loading config: {e}")
        return defaults


def save_config(config: dict) -> bool:
    """Save config to disk."""
    try:
        # Validate config structure
        if not isinstance(config, dict):
            raise ValueError("Config must be dict")
        
        # Ensure directory exists
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to file
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"[WebServer] 💾 Config saved to {CONFIG_PATH}")
        state.config = config
        return True
    except Exception as e:
        print(f"[WebServer] ❌ Error saving config: {e}")
        return False


# ========== HELPER FUNCTIONS ==========


def create_channel_mapping(lsl_info) -> Dict:
    """Create channel mapping from LSL stream info."""
    mapping = {}
    config = state.config or load_config()
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
        streams = pylsl.resolve_stream('name', EVENT_STREAM_NAME)
        
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
                print(f"[WebServer] ⚡ Event Received: {raw_event}")
                
                try:
                    event_data = json.loads(raw_event)
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

def broadcast_data():
    """Broadcast stream data to all connected clients."""
    print("[WebServer] 📡 Starting broadcast thread...")

    while state.running:
        if state.inlet is None:
            time.sleep(0.1)
            continue

        try:
            sample, ts = state.inlet.pull_sample(timeout=1.0)

            if sample is not None and len(sample) == state.num_channels:
                state.sample_count += 1

                # Format data for broadcasting
                channels_data = {}
                for ch_idx in range(state.num_channels):
                    ch_mapping = state.channel_mapping.get(ch_idx, {})
                    channels_data[ch_idx] = {
                        "label": ch_mapping.get("label", f"ch{ch_idx}"),
                        "type": ch_mapping.get("type", "UNKNOWN"),
                        "value": float(sample[ch_idx]),
                        "timestamp": ts
                    }

                data = {
                    "stream_name": RAW_STREAM_NAME,
                    "channels": channels_data,
                    "channel_count": state.num_channels,
                    "sample_rate": state.sr,
                    "sample_count": state.sample_count,
                    "timestamp": ts
                }

                socketio.emit('bio_data_update', data)

                # Log progress every 512 samples
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
    config = state.config or load_config()
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


def compute_features(samples):
    """Compute a basic set of time-domain features for a 1-D signal window.

    Returns a dict of feature_name -> value.
    """
    if not samples:
        return {}

    # ensure floats
    xs = [float(x) for x in samples]
    n = len(xs)

    energy = sum(x * x for x in xs)
    iemg = sum(abs(x) for x in xs)
    mav = iemg / n if n else 0.0
    peak = max(abs(x) for x in xs)
    rng = max(xs) - min(xs)
    mean_sq = sum(x * x for x in xs) / n if n else 0.0
    rms = math.sqrt(mean_sq)
    var = statistics.pvariance(xs) if n > 1 else 0.0
    wl = sum(abs(xs[i] - xs[i - 1]) for i in range(1, n)) if n > 1 else 0.0

    # zero-crossing rate (relative)
    zc_count = 0
    for i in range(1, n):
        if xs[i - 1] == 0 or xs[i] == 0:
            continue
        if (xs[i - 1] > 0) != (xs[i] > 0):
            zc_count += 1
    zcr = zc_count / (n - 1) if n > 1 else 0.0

    # approximate entropy using amplitude histogram
    try:
        bins = 20
        lo = min(xs)
        hi = max(xs)
        if hi == lo:
            entropy = 0.0
        else:
            width = (hi - lo) / bins
            counts = [0] * bins
            for v in xs:
                idx = int((v - lo) / width)
                if idx >= bins:
                    idx = bins - 1
                counts[idx] += 1
            probs = [c / n for c in counts if c > 0]
            entropy = -sum(p * math.log2(p) for p in probs)
    except Exception:
        entropy = 0.0

    features = {
        "energy": energy,
        "entropy": entropy,
        "iemg": iemg,
        "mav": mav,
        "peak": peak,
        "range": rng,
        "rms": rms,
        "var": var,
        "wl": wl,
        "zcr": zcr
    }

    return features


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

        sensor = payload.get('sensor')
        action = payload.get('action')
        channel = payload.get('channel', None)
        samples = payload.get('samples')
        timestamps = payload.get('timestamps', None)

        # samples may be an empty list (allowed). Ensure required keys exist.
        if sensor is None or action is None or samples is None:
            return jsonify({"error": "Missing required fields: sensor, action, samples"}), 400

        # Create output directories
        windows_dir = PROJECT_ROOT / 'data' / 'processed' / 'windows' / sensor / action
        windows_dir.mkdir(parents=True, exist_ok=True)

        ts = time.time()
        safe_name = f"window__{action}__{int(ts)}__ch{channel if channel is not None else 'na'}.csv"
        csv_path = windows_dir / safe_name

        # Save CSV: timestamp,value
        with open(csv_path, 'w') as f:
            f.write('timestamp,value\n')
            if timestamps and len(timestamps) == len(samples):
                for t, v in zip(timestamps, samples):
                    f.write(f"{t},{v}\n")
            else:
                # write sample index as time
                for i, v in enumerate(samples):
                    f.write(f"{i},{v}\n")

        # Compute features
        features = compute_features(samples)

        # Save features JSON alongside CSV
        feat_path = csv_path.with_suffix('.features.json')
        with open(feat_path, 'w') as f:
            json.dump({"features": features, "sensor": sensor, "action": action, "channel": channel, "saved_at": ts}, f, indent=2)

        # Load config and update thresholds for sensor/action
        cfg = state.config or load_config()
        cfg_features = cfg.setdefault('features', {})
        sensor_features = cfg_features.setdefault(sensor, {})

        # Ensure action entry exists
        action_entry = sensor_features.setdefault(action, {})

        updated = {}
        matches = 0
        total = 0

        for k, val in features.items():
            total += 1
            old_range = action_entry.get(k)
            # if existing range, check match
            if isinstance(old_range, list) and len(old_range) == 2:
                lo, hi = float(old_range[0]), float(old_range[1])
                if lo <= val <= hi:
                    matches += 1
                # expand range to include observed value
                new_lo = min(lo, val)
                new_hi = max(hi, val)
                action_entry[k] = [new_lo, new_hi]
                updated[k] = [new_lo, new_hi]
            else:
                # create initial range +/-10%
                if val == 0:
                    new_lo, new_hi = 0.0, 0.0
                else:
                    new_lo = val * 0.9
                    new_hi = val * 1.1
                action_entry[k] = [new_lo, new_hi]
                updated[k] = [new_lo, new_hi]

        # Save updated config to disk
        save_success = save_config(cfg)

        # Simple detection: majority of features fall within the target action ranges
        detected = (matches / total) >= 0.6 if total > 0 else False

        result = {
            "status": "saved",
            "csv_path": str(csv_path),
            "features": features,
            "detected": detected,
            "updated_thresholds": updated,
            "config_saved": save_success
        }

        # Broadcast via socket for live UI updates
        try:
            socketio.emit('window_saved', {"sensor": sensor, "action": action, "features": features, "detected": detected})
        except Exception:
            pass

        print(f"[WebServer] 💾 Window saved: {csv_path} (detected={detected})")
        return jsonify(result)

    except Exception as e:
        print(f"[WebServer] ❌ Error saving window: {e}")
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

    # ===== MONITOR CONFIG CHANGES & BROADCAST TO WEBSOCKET =====
    def monitor_config_changes():
        """Monitor config via ConfigWatcher and broadcast changes."""
        last_config = state.config.copy() if state.config else {}
        
        while state.running:
            try:
                current_config = state.config.copy() if state.config else {}
                
                # If config changed, broadcast to all WebSocket clients
                if current_config != last_config:
                    print("[WebServer] 🔔 Config changed - broadcasting to clients...")
                    socketio.emit('config_updated', {
                        'status': 'config_changed',
                        'config': current_config,
                        'source': 'acquisition_app'
                    }, broadcast=True)
                    last_config = current_config
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                print(f"[WebServer] ⚠️ Config monitor error: {e}")
                time.sleep(1)


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

    # Start SocketIO server
    print("[WebServer] 🚀 Starting WebSocket server...")
    print(f"[WebServer] 📡 WebSocket endpoint: ws://localhost:5000")
    print(f"[WebServer] 🌐 Dashboard: http://localhost:5000")
    print(f"[WebServer] 📊 API: http://localhost:5000/api/status")
    print(f"[WebServer] ⚙️  Config: http://localhost:5000/api/config")
    print()

    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
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

