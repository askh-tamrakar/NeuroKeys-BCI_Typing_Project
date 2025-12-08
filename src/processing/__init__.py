"""
Acquisition subpackage.

Contains modules for hardware data acquisition (EMG/EEG/EOG/etc.).
"""
# Empty to avoid circular imports or missing file errors during testing
# The main app is in acquisition.py
try:
    from .emg import EMGProcessor
except Exception:
    pass

try:
    from .eog import EOGProcessor
except Exception:
    pass

try:
    from .ffteeg import EEGFFTProcessor
except Exception:
    pass