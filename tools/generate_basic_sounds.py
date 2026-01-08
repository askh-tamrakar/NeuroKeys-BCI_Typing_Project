import wave
import math
import struct
import os
import random

def generate_tone(filename, duration=0.5, freq_start=440.0, freq_end=440.0, volume=0.5, sample_rate=44100, wave_type='sine'):
    n_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(n_samples):
            t = i / sample_rate
            progress = i / n_samples
            
            # Frequency sweep
            current_freq = freq_start + (freq_end - freq_start) * (progress**2) # Exponential sweep
            
            # Waveform generation
            phase = 2 * math.pi * current_freq * t
            if wave_type == 'sine':
                value = math.sin(phase)
            elif wave_type == 'square':
                value = 1.0 if math.sin(phase) > 0 else -1.0
            elif wave_type == 'sawtooth':
                value = 2.0 * (t * current_freq - math.floor(0.5 + t * current_freq))
            elif wave_type == 'triangle':
                value = 2.0 * abs(2.0 * (t * current_freq - math.floor(t * current_freq + 0.5))) - 1.0
            else:
                value = math.sin(phase)

            # Envelope (Attack/Decay)
            envelope = 1.0
            if progress < 0.1: # Attack
                envelope = progress / 0.1
            elif progress > 0.8: # Release
                envelope = (1.0 - progress) / 0.2
            
            data = int(value * volume * envelope * 32767.0)
            wav_file.writeframes(struct.pack('<h', data))

def generate_noise_burst(filename, duration=0.1, volume=0.5, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(n_samples):
            progress = i / n_samples
            envelope = 1.0 - progress # Direct fade out
            
            value = random.uniform(-1, 1)
            data = int(value * volume * envelope * 32767.0)
            wav_file.writeframes(struct.pack('<h', data))

output_dir = r"D:\Neuroscience\BCI\src\web\frontend\public\sounds"
os.makedirs(output_dir, exist_ok=True)

print("Generating new sounds...")

# Jump: Retro "Jay-ump" (Square wave, rising pitch)
generate_tone(os.path.join(output_dir, "jump.wav"), duration=0.3, freq_start=150, freq_end=450, volume=0.4, wave_type='square')

# Hover: High-tech "Pip" (Sine, very short, high pitch)
generate_tone(os.path.join(output_dir, "hover.wav"), duration=0.08, freq_start=1200, freq_end=1500, volume=0.2, wave_type='sine')

# Click: Mechanical "Clack" (Noise burst + short tone)
generate_noise_burst(os.path.join(output_dir, "click.wav"), duration=0.05, volume=0.6)

# Background: Ambient Space Drone (Low triangle wave, slow pulsation)
generate_tone(os.path.join(output_dir, "background.wav"), duration=5.0, freq_start=60, freq_end=65, volume=0.3, wave_type='triangle')

print("New sounds generated.")
