import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SENSOR_CONFIG = CONFIG_DIR / "sensor_config.json"
FEATURE_CONFIG = CONFIG_DIR / "feature_config.json"
FILTER_CONFIG = CONFIG_DIR / "filter_config.json"

def migrate():
    print("Starting Configuration Migration...")
    
    if not SENSOR_CONFIG.exists():
        print(f"ERROR: {SENSOR_CONFIG} not found.")
        sys.exit(1)

    # 1. Load Monolithic Config
    with open(SENSOR_CONFIG, "r") as f:
        data = json.load(f)
    print(f"Loaded sensor_config.json ({len(data)} keys)")

    # 2. Extract Features
    features = data.pop("features", None)
    if features:
        print(f"Found features block: {list(features.keys())}")
        with open(FEATURE_CONFIG, "w") as f:
            json.dump(features, f, indent=2)
        print(f"Migrated features to {FEATURE_CONFIG}")
    else:
        print("⚠️ No features block found in sensor_config.")
        # Create empty if not exists
        if not FEATURE_CONFIG.exists():
             with open(FEATURE_CONFIG, "w") as f:
                json.dump({}, f, indent=2)

    # 3. Extract Filters
    # Check if filter_config already exists and has data?
    # The user analysis said filter_config HAS data but it mismatches.
    # We should probably PRIORITIZE sensor_config data if we want to preserve current behavior,
    # OR prioritize filter_config if that was the "intended" new source.
    # Given web_server uses sensor_config data, that is the "live" data. 
    # Let's overwrite filter_config with what was in sensor_config to ensure stability.
    
    filters = data.pop("filters", None)
    if filters:
        print(f"Found filters block: {list(filters.keys())}")
        with open(FILTER_CONFIG, "w") as f:
            json.dump(filters, f, indent=2)
        print(f"Migrated/Overwrote filters to {FILTER_CONFIG}")
    else:
        print("⚠️ No filters block found in sensor_config.")

    # 4. Save Cleaned Sensor Config
    with open(SENSOR_CONFIG, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Cleaned sensor_config.json")

    print("Migration Complete.")

if __name__ == "__main__":
    migrate()
