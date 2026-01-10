
import sys
import os
from pathlib import Path
import numpy as np

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from feature.extractors.rps_extractor import RPSExtractor

def test_extractor():
    print("[TEST] Initializing RPSExtractor...")
    try:
        # Pseudo channel index 0, dummy config, sr 512
        extractor = RPSExtractor(0, {}, 512)
        
        # Create a dummy enveloped signal (positive values)
        # Sine wave + offset
        t = np.linspace(0, 1, 512)
        signal = np.abs(np.sin(2 * np.pi * 5 * t)) # Enveloped-ish
        
        print("[TEST] Processing 512 samples...")
        features = None
        for i, val in enumerate(signal):
            res = extractor.process(val)
            if res:
                features = res
                print(f"[TEST] Features extracted at sample {i+1}")
                break
                
        if features:
            print("[TEST] Extracted Features Keys:", list(features.keys()))
            
            required = ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
            forbidden = ['zcr']
            
            missing = [k for k in required if k not in features]
            present_forbidden = [k for k in forbidden if k in features]
            
            if not missing and not present_forbidden:
                print("[TEST] SUCCESS: All new features present, ZCR removed.")
                # Print values for sanity check
                print(json.dumps(features, indent=2))
            else:
                print(f"[TEST] FAILURE: Missing: {missing}, Unexpected: {present_forbidden}")
        else:
            print("[TEST] FAILURE: No features extracted (buffer logic issues?)")

    except Exception as e:
        print(f"[TEST] CRASH: {e}")
        import traceback
        traceback.print_exc()

import json
if __name__ == "__main__":
    test_extractor()
