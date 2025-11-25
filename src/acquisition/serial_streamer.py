# src/acquisition/serial_streamer.py

import serial
import time
import numpy as np
import struct

class ChordsSerialStreamer:
    """Stream mock BCI data to Chords via serial port"""
    
    def __init__(self, port='/dev/pts/2', baudrate=115200, channels=8, fs=250):
        """
        Args:
            port: Serial port (use virtual port from socat)
            baudrate: Must match Chords settings (usually 115200 or 230400)
            channels: Number of EEG/EMG/EOG channels
            fs: Sampling rate in Hz
        """
        self.port = port
        self.baudrate = baudrate
        self.channels = channels
        self.fs = fs
        self.ser = None
    
    def connect(self):
        """Open serial connection"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            print(f"✓ Connected to {self.port} at {self.baudrate} baud")
            time.sleep(2)  # Wait for connection to stabilize
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def generate_sample(self):
        """Generate one sample of mock data (all channels)"""
        # Base noise
        sample = 0.1 * np.random.randn(self.channels)
        
        # Add occasional "event" (blink, movement, etc.)
        if np.random.rand() < 0.05:  # 5% chance
            sample += 2.0 * np.random.randn(self.channels)
        
        # Scale to microvolts (typical EEG range: ±100 µV)
        sample = sample * 50.0  # ±5 µV baseline noise, ±100 µV events
        
        return sample
    
    def format_for_chords(self, sample):
        """
        Format data for Chords
        
        Upside Down Labs devices typically send data as:
        - Start byte(s)
        - Channel data (16-bit or 24-bit integers)
        - End byte(s)
        
        Check Chords documentation for exact format!
        """
        # Common format: comma-separated values + newline
        # Example: "ch1,ch2,ch3,ch4,ch5,ch6,ch7,ch8\n"
        formatted = ",".join([f"{int(val)}" for val in sample]) + "\n"
        return formatted.encode('utf-8')
    
    def stream(self, duration=None):
        """
        Stream data continuously
        
        Args:
            duration: Stream duration in seconds (None = infinite)
        """
        if not self.ser:
            print("Not connected! Call connect() first.")
            return
        
        print(f"Streaming {self.channels} channels at {self.fs} Hz...")
        print("Press Ctrl+C to stop")
        
        start_time = time.time()
        sample_count = 0
        
        try:
            while True:
                # Generate and send one sample
                sample = self.generate_sample()
                data = self.format_for_chords(sample)
                self.ser.write(data)
                
                sample_count += 1
                
                # Maintain sampling rate
                time.sleep(1.0 / self.fs)
                
                # Status update every second
                if sample_count % self.fs == 0:
                    elapsed = time.time() - start_time
                    print(f"Sent {sample_count} samples ({elapsed:.1f}s)")
                
                # Stop after duration if specified
                if duration and (time.time() - start_time) >= duration:
                    break
                    
        except KeyboardInterrupt:
            print("\n✓ Streaming stopped by user")
        except Exception as e:
            print(f"\n✗ Error: {e}")
        finally:
            self.close()
    
    def close(self):
        """Close serial connection"""
        if self.ser:
            self.ser.close()
            print("✓ Serial port closed")


# Usage
if __name__ == "__main__":
    # Configure for your Upside Down Labs device
    streamer = ChordsSerialStreamer(
        port= "COM6",      # Change to your virtual port
        baudrate=115200,        # Match Chords settings
        channels=8,             # EEG channels
        fs=250                  # Sampling rate
    )
    
    if streamer.connect():
        streamer.stream(duration=60)  # Stream for 60 seconds
