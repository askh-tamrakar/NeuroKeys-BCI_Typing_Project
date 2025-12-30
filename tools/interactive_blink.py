import sys
import os
import time
import math
import subprocess
import threading
import signal
import random
import pylsl
import msvcrt
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Configuration
STREAM_NAME = "BioSignals-Processed"
CHANNELS = 4
SR = 512
EOG_CH_IDX = 1  # From config, Ch1 is EOG

def run_component(name, module):
    print(f"[Launcher] Starting {name}...")
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", module],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    
    def log_output(p, n):
        for line in iter(p.stdout.readline, b''):
            try:
                print(f"[{n}] {line.decode().strip()}")
            except:
                pass
    
    t = threading.Thread(target=log_output, args=(proc, name), daemon=True)
    t.start()
    return proc

def generate_blink_wave(sr, amplitude=150.0):
    """Generate a bell-shaped blink signal."""
    duration = 0.3 # seconds
    samples = int(duration * sr)
    t = [i/samples for i in range(samples)]
    # Sin^2 shape for a smooth bump
    wave = [amplitude * math.sin(math.pi * x)**2 for x in t]
    return wave

def main():
    print("="*60)
    print("  Interactive Blink Simulator")
    print("  1. Creates LSL Stream 'BioSignals-Processed'")
    print("  2. Launches Feature Router & Web Server")
    print("  3. Press 'b' to generating a BLINK on Ch1")
    print("  4. Press 'q' to Quit")
    print("="*60)

    # 1. Setup LSL Outlet
    info = pylsl.StreamInfo(STREAM_NAME, 'EEG', CHANNELS, SR, 'float32', 'sim123')
    outlet = pylsl.StreamOutlet(info)
    print(f"[Simulator] Stream '{STREAM_NAME}' created.")

    # 2. Launch Components
    router_proc = run_component("FeatureRouter", "src.feature.router")
    server_proc = run_component("WebServer", "src.web.web_server")
    
    time.sleep(2) # Give them time to initalize

    print("\n[Simulator] Ready! Press 'b' to blink.\n")

    running = True
    blink_queue = []
    
    # 3. Main Loop
    try:
        while running:
            # Check Input
            if msvcrt.kbhit():
                key = msvcrt.getch().decode().lower()
                if key == 'q':
                    running = False
                    break
                elif key == 'b':
                    print(">>> BLINK SENT!")
                    blink_queue.extend(generate_blink_wave(SR))
            
            # Generate Sample
            sample = [0.0] * CHANNELS
            
            # Noise
            for i in range(CHANNELS):
                sample[i] = random.gauss(0, 2.0)
                
            # Add Blink
            if blink_queue:
                val = blink_queue.pop(0)
                sample[EOG_CH_IDX] += val
            
            # Push
            outlet.push_sample(sample)
            
            # Rate limiting (rough)
            time.sleep(1.0/SR)
            
    except KeyboardInterrupt:
        pass
    finally:
        print("[Simulator] Stopping...")
        router_proc.terminate()
        server_proc.terminate()
        print("[Simulator] Done.")

if __name__ == "__main__":
    main()
