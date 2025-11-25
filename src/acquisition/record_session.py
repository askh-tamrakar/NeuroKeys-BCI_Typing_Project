# record_session.py
import time, json, os
from pathlib import Path
from pylsl import StreamInlet, resolve_stream, StreamOutlet, StreamInfo

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def record_windows(win_s=1.0, fs=250, modality="EEG"):
    streams = resolve_stream(timeout=5)
    if not streams:
        raise RuntimeError("No LSL streams found")
    inlet = StreamInlet(streams[0])
    buflen = int(win_s * fs)
    buffer = []
    print("Recording... Ctrl-C to stop")
    try:
        while True:
            sample, ts = inlet.pull_sample(timeout=1.0)
            if sample:
                buffer.append(sample)
            if len(buffer) >= buflen:
                arr = [list(x) for x in buffer[-buflen:]]
                ts_ms = int(time.time() * 1000)
                fname = OUT_DIR / f"{modality}_window_{ts_ms}.npz"
                import numpy as np
                np.savez_compressed(fname, data=np.array(arr).T, fs=fs, timestamp=ts_ms, modality=modality)
                print("Saved", fname.name)
                buffer = []
    except KeyboardInterrupt:
        print("Stopped.")
