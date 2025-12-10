# web_server.py - FIXED VERSION with CONFIG ENDPOINTS
# 
# Critical additions:
# 1. /api/config GET/POST endpoints for config persistence
# 2. SAVE_CONFIG message handler for websocket
# 3. Proper config merging and validation


import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional


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


RAW_STREAM_NAME = "BioSignals-Processed"
LSL_TIMEOUT = 3.0
DEFAULT_SR = 512


# Ensure config directory exists
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


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


# ========== Global State ==========


class WebServerState:
    def __init__(self):
        self.inlet = None
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
        "sampling_rate": 512,
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
        print(f"[WebServer] ℹ️  Config file not found at {CONFIG_PATH}")
        return defaults

    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        print(f"[WebServer] ✅ Loaded config from {CONFIG_PATH}")
        # Merge with defaults to ensure all keys present
        merged = {**defaults, **cfg}
        # Deep merge for nested objects
        if 'channel_mapping' in cfg:
            merged['channel_mapping'] = {**defaults.get('channel_mapping', {}), **cfg['channel_mapping']}
        return merged
    except Exception as e:
        print(f"[WebServer] ⚠️  Error loading config: {e}")
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
    print("[WebServer] ✅ Broadcast thread started")
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
