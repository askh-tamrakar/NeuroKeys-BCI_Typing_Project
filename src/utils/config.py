"""
config.py (ENHANCED VERSION)
----------------------------

Loads and watches multiple configuration JSON files:
- sensor_config.json (main hardware config)
- filter_config.json (filter parameters by sensor)
- calibration_config.json (calibration data by channel)

Provides:
1. ConfigWatcher - Auto-reload on file changes
2. ConfigWriter - Save configs with validation
3. Global instances for easy access
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigWatcher:
    """Watches a config JSON file and auto-reloads on changes."""

    def __init__(self, config_path: str, name: str = "Config"):
        self.config_path = Path(config_path)
        self.name = name
        self._last_modified = None
        self._config_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()

        # Load immediately
        self._load_config()

        # Start background watcher
        self._watcher_thread = threading.Thread(
            target=self._watch_loop, daemon=True, name=f"{name}-Watcher"
        )
        self._watcher_thread.start()

    def _load_config(self) -> bool:
        """Load config JSON safely. Returns True if successful."""
        try:
            if not self.config_path.exists():
                logger.warning(f"⚠️ {self.name} file not found: {self.config_path}")
                return False

            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            with self._lock:
                self._config_cache = config
                self._last_modified = os.path.getmtime(self.config_path)

            logger.info(f"✅ {self.name} loaded: {self.config_path}")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"❌ {self.name} JSON syntax error: {e}")
            logger.error(f"   File: {self.config_path}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to load {self.name}: {e}")
            return False

    def _watch_loop(self):
        """Background thread detecting file modifications."""
        while True:
            try:
                if not self.config_path.exists():
                    time.sleep(1)
                    continue

                current_mtime = os.path.getmtime(self.config_path)

                if self._last_modified is None:
                    self._last_modified = current_mtime
                    time.sleep(1)
                    continue

                # File was modified
                if current_mtime != self._last_modified:
                    logger.info(f"📁 {self.name} changed — reloading...")
                    self._load_config()

                time.sleep(1)

            except FileNotFoundError:
                logger.warning(f"⚠️ {self.name} file missing")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Watcher error ({self.name}): {e}")
                time.sleep(2)

    def get(self, key: str, default=None):
        """Get value by key (simple dict-style getter)."""
        with self._lock:
            return self._config_cache.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Return entire config as a dictionary."""
        with self._lock:
            return dict(self._config_cache)

    def has_key(self, key: str) -> bool:
        """Check if key exists in config."""
        with self._lock:
            return key in self._config_cache


