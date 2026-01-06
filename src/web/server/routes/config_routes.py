from flask import Blueprint, jsonify, request
from src.web.server.state import state
from src.web.server.config_manager import load_config, save_config
from src.web.server.extensions import socketio

config_bp = Blueprint('config', __name__)

@config_bp.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration."""
    config = state.config or load_config()
    return jsonify(config)

@config_bp.route('/api/config', methods=['POST'])
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
        print(f"[Config_Routes] ❌ Error saving config: {e}")
        return jsonify({"error": str(e)}), 500

@config_bp.route('/api/config', methods=['DELETE'])
def api_delete_config():
    """Reset to default configuration."""
    try:
        defaults = load_config()
        save_config(defaults)
        socketio.emit('config_updated', {"status": "reset"})
        return jsonify({"status": "ok", "message": "Config reset to defaults"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
