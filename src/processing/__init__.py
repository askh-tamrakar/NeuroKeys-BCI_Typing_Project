"""
Acquisition subpackage.

Contains modules for hardware data acquisition (EMG/EEG/EOG/etc.).
"""
# Empty to avoid circular imports or missing file errors during testing
# The main app is in acquisition.py
try:
    from .emg_processor import EMGProcessor
except Exception:
    pass

try:
    from .eog_processor import EOGProcessor
except Exception:
    pass

try:
    from .eeg_processor import EEGFFTProcessor
except Exception:
    pass

__all__ = ["emg_processor", "eog_processor", "eeg_processor"]