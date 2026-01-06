import wave
import math
import struct
import os
import random

def generate_tone(filename, duration=0.5, freq_start=440.0, freq_end=440.0, volume=0.5, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(n_samples):
            t = i / sample_rate
            # Linear frequency sweep
            progress = i / n_samples
            current_freq = freq_start + (freq_end - freq_start) * progress
            
            # Sine wave
            value = math.sin(2 * math.pi * current_freq * t)
            
            # Apply volume and envelope (fade out at end)
            envelope = 1.0
            if progress > 0.9:
                envelope = 1.0 - (progress - 0.9) * 10
            
            data = int(value * volume * envelope * 32767.0)
            wav_file.writeframes(struct.pack('<h', data))

def generate_noise(filename, duration=1.0, volume=0.2, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(n_samples):
            value = random.uniform(-1, 1)
            data = int(value * volume * 32767.0)
            wav_file.writeframes(struct.pack('<h', data))

output_dir = r"D:\Neuroscience\BCI\src\web\frontend\public\sounds"
os.makedirs(output_dir, exist_ok=True)

print("Generating sounds...")

# Jump: Quick rising pitch (Boop!)
generate_tone(os.path.join(output_dir, "jump.wav"), duration=0.3, freq_start=300, freq_end=600, volume=0.6)
print("Created jump.wav")

# Hover: Very short high pitch tick
generate_tone(os.path.join(output_dir, "hover.wav"), duration=0.05, freq_start=800, freq_end=1200, volume=0.3)
print("Created hover.wav")

# Background: Low pulsating drone (simulated with low freq sine)
generate_tone(os.path.join(output_dir, "background.wav"), duration=5.0, freq_start=100, freq_end=105, volume=0.2)
print("Created background.wav")

print("Done.")
