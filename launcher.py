"""
🚀 UNIFIED LAUNCHER - Start ALL services with ONE command!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This script automatically:
  ✅ Checks Python dependencies
  ✅ Creates required directories
  ✅ Starts 3 backend services (async)
  ✅ Optionally starts React dev server
  ✅ Displays status dashboard
  ✅ Monitors all processes
  ✅ Gracefully shutdowns on Ctrl+C

Usage:
  python launcher.py                    # Start all 3 backend services
  python launcher.py --with-frontend   # Also start React dev server
  python launcher.py --stop            # Stop all running services

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')  # Windows emoji fix
import subprocess
import time
import signal
import platform
from pathlib import Path
from datetime import datetime
import json


class UnifiedLauncher:
    """Manage all backend services from single process"""
    
    def __init__(self):
        self.processes = {}
        self.project_root = Path(__file__).parent
        self.frontend_dir = self.project_root / "frontend"
        self.data_dir = self.project_root / "data" / "raw" / "session"
        self.start_time = datetime.now()
        self.running = True
        
    def log(self, message, level="INFO"):
        """Pretty print log messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        levels = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "DEBUG": "🔍",
            "PROCESS": "🔄",
            "PORT": "🔌"
        }
        prefix = levels.get(level, "•")
        print(f"[{timestamp}] {prefix} {message}")
    
    def check_python_version(self):
        """Ensure Python 3.8+"""
        if sys.version_info < (3, 8):
            self.log("Python 3.8+ required. Current: " + platform.python_version(), "ERROR")
            sys.exit(1)
        self.log(f"Python {platform.python_version()} ✓", "SUCCESS")
    
    def check_dependencies(self):
        """Check if all required packages are installed"""
        self.log("Checking dependencies...", "INFO")
        
        required = ['serial', 'numpy', 'scipy', 'flask', 'websockets', 'matplotlib']
        missing = []
        
        for module in required:
            try:
                __import__(module)
                self.log(f"  ✓ {module}", "SUCCESS")
            except ImportError:
                missing.append(module)
                self.log(f"  ✗ {module} MISSING", "ERROR")
        
        if missing:
            self.log(f"Missing packages: {', '.join(missing)}", "WARNING")
            self.log("Installing dependencies...", "INFO")
            
            requirements_file = self.project_root / "requirements.txt"
            if not requirements_file.exists():
                self.log("requirements.txt not found!", "ERROR")
                sys.exit(1)
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])
                self.log("Dependencies installed successfully", "SUCCESS")
            except subprocess.CalledProcessError as e:
                self.log(f"Failed to install dependencies: {e}", "ERROR")
                sys.exit(1)
        else:
            self.log("All Python dependencies ready ✓", "SUCCESS")
    
    def create_directories(self):
        """Create required data directories"""
        self.log("Setting up directories...", "INFO")
        
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.log(f"  ✓ {self.data_dir}", "SUCCESS")
        except Exception as e:
            self.log(f"Failed to create data directory: {e}", "ERROR")
            sys.exit(1)
    
    def check_files_exist(self):
        """Verify all required Python files exist"""
        self.log("Checking required files...", "INFO")
        
        required_files = [
            "unified_acquisition.py",
            "data_router.py",
            "websocket_bridge.py",
            "api_server.py"
        ]
        
        missing = []
        for filename in required_files:
            filepath = self.project_root / "src/acquisition" / filename
            if filepath.exists():
                self.log(f"  ✓ {filename}", "SUCCESS")
            else:
                self.log(f"  ✗ {filename} MISSING", "ERROR")
                missing.append(filename)
        
        if missing:
            self.log(f"Missing files: {', '.join(missing)}", "ERROR")
            self.log("Please ensure all Python files are in the project root", "ERROR")
            sys.exit(1)
    
    def start_process(self, name, script_name, cwd=None):
        """Start a background process"""
        self.log(f"Starting {name}...", "PROCESS")
        
        try:
            if cwd is None:
                cwd = self.project_root
            
            # Use subprocess.Popen to run without blocking
            process = subprocess.Popen(
                [sys.executable, str(self.project_root / script_name)],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self.processes[name] = process
            time.sleep(1)  # Give process time to start
            
            # Check if process is still running
            if process.poll() is None:
                self.log(f"✓ {name} started (PID: {process.pid})", "SUCCESS")
                return True
            else:
                stderr = process.stderr.read()
                self.log(f"✗ {name} failed to start: {stderr}", "ERROR")
                return False
        
        except Exception as e:
            self.log(f"Failed to start {name}: {e}", "ERROR")
            return False
    
    def start_frontend(self):
        """Start React dev server"""
        self.log("Starting React dev server...", "PROCESS")
        
        if not self.frontend_dir.exists():
            self.log("Frontend directory not found at: " + str(self.frontend_dir), "ERROR")
            return False
        
        try:
            process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=self.frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes["frontend"] = process
            time.sleep(3)  # Give React time to start
            
            if process.poll() is None:
                self.log(f"✓ React dev server started (PID: {process.pid})", "SUCCESS")
                return True
            else:
                stderr = process.stderr.read()
                self.log(f"✗ React server failed to start: {stderr}", "ERROR")
                return False
        
        except FileNotFoundError:
            self.log("npm not found. Is Node.js installed?", "ERROR")
            return False
        except Exception as e:
            self.log(f"Failed to start React dev server: {e}", "ERROR")
            return False
    
    def display_status(self):
        """Display status dashboard"""
        print("\n")
        print("╔════════════════════════════════════════════════════════════╗")
        print("║         🚀 BIOSIGNAL ACQUISITION SYSTEM RUNNING           ║")
        print("╚════════════════════════════════════════════════════════════╝\n")
        
        print("📊 RUNNING SERVICES:\n")
        
        for name, process in self.processes.items():
            status = "🟢 Running" if process.poll() is None else "🔴 Stopped"
            pid = f"(PID: {process.pid})" if process.poll() is None else ""
            print(f"  {status} {name:25} {pid}")
        
        print("\n🔌 ACCESS POINTS:\n")
        print("  Web UI:        http://localhost:5173")
        print("  API Server:    http://localhost:8000")
        print("  WebSocket:     ws://localhost:8765")
        
        print("\n📝 DATA LOCATION:\n")
        print(f"  Recordings:    {self.data_dir}")
        
        print("\n⌨️ COMMANDS:\n")
        print("  • Open browser: http://localhost:5173")
        print("  • View API:     http://localhost:8000/api/health")
        print("  • Stop all:     Press Ctrl+C")
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"\n⏱️ UPTIME: {elapsed:.0f} seconds\n")
    
    def monitor_processes(self):
        """Continuously monitor processes"""
        self.log("Monitoring services...", "INFO")
        
        try:
            while self.running:
                time.sleep(5)
                
                # Check if any process died
                for name, process in list(self.processes.items()):
                    if process.poll() is not None:
                        self.log(f"⚠️ {name} stopped unexpectedly!", "WARNING")
                
                # Display status every 30 seconds
                if int(time.time()) % 30 == 0:
                    self.display_status()
        
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown all processes"""
        self.log("\n\nShutting down services...", "WARNING")
        self.running = False
        
        for name, process in self.processes.items():
            if process.poll() is None:
                self.log(f"Stopping {name} (PID: {process.pid})...", "INFO")
                
                try:
                    if platform.system() == "Windows":
                        process.terminate()
                    else:
                        process.send_signal(signal.SIGTERM)
                    
                    process.wait(timeout=5)
                    self.log(f"✓ {name} stopped", "SUCCESS")
                except subprocess.TimeoutExpired:
                    self.log(f"Force killing {name}...", "WARNING")
                    process.kill()
                    process.wait()
        
        self.log("\nAll services stopped. Goodbye! 👋", "SUCCESS")
        sys.exit(0)
    
    def run(self, with_frontend=False):
        """Run everything"""
        print("\n" + "="*60)
        print("   🚀 UNIFIED BIOSIGNAL ACQUISITION LAUNCHER")
        print("="*60 + "\n")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, lambda s, f: self.shutdown())
        signal.signal(signal.SIGTERM, lambda s, f: self.shutdown())
        
        # Pre-flight checks
        self.log("Starting pre-flight checks...", "INFO")
        self.check_python_version()
        self.check_files_exist()
        self.check_dependencies()
        self.create_directories()
        
        self.log("\nAll checks passed! ✓", "SUCCESS")
        
        # Start services
        self.log("\nStarting services...\n", "INFO")
        
        success = True
        success &= self.start_process("Acquisition App", "src/acquisition/unified_acquisition.py")
        time.sleep(1)
        success &= self.start_process("WebSocket Server", "src/acquisition/websocket_bridge.py")
        time.sleep(1)
        success &= self.start_process("API Server", "src/acquisition/api_server.py")
        
        if not success:
            self.log("Some services failed to start", "ERROR")
            self.shutdown()
        
        # Optional: Start frontend
        if with_frontend:
            self.log("\n", "INFO")
            if not self.start_frontend():
                self.log("Frontend failed to start (but backend is running)", "WARNING")
        
        # Display status
        time.sleep(2)
        self.display_status()
        
        # Monitor
        self.monitor_processes()


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="🚀 Launch all biosignal acquisition services"
    )
    parser.add_argument(
        "--with-frontend",
        action="store_true",
        help="Also start React dev server (requires npm and Node.js)"
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop all running services"
    )
    
    args = parser.parse_args()
    
    launcher = UnifiedLauncher()
    
    if args.stop:
        launcher.shutdown()
    else:
        launcher.run(with_frontend=args.with_frontend)


if __name__ == "__main__":
    main()