"""
Verification script for EMG Processor updates.
Generates synthetic signals and verifies filtering/enveloping logic.
Produces visualization: test_emg_verification.png
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Ensure src is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.processing.emg_processor import EMGFilterProcessor

def run_verification():
    print("Testing EMG Processor...")
    
    # 1. Setup Processor with matching config
    config = {
        "filters": {
            "EMG": {
                "cutoff": 70.0,
                "order": 4,
                "notch_enabled": False, 
                "bandpass_enabled": False,
                "envelope_enabled": True,
                "envelope_cutoff": 10.0,
                "envelope_order": 4
            }
        }
    }
    
    sr = 512
    processor = EMGFilterProcessor(config, sr)
    
    # 2. Generate Synthetic Data
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration))
    
    # Signal A: Low Frequency Motion Artifact (10Hz) - Should be removed by HP
    sig_motion = 500 * np.sin(2 * np.pi * 10 * t)
    
    # Signal B: Mains Hum (50Hz) - Should be suppressed by Envelope LP
    sig_mains = 200 * np.sin(2 * np.pi * 50 * t)
    
    # Signal C: Muscle Burst (100Hz modulated) - Should be enveloped
    envelope_shape = np.exp(-0.5 * ((t - 1.0) / 0.1)**2) # Gaussian at 1.0s
    sig_muscle = 1000 * np.sin(2 * np.pi * 100 * t) * envelope_shape
    
    raw_signal = sig_motion + sig_mains + sig_muscle
    
    # 3. Process
    processed_signal = []
    
    # Pre-warm filter to settle state
    for _ in range(100):
        processor.process_sample(0)
        
    for val in raw_signal:
        processed_signal.append(processor.process_sample(val))
    
    processed_signal = np.array(processed_signal)
    
    # 4. Analysis
    max_motion_output = np.max(np.abs(processed_signal[:100])) # Early part is mostly motion
    max_burst_output = np.max(processed_signal)
    
    print(f"Max Amplitude (Raw): {np.max(np.abs(raw_signal)):.2f}")
    print(f"Max Amplitude (Processed): {max_burst_output:.2f}")
    
    # 5. Visualization
    plt.figure(figsize=(12, 8))
    
    plt.subplot(3, 1, 1)
    plt.title("Raw Synthetic Input (Motion + Mains + Burst)")
    plt.plot(t, raw_signal, color='gray', alpha=0.7, label='Raw')
    plt.plot(t, sig_muscle, color='blue', alpha=0.5, linestyle='--', label='True Muscle Component')
    plt.legend()
    plt.grid(True)
    
    plt.subplot(3, 1, 2)
    plt.title("Processed Output (High-Pass + Rectified + Low-Pass Envelope)")
    plt.plot(t, processed_signal, color='red', label='Envelope Output')
    plt.legend()
    plt.grid(True)
    
    plt.subplot(3, 1, 3)
    plt.title("Overlay (Zoomed on Burst)")
    plt.plot(t, np.abs(sig_muscle), color='gray', alpha=0.3, label='Abs(Muscle)')
    plt.plot(t, processed_signal, color='red', linewidth=2, label='Envelope')
    plt.xlim(0.8, 1.2)
    plt.legend()
    plt.grid(True)
    
    output_path = "test_emg_verification.png"
    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Visualization saved to: {output_path}")

if __name__ == "__main__":
    run_verification()
