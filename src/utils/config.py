"""
config.py
---------
Loads and watches sensor_config.json. Any modification to the JSON file
automatically reloads configuration in real time.

Used by acquisition, processing, or routing modules.
"""

import json
import os
import threading
import time
from pathlib import Path


class ConfigWatcher:
    """Watches the sensor_config.json file and reloads when changed."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._last_modified = None
        self._config_cache = {}
        self._lock = threading.Lock()

        # Load immediately
        self._load_config()

        # Start background watcher
        self._watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watcher_thread.start()

    # --------------------------------------------------
    def _load_config(self):
        """Load config JSON safely."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            with self._lock:
                self._config_cache = config
                self._last_modified = os.path.getmtime(self.config_path)

            print(f"🔄 Config loaded: {self.config_path}")

        except Exception as e:
            print(f"❌ Failed to load config.json: {e}")

    # --------------------------------------------------
    def _watch_loop(self):
        """Background thread detecting file modifications."""
        while True:
            try:
                current_mtime = os.path.getmtime(self.config_path)

                if self._last_modified is None:
                    self._last_modified = current_mtime

                # Check file modified
                if current_mtime != self._last_modified:
                    print("📁 sensor_config.json changed — reloading...")
                    self._load_config()

            except FileNotFoundError:
                print("⚠️ sensor_config.json missing...")
            except Exception as e:
                print(f"Watcher error: {e}")

            time.sleep(1)

    # --------------------------------------------------
    def get(self, key: str, default=None):
        """Simple dictionary-style getter."""
        with self._lock:
            return self._config_cache.get(key, default)

    def get_all(self):
        """Return entire config dictionary."""
        with self._lock:
            return dict(self._config_cache)


# ------------------------------------------------------
# Global instance that all modules will use
# ------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "sensor_config.json"

config = ConfigWatcher(CONFIG_PATH)
