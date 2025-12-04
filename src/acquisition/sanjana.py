#!/usr/bin/env python3
"""
eog_dino_controller.py

Simple EOG -> Dino controller:
- Serial input (ASCII floats per line) OR mock input
- Bandpass 0.1-10 Hz + optional notch
- Threshold blink detection -> press space (pyautogui)
- Live plot of rolling window
- Save CSV on exit

Usage:
    python eog_dino_controller.py          # mock input
    python eog_dino_controller.py --port /dev/ttyUSB0 --baud 115200
"""

import argparse
import time
from collections import deque
import csv
import sys

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch
import matplotlib.pyplot as plt

# Optional imports; handled gracefully
try:
    import serial
except Exception:
    serial = None

try:
    import pyautogui
except Exception:
    pyautogui = None

# -----------------------
# Filtering utilities
# -----------------------
def bandpass(data, low=0.1, high=10, fs=250, order=4):
    nyq = 0.5 * fs
    lowc = low / nyq
    highc = high / nyq
    b, a = butter(order, [lowc, highc], btype="band")
    return filtfilt(b, a, data)

def notch50(data, fs=250, freq=50.0, q=30.0):
    # If you need 60 Hz, call with freq=60.0
    w0 = freq / (fs / 2)
    b, a = iirnotch(w0, q)
    return filtfilt(b, a, data)

# -----------------------
# Mock / serial reading
# -----------------------
def mock_eog_sample(p_blink=0.005):
    """Return a scalar sample: baseline noise plus rare blinks."""
    v = 0.05 * np.random.randn()
    if np.random.rand() < p_blink:
        # simulate blink burst (single-sample height)
        v += 2.0 + 0.2 * np.random.randn()
    return float(v)

def read_serial_sample(ser):
    """Read one ASCII float from serial, return None on failure/timeouts."""
    try:
        line = ser.readline()
        if not line:
            return None
        s = line.decode(errors="ignore").strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None

# -----------------------
# Blink detection
# -----------------------
def is_blink(value, thresh=1.0):
    return value > thresh

# -----------------------
# CSV saving
# -----------------------
def save_csv(filename, timestamps, samples):
    try:
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp_s", "eog"])
            for t, s in zip(timestamps, samples):
                writer.writerow([f"{t:.6f}", f"{s:.6f}"])
        print("Saved session to", filename)
    except Exception as e:
        print("Failed to save CSV:", e)

# -----------------------
# Main realtime loop + plotting
# -----------------------
def run(port=None, baud=115200, fs=250, window_sec=2.0, threshold=1.0, notch_freq=None, savefile="eog_session.csv"):
    samples_buffer = deque(maxlen=int(fs * window_sec))
    time_buffer = deque(maxlen=int(fs * window_sec))

    ser = None
    if port:
        if serial is None:
            print("pyserial not available. Install with: pip install pyserial")
            return
        try:
            ser = serial.Serial(port, baud, timeout=1)
            print(f"Opened serial: {port} @ {baud}")
        except Exception as e:
            print("Could not open serial port:", e)
            ser = None
            return

    # Matplotlib setup
    plt.ion()
    fig, ax = plt.subplots()
    line, = ax.plot([], [], lw=1)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("EOG amplitude")
    ax.set_title("Live EOG (rolling {:.1f}s)".format(window_sec))
    ax.set_ylim(-1.0, 3.0)

    start_ts = time.time()
    last_blink_time = -1.0
    min_blink_interval = 0.25  # sec, to avoid multiple triggers for one blink

    print("Starting. Focus the Dino (or game) window so spacebar works for jump.")
    try:
        while True:
            now = time.time() - start_ts
            # Get sample
            if ser:
                s = read_serial_sample(ser)
                if s is None:
                    # if no sample available, skip a short time
                    time.sleep(1.0 / fs)
                    continue
                sample = float(s)
            else:
                sample = mock_eog_sample()

            samples_buffer.append(sample)
            time_buffer.append(now)

            # Process only once buffer has enough samples
            if len(samples_buffer) >= 3:  # need some points for filtering
                raw = np.array(samples_buffer)
                try:
                    filtered = bandpass(raw, low=0.1, high=10.0, fs=fs, order=4)
                    if notch_freq:
                        filtered = notch50(filtered, fs=fs, freq=notch_freq, q=30.0)
                    last_val = float(filtered[-1])
                except Exception:
                    # fallback: use raw last value if filter fails
                    last_val = float(raw[-1])

                # Blink detection with refractory period
                if is_blink(last_val, thresh=threshold) and (now - last_blink_time) > min_blink_interval:
                    last_blink_time = now
                    print(f"[{now:.2f}s] Blink detected (val={last_val:.2f})")
                    # attempt pyautogui press
                    if pyautogui:
                        try:
                            pyautogui.press("space")
                        except Exception as e:
                            # sometimes OS blocks programmatic keypresses
                            print("pyautogui press failed:", e)

            # Update live plot
            if len(time_buffer) > 0:
                x0 = time_buffer[0]
                x = [t - x0 for t in time_buffer]
                y = list(samples_buffer)
                line.set_data(x, y)
                ax.set_xlim(0, window_sec)
                # autoscale y a bit if necessary
                ymin = min(-1.0, min(y) - 0.1)
                ymax = max(3.0, max(y) + 0.1)
                ax.set_ylim(ymin, ymax)
                fig.canvas.draw()
                fig.canvas.flush_events()

            time.sleep(1.0 / fs)

    except KeyboardInterrupt:
        print("\nExiting on user interrupt...")
    finally:
        # save what we have
        save_csv(savefile, list(time_buffer), list(samples_buffer))
        if ser:
            ser.close()
        plt.ioff()
        plt.close(fig)

# -----------------------
# CLI
# -----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EOG Dino Controller (simple)")
    parser.add_argument("--port", help="Serial port (e.g. /dev/ttyUSB0 or COM3). If omitted, uses mock input.")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--fs", type=int, default=250, help="Sampling rate (Hz) - used for buffering/filtering")
    parser.add_argument("--window", type=float, default=2.0, help="Live plot window (seconds)")
    parser.add_argument("--thresh", type=float, default=1.0, help="Blink detection threshold (amplitude)")
    parser.add_argument("--notch", type=float, default=None, help="Optional notch frequency (50 or 60). e.g. --notch 50")
    parser.add_argument("--save", default="eog_session.csv", help="CSV filename to save session on exit")
    args = parser.parse_args()

    run(port=args.port, baud=args.baud, fs=args.fs, window_sec=args.window, threshold=args.thresh, notch_freq=args.notch, savefile=args.save)
