import time
import pylsl
import numpy as np

def main():
    print("[Mock] Creating BioSignals-Raw-uV outlet...")
    info = pylsl.StreamInfo("BioSignals-Raw-uV", "EEG", 2, 512, "float32", "mock_source_id_123")
    outlet = pylsl.StreamOutlet(info)
    
    print("[Mock] Sending data (Sine waves at 10Hz/20Hz)...")
    t = 0
    srate = 512
    try:
        while True:
            # Generate 2ch sample
            val0 = np.sin(2 * np.pi * 10 * t) + np.random.normal(0, 0.1) # 10Hz + noise
            val1 = np.sin(2 * np.pi * 20 * t) + np.random.normal(0, 0.1) # 20Hz + noise
            outlet.push_sample([val0, val1])
            t += 1.0/srate
            time.sleep(1.0/srate)
    except KeyboardInterrupt:
        print("[Mock] Stopped.")

if __name__ == "__main__":
    main()
