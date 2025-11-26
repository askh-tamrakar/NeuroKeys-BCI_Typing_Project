#!/usr/bin/env python3
"""
BCI_Run.py - Master launcher that starts backend, simulator, fusion (optional),
and the frontend dev server (npm start). Auto-restarts crashed processes.

Place at project root (bci-project/) and run:
    python BCI_Run.py

Make sure to run `npm install` in the frontend folder before using this script.
"""

import os
import sys
import time
import signal
import threading
import subprocess
import platform
import webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
BACKEND_SCRIPT = ROOT / "src" / "web" / "mock_server.py"
SIM_SCRIPT = ROOT / "scripts" / "post_window.py"
FUSION_SCRIPT = ROOT / "src" / "models" / "fusion_server.py"

# Toggle services
ENABLE_MOCK_BACKEND = True
ENABLE_ACQUISITION_SIM = True
ENABLE_FUSION_PIPELINE = False
ENABLE_FRONTEND = True

# Frontend dev server URL (default CRA)
FRONTEND_URL = "http://localhost:3000"
# Local project proposal path (for convenience in UI)
PROPOSAL_LOCAL_PATH = "/mnt/data/BCI_Project_Proposal_v2.pdf"

# Graceful stop flag
_stop_event = threading.Event()

def _is_windows():
    return platform.system().lower().startswith("win")

def run_and_monitor(name, cmd, cwd=None, env=None, restart_delay=2):
    """Run a command in a subprocess and restart if it exits (daemon thread)."""
    while not _stop_event.is_set():
        try:
            print(f"[LAUNCH] {name}: {cmd} (cwd={cwd})")
            # Use shell on Windows for .cmd handling, but prefer list on Unix
            if _is_windows():
                proc = subprocess.Popen(cmd if isinstance(cmd, str) else " ".join(cmd),
                                        cwd=str(cwd) if cwd else None,
                                        shell=True,
                                        env=env)
            else:
                proc = subprocess.Popen(cmd if isinstance(cmd, list) else cmd.split(" "),
                                        cwd=str(cwd) if cwd else None,
                                        shell=False,
                                        env=env)
            # Wait loop that can break on _stop_event
            while True:
                if _stop_event.is_set():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    proc.wait(timeout=5)
                    break
                ret = proc.poll()
                if ret is not None:
                    print(f"[EXIT] {name} exited with code {ret}")
                    break
                time.sleep(0.5)
        except Exception as e:
            print(f"[ERROR] {name} crashed to launcher: {e}")
        if _stop_event.is_set():
            break
        print(f"[RESTART] {name} restarting in {restart_delay}s...")
        time.sleep(restart_delay)
    print(f"[STOPPED] monitor thread for {name} exiting.")

def launch_threaded(name, cmd, cwd=None, env=None):
    t = threading.Thread(target=run_and_monitor, args=(name, cmd, cwd, env), daemon=True)
    t.start()
    return t

def wait_for_url(url, timeout=15.0, interval=0.5):
    """Wait until the url returns an HTTP response (or times out)."""
    end = time.time() + timeout
    while time.time() < end and not _stop_event.is_set():
        try:
            with urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False

def open_frontend_in_browser(url):
    try:
        webbrowser.open(url, new=2)
        print(f"[BROWSER] Attempted to open {url} in your default browser.")
    except Exception as e:
        print(f"[BROWSER] Could not open browser: {e}")

def signal_handler(sig, frame):
    print("\n[SHUTDOWN] Signal received, stopping services...")
    _stop_event.set()
    # Give threads time to stop
    time.sleep(1)
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    threads = []

    # Backend (FastAPI mock server)
    if ENABLE_MOCK_BACKEND and BACKEND_SCRIPT.exists():
        backend_cmd = [sys.executable, str(BACKEND_SCRIPT)]
        threads.append(launch_threaded("Mock Backend", backend_cmd, cwd=str(ROOT)))
    else:
        print("[SKIP] Mock backend not enabled or missing:", BACKEND_SCRIPT)

    # Acquisition simulator (script that posts windows to /infer or provides simulated data)
    if ENABLE_ACQUISITION_SIM and SIM_SCRIPT.exists():
        sim_cmd = [sys.executable, str(SIM_SCRIPT)]
        threads.append(launch_threaded("Acquisition Simulator", sim_cmd, cwd=str(ROOT)))
    else:
        print("[SKIP] Acquisition simulator not enabled or missing:", SIM_SCRIPT)

    # Fusion / model server
    if ENABLE_FUSION_PIPELINE and FUSION_SCRIPT.exists():
        fusion_cmd = [sys.executable, str(FUSION_SCRIPT)]
        threads.append(launch_threaded("Fusion Server", fusion_cmd, cwd=str(ROOT)))
    else:
        print("[SKIP] Fusion pipeline not enabled or missing:", FUSION_SCRIPT)

    # Frontend (npm start)
    if ENABLE_FRONTEND and FRONTEND_DIR.exists():
        # Ensure npm command works on platform
        npm_cmd = "npm"
        if _is_windows():
            # Windows: npm is usually available as 'npm' or 'npm.cmd' in PATH; spawn with shell True if needed
            frontend_cmd = "npm run dev"
        else:
            # Unix-like: use list to avoid shell
            frontend_cmd = ["npm", "run", "dev"]
        # Start frontend in its folder
        threads.append(launch_threaded("Frontend (npm run dev)", frontend_cmd, cwd=str(FRONTEND_DIR)))
        # Try to open the browser once server is up
        print("[INFO] Waiting for frontend dev server to respond at", FRONTEND_URL)
        if wait_for_url(FRONTEND_URL, timeout=25.0):
            open_frontend_in_browser(FRONTEND_URL)
        else:
            print("[WARN] Frontend URL did not respond within timeout. Open manually:", FRONTEND_URL)
    else:
        print("[SKIP] Frontend not enabled or missing:", FRONTEND_DIR)

    # Print link to project proposal for team reference
    print("\n[INFO] Project proposal local path (open in your system):", PROPOSAL_LOCAL_PATH)

    # Keep main alive while threads are running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] KeyboardInterrupt received. Stopping...")
        _stop_event.set()
        time.sleep(1)

if __name__ == "__main__":
    main()
