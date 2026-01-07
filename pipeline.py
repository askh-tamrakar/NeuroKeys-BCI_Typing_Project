import subprocess
import sys
import argparse
import time
import signal
import threading
from pathlib import Path

# Configuration
COMPONENTS = [
    {
        "name": "Stream Manager",
        "module": "src.acquisition.stream_manager",
        "color": "\033[95m",  # Purple
        "ready_pattern": "[StreamManager] Created stream 'BioSignals-Events'"
    },
    {
        "name": "Filter Router",
        "module": "src.processing.filter_router",
        "color": "\033[94m",  # Blue
        "ready_pattern": "[Router] [OK] Connected to raw stream"
    },

    {
        "name": "Feature Router",
        "module": "src.feature.router",
        "color": "\033[92m",  # Green
        "ready_pattern": "[FeatureRouter] [OK] Connected to BioSignals-Processed"
    },
    {
        "name": "Web Server",
        "module": "src.web.web_server",
        "color": "\033[93m",  # Yellow
        "ready_pattern": None  # Web server is the last step
    }
]

RESET = "\033[0m"

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

processes = []
ready_events = {}

def log_process(process, name, color, ready_pattern=None, ready_event=None):
    """Log process output and detect ready pattern."""
    for line in iter(process.stdout.readline, b''):
        try:
            msg = line.decode('utf-8', errors='replace').strip()
            print(f"{color}[{name}]{RESET} {msg}")
            
            if ready_pattern and ready_event and not ready_event.is_set():
                if ready_pattern in msg:
                    print(f"\033[96m[System] >>> {name} is READY\033[0m")
                    ready_event.set()
        except Exception:
            pass

def shutdown_handler(signum, frame):
    """Gracefully shutdown all processes."""
    print(f"\n[System] Shutting down all components...")
    for p in processes:
        print(f"[System] Terminating {p.name}...")
        p.terminate()
    
    # Wait for processes to exit
    for p in processes:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[System] Force killing {p.name}...")
            p.kill()
    
    print("[System] Done.")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Brain-To-Brain System Orchestrator")
    parser.add_argument("-s", "--skip-build", action="store_true", help="Skip frontend build")
    args = parser.parse_args()

    print("  Brain-To-Brain System Orchestrator (Pipeline)")
    print("  Sequential Launch: Filter -> Feature -> Web Server")
    print("=" * 60)
    print()

    if not args.skip_build:
        # --- FRONTEND CHECK ---
        frontend_dir = Path("src/web/frontend").resolve()
        
        print("[System] 🔨 Building frontend...")
        try:
            # Install dependencies if node_modules missing (still good to check this to avoid errors)
            if not (frontend_dir / "node_modules").exists():
                    print("[System] Installing npm dependencies...")
                    subprocess.run(["npm", "install"], cwd=frontend_dir, shell=True, check=True)
            
            # Always Build
            print("[System] Running npm run build...")
            subprocess.run(["npm", "run", "build"], cwd=frontend_dir, shell=True, check=True)
            print("\033[92m[System] Frontend built successfully!\033[0m")
        except Exception as e:
            print(f"\033[91m[System] Frontend build FAILED: {e}\033[0m")
            print("[System] Continuing anyway (Web Server might fail to serve UI)...")
    else:
        print("[System] ⏩ Skipping frontend build...")



    # Register signal handler
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    python_exe = sys.executable

    # Start processes sequentially
    for component in COMPONENTS:
        name = component["name"]
        print(f"[System] Launching {name}...")
        
        ready_event = threading.Event()
        ready_events[name] = ready_event

        proc = subprocess.Popen(
            [python_exe, "-u", "-m", component["module"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).parent)
        )
        
        proc.name = name
        processes.append(proc)
        
        # Start logging thread
        t = threading.Thread(
            target=log_process, 
            args=(proc, name, component["color"], component["ready_pattern"], ready_event),
            daemon=True
        )
        t.start()

        # Wait for component to be ready if it has a pattern
        if component["ready_pattern"]:
            print(f"[System] Waiting for {name} to connect...")
            # Wait up to 30 seconds for connection
            if not ready_event.wait(timeout=30.0):
                print(f"\033[91m[System] ERROR: {name} timed out while connecting!\033[0m")
                shutdown_handler(None, None)
            time.sleep(1) # Small pause after connection before next launch

    print("\n[System] All components running in sequence. Press Ctrl+C to stop.\n")

    # Monitor processes
    while True:
        for p in processes:
            if p.poll() is not None:
                print(f"[System] ❌ {p.name} has stopped (exit code: {p.returncode})")
                shutdown_handler(None, None)
        time.sleep(1)

if __name__ == "__main__":
    main()
