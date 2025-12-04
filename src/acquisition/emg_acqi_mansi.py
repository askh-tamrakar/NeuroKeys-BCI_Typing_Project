"""
EMG Neuroscience Application
----------------------------
This script performs basic EMG signal processing including:
    • Loading EMG data
    • Bandpass filtering (20–450 Hz)
    • Notch filtering (50/60 Hz line noise)
    • Rectification & envelope extraction
    • Muscle activation detection
    • Plotting results

Author: ChatGPT
"""

import numpy as np
import scipy.signal as signal
import matplotlib.pyplot as plt
import argparse


# -------------------------------------------------------------
# 1. Load EMG Data
# -------------------------------------------------------------
def load_emg(file_path, column=0):
    """
    Load EMG data from a CSV file.

    Parameters:
        file_path (str): Path to CSV file
        column (int): Column index for EMG signal

    Returns:
        numpy array of EMG data
    """
    data = np.loadtxt(file_path, delimiter=',')
    return data[:, column]


# -------------------------------------------------------------
# 2. Bandpass Filter (20–450 Hz typical EMG range)
# -------------------------------------------------------------
def bandpass_filter(emg, fs, low=20, high=450):
    nyquist = fs / 2
    b, a = signal.butter(4, [low / nyquist, high / nyquist], btype='band')
    return signal.filtfilt(b, a, emg)


# -------------------------------------------------------------
# 3. Notch Filter (50 or 60 Hz line noise)
# -------------------------------------------------------------
def notch_filter(emg, fs, freq=60):
    nyquist = fs / 2
    b, a = signal.iirnotch(freq / nyquist, 30)
    return signal.filtfilt(b, a, emg)


# -------------------------------------------------------------
# 4. Extract EMG Envelope
# -------------------------------------------------------------
def extract_envelope(emg, fs, lowpass=10):
    """
    Rectify the signal and apply low-pass filter to get the envelope.
    """
    rectified = np.abs(emg)
    b, a = signal.butter(4, lowpass / (fs / 2), btype='low')
    envelope = signal.filtfilt(b, a, rectified)
    return envelope


# -------------------------------------------------------------
# 5. Detect Muscle Activation (simple threshold method)
# -------------------------------------------------------------
def detect_activation(envelope, threshold_factor=2.5):
    threshold = threshold_factor * np.mean(envelope)
    activation = envelope > threshold
    return activation, threshold


# -------------------------------------------------------------
# 6. Main Application
# -------------------------------------------------------------
def run_emg_app(input_csv, fs):
    emg = load_emg(input_csv)

    # Filtering
    emg_bp = bandpass_filter(emg, fs)
    emg_clean = notch_filter(emg_bp, fs)

    # Envelope
    envelope = extract_envelope(emg_clean, fs)

    # Activation detection
    activation, threshold = detect_activation(envelope)

    # Plotting
    t = np.arange(len(emg)) / fs

    plt.figure(figsize=(12, 8))

    # Raw EMG
    plt.subplot(3, 1, 1)
    plt.plot(t, emg)
    plt.title("Raw EMG Signal")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")

    # Filtered EMG
    plt.subplot(3, 1, 2)
    plt.plot(t, emg_clean)
    plt.title("Filtered EMG (Bandpass + Notch)")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")

    # Envelope + Activation
    plt.subplot(3, 1, 3)
    plt.plot(t, envelope, label="EMG Envelope")
    plt.axhline(threshold, color='r', linestyle='--', label="Activation Threshold")
    plt.fill_between(t, 0, envelope, where=activation, color='orange', alpha=0.3, label="Active")
    plt.title("EMG Envelope & Muscle Activation")
    plt.xlabel("Time (s)")
    plt.ylabel("Envelope")

    plt.legend()
    plt.tight_layout()
    plt.show()


# -------------------------------------------------------------
# CLI (Command-line interface)
# -------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EMG Neuroscience Application")
    parser.add_argument("input_csv", help="Input CSV file containing EMG data")
    parser.add_argument("--fs", type=int, default=1000, help="Sampling frequency (Hz)")

    args = parser.parse_args()
    run_emg_app(args.input_csv, args.fs)
 