# serial_acquirer.py
import serial
import time
import numpy as np
import os
import argparse

def main(port="/dev/ttyUSB0", baud=115200, out_dir="./data/raw", win_s=0.5, fs=1000):
    ser = serial.Serial(port, baud, timeout=1.0)
    buf = []
    buflen = int(win_s * fs)
    os.makedirs(out_dir, exist_ok=True)
    print(f"Opened serial {port} @ {baud}")
    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue
            # Expect CSV: val1,val2,val3...
            parts = line.split(",")
            try:
                vals = [float(p) for p in parts]
            except:
                continue
            buf.append(vals)
            if len(buf) >= buflen:
                arr = np.array(buf[-buflen:]).T
                ts = int(time.time()*1000)
                np.savez_compressed(os.path.join(out_dir, f"serial_window_{ts}.npz"), data=arr, fs=fs, timestamp=ts)
                buf = []
    except KeyboardInterrupt:
        ser.close()
        print("Stopped.")
