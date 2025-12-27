import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.processing.eeg_processor import EEGFilterProcessor
from src.processing.eog_processor import EOGFilterProcessor
from src.processing.emg_processor import EMGFilterProcessor

def test_processors():
    print("Testing Processor Classes with SOS Filters...")
    
    # 1. EEG
    print("\n--- Testing EEGFilterProcessor ---")
    eeg_config = {"filters": {"EEG": {"filters": [{"type": "bandpass", "low": 0.5, "high": 45.0, "order": 4}]}}}
    try:
        eeg = EEGFilterProcessor(eeg_config, sr=512)
        out = eeg.process_sample(10.0)
        print(f"  [OK] EEG Processed sample: {out}")
    except Exception as e:
        print(f"  [FAILED] EEG: {e}")
        raise e

    # 2. EOG
    print("\n--- Testing EOGFilterProcessor ---")
    eog_config = {"filters": {"EOG": {"cutoff": 10.0, "bandpass_enabled": True, "bandpass_low": 0.4, "bandpass_high": 10.0}}}
    try:
        eog = EOGFilterProcessor(eog_config, sr=512)
        out = eog.process_sample(100.0)
        print(f"  [OK] EOG Processed sample: {out}")
    except Exception as e:
        print(f"  [FAILED] EOG: {e}")
        raise e

    # 3. EMG
    print("\n--- Testing EMGFilterProcessor ---")
    emg_config = {"filters": {"EMG": {"cutoff": 70.0, "notch_enabled": True}}}
    try:
        emg = EMGFilterProcessor(emg_config, sr=512)
        out = emg.process_sample(50.0)
        print(f"  [OK] EMG Processed sample: {out}")
    except Exception as e:
        print(f"  [FAILED] EMG: {e}")
        raise e

if __name__ == "__main__":
    test_processors()
