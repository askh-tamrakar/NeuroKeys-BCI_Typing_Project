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
from scipy import stats as scipy_stats
from scipy import signal as scipy_signal


# ========== Configuration ==========


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "sensor_config.json"
FILTER_CONFIG_PATH = PROJECT_ROOT / "config" / "filter_config.json"
TEMPLATES_DIR = PROJECT_ROOT / "src" / "web" / "frontend" / "dist"
DEFAULT_SR = 512

RAW_STREAM_NAME = "BioSignals-Processed"
EVENT_STREAM_NAME = "BioSignals-Events"


# ========== Flask App Setup ==========

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR) if TEMPLATES_DIR.exists() else None,
    static_folder=str(TEMPLATES_DIR / "assets") if (TEMPLATES_DIR / "assets").exists() else None,
    static_url_path="/assets"
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
    """Load config from sensor_config.json and filter_config.json, returning a merged view."""
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
             "EMG": {"cutoff": 20.0, "order": 4, "notch_enabled": True, "notch_freq": 50, "bandpass_enabled": True, "bandpass_low": 20, "bandpass_high": 250},
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

    merged = defaults.copy()

    # 1. Load Sensor Config
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            # Merge with defaults
            merged.update(cfg)
            # Deep merge channel_mapping if needed
            if 'channel_mapping' in cfg:
                merged['channel_mapping'] = {**defaults.get('channel_mapping', {}), **cfg['channel_mapping']}
        except Exception as e:
             print(f"[WebServer] ⚠️  Error loading sensor config: {e}")
    else:
        print(f"[WebServer] ℹ️  Config file not found at {CONFIG_PATH}")

    # 2. Load Filter Config (Overrides 'filters' key)
    if FILTER_CONFIG_PATH.exists():
        try:
             with open(FILTER_CONFIG_PATH) as f:
                filter_cfg = json.load(f)
             if 'filters' in filter_cfg:
                 merged['filters'] = filter_cfg['filters']
        except Exception as e:
            print(f"[WebServer] ⚠️  Error loading filter config: {e}")

    return merged


def save_config(config: dict) -> bool:
    """Save config to disk (Splits into sensor_config.json and filter_config.json)."""
    try:
        if not isinstance(config, dict):
            raise ValueError("Config must be dict")
        
        # Ensure directory exists
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # 1. Save Filters to filter_config.json
        if 'filters' in config:
            filter_payload = {"filters": config['filters']}
            with open(FILTER_CONFIG_PATH, 'w') as f:
                json.dump(filter_payload, f, indent=2)
            print(f"[WebServer] 💾 Filters saved to {FILTER_CONFIG_PATH}")

        # 2. Save Sensor/Display Config to sensor_config.json (exclude filters)
        sensor_payload = config.copy()
        if 'filters' in sensor_payload:
            del sensor_payload['filters']
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(sensor_payload, f, indent=2)
        
        print(f"[WebServer] 💾 Sensor config saved to {CONFIG_PATH}")
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
            # Pull sample with short timeout
            sample, ts = state.inlet.pull_sample(timeout=1.0)

            if sample is not None and len(sample) == state.num_channels:
                state.sample_count += 1

                # Format single sample
                channels_data = {}
                for ch_idx in range(state.num_channels):
                    ch_mapping = state.channel_mapping.get(ch_idx, {})
                    channels_data[ch_idx] = {
                        "label": ch_mapping.get("label", f"ch{ch_idx}"),
                        "type": ch_mapping.get("type", "UNKNOWN"),
                        "value": float(sample[ch_idx]),
                        "timestamp": ts
                    }

                # Add to batch buffer
                batch_buffer.append({
                    "channels": channels_data,
                    "timestamp": ts,
                    "sample_count": state.sample_count
                })

                # Check if it's time to flush batch
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
                    
                    # Reset buffer
                    batch_buffer = []
                    last_batch_time = now

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


