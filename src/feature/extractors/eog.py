from ..detectors.blink import BlinkDetector

class EOGExtractor:
    """
    Feature Extractor for EOG channels.
    Currently focuses on Blink Detection.
    """
    
    def __init__(self, channel_index: int, config: dict, sr: int):
        self.channel_index = channel_index
        self.sr = sr
        
        # Extract thresholds from config or use defaults
        # Config structure might need 'features' section, or we use hard defaults for now
        # User defined: abs > THRESH and slope > SLOPE
        
        eog_cfg = config.get("features", {}).get("EOG", {})
        
        self.detector = BlinkDetector(
            amp_threshold=eog_cfg.get("amp_threshold", 80.0),
            slope_threshold=eog_cfg.get("slope_threshold", 5.0), # Need to tune this based on signal scale
            refractory_period_ms=eog_cfg.get("refractory_ms", 400.0),
            sampling_rate=sr
        )
    
    def process(self, sample_val: float):
        """
        Process a sample.
        Returns event string if detected, else None.
        """
        is_blink = self.detector.process(sample_val)
        
        if is_blink:
            return "BLINK"
            
        return None
    
    def update_config(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        self.detector.update_config(
            eog_cfg.get("amp_threshold"),
            eog_cfg.get("slope_threshold")
        )
