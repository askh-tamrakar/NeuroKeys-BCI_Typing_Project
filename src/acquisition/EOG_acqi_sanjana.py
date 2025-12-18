"""
EOG-Based BCI Signal Processing Script
--------------------------------------
This script demonstrates basic EOG signal acquisition, filtering,
feature extraction, and event detection for a simple Brain-Computer
Interface (BCI) application.

Requirements:
- numpy
- scipy
- matplotlib

Replace the `read_eog_data()` function with actual hardware integration.
"""

import numpy as np
from scipy.signal import butter, filtfilt
import matplotlib.pyplot as plt

# ----------------------------
# 1. Read EOG Data (Mock)
# ----------------------------
def read_eog_data(duration=5, fs=250):
    """
    Simulate raw EOG signal.
    Replace with actual sensor read code (e.g., serial.read()).
    """
    t = np.linspace(0, duration, duration * fs)
    # mock signal: blinking events + noise
    signal = 0.5 * np.sin(2 * np.pi * 1 * t) + 0.2 * np.random.randn(len(t))
    signal[500:520] += 2  # mock blink
    signal[1500:1520] += 2
    return t, signal

# ----------------------------
# 2. Bandpass Filter
# ----------------------------
def bandpass_filter(data, low=0.1, high=10, fs=250, order=4):
    nyq = 0.5 * fs
    lowcut = low / nyq
    highcut = high / nyq
    b, a = butter(order, [lowcut, highcut], btype="band")
    return filtfilt(b, a, data)

# ----------------------------
# 3. Blink Detection Algorithm
# ----------------------------
def detect_blinks(filtered_data, threshold=1.0):
    """
    Detect EOG blinks based on amplitude threshold.
    Returns indices where blinks are detected.
    """
    blink_indices = np.where(filtered_data > threshold)[0]
    return blink_indices

# ----------------------------
# 4. Main Execution
# ----------------------------
if __name__ == "__main__":
    fs = 250
    t, raw = read_eog_data(fs=fs)

    filtered = bandpass_filter(raw, fs=fs)
    blinks = detect_blinks(filtered)

    print(f"Detected {len(blinks)} blink samples.")

    # Plot
    plt.figure(figsize=(10,5))
    plt.plot(t, filtered, label="Filtered EOG")
    plt.scatter(t[blinks], filtered[blinks], color="red", label="Detected Blinks")
    plt.title("EOG Signal with Blink Detection")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude (mV)")
    plt.legend()
    plt.show()