@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route for SPA (React Router)."""
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


def extract_emg_features(samples: list, sr: int = 512) -> dict:
    """Extract EMG features matching RPSExtractor.
    
    Features: rms, mav, zcr, var, wl, peak, range, iemg, entropy, energy
    """
    if not samples or len(samples) < 2:
        return {}
    
    data = np.array(samples, dtype=float)
    n = len(data)
    
    # Core EMG features (matching rps_extractor.py)
    rms = float(np.sqrt(np.mean(data**2)))
    mav = float(np.mean(np.abs(data)))
    zcr = float(((data[:-1] * data[1:]) < 0).sum() / n)
    var = float(np.var(data))
    wl = float(np.sum(np.abs(np.diff(data))))
    peak = float(np.max(np.abs(data)))
    rng = float(np.ptp(data))
    iemg = float(np.sum(np.abs(data)))
    energy = float(np.sum(data**2))
    
    # Entropy via histogram
    try:
        hist, _ = np.histogram(data, bins=10, density=True)
        hist = hist[hist > 0]
        entropy = float(-np.sum(hist * np.log2(hist))) if len(hist) > 0 else 0.0
    except Exception:
        entropy = 0.0
    
    return {
        "rms": rms,
        "mav": mav,
        "zcr": zcr,
        "var": var,
        "wl": wl,
        "peak": peak,
        "range": rng,
        "iemg": iemg,
        "entropy": entropy,
        "energy": energy
    }


def extract_eog_features(samples: list, sr: int = 512) -> dict:
    """Extract EOG blink features matching BlinkExtractor.
    
    Features: amplitude, duration_ms, rise_time_ms, fall_time_ms, asymmetry, kurtosis, skewness
    """
    if not samples or len(samples) < 2:
        return {}
    
    data = np.array(samples, dtype=float)
    abs_data = np.abs(data)
    n = len(data)
    
    peak_idx = int(np.argmax(abs_data))
    peak_amp = float(abs_data[peak_idx])
    
    duration_ms = float((n / sr) * 1000.0)
    rise_time_ms = float((peak_idx / sr) * 1000.0)
    fall_time_ms = float(((n - peak_idx) / sr) * 1000.0)
    
    asymmetry = float(rise_time_ms / (fall_time_ms + 1e-6))
    
    # Statistical features
    kurt = float(scipy_stats.kurtosis(data))
    skew = float(scipy_stats.skew(data))
    
    return {
        "amplitude": peak_amp,
        "duration_ms": duration_ms,
        "rise_time_ms": rise_time_ms,
        "fall_time_ms": fall_time_ms,
        "asymmetry": asymmetry,
        "kurtosis": kurt,
        "skewness": skew
    }


def extract_eeg_features(samples: list, sr: int = 512) -> dict:
    """Extract EEG features matching EEGExtractor.
    
    Features: band powers (delta, theta, alpha, beta) and relative powers
    """
    if not samples or len(samples) < 16:
        return {}
    
    data = np.array(samples, dtype=float)
    
    # Welch's periodogram
    try:
        freqs, psd = scipy_signal.welch(data, sr, nperseg=min(len(data), 256))
    except Exception:
        return {}
    
    freq_bands = {
        "delta": (0.5, 4),
        "theta": (4, 8),
        "alpha": (8, 13),
        "beta": (13, 30)
    }
    
    features = {}
    total_power = 0.0
    
    for band, (low, high) in freq_bands.items():
        idx = np.logical_and(freqs >= low, freqs <= high)
        power = float(np.sum(psd[idx]))
        features[band] = power
        total_power += power
    
    features["total_power"] = total_power
    
    # Relative powers
    if total_power > 0:
        for band in freq_bands.keys():
            features[f"{band}_rel"] = features[band] / total_power
    
    return features


def extract_features_for_sensor(sensor: str, samples: list, sr: int = 512) -> dict:
    """Route to sensor-specific feature extraction."""
    sensor = sensor.upper()
    
    if sensor == "EMG":
        return extract_emg_features(samples, sr)
    elif sensor == "EOG":
        return extract_eog_features(samples, sr)
    elif sensor == "EEG":
        return extract_eeg_features(samples, sr)
    else:
        # Fallback to EMG features for unknown sensors
        return extract_emg_features(samples, sr)


def detect_for_sensor(sensor: str, action: str, features: dict, config: dict) -> bool:
    """Run sensor-specific detection logic matching the detectors."""
    sensor = sensor.upper()
    sensor_cfg = config.get("features", {}).get(sensor, {})
    
    if sensor == "EOG":
        # BlinkDetector logic
        if not features:
            return False
        
        min_duration = sensor_cfg.get("min_duration_ms", 100.0)
        max_duration = sensor_cfg.get("max_duration_ms", 600.0)
        min_asymmetry = sensor_cfg.get("min_asymmetry", 0.05)
        max_asymmetry = sensor_cfg.get("max_asymmetry", 2.5)
        min_kurtosis = sensor_cfg.get("min_kurtosis", -3.0)
        
        dur = features.get("duration_ms", 0)
        asym = features.get("asymmetry", 0)
        kurt = features.get("kurtosis", 0)
        
        is_valid_duration = min_duration <= dur <= max_duration
        is_valid_asymmetry = min_asymmetry <= asym <= max_asymmetry
        is_valid_shape = kurt >= min_kurtosis
        
        return is_valid_duration and is_valid_asymmetry and is_valid_shape
    
    elif sensor == "EMG":
        # RPSDetector logic - check if features match action profile
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
            return score >= 0.6  # Consensus threshold
        return False
    
    elif sensor == "EEG":
        # EEGDetector logic
        profiles = sensor_cfg.get("profiles", {})
        action_profile = profiles.get(action, {})
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
            return (match_count / total_features) >= 0.6
        return False
    
    return False


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

        # Compute features using sensor-specific extraction
        sr = state.config.get('sampling_rate', 512) if state.config else 512
        features = extract_features_for_sensor(sensor, samples, sr)

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

        # Use sensor-specific detection logic
        detected = detect_for_sensor(sensor, action, features, cfg)

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

# ========== CALIBRATION THRESHOLD OPTIMIZATION ==========


@app.route('/api/calibrate', methods=['POST'])
def api_calibrate():
    """
    Calibrate detection thresholds based on collected windows.
    
    Uses percentile-based approach to compute optimal feature ranges
    from labeled windows, excluding outliers.
    
    Expected JSON:
    {
        "sensor": "EOG",
        "windows": [
            {"action": "blink", "features": {...}, "status": "correct"},
            ...
        ]
    }
    
    Returns:
    {
        "updated_thresholds": {...},
        "accuracy_before": 0.65,
        "accuracy_after": 0.92,
        "samples_per_action": {"blink": 20, "Rest": 15},
        "recommended_samples": 20
    }
    """
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No payload provided"}), 400
        
        sensor = payload.get('sensor')
        windows = payload.get('windows', [])
        
        if not sensor or not windows:
            return jsonify({"error": "Missing sensor or windows"}), 400
        
        # Group windows by action
        windows_by_action = {}
        for w in windows:
            action = w.get('action')
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
        
        # Calculate accuracy before calibration
        total_before = len(windows)
        correct_before = sum(1 for w in windows if w.get('status') == 'correct')
        accuracy_before = correct_before / total_before if total_before > 0 else 0
        
        # Compute optimal thresholds using percentile approach
        updated_thresholds = {}
        samples_per_action = {}
        
        for action, action_windows in windows_by_action.items():
            samples_per_action[action] = len(action_windows)
            
            if len(action_windows) < 3:
                # Not enough samples for reliable thresholds
                continue
            
            # Collect all feature values
            feature_values = {}
            for w in action_windows:
                for feat_name, feat_val in w['features'].items():
                    if isinstance(feat_val, (int, float)):
                        if feat_name not in feature_values:
                            feature_values[feat_name] = []
                        feature_values[feat_name].append(feat_val)
            
            # Compute percentile-based ranges (5th-95th to exclude outliers)
            action_thresholds = {}
            for feat_name, values in feature_values.items():
                if len(values) >= 3:
                    sorted_vals = sorted(values)
                    n = len(sorted_vals)
                    # 5th percentile
                    idx_lo = max(0, int(n * 0.05))
                    # 95th percentile
                    idx_hi = min(n - 1, int(n * 0.95))
                    
                    min_val = sorted_vals[idx_lo]
                    max_val = sorted_vals[idx_hi]
                    
                    # Add small margin (5%)
                    margin = (max_val - min_val) * 0.05 if max_val != min_val else abs(min_val) * 0.1
                    action_thresholds[feat_name] = [
                        round(min_val - margin, 4),
                        round(max_val + margin, 4)
                    ]
            
            if action_thresholds:
                updated_thresholds[action] = action_thresholds
        
        # Load current config and update thresholds
        cfg = state.config or load_config()
        cfg_features = cfg.setdefault('features', {})
        sensor_features = cfg_features.setdefault(sensor, {})
        
        # Update thresholds for each action
        for action, thresholds in updated_thresholds.items():
            if action not in sensor_features:
                sensor_features[action] = {}
            sensor_features[action].update(thresholds)
        
        # Also update global sensor thresholds for detection (EOG specific)
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
        
        # Save updated config
        save_success = save_config(cfg)
        
        # Recalculate accuracy with new thresholds (simulate)
        correct_after = 0
        for w in windows:
            action = w.get('action')
            features = w.get('features', {})
            if action in updated_thresholds:
                # Check if features fall within new thresholds
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
        
        # Recommended sample count based on sensor type
        recommended_samples = {
            'EOG': 20,
            'EMG': 30,
            'EEG': 25
        }.get(sensor, 20)
        
        result = {
            "status": "calibrated",
            "updated_thresholds": updated_thresholds,
            "accuracy_before": round(accuracy_before, 4),
            "accuracy_after": round(accuracy_after, 4),
            "samples_per_action": samples_per_action,
            "recommended_samples": recommended_samples,
            "config_saved": save_success
        }
        
        # Broadcast config update
        try:
            socketio.emit('config_updated', {"sensor": sensor})
        except Exception:
            pass
        
        print(f"[WebServer] 🎯 Calibration complete: {sensor} | Accuracy: {accuracy_before:.1%} → {accuracy_after:.1%}")
        return jsonify(result)
    
    except Exception as e:
        print(f"[WebServer] ❌ Calibration error: {e}")
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

