
import sys
import os
from pathlib import Path

# Add project root to path
project_root = str(Path(os.getcwd()))
sys.path.append(project_root)

try:
    from src.processing.emg_processor import EMGFilterProcessor
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

def test_fix():
    print("Testing EMGFilterProcessor with Notch Freq = 0...")
    
    # Config with Notch Enabled but Freq 0 (Problematic usage)
    config = {
        "filters": {
            "EMG": {
                "cutoff": 20.1,
                "order": 4,
                "notch_enabled": True,
                "notch_freq": 0,  # THE CULPRIT
                "bandpass_enabled": False,
                "envelope_enabled": True,
                "envelope_cutoff": 10.0
            }
        }
    }
    
    try:
        processor = EMGFilterProcessor(config, sr=512, channel_key="ch0")
        print("Initialization: OK")
        
        # Test update_config as well
        new_config = config.copy()
        new_config["filters"]["EMG"]["notch_freq"] = 0
        processor.update_config(new_config, sr=512)
        print("Update Config: OK")
        
        # Test processing
        val = processor.process_sample(100.0)
        print(f"Process Sample: OK (Order Check: {val:.4f})")
        
    except Exception as e:
        print(f"TEST FAILED with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fix()
