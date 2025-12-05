import numpy as np
from scipy.signal import butter, filtfilt, iirnotch
import serial
import pyautogui
import time

# -------------------------------------------------
# FILTERS (Step-by-step as requested)
# -------------------------------------------------

def bandpass_filter(data, low=0.1, high=10, fs=250, order=4):
    """Band-pass filter for EOG signals."""
    nyq = fs * 0.5
    b, a = butter(order, [low/nyq, high/nyq], btype='band')
    return filtfilt(b, a, data)

def notch_filter(data, freq=50, fs=250, q=30):
    """Notch filter to remove 50/60 Hz noise."""
    w0 = freq / (fs/2)
    b, a = iirnotch(w0, q)
    return filtfilt(b, a, data)

def smooth_signal(data, window=5):
    """Optional smoothing filter."""
    return np.convolve(data, np.ones(window)/window, mode='same')

# -------------------------------------------------
# BLINK DETECTOR
# -------------------------------------------------

def detect_blink(value, threshold=0.8):
    """Detect blink using amplitude threshold."""
    return value > threshold

# -------------------------------------------------
# MAIN DINO CONTROLLER (Updated)
# -------------------------------------------------

def run_eog_dino(port="COM3", fs=250, thresh=0.8):
    ser = serial.Serial(port, 115200)
    buffer = []

    print("\nEOG Dino Game Controller Running…")
    print("Blink = JUMP\n")

    while True:
        try:
            # Read a single sample from serial
            line = ser.readline().decode().strip()
            if line == "":
                continue

            sample = float(line)
            buffer.append(sample)

            # Need at least 1 second of data for filtering
            if len(buffer) >= fs:
                window = np.array(buffer[-fs:])

                # ---------- STEP-BY-STEP FILTERS ----------
                bp = bandpass_filter(window, fs=fs)
                notched = notch_filter(bp, fs=fs)
                smooth = smooth_signal(notched, window=5)

                latest = smooth[-1]  # final filtered sample

                # ---------- BLINK EVENT ----------
                if detect_blink(latest, threshold=thresh):
                    print("Blink → Dino JUMP!")
                    pyautogui.press("space")
                    time.sleep(0.25)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print("Error:", e)
            continue

# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    run_eog_dino("COM3")  # Change COM port for your device
