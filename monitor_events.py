"""
Monitor LSL Events
"""
import time
import sys
try:
    import pylsl
except ImportError:
    print("pylsl not installed")
    sys.exit(1)

EVENT_STREAM_NAME = "BioSignals-Events"

def main():
    print(f"Resolving {EVENT_STREAM_NAME}...")
    streams = pylsl.resolve_byprop('name', EVENT_STREAM_NAME, timeout=5.0)
    
    if not streams:
        print("Stream not found.")
        return

    inlet = pylsl.StreamInlet(streams[0])
    print("Connected. Listening for events...")
    
    start_time = time.time()
    while time.time() - start_time < 10:
        sample, ts = inlet.pull_sample(timeout=1.0)
        if sample:
            print(f"Event received: {sample[0]} at {ts}")
        else:
            # print(".", end="", flush=True)
            pass
            
    print("\nDone.")

if __name__ == "__main__":
    main()
