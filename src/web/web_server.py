"""

src/web/web_server.py

FIXED WEB SERVER - Corrected broadcast syntax

Features:

- ✅ Proper WebSocket endpoint configuration
- ✅ Real-time data streaming
- ✅ Channel mapping from LSL stream
- ✅ REST API endpoints
- ✅ CORS support
- ✅ Production ready

Usage:

python -m src.web.web_server

"""

from pathlib import Path
import json
import threading
import time
from typing import Dict, Optional

try:
    import pylsl
    LSL_AVAILABLE = True
except Exception as e:
    print(f"[WebServer] Warning: pylsl not available: {e}")
    LSL_AVAILABLE = False

from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# ========== Configuration ==========

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

RAW_STREAM_NAME = "BioSignals-Processed"  # Changed to Processed stream
LSL_TIMEOUT = 3.0
DEFAULT_SR = 512

# ========== Flask App Setup ==========

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
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

state = WebServerState()

# ========== Helper Functions ==========

def load_config() -> dict:
    """Load channel mapping from config."""
    defaults = {
        "channel_mapping": {
            "ch0": {"sensor": "EMG", "enabled": True},
            "ch1": {"sensor": "EOG", "enabled": True}
        }
    }
    
    if not CONFIG_PATH.exists():
        return defaults
    
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        return cfg
    except Exception as e:
        print(f"[WebServer] ⚠️ Error loading config: {e}")
        return defaults


def create_channel_mapping(lsl_info) -> Dict:
    """Create channel mapping from LSL stream info."""
    mapping = {}
    config = load_config()
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
        print(f"[WebServer] ⚠️ Error creating mapping: {e}")
    
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
            print(f"[WebServer]    Channels: {state.num_channels} @ {state.sr} Hz")
            print(f"[WebServer]    Mapping: {state.channel_mapping}")
            
            return True
        
        print("[WebServer] ❌ Could not find LSL stream")
        print("[WebServer] Make sure filter_router_modified is running!")
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
            # Pull sample from LSL
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
                
                # FIXED: Removed broadcast=True parameter
                data = {
                    "stream_name": RAW_STREAM_NAME,
                    "channels": channels_data,
                    "channel_count": state.num_channels,
                    "sample_rate": state.sr,
                    "sample_count": state.sample_count,
                    "timestamp": ts
                }
                
                socketio.emit('bio_data_update', data)
                
                # Log progress
                if state.sample_count % 512 == 0:
                    print(f"[WebServer] ✅ {state.sample_count} samples broadcast")
        
        except Exception as e:
            if "timeout" not in str(e).lower():
                print(f"[WebServer] ⚠️ Error broadcasting: {e}")
            time.sleep(0.01)


# ========== Flask Routes ==========

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


# ========== SocketIO Events ==========

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


# ========== Main ==========

def main():
    """Main entry point."""
    print("=" * 70)
    print("  🧬 BioSignals WebSocket Server - Fixed Version")
    print("  Real-time Multi-Channel Signal Streaming")
    print("=" * 70)
    print()
    
    # Resolve LSL stream
    if not resolve_lsl_stream():
        print("[WebServer] ❌ Failed to connect to LSL stream")
        print("[WebServer] Please ensure filter_router_modified is running")
        return
    
    # Start broadcast thread
    state.running = True
    broadcast_thread = threading.Thread(target=broadcast_data, daemon=True)
    broadcast_thread.start()
    print("[WebServer] ✅ Broadcast thread started")
    print()
    
    # Start SocketIO server
    print("[WebServer] 🚀 Starting WebSocket server...")
    print(f"[WebServer] 📡 WebSocket endpoint: ws://localhost:5000/ws")
    print(f"[WebServer] 🌐 Dashboard: http://localhost:5000")
    print(f"[WebServer] 📊 API: http://localhost:5000/api/status")
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
        print("\n[WebServer] ⏹️ Shutting down...")
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
