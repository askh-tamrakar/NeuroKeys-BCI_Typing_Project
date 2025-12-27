import numpy as np
from scipy.signal import butter, iirnotch, lfilter, tf2sos, sosfilt
import json

def test_filter_design():
    print("Testing Filter Designs...")
    sr = 512
    nyq = sr / 2.0

    # 1. EEG Filter (Suspect)
    # Bandpass 0.5 - 45 Hz, Order 4
    print("\n--- EEG Bandpass (0.5-45 Hz, Order 4) ---")
    try:
        low = 0.5 / nyq
        high = 45.0 / nyq
        b, a = butter(4, [low, high], btype='bandpass', analog=False)
        print("  [BA] Design OK")
        # Test filtering with random data
        data = np.random.randn(1000)
        out = lfilter(b, a, data)
        print("  [BA] Filtering OK")
    except Exception as e:
        print(f"  [BA] FAILED: {e}")

    # 2. EOG Filter (Suspect)
    # Bandpass 0.4 - 10 Hz, Order 4
    print("\n--- EOG Bandpass (0.4-10 Hz, Order 4) ---")
    try:
        low = 0.4 / nyq
        high = 10.0 / nyq
        b, a = butter(4, [low, high], btype='bandpass', analog=False)
        print("  [BA] Design OK")
        data = np.random.randn(1000)
        out = lfilter(b, a, data)
        print("  [BA] Filtering OK")
    except Exception as e:
        print(f"  [BA] FAILED: {e}")

    # 3. Reference SOS Implementation (The Fix)
    print("\n--- EOG Bandpass (SOS Implementation) ---")
    try:
        low = 0.4 / nyq
        high = 10.0 / nyq
        sos = butter(4, [low, high], btype='bandpass', output='sos', analog=False)
        print("  [SOS] Design OK")
        data = np.random.randn(1000)
        out = sosfilt(sos, data)
        print("  [SOS] Filtering OK")
    except Exception as e:
        print(f"  [SOS] FAILED: {e}")

if __name__ == "__main__":
    test_filter_design()
