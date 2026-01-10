import sys
from pathlib import Path

# Add project root to path to ensure imports work if run from this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.web.server import create_app, start_background_threads, socketio

if __name__ == '__main__':
    app = create_app()
    start_background_threads()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
