
import numpy as np
from scipy.signal import butter, lfilter_zi, iirnotch

def test_filters():
    sr = 512
    nyq = sr / 2.0
    
    # Notch 0 Hz
    notch_freq = 0.0
    notch_q = 30.0
    print(f"Testing Notch: Freq={notch_freq}, Q={notch_q}")
    
    try:
        b_notch, a_notch = iirnotch(notch_freq, notch_q, fs=sr)
        print(f"Notch Design OK: b={b_notch}, a={a_notch}")
        zi_notch = lfilter_zi(b_notch, a_notch)
        print("Notch lfilter_zi: OK")
    except Exception as e:
        print(f"Notch lfilter_zi FAILED: {e}")

if __name__ == "__main__":
    test_filters()
