from flask import Blueprint, jsonify, request
from pathlib import Path
import json
import os

recording_bp = Blueprint('recording', __name__)

# Paths
# src/web/server/routes/recording_routes.py -> ../../../../ = root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

@recording_bp.route('/api/record', methods=['POST'])
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

        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        filepath = PROCESSED_DATA_DIR / safe_filename

        with open(filepath, 'w') as f:
            json.dump(payload, f, indent=2)

        print(f"[Recording_Routes] 💾 Session saved: {filepath}")
        return jsonify({
            "status": "success",
            "message": f"Session saved to {safe_filename}",
            "path": str(filepath)
        })
    except Exception as e:
        print(f"[Recording_Routes] ❌ Error recording session: {e}")
        return jsonify({"error": str(e)}), 500


@recording_bp.route('/api/recordings', methods=['GET'])
def api_list_recordings():
    """List all available recordings in data/processed."""
    try:
        if not PROCESSED_DATA_DIR.exists():
            print("[Recording_Routes] 📂 No processed data found")
            return jsonify([])

        recordings = []
        for file in PROCESSED_DATA_DIR.glob('*.json'):
            stat = file.stat()
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
        print(f"[Recording_Routes] ❌ Error listing recordings: {e}")
        return jsonify({"error": str(e)}), 500


@recording_bp.route('/api/recordings/<filename>', methods=['GET'])
def api_get_recording(filename):
    """Get the content of a specific recording."""
    try:
        # Path protection: ensure filename is safe
        safe_filename = os.path.basename(filename)
        filepath = PROCESSED_DATA_DIR / safe_filename

        if not filepath.exists():
            return jsonify({"error": "Recording not found"}), 404

        with open(filepath, 'r') as f:
            data = json.load(f)

        return jsonify(data)
    except Exception as e:
        print(f"[Recording_Routes] ❌ Error getting recording: {e}")
        return jsonify({"error": str(e)}), 500
