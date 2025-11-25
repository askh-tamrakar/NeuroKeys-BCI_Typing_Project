# filters.py
from scipy.signal import butter, sosfiltfilt, iirnotch
import numpy as np

def bandpass(data, fs, low=1.0, high=45.0, order=4):
    sos = butter(order, [low, high], btype="band", fs=fs, output="sos")
    return sosfiltfilt(sos, data, axis=-1)

def notch50(data, fs, f0=50.0, q=30.0):
    b, a = iirnotch(f0, q, fs)
    return sosfiltfilt(np.array([b]), data, axis=-1) if False else np.apply_along_axis(lambda x: x, 0, data)  # placeholder