class ConfigWriter:
    """Write configurations to JSON files with validation."""

    def __init__(self, config_path: str, name: str = "Config"):
        self.config_path = Path(config_path)
        self.name = name

    def save(
        self, config: Dict[str, Any], validate: bool = True, backup: bool = True
    ) -> bool:
        """
        Save config to JSON file with optional backup and validation.

        Args:
            config: Dictionary to save
            validate: Validate JSON structure before saving
            backup: Create backup of existing file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate
            if validate:
                json_str = json.dumps(config, indent=2)
                # Will raise JSONDecodeError if invalid
                json.loads(json_str)

            # Create backup
            if backup and self.config_path.exists():
                backup_path = self.config_path.with_suffix(".json.bak")
                try:
                    with open(self.config_path, "r", encoding="utf-8") as src:
                        with open(backup_path, "w", encoding="utf-8") as dst:
                            dst.write(src.read())
                    logger.info(f"📦 Backup created: {backup_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Backup failed: {e}")

            # Create directory if needed
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            logger.info(f"✅ {self.name} saved: {self.config_path}")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON structure: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to save {self.name}: {e}")
            return False


class ConfigManager:
    """
    Unified configuration manager for all config files.

    Manages:
    - sensor_config.json (main config)
    - filter_config.json (filters by sensor)
    - calibration_config.json (calibration by channel)
    """

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Default: project_root/config/
            config_dir = Path(__file__).parent

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize watchers for all config files
        self.sensor_config = ConfigWatcher(
            self.config_dir / "sensor_config.json", name="SensorConfig"
        )
        self.filter_config = ConfigWatcher(
            self.config_dir / "filter_config.json", name="FilterConfig"
        )
        self.calib_config = ConfigWatcher(
            self.config_dir / "calibration_config.json", name="CalibrationConfig"
        )
        self.feature_config = ConfigWatcher(
            self.config_dir / "feature_config.json", name="FeatureConfig"
        )

        # Initialize writers
        self.sensor_writer = ConfigWriter(
            self.config_dir / "sensor_config.json", name="SensorConfig"
        )
        self.filter_writer = ConfigWriter(
            self.config_dir / "filter_config.json", name="FilterConfig"
        )
        self.calib_writer = ConfigWriter(
            self.config_dir / "calibration_config.json", name="CalibrationConfig"
        )
        self.feature_writer = ConfigWriter(
            self.config_dir / "feature_config.json", name="FeatureConfig"
        )

    # ============== SENSOR CONFIG ==============

    def get_sampling_rate(self, default: int = 512) -> int:
        """Get sampling rate from sensor config."""
        return int(self.sensor_config.get("sampling_rate", default))

    def get_channel_mapping(self) -> Dict[str, Any]:
        """Get channel-to-sensor mapping."""
        return self.sensor_config.get("channel_mapping", {})

    def get_channel_info(self, channel_key: str) -> Dict[str, Any]:
        """Get info for specific channel (ch0, ch1, etc)."""
        mapping = self.get_channel_mapping()
        return mapping.get(channel_key, {})

    def get_adc_settings(self) -> Dict[str, Any]:
        """Get ADC configuration."""
        return self.sensor_config.get("adc_settings", {})

    def get_ui_settings(self) -> Dict[str, Any]:
        """Get UI settings."""
        return self.sensor_config.get("ui_settings", {})

    def save_sensor_config(self, config: Dict[str, Any]) -> bool:
        """Save sensor configuration."""
        return self.sensor_writer.save(config, validate=True, backup=True)

    # ============== FILTER CONFIG ==============

    def get_filter_for_sensor(self, sensor_type: str) -> Dict[str, Any]:
        """Get filter configuration for a specific sensor type (EMG, EOG, EEG)."""
        return self.filter_config.get(sensor_type.upper(), {})

    def get_all_filters(self) -> Dict[str, Any]:
        """Get all sensor filters."""
        return self.filter_config.get_all()

    def save_filter_config(self, config: Dict[str, Any]) -> bool:
        """Save filter configuration."""
        return self.filter_writer.save(config, validate=True, backup=True)

    # ============== CALIBRATION CONFIG ==============

    def get_channel_calibration(self, channel_key: str) -> Dict[str, Any]:
        """Get calibration data for specific channel."""
        return self.calib_config.get(channel_key, {})

    def get_all_calibrations(self) -> Dict[str, Any]:
        """Get all channel calibrations."""
        return self.calib_config.get_all()

    def save_calibration_config(self, config: Dict[str, Any]) -> bool:
        """Save calibration configuration."""
        return self.calib_writer.save(config, validate=True, backup=True)

    # ============== FEATURE CONFIG ==============

    def get_feature_config(self) -> Dict[str, Any]:
        """Get all feature configuration."""
        return self.feature_config.get_all()

    def get_features_for_sensor(self, sensor_type: str) -> Dict[str, Any]:
        """Get feature config for a specific sensor type (EMG, EOG, etc)."""
        return self.feature_config.get(sensor_type.upper(), {})

    def save_feature_config(self, config: Dict[str, Any]) -> bool:
        """Save feature configuration."""
        return self.feature_writer.save(config, validate=True, backup=True)

    # ============== DETECTION STATE ==============

    def get_detection_state(self) -> bool:
        """Read detection active state from file."""
        state_path = self.config_dir / "detection_state.json"
        try:
            if state_path.exists():
                with open(state_path, 'r') as f:
                    data = json.load(f)
                    return data.get("active", False)
            return False
        except:
            return False

    # ============== FACADE (UNIFIED) ==============

    def get_all_configs(self) -> Dict[str, Any]:
        """
        Return a merged dictionary containing ALL configurations.
        Structure matches the legacy monolithic sensor_config.json for compatibility.
        """
        sensor = self.sensor_config.get_all()
        filters = self.filter_config.get_all()
        features = self.feature_config.get_all()

        # Start with sensor config (hardware/mapping)
        merged = sensor.copy()
        
        # Inject modular sections
        merged["filters"] = filters
        merged["features"] = features
        
        return merged

    # ============== UTILITY ==============

    def validate_json_file(self, filepath: Path) -> tuple[bool, str]:
        """
        Validate a JSON file.

        Returns:
            (is_valid, error_message)
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                json.load(f)
            return True, ""
        except json.JSONDecodeError as e:
            return False, f"JSON Syntax Error: {e}"
        except FileNotFoundError:
            return False, "File not found"
        except Exception as e:
            return False, str(e)


# ============================================================
# Global instances - use these throughout the application
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

# Create global manager
config_manager = ConfigManager(CONFIG_DIR)

# Convenience exports for backwards compatibility
sensor_config = config_manager.sensor_config
filter_config = config_manager.filter_config
calib_config = config_manager.calib_config
feature_config = config_manager.feature_config


# ============================================================
# Example Usage
# ============================================================

if __name__ == "__main__":
    print("Configuration Manager Demo")
    print("=" * 60)

    # Load configurations
    print("\n1. Load Sensor Config")
    print(f"   Sampling Rate: {config_manager.get_sampling_rate()} Hz")
    print(f"   Channel Mapping: {config_manager.get_channel_mapping()}")

    print("\n2. Load Filter Config")
    filters = config_manager.get_all_filters()
    for sensor, config in filters.items():
        print(f"   {sensor}: {config}")

    print("\n3. Load Calibration Config")
    calibs = config_manager.get_all_calibrations()
    for channel, calib in calibs.items():
        print(f"   {channel}: {calib}")

    print("\n✅ Configuration system initialized successfully")