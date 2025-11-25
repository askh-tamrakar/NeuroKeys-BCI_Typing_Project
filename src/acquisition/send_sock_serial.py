import serial
import time
import numpy as np

# CONFIGURE:
SERIAL_PORT = "COM8"      # One end of your COM pair
BAUDRATE = 115200         # Must match Chords settings
CHANNELS = 8              # For 8-channel EEG
FS = 250                  # Sampling rate, Hz

def generate_mock_sample(channels=CHANNELS):
    """Generate an array of mock EEG/EMG/EOG values for 1 timepoint."""
    # Simulate with noise
    base = 0.1 * np.random.randn(channels)
    # Add occasional larger events
    if np.random.rand() < 0.05:
        base += 2.0 * np.random.randn(channels)
    # Scale to typical microvolt levels
    return (base * 100).astype(int)

ser = serial.Serial(SERIAL_PORT, BAUDRATE)
time.sleep(2)  # Let connection stabilize

print(f"Streaming mock data to {SERIAL_PORT}... Press Ctrl+C to stop.")

try:
    while True:
        sample = generate_mock_sample()
        # Format: "val1,val2,...,val8\\n" (Chords expects CSV lines)
        line = ",".join(map(str, sample)) + "\n"
        ser.write(line.encode("utf-8"))
        time.sleep(1.0 / FS)
except KeyboardInterrupt:
    print("Stopped streaming.")
finally:
    ser.close()
