import collections

class WebServerState:
    def __init__(self):
        self.inlet = None
        self.event_inlet = None
        self.channel_mapping = {}
        self.running = False
        self.connected = False
        self.sample_count = 0
        self.clients = 0
        self.sr = 512 # Default, will be updated from inlet
        self.num_channels = 0
        self.config = {}
        self.rps_detector = None
        self.emg_buffer = collections.deque(maxlen=512) # 1 second buffer at 512Hz
        self.last_pred_time = 0
        self.session = None # Assigned by main app or initialized here? Initialize in app setup.

# Global instance
state = WebServerState()
