from flask_socketio import SocketIO

# Initialize SocketIO with no arguments first. 
# We'll call init_app later in the factory.
socketio = SocketIO(cors_allowed_origins="*", ping_timeout=10, ping_interval=5, engineio_logger=False, logger=False)
