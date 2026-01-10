
import json
import os
from pathlib import Path
import shutil

# --- MOCKING THE ENVIRONMENT ---
# We will create a temporary directory for config files
TEMP_DIR = Path("temp_config_test")
if TEMP_DIR.exists():
    shutil.rmtree(TEMP_DIR)
TEMP_DIR.mkdir()

CONFIG_PATH = TEMP_DIR / "sensor_config.json"
FILTER_CONFIG_PATH = TEMP_DIR / "filter_config.json"

# --- THE LOGIC TO TEST (Copied from web_server.py) ---
def save_config(config: dict) -> bool:
    try:
        if not isinstance(config, dict):
            raise ValueError("Config must be dict")
        
        # Ensure directory exists
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # 1. Save Filters to filter_config.json
        if 'filters' in config:
            filter_payload = {"filters": config['filters']}
            with open(FILTER_CONFIG_PATH, 'w') as f:
                json.dump(filter_payload, f, indent=2)
            print(f"[TEST] (SAVED) Filters saved to {FILTER_CONFIG_PATH}")

        # 2. Save Sensor/Display Config to sensor_config.json (exclude filters)
        sensor_payload = config.copy()
        if 'filters' in sensor_payload:
            del sensor_payload['filters']
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(sensor_payload, f, indent=2)
        
        print(f"[TEST] (SAVED) Sensor config saved to {CONFIG_PATH}")
        return True
    except Exception as e:
        print(f"[TEST] X Error saving config: {e}")
        return False

# --- THE TESTS ---

def test_save_separation():
    print("--- Test 1: Full Config (Separation) ---")
    full_config = {
        "sampling_rate": 512,
        "channel_mapping": {"ch0": "EMG"},
        "filters": {
            "EMG": {"cutoff": 20},
            "EEG": {"notch": 50}
        },
        "display": {"showGrid": True}
    }

    save_config(full_config)

    # CHECK FILTER FILE
    with open(FILTER_CONFIG_PATH) as f:
        f_data = json.load(f)
    if list(f_data.keys()) == ["filters"] and f_data["filters"]["EMG"]["cutoff"] == 20:
        print("[OK] Filter Config File: Correct (Contains only filters)")
    else:
        print(f"[FAIL] Filter Config File: FAILED. Content: {f_data}")

    # CHECK SENSOR FILE
    with open(CONFIG_PATH) as f:
        s_data = json.load(f)
    if "filters" not in s_data and s_data["sampling_rate"] == 512:
        print("[OK] Sensor Config File: Correct (Does NOT contain filters)")
    else:
        print(f"[FAIL] Sensor Config File: FAILED. Content: {s_data}")

def test_partial_update_no_filters():
    print("\n--- Test 2: Update Sensor Only (Preserve Separation) ---")
    # Scenario: Frontend sends update but MIGHT send filters or might not. 
    # Usually frontend ConfigService sends EVERYTHING.
    # But let's verify what happens if we send data WITHOUT filters.
    # If we send config WITHOUT filters, the logic says:
    # "if 'filters' in config: save to filter file"
    # So if filters are MISSING in input, filter file is NOT touched.
    
    # Setup files first
    with open(FILTER_CONFIG_PATH, 'w') as f:
        json.dump({"filters": {"EXISTING": True}}, f)
    
    partial_config = {
        "sampling_rate": 1024, # Changed
        "display": {"showGrid": False}
    }
    
    save_config(partial_config)
    
    # Filter file should be UNTOUCHED (or at least not overwritten with empty)
    # The logic: if 'filters' in config... NO. So it skips saving filters.
    # Result: Filter file remains as is. Correct.
    with open(FILTER_CONFIG_PATH) as f:
        f_data = json.load(f)
    if f_data["filters"]["EXISTING"] == True:
         print("[OK] Filter Config File: Protected (Not overwritten when filters missing)")
    
    # Sensor file should be updated
    with open(CONFIG_PATH) as f:
        s_data = json.load(f)
    if s_data["sampling_rate"] == 1024:
        print("[OK] Sensor Config File: Updated correctly")

def test_split_assurance():
    print("\n--- Test 3: Frontend sends merged config, Backend splits correctly ---")
    # This simulates what ConfigService.js sends: A merged object
    merged_input = {
        "num_channels": 4,
        "filters": { "EMG": "NEW_SETTINGS" }, # Filter data
        "display": { "theme": "Dark" }        # Sensor data
    }
    
    save_config(merged_input)
    
    with open(FILTER_CONFIG_PATH) as f:
        f_out = json.load(f)
    
    with open(CONFIG_PATH) as f:
        s_out = json.load(f)
        
    if f_out == {"filters": {"EMG": "NEW_SETTINGS"}} and "filters" not in s_out and s_out["display"]["theme"] == "Dark":
        print("[OK] Split Assurance: PASSED. Inputs split into respective files.")
    else:
        print("[FAIL] Split Assurance: FAILED")
        print(f"Filter File: {f_out}")
        print(f"Sensor File: {s_out}")

# --- RUN ---
if __name__ == "__main__":
    test_save_separation()
    test_partial_update_no_filters()
    test_split_assurance()
    
    # Cleanup
    # shutil.rmtree(TEMP_DIR)
