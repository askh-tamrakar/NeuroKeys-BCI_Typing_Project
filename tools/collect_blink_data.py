import time
import json
import argparse
from pathlib import Path
from datetime import datetime
import numpy as np

try:
    import pylsl
except ImportError:
    print("Error: pylsl not found. Please install it with `pip install pylsl`")
    exit(1)

def resolve_stream(name, timeout=5.0):
    print(f"Searching for stream: {name}...")
    streams = pylsl.resolve_byprop('name', name, timeout=timeout)
    if not streams:
        print(f"Stream '{name}' not found.")
        return None
    return streams[0]

def collect_data(duration, output_file, description=""):
    print(f"Preparing to collect data for {duration} seconds...")
    
    # 1. Resolve streams
    raw_info = resolve_stream("BioSignals-Raw-uV")
    proc_info = resolve_stream("BioSignals-Processed")
    
    inlets = []
    streams_meta = []

    if raw_info:
        inlet = pylsl.StreamInlet(raw_info)
        inlets.append({"name": "raw", "inlet": inlet})
        streams_meta.append({
            "name": "raw",
            "type": raw_info.type(),
            "channel_count": raw_info.channel_count(),
            "srate": raw_info.nominal_srate()
        })
        print("Connected to Raw stream.")
    
    if proc_info:
        inlet = pylsl.StreamInlet(proc_info)
        inlets.append({"name": "processed", "inlet": inlet})
        streams_meta.append({
            "name": "processed",
            "type": proc_info.type(),
            "channel_count": proc_info.channel_count(),
            "srate": proc_info.nominal_srate()
        })
        print("Connected to Processed stream.")

    if not inlets:
        print("No streams found. Ensure Acquisition App and Filter Router are running.")
        return

    # 2. Collection Loop
    data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "description": description,
            "streams": streams_meta
        },
        "raw": [],
        "processed": []
    }

    start_time = time.time()
    print("\n--- RECORDING STARTED ---")
    print("Blink now! (or perform the target gesture)")
    
    try:
        while (time.time() - start_time) < duration:
            for item in inlets:
                name = item["name"]
                inlet = item["inlet"]
                
                # Pull all available samples
                while True:
                    sample, timestamp = inlet.pull_sample(timeout=0.0)
                    if sample is None:
                        break
                    data[name].append({
                        "ts": timestamp,
                        "val": sample
                    })
            
            time.sleep(0.001) # Yield slightly
            
            # Progress bar
            elapsed = time.time() - start_time
            print(f"\rTime: {elapsed:.1f}/{duration}.0s", end="")
            
    except KeyboardInterrupt:
        print("\nRecording stopped manually.")

    print("\n--- RECORDING FINISHED ---")

    # 3. Save Data
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
        
    print(f"Data saved to {output_path}")
    print(f"Raw samples: {len(data['raw'])}")
    print(f"Processed samples: {len(data['processed'])}")

    # 4. Simple Analysis (suggestion)
    if len(data['processed']) > 0:
        vals = np.array([x['val'] for x in data['processed']])
        if vals.ndim == 2:
            print("\nStatistics (Processed Stream):")
            for i in range(vals.shape[1]):
                col = vals[:, i]
                print(f"Ch{i}: Min={np.min(col):.2f}, Max={np.max(col):.2f}, Mean={np.mean(col):.2f}, Std={np.std(col):.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect Blink Data from LSL")
    parser.add_argument("--duration", type=float, default=10.0, help="Duration in seconds")
    parser.add_argument("--output", type=str, default="data/collected_blinks/latest.json", help="Output file path")
    parser.add_argument("--desc", type=str, default="", help="Description of the session")
    
    args = parser.parse_args()
    
    collect_data(args.duration, args.output, args.desc)
