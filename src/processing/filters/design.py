from scipy.signal import butter, iirnotch, tf2sos

def design_emg_highpass(cutoff_hz, fs, order=4):
    nyq = 0.5*fs
    sos = butter(order, cutoff_hz/nyq, btype='highpass', output='sos')
    return sos

def design_eog_lowpass(cutoff_hz, fs, order=4):
    nyq = 0.5*fs
    return butter(order, cutoff_hz/nyq, btype='lowpass', output='sos')

def design_eeg_notch_band(notch_freq, q, low, high, fs, order=4):
    b,a = iirnotch(notch_freq, q, fs=fs)
    notch_sos = tf2sos(b,a)
    nyq = 0.5*fs
    bp = butter(order, [low/nyq, high/nyq], btype='bandpass', output='sos')
    return np.vstack((notch_sos, bp))
