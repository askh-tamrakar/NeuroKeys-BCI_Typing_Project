# features.py
import numpy as np
from scipy.signal import welch

BANDS = {"delta":(1,4),"theta":(4,8),"alpha":(8,12),"beta":(12,30),"gamma":(30,45)}

def bandpower(x, fs, band):
    f, Pxx = welch(x, fs=fs, nperseg=min(len(x), fs*2))
    idx = (f>=band[0]) & (f<=band[1])
    return np.trapz(Pxx[idx], f[idx]) if idx.any() else 0.0

def extract_features(window, fs):
    # window: (channels, samples)
    feats = []
    for ch in range(window.shape[0]):
        d = window[ch]
        feats += [d.mean(), d.std(), np.sqrt(np.mean(d**2))]  # mean, std, RMS
        for band in BANDS.values():
            feats.append(bandpower(d, fs, band))
    return np.array(feats)
