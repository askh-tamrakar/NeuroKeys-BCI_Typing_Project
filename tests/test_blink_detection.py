import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from feature.extractors.blink_extractor import BlinkExtractor
from feature.detectors.blink_detector import BlinkDetector

def generate_blink(sr, duration_ms, amplitude):
    """Generates a synthetic asymmetric blink waveform."""
    t = np.linspace(0, duration_ms / 1000.0, int((duration_ms / 1000.0) * sr))
    # Gaussian-like with asymmetry
    peak_t = 0.05 # 50ms rise
    sigma_rise = 0.02
    sigma_fall = 0.06
    
    y = np.zeros_like(t)
    for i, ti in enumerate(t):
        if ti < peak_t:
            y[i] = amplitude * np.exp(-((ti - peak_t)**2) / (2 * sigma_rise**2))
        else:
            y[i] = amplitude * np.exp(-((ti - peak_t)**2) / (2 * sigma_fall**2))
    return y

def test_blink_detection():
    sr = 512
    config = {
        "features": {
            "EOG": {
                "amp_threshold": 50.0,
                "min_duration_ms": 100.0,
                "max_duration_ms": 500.0
            }
        }
    }
    
    extractor = BlinkExtractor(0, config, sr)
    detector = BlinkDetector(config)
    
    # 1. Test Valid Blink
    print("\n--- Testing Valid Blink ---")
    blink_sig = generate_blink(sr, 300, 100.0)
    # Add some noise
    blink_sig += np.random.normal(0, 2, len(blink_sig))
    
    detector.min_kurtosis = -2.0 # Relax for synthetic test
    
    detected = False
    for val in blink_sig:
        features = extractor.process(val)
        if features:
            print(f"Candidate detected: {features}")
            if detector.detect(features):
                print("[PASS] Blink correctly classified!")
                detected = True
                break
    
    if not detected:
        print("[FAIL] Failed to detect valid blink")

    # 2. Test Small Signal (Noise)
    print("\n--- Testing Low Amplitude Noise ---")
    noise_sig = np.random.normal(0, 5, 512)
    detected = False
    for val in noise_sig:
        features = extractor.process(val)
        if features:
            if detector.detect(features):
                print("[FAIL] ERROR: Detected noise as blink!")
                detected = True
    if not detected:
        print("[PASS] Noise correctly ignored.")

    # 3. Test Too Symmetric (Artifact)
    print("\n--- Testing Symmetric Artifact ---")
    # A symmetric Gaussian might have asymmetry ~1.0
    t = np.linspace(-0.1, 0.1, 100)
    sym_sig = 100.0 * np.exp(-(t**2) / (2 * 0.02**2))
    detected = False
    for val in sym_sig:
        features = extractor.process(val)
        if features:
            print(f"Features: {features}")
            if detector.detect(features):
                print("[FAIL] ERROR: Detected symmetric artifact as blink!")
                detected = True
    if not detected:
        print("[PASS] Symmetric artifact correctly ignored.")

if __name__ == "__main__":
    test_blink_detection()
