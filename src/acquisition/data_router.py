"""
Data Router - Routes data to correct filter based on channel mapping
Manages EMG, EOG, and EEG filters
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')  # Windows emoji fix
import numpy as np
from scipy.signal import butter, filtfilt
from datetime import datetime
from collections import deque


class FilterManager:
    """Manages all signal filters (EMG, EOG, EEG)"""
    
    def __init__(self, sampling_rate=512):
        self.fs = sampling_rate
        
        # EMG filter: High-pass at 70 Hz
        self.emg_b, self.emg_a = butter(4, 70.0 / (0.5 * self.fs), btype='high')
        self.emg_buffer = deque(maxlen=100)
        self.emg_rms_window = int(0.1 * self.fs)
        
        # EOG filter: Band-pass 0.5-50 Hz
        self.eog_b_low, self.eog_a_low = butter(4, 0.5 / (0.5 * self.fs), btype='high')
        self.eog_b_high, self.eog_a_high = butter(4, 50.0 / (0.5 * self.fs), btype='low')
        self.eog_buffer = deque(maxlen=100)
        
        # EEG filter: Band-pass 0.1-40 Hz
        self.eeg_b_low, self.eeg_a_low = butter(4, 0.1 / (0.5 * self.fs), btype='high')
        self.eeg_b_high, self.eeg_a_high = butter(4, 40.0 / (0.5 * self.fs), btype='low')
        self.eeg_buffer = deque(maxlen=256)
        
    def filter_emg(self, value):
        """Apply EMG filter (high-pass 70 Hz) + RMS envelope"""
        self.emg_buffer.append(value)
        
        if len(self.emg_buffer) < self.emg_rms_window:
            return {"filtered": value, "envelope": 0}
        
        # Apply high-pass filter
        emg_array = np.array(list(self.emg_buffer))
        filtered = filtfilt(self.emg_b, self.emg_a, emg_array)[-1]
        
        # Calculate RMS envelope
        abs_filtered = np.abs(filtered)
        envelope = np.sqrt(np.mean(abs_filtered ** 2))
        
        return {
            "filtered": float(filtered),
            "envelope": float(envelope)
        }
    
    def filter_eog(self, value):
        """Apply EOG filter (band-pass 0.5-50 Hz)"""
        self.eog_buffer.append(value)
        
        if len(self.eog_buffer) < 10:
            return {"filtered": value}
        
        eog_array = np.array(list(self.eog_buffer))
        
        # Apply band-pass filter
        filtered_low = filtfilt(self.eog_b_low, self.eog_a_low, eog_array)
        filtered = filtfilt(self.eog_b_high, self.eog_a_high, filtered_low)[-1]
        
        return {"filtered": float(filtered)}
    
    def filter_eeg(self, value):
        """Apply EEG filter (band-pass 0.1-40 Hz) + FFT"""
        self.eeg_buffer.append(value)
        
        if len(self.eeg_buffer) < 10:
            return {"filtered": value}
        
        eeg_array = np.array(list(self.eeg_buffer))
        
        # Apply band-pass filter
        filtered_low = filtfilt(self.eeg_b_low, self.eeg_a_low, eeg_array)
        filtered = filtfilt(self.eeg_b_high, self.eeg_a_high, filtered_low)[-1]
        
        # Simple FFT features
        fft = np.abs(np.fft.fft(eeg_array))
        fft_power = np.sum(fft ** 2)
        
        return {
            "filtered": float(filtered),
            "fft_power": float(fft_power)
        }


class DataRouter:
    """Routes data to correct filter based on channel mapping"""
    
    def __init__(self, sampling_rate=512):
        self.fs = sampling_rate
        self.filters = {
            'EMG': FilterManager(sampling_rate),
            'EOG': FilterManager(sampling_rate),
            'EEG': FilterManager(sampling_rate)
        }
        self.current_mapping = {0: 'EEG', 1: 'EOG'}
    
    def route_data(self, ch0_value, ch0_type, ch1_value, ch1_type, timestamp):
        """
        Route raw data to appropriate filters based on channel type
        
        Returns:
            dict with filtered data for each channel
        """
        processed = {
            "timestamp": timestamp,
            "ch0": {},
            "ch1": {}
        }
        
        # Filter channel 0
        if ch0_type == 'EMG':
            processed["ch0"]["type"] = "EMG"
            processed["ch0"].update(self.filters['EMG'].filter_emg(ch0_value))
        elif ch0_type == 'EOG':
            processed["ch0"]["type"] = "EOG"
            processed["ch0"].update(self.filters['EOG'].filter_eog(ch0_value))
        elif ch0_type == 'EEG':
            processed["ch0"]["type"] = "EEG"
            processed["ch0"].update(self.filters['EEG'].filter_eeg(ch0_value))
        
        # Filter channel 1
        if ch1_type == 'EMG':
            processed["ch1"]["type"] = "EMG"
            processed["ch1"].update(self.filters['EMG'].filter_emg(ch1_value))
        elif ch1_type == 'EOG':
            processed["ch1"]["type"] = "EOG"
            processed["ch1"].update(self.filters['EOG'].filter_eog(ch1_value))
        elif ch1_type == 'EEG':
            processed["ch1"]["type"] = "EEG"
            processed["ch1"].update(self.filters['EEG'].filter_eeg(ch1_value))
        
        return processed
    
    def update_mapping(self, mapping):
        """Update channel mapping dynamically"""
        self.current_mapping = mapping
        print(f"✅ Router mapping updated: {mapping}")