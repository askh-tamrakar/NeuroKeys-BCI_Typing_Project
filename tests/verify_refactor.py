
import time
import threading
import pylsl
import numpy as np
import json
from pathlib import Path

# Adjust path to find src
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.processing.filter_router import FilterRouter

def mock_raw_stream(stop_event):
    """Generates mock raw data."""
    info = pylsl.StreamInfo("BioSignals-Raw-uV", "EEG", 2, 512, "float32", "mock_source_id")
    outlet = pylsl.StreamOutlet(info)
    print("[Mock] Created BioSignals-Raw-uV outlet")
    
    t = 0
    while not stop_event.is_set():
        # Sine wave mock data
        val0 = np.sin(2 * np.pi * 10 * t) # 10 Hz
        val1 = np.sin(2 * np.pi * 20 * t) # 20 Hz
        outlet.push_sample([val0, val1])
        t += 1/512.0
        time.sleep(1/512.0)
    print("[Mock] Stopped raw stream")

def verify_output(stop_event):
    """Listens for processed data."""
    print("[Verify] resolve_streams('BioSignals-Processed')...")
    streams = pylsl.resolve_streams()
    # Filter by name manually or use resolve_byprop if available, generic resolve_streams returns all.
    # actually resolve_stream("name", "name") works in C++ API but python might differ.
    # safest is resolve_byprop
    streams = pylsl.resolve_byprop("name", "BioSignals-Processed", timeout=5)
    inlet = pylsl.StreamInlet(streams[0])
    print(f"[Verify] Connected to {inlet.info().name()}")
    
    # Check channel metadata
    info = inlet.info()
    ch_count = info.channel_count()
    print(f"[Verify] Channel count: {ch_count}")
    
    start_time = time.time()
    count = 0
    while not stop_event.is_set():
        sample, ts = inlet.pull_sample(timeout=1.0)
        if sample:
            count += 1
            if count % 100 == 0:
                print(f"[Verify] Received sample {count}: {sample}")
        
        if count > 500:
            print("[Verify] Received > 500 samples. Success.")
            break

def main():
    stop_event = threading.Event()
    
    # 1. Start mock raw stream
    raw_thread = threading.Thread(target=mock_raw_stream, args=(stop_event,), daemon=True)
    raw_thread.start()
    time.sleep(1) # wait for LSL
    
    # 2. Start Router (in separate thread to simulate running)
    router = FilterRouter()
    router_thread = threading.Thread(target=router.run, daemon=True)
    router_thread.start()
    
    # 3. Verify output
    try:
        verify_output(stop_event)
    except Exception as e:
        print(f"[Verify] Error: {e}")
    finally:
        stop_event.set()
        router.stop()
        time.sleep(1)
        print("[Verify] Done")

if __name__ == "__main__":
    main()
