# import numpy as np
# from scipy.signal import butter, filtfilt, iirnotch
# import serial
# import pyautogui
# import time

# # -------------------------------------------------
# # FILTERS
# # -------------------------------------------------

# def bandpass_filter(data, low=0.1, high=10, fs=250, order=4):
#     nyq = fs * 0.5
#     b, a = butter(order, [low/nyq, high/nyq], btype='band')
#     return filtfilt(b, a, data)

# def notch_filter(data, freq=50, fs=250, q=30):
#     w0 = freq / (fs/2)
#     b, a = iirnotch(w0, q)
#     return filtfilt(b, a, data)

# # -------------------------------------------------
# # BLINK DETECTOR
# # -------------------------------------------------

# def detect_blink(value, threshold=0.8):
#     return value > threshold

# # -------------------------------------------------
# # MAIN DINO CONTROLLER
# # -------------------------------------------------

# def run_eog_dino(port="COM3", fs=250):
#     ser = serial.Serial(port, 115200)
#     buffer = []

#     print("\nEOG Dino Game Controller Running…")
#     print("Blink = JUMP\n")

#     while True:
#         try:
#             # -------- Read a single EOG sample --------
#             line = ser.readline().decode().strip()
#             if line == "":
#                 continue

#             sample = float(line)
#             buffer.append(sample)

#             # Need at least 1 second of data to filter
#             if len(buffer) >= fs:

#                 window = np.array(buffer[-fs:])   # last 1 second

#                 # -------- FILTERING --------
#                 filtered = bandpass_filter(window, fs=fs)
#                 filtered = notch_filter(filtered, fs=fs)

#                 latest = filtered[-1]  # last filtered sample

#                 # -------- BLINK EVENT --------
#                 if detect_blink(latest):
#                     print("Blink → Dino JUMP!")
#                     pyautogui.press("space")
#                     time.sleep(0.25)   # small debounce

#         except KeyboardInterrupt:
#             print("\nStopped.")
#             break

#         except:
#             continue


# # -------------------------------------------------
# # RUN
# # -------------------------------------------------

# if __name__ == "__main__":
#     run_eog_dino("COM3")  # Change COM port for your device


import json
import numpy as np
from scipy.signal import butter, filtfilt, iirnotch
import pyautogui
import time

# -------------------------------------------------
# FILTERS
# -------------------------------------------------

def bandpass_filter(data, low=0.1, high=10, fs=250, order=4):
    nyq = fs * 0.5
    b, a = butter(order, [low/nyq, high/nyq], btype='band')
    return filtfilt(b, a, data)

def notch_filter(data, freq=50, fs=250, q=30):
    w0 = freq / (fs/2)
    b, a = iirnotch(w0, q)
    return filtfilt(b, a, data)

def smooth_signal(data, window=5):
    return np.convolve(data, np.ones(window)/window, mode='same')

# -------------------------------------------------
# DETECT EVENTS
# -------------------------------------------------

def detect_blink(value, threshold=0.8):
    return value > threshold

def detect_left_right(left_val, right_val, threshold=0.25):
    diff = left_val - right_val
    if diff > threshold:
        return "LEFT"
    elif diff < -threshold:
        return "RIGHT"
    return None

# -------------------------------------------------
# MAIN JSON READER + CONTROLLER
# -------------------------------------------------

def run_eog_dino(port="COM3", fs=250):
    ser = serial.Serial(port, 115200)
    buffer = []

    print("\nEOG Dino Game Controller Running…")
    print("Blink = JUMP\n")

    while True:
        try:
            # -------- Read a single EOG sample --------
            line = ser.readline().decode().strip()
            if line == "":
                continue

            sample = float(line)
            buffer.append(sample)

            # Need at least 1 second of data to filter
            if len(buffer) >= fs:

                window = np.array(buffer[-fs:])   # last 1 second

                # -------- FILTERING --------
                filtered = bandpass_filter(window, fs=fs)
                filtered = notch_filter(filtered, fs=fs)

                latest = filtered[-1]  # last filtered sample

                # -------- BLINK EVENT --------
                if detect_blink(latest):
                    print("Blink → Dino JUMP!")
                    pyautogui.press("space")
                    time.sleep(0.25)   # small debounce

        except KeyboardInterrupt:
            print("\nStopped.")
            break

        except:
            continue


# -------------------------------------------------
# RUN
# -------------------------------------------------

if __name__ == "__main__":
    run_eog_dino("COM3")  # Change COM port for your device
