# lsl_acquirer.py
import time
import argparse
import numpy as np
from pylsl import StreamInlet, resolve_stream
import os
import json

def save_window(window, meta, out_dir):
    ts = int(time.time()*1000)
    fname = os.path.join(out_dir, f"{meta['modality']}_window_{ts}.npz")
    np.savez_compressed(fname, data=window, meta=meta)

def main(modality="EEG", out_dir="./data/raw", win_s=1.0, fs=250):
    # resolve first stream with matching name
    streams = resolve_stream()
    inlet = StreamInlet(streams[0])
    buflen = int(fs * win_s)
    buffer = []

    print("Listening to LSL stream. Press Ctrl-C to stop.")
    try:
        while True:
            sample, timestamp = inlet.pull_sample(timeout=1.0)
            if sample:
                buffer.append(sample)
            if len(buffer) >= buflen:
                arr = np.array(buffer[-buflen:]).T  # shape (channels, samples)
                meta = {"modality": modality, "fs": fs, "timestamp": timestamp}
                save_window(arr, meta, out_dir)
                buffer = []  # sliding window behavior can be implemented
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--modality", default="EEG")
    parser.add_argument("--out_dir", default="./data/raw")
    parser.add_argument("--fs", type=int, default=250)
    parser.add_argument("--win_s", type=float, default=1.0)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    main(args.modality, args.out_dir, args.win_s, args.fs)
