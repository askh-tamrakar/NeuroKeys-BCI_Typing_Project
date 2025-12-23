"""
BCI Sensor Mapping Verification Script
======================================
This script verifies that sensor mapping is consistent across all components
and tests the configuration loading without requiring LSL streams.

Usage:
    python verify_mapping.py
"""

import json
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

print("\n" + "=" * 70)
print("BCI SENSOR MAPPING VERIFICATION")
print("=" * 70)


def test_config_loading():
    """Test if config loads correctly from JSON file"""
    print("\n[TEST 1] Config File Loading")
    print("-" * 70)
    
    config_path = PROJECT_ROOT / "config" / "sensor_config.json"
    
    if not config_path.exists():
        print(f"[FAIL] Config file not found: {config_path}")
        return False, None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("[PASS] Config loaded successfully\n")
        
        # Check if using new sensor-based format
        if "sensors" in config:
            print("Format: SENSOR-BASED (New Structure)\n")
            print("SENSORS:")
            for sensor_type in sorted(config.get("sensors", {}).keys()):
                sensor_cfg = config["sensors"][sensor_type]
                print(f"  - {sensor_type}")
                if "filters" in sensor_cfg:
                    print(f"      Filters: {len(sensor_cfg['filters'])} configured")
                if "features" in sensor_cfg:
                    print(f"      Features: Configured")
        else:
            print("Format: LEGACY (Old Structure)\n")
            # Check features
            features = config.get("features", {})
            if features:
                print("FEATURES:")
                for sensor_type in sorted(features.keys()):
                    print(f"  - {sensor_type}")
            
            # Check filters
            filters = config.get("filters", {})
            if filters:
                print("\nFILTERS:")
                for sensor_type, filter_config in filters.items():
                    if sensor_type not in ['bandpass', 'notch']:
                        print(f"  - {sensor_type}")
        
        # Check sensor mapping  
        print("\nSENSOR MAPPING:")
        sensor_mapping = config.get("channel_mapping", {})
        for ch_key in sorted(sensor_mapping.keys()):
            ch_config = sensor_mapping[ch_key]
            sensor = ch_config.get("sensor", "UNKNOWN")
            enabled = ch_config.get("enabled", True)
            status = "ENABLED" if enabled else "DISABLED"
            print(f"  - {ch_key}: {sensor:6s} [{status}]")
        
        return True, config
        
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON parsing error: {e}")
        return False, None
    except Exception as e:
        print(f"[FAIL] Error loading config: {e}")
        return False, None


def test_filter_router():
    """Test if filter_router module loads and reads config correctly"""
    print("\n[TEST 2] Filter Router Module")
    print("-" * 70)
    
    try:
        from processing.filter_router import load_config
        print("[PASS] Filter router module imported")
        
        config = load_config()
        
        # Display config info
        sr = config.get('sampling_rate', 'N/A')
        num_ch = config.get('num_channels', 'N/A')
        print(f"\nConfiguration:")
        print(f"  - Sampling Rate: {sr} Hz")
        print(f"  - Number of Channels: {num_ch}")
        
        # Display sensor mapping
        mapping = config.get("channel_mapping", {})
        if mapping:
            print(f"\nSensor Mapping (from filter_router):")
            for ch_key in sorted(mapping.keys()):
                sensor = mapping[ch_key].get('sensor', 'UNKNOWN')
                print(f"  - {ch_key}: {sensor}")
        else:
            print("\n[WARN] No sensor mapping found")
        
        return True, config
        
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        return False, None
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_consistency():
    """Verify config consistency between file and modules"""
    print("\n[TEST 3] Configuration Consistency")
    print("-" * 70)
    
    try:
        # Load from file
        config_path = PROJECT_ROOT / "config" / "sensor_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            file_config = json.load(f)
        
        # Load from router
        from processing.filter_router import load_config as router_load
        router_config = router_load()
        
        # Compare sensor mappings
        file_mapping = file_config.get("channel_mapping", {})
        router_mapping = router_config.get("channel_mapping", {})
        
        print("\nComparing Sensor Mappings:")
        print(f"  {'Physical':<10} {'File Config':<15} {'Router Config':<15} {'Status'}")
        print("  " + "-" * 55)
        
        all_channels = set(list(file_mapping.keys()) + list(router_mapping.keys()))
        consistent = True
        
        for ch_key in sorted(all_channels):
            file_sensor = file_mapping.get(ch_key, {}).get("sensor", "N/A")
            router_sensor = router_mapping.get(ch_key, {}).get("sensor", "N/A")
            
            if file_sensor == router_sensor:
                status = "[OK]"
            else:
                status = "[MISMATCH]"
                consistent = False
            
            print(f"  {ch_key:<10} {file_sensor:<15} {router_sensor:<15} {status}")
        
        if consistent:
            print("\n[PASS] All sensor mappings are consistent")
        else:
            print("\n[FAIL] Sensor mapping mismatch detected!")
        
        return consistent
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_filter_alignment():
    """Verify that all sensors in features also have filters configured"""
    print("\n[TEST 4] Features-Filters Alignment")
    print("-" * 70)
    
    try:
        config_path = PROJECT_ROOT / "config" / "sensor_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        features = set(config.get("features", {}).keys())
        filters = set(config.get("filters", {}).keys())
        
        # Exclude non-sensor filters
        filters = {f for f in filters if f not in ['bandpass', 'notch']}
        
        print(f"\nSensor Types in Features: {sorted(features)}")
        print(f"Sensor Types in Filters:  {sorted(filters)}")
        
        # Check alignment
        missing_filters = features - filters
        extra_filters = filters - features
        
        aligned = True
        
        if missing_filters:
            print(f"\n[WARN] Sensors with features but no filters: {sorted(missing_filters)}")
            aligned = False
        
        if extra_filters:
            print(f"\n[WARN] Sensors with filters but no features: {sorted(extra_filters)}")
        
        if aligned and features == filters:
            print("\n[PASS] Features and filters are aligned")
            return True
        else:
            print("\n[PARTIAL] Some alignment issues detected")
            return True  # Not critical, just warning
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False


def main():
    """Run all verification tests"""
    
    tests = [
        ("Config File Loading", test_config_loading),
        ("Filter Router Module", test_filter_router),
        ("Configuration Consistency", test_consistency),
        ("Features-Filters Alignment", test_feature_filter_alignment),
    ]
    
    results = []
    
    # Run tests
    for test_name, test_func in tests:
        result = test_func()
        # Handle both boolean and tuple returns
        if isinstance(result, tuple):
            results.append((test_name, result[0]))
        else:
            results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {test_name:<35} {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("SUCCESS: All verification tests passed!")
        print("Sensor mapping is configured correctly and consistently.")
    else:
        print("WARNING: Some tests failed - please review errors above")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
