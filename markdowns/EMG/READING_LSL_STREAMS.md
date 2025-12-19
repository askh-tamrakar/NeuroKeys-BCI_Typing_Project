# 🔌 HOW TO READ FROM YOUR LSL STREAMS & EXTRACT FEATURES

## LSL (Lab Streaming Layer) Overview

```
What is LSL?
═══════════════════════════════════════════════════════════════
Lab Streaming Layer is a standardized system for streaming 
physiological data in real-time.

Your EMG processor streams two channels:
├─ Stream 1: BioSignal-Raw-uV (raw, noisy)
└─ Stream 2: BioSignal-Processed (filtered, clean) ← USE THIS!

Why LSL?
├─ Standard format (works with many applications)
├─ Real-time streaming (low latency)
├─ Easy to read programmatically
├─ Multiple applications can read simultaneously
└─ Professional-grade signal distribution!
```

---

## Understanding Your Two LSL Streams

### Stream 1: BioSignal-Raw-uV

```
STREAM PROPERTIES:
├─ Name: BioSignal-Raw-uV
├─ Type: EMG
├─ Channels: 1 (single electrode pair)
├─ Sampling rate: 512 Hz
├─ Units: Microvolts (uV)
├─ Data type: Float
└─ Status: Raw, unfiltered

CHARACTERISTICS:
├─ Contains: EMG + power line hum + drift + noise
├─ Frequency range: 0-512 Hz (includes all noise)
├─ Typical values: -5000 to +5000 uV
├─ Looks: Noisy, contains visible oscillations
└─ Usefulness: NOT good for features

WHEN TO READ THIS STREAM:
├─ Debugging (is hardware working?)
├─ Noise analysis (what's the noise level?)
├─ Filter verification (compare before/after)
└─ Research only (don't use for features)

VISUALIZATION:
Amplitude
    │
 500├─ ╱╲    ╱╲  ╱╲   ╱╲
    │╱╲╱ ╲╱╲╱  ╲╱  ╲ ╱  ╲ ╱╲
    │                      
    0├─ (noisy, lots of jitter)
    │
    └────────────────────→ Time
```

### Stream 2: BioSignal-Processed (USE THIS!)

```
STREAM PROPERTIES:
├─ Name: BioSignal-Processed
├─ Type: EMG
├─ Channels: 1 (single electrode pair)
├─ Sampling rate: 512 Hz
├─ Units: Microvolts (uV)
├─ Data type: Float
└─ Status: Filtered, cleaned

CHARACTERISTICS:
├─ Contains: EMG only (noise removed)
├─ Frequency range: 20-400 Hz (EMG band)
├─ Typical values: -4800 to +4800 uV
├─ Looks: Smooth with clear patterns
└─ Usefulness: PERFECT for features!

WHEN TO READ THIS STREAM:
├─ Feature extraction ✅ (ALWAYS!)
├─ Real-time classification ✅
├─ Any analysis requiring clean signal ✅
└─ This is your primary input!

VISUALIZATION:
Amplitude
    │
 500├─ ╱╲       ╱╲
    │╱  ╲     ╱  ╲
    │     ╲   ╱   ╲    ╱╲
    0├─    ╲╱      ╲╱   (smooth, clean)
    │
    └────────────────────→ Time
```

---

## Reading from LSL Streams in Python

### Method 1: Using pylsl (Official Python Library)

```python
from pylsl import StreamInlet, resolve_stream
import numpy as np

# ═══════════════════════════════════════════════════════════════
# STEP 1: Find the LSL stream
# ═══════════════════════════════════════════════════════════════

def find_stream(stream_name="BioSignal-Processed", timeout=5):
    """
    Find and connect to an LSL stream
    
    Args:
        stream_name: Name of the stream to find
                    Options: "BioSignal-Processed" (clean)
                            "BioSignal-Raw-uV" (raw, noisy)
        timeout: How long to search (seconds)
    
    Returns:
        StreamInlet object to read from
    """
    
    print(f"Looking for stream: {stream_name}")
    
    # Search for the stream
    streams = resolve_stream('name', stream_name, timeout=timeout)
    
    if len(streams) == 0:
        raise RuntimeError(f"Stream '{stream_name}' not found!")
    
    print(f"✓ Found stream: {streams[0].name()}")
    print(f"  Type: {streams[0].type()}")
    print(f"  Channels: {streams[0].channel_count()}")
    print(f"  Sampling rate: {streams[0].nominal_srate()} Hz")
    
    # Create inlet to read from stream
    inlet = StreamInlet(streams[0])
    return inlet


# ═══════════════════════════════════════════════════════════════
# STEP 2: Read samples from stream
# ═══════════════════════════════════════════════════════════════

def read_single_sample(inlet):
    """
    Read one sample from stream
    
    Returns:
        (sample_value, timestamp)
    """
    sample, timestamp = inlet.pull_sample()
    # sample is a list (even for 1 channel)
    # sample[0] is the actual EMG value in uV
    return sample[0], timestamp


def read_multiple_samples(inlet, num_samples):
    """
    Read multiple samples from stream
    
    Returns:
        list of EMG values (in uV)
    """
    samples = []
    for _ in range(num_samples):
        sample, _ = inlet.pull_sample()
        samples.append(sample[0])  # Extract uV value
    return samples


def read_window_with_timeout(inlet, window_size=512, timeout_ms=2000):
    """
    Read exactly 'window_size' samples with timeout
    
    Args:
        inlet: LSL stream inlet
        window_size: How many samples to read (512 for 1 second at 512 Hz)
        timeout_ms: Timeout in milliseconds
    
    Returns:
        list of EMG values or None if timeout
    """
    samples = []
    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0
    
    while len(samples) < window_size:
        try:
            sample, _ = inlet.pull_sample(timeout=0.1)
            if sample is not None:
                samples.append(sample[0])
        except:
            pass
        
        # Check timeout
        if (time.time() - start_time) > timeout_sec:
            print(f"Timeout! Only got {len(samples)} samples")
            return None
    
    return samples


# ═══════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import time
    
    # Connect to processed stream
    inlet = find_stream("BioSignal-Processed")
    
    # Read a window of data
    print("\nReading 512 samples (1 second at 512 Hz)...")
    samples = read_multiple_samples(inlet, 512)
    
    print(f"Read {len(samples)} samples")
    print(f"Min: {min(samples):.1f} uV")
    print(f"Max: {max(samples):.1f} uV")
    print(f"Mean: {np.mean(samples):.1f} uV")
    print(f"Std: {np.std(samples):.1f} uV")
```

### Method 2: Real-Time Feature Extraction Pipeline

```python
from pylsl import StreamInlet, resolve_stream
import numpy as np
import time

class EMGFeatureExtractor:
    """Extract features from LSL EMG stream in real-time"""
    
    def __init__(self, stream_name="BioSignal-Processed", 
                 window_size=512, sampling_rate=512):
        """
        Initialize feature extractor
        
        Args:
            stream_name: "BioSignal-Processed" (clean, recommended)
                        or "BioSignal-Raw-uV" (noisy, debug only)
            window_size: Number of samples per window (512 = 1 second)
            sampling_rate: 512 Hz
        """
        self.window_size = window_size
        self.sampling_rate = sampling_rate
        
        # Find and connect to stream
        print(f"[EMG] Connecting to stream: {stream_name}")
        streams = resolve_stream('name', stream_name, timeout=5)
        if not streams:
            raise RuntimeError(f"Stream '{stream_name}' not found!")
        
        self.inlet = StreamInlet(streams[0])
        print(f"[EMG] Connected! Rate: {streams[0].nominal_srate()} Hz")
        
        # Buffer for windowing
        self.buffer = []
    
    def add_sample(self, emg_value):
        """Add one sample to buffer"""
        self.buffer.append(emg_value)
        
        # Keep buffer size bounded (prevent memory issues)
        if len(self.buffer) > self.window_size * 2:
            self.buffer.pop(0)
    
    def get_window_ready(self):
        """Check if we have enough samples for feature extraction"""
        return len(self.buffer) >= self.window_size
    
    def extract_window(self):
        """Extract features from current window"""
        if not self.get_window_ready():
            return None
        
        # Get window (512 samples)
        window = self.buffer[:self.window_size]
        
        # Extract all 10 features
        features = {
            'rms': self.calc_rms(window),
            'mav': self.calc_mav(window),
            'zcr': self.calc_zcr(window),
            'variance': self.calc_variance(window),
            'waveform_length': self.calc_waveform_length(window),
            'peak': self.calc_peak(window),
            'range': self.calc_range(window),
            'iemg': self.calc_iemg(window),
            'entropy': self.calc_entropy(window),
            'energy': self.calc_energy(window)
        }
        
        # Slide window (50% overlap)
        self.buffer = self.buffer[self.window_size // 2:]
        
        return features
    
    # ─────────────────────────────────────────────────────────
    # Feature calculation methods
    # ─────────────────────────────────────────────────────────
    
    def calc_rms(self, signal):
        """Root Mean Square - Muscle intensity"""
        return np.sqrt(np.mean(np.array(signal) ** 2))
    
    def calc_mav(self, signal):
        """Mean Absolute Value - Average activity"""
        return np.mean(np.abs(signal))
    
    def calc_zcr(self, signal):
        """Zero Crossing Rate - Frequency content"""
        signal = np.array(signal)
        mean = np.mean(signal)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(signal - mean)))) / 2
        return zero_crossings / len(signal)
    
    def calc_variance(self, signal):
        """Variance - Signal spread"""
        return np.var(signal)
    
    def calc_waveform_length(self, signal):
        """Waveform Length - Complexity"""
        return np.sum(np.abs(np.diff(signal)))
    
    def calc_peak(self, signal):
        """Peak - Maximum amplitude"""
        return np.max(np.abs(signal))
    
    def calc_range(self, signal):
        """Range - Max-Min span"""
        return np.max(signal) - np.min(signal)
    
    def calc_iemg(self, signal):
        """Integrated EMG - Total activity"""
        return np.sum(np.abs(signal))
    
    def calc_entropy(self, signal):
        """Entropy - Signal randomness"""
        signal = np.array(signal)
        hist, _ = np.histogram(signal, bins=20)
        hist = hist / len(signal)
        entropy = -np.sum(hist * np.log2(hist + 1e-10))
        return entropy
    
    def calc_energy(self, signal):
        """Energy - Power in signal"""
        return np.sum(np.array(signal) ** 2) / len(signal)
    
    def run_realtime(self, callback=None):
        """
        Run real-time feature extraction
        
        Args:
            callback: Function to call when features ready
                     callback(features) is called
        """
        print("[EMG] Starting real-time extraction...")
        
        try:
            while True:
                # Read one sample from stream
                sample, timestamp = self.inlet.pull_sample(timeout=1.0)
                
                if sample is None:
                    continue
                
                # Add to buffer
                self.add_sample(sample[0])
                
                # When window ready, extract features
                if self.get_window_ready():
                    features = self.extract_window()
                    
                    if callback:
                        callback(features)
                    else:
                        print(f"Features: RMS={features['rms']:.0f} uV, "
                              f"ZCR={features['zcr']:.3f}")
        
        except KeyboardInterrupt:
            print("[EMG] Stopped")


# ═══════════════════════════════════════════════════════════════
# COMPLETE EXAMPLE
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    
    # Create extractor (automatically connects to stream)
    extractor = EMGFeatureExtractor(
        stream_name="BioSignal-Processed",  # Use filtered stream!
        window_size=512  # 1 second at 512 Hz
    )
    
    # Define callback for when features are ready
    def on_features_ready(features):
        """Called when features extracted"""
        print("─" * 60)
        print(f"RMS:              {features['rms']:>10.0f} uV")
        print(f"MAV:              {features['mav']:>10.0f} uV")
        print(f"ZCR:              {features['zcr']:>10.4f}")
        print(f"Variance:         {features['variance']:>10.0f}")
        print(f"Waveform Length:  {features['waveform_length']:>10.0f}")
        print(f"Peak:             {features['peak']:>10.0f} uV")
        print(f"Range:            {features['range']:>10.0f} uV")
        print(f"IEMG:             {features['iemg']:>10.0f} uV")
        print(f"Entropy:          {features['entropy']:>10.2f}")
        print(f"Energy:           {features['energy']:>10.0f}")
    
    # Run real-time extraction
    extractor.run_realtime(callback=on_features_ready)
```

### Method 3: Buffered Reading (No Blocking)

```python
from pylsl import StreamInlet, resolve_stream
import numpy as np
import threading
import queue

class NonBlockingEMGReader:
    """Read from LSL stream without blocking main thread"""
    
    def __init__(self, stream_name="BioSignal-Processed"):
        """Setup background thread to read from stream"""
        
        # Find stream
        streams = resolve_stream('name', stream_name, timeout=5)
        self.inlet = StreamInlet(streams[0])
        
        # Queue for samples
        self.sample_queue = queue.Queue()
        
        # Background thread
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        
        print(f"[EMG] Reader started for {stream_name}")
    
    def _read_loop(self):
        """Background thread: continuously read samples"""
        while True:
            try:
                sample, _ = self.inlet.pull_sample(timeout=1.0)
                if sample is not None:
                    self.sample_queue.put(sample[0])
            except:
                pass
    
    def get_samples(self, num_samples, block=True):
        """
        Get samples from queue (non-blocking option)
        
        Args:
            num_samples: How many to get
            block: If True, wait until available
                  If False, return what's available
        
        Returns:
            list of samples (may be shorter if block=False)
        """
        samples = []
        
        for _ in range(num_samples):
            try:
                sample = self.sample_queue.get(block=block, timeout=0.1)
                samples.append(sample)
            except queue.Empty:
                if not block:
                    break
        
        return samples
    
    def get_window(self, window_size=512):
        """Get a full window of data"""
        return self.get_samples(window_size, block=True)


# Usage
if __name__ == "__main__":
    reader = NonBlockingEMGReader("BioSignal-Processed")
    
    for i in range(5):
        print(f"\nWindow {i+1}:")
        window = reader.get_window(512)
        print(f"  Got {len(window)} samples")
        print(f"  Min: {min(window):.0f} uV")
        print(f"  Max: {max(window):.0f} uV")
        print(f"  Mean: {np.mean(window):.0f} uV")
```

---

## Installation & Setup

### Install Required Libraries

```bash
# Install pylsl (official LSL Python library)
pip install pylsl

# Install numpy (for calculations)
pip install numpy

# Optional: for visualization
pip install matplotlib

# Optional: for advanced ML features
pip install scikit-learn
```

### Verify LSL Stream is Running

```python
from pylsl import resolve_stream

# Check if stream exists
print("Looking for LSL streams...")

# Try to find processed stream
processed_streams = resolve_stream('name', 'BioSignal-Processed', timeout=2)
if processed_streams:
    print("✓ BioSignal-Processed found!")
else:
    print("✗ BioSignal-Processed NOT found")

# Try to find raw stream
raw_streams = resolve_stream('name', 'BioSignal-Raw-uV', timeout=2)
if raw_streams:
    print("✓ BioSignal-Raw-uV found!")
else:
    print("✗ BioSignal-Raw-uV NOT found")
```

---

## Best Practices for Feature Extraction from LSL

### DO's ✅

```python
# ✅ DO: Read from BioSignal-Processed (filtered)
inlet = find_stream("BioSignal-Processed")

# ✅ DO: Use 1-second windows (512 samples at 512 Hz)
window_size = 512

# ✅ DO: Check stream is available before reading
if stream_available:
    sample = inlet.pull_sample()

# ✅ DO: Handle timeout gracefully
try:
    sample, _ = inlet.pull_sample(timeout=1.0)
except RuntimeError:
    print("Stream timeout!")

# ✅ DO: Use reasonable overlap (50%)
new_buffer = buffer[256:]  # Keep second half

# ✅ DO: Validate samples before processing
if sample is not None and len(sample) > 0:
    process(sample[0])
```

### DON'Ts ❌

```python
# ❌ DON'T: Read from raw stream for features
inlet = find_stream("BioSignal-Raw-uV")  # Noisy!

# ❌ DON'T: Use tiny windows (<100 ms)
window_size = 50  # Too short, noisy features

# ❌ DON'T: Block forever waiting for data
sample = inlet.pull_sample()  # No timeout!

# ❌ DON'T: Process invalid/None samples
sample, _ = inlet.pull_sample()
value = sample[0]  # Crash if sample is None!

# ❌ DON'T: Assume stream always available
inlet = StreamInlet(streams[0])  # What if streams empty?

# ❌ DON'T: Ignore sampling rate
# Always know your stream's sampling rate!
```

---

## Troubleshooting Common Issues

### Issue 1: Stream Not Found

```python
# Problem: "Stream not found"

# Solution 1: Check stream name spelling
resolve_stream('name', 'BioSignal-Processed')  # Exact name!

# Solution 2: Increase timeout
resolve_stream('name', 'BioSignal-Processed', timeout=10)

# Solution 3: Check if EMG processor is running
# Make sure EMG processor application is running!

# Solution 4: List all available streams
from pylsl import resolve_streams
all_streams = resolve_streams()
print([s.name() for s in all_streams])
```

### Issue 2: Samples are None

```python
# Problem: "Getting None samples"

# Solution: Use timeout and error handling
try:
    sample, _ = inlet.pull_sample(timeout=1.0)
    if sample is None:
        print("No sample available")
    else:
        process(sample[0])
except RuntimeError:
    print("Stream timeout or error")
```

### Issue 3: Extremely High/Low Values

```python
# Problem: "Values are -5000 or +5000 uV consistently"

# Likely cause: Electrode problem
# Solution:
# 1. Check electrode contact
# 2. Check electrode placement
# 3. Check if EMG processor is filtering properly
# 4. Try reading from raw stream to see if hardware OK
```

### Issue 4: Inconsistent Features

```python
# Problem: "Same gesture gives different features each time"

# Likely cause: Reading from raw stream (too noisy)
# Solution:
inlet = find_stream("BioSignal-Processed")  # Use filtered!

# Alternative cause: Poor electrode placement
# Solution: Adjust electrode position
```

---

## Summary: Reading Your LSL Streams

```
STEP 1: Install pylsl
└─ pip install pylsl

STEP 2: Find stream
└─ streams = resolve_stream('name', 'BioSignal-Processed')

STEP 3: Create inlet
└─ inlet = StreamInlet(streams[0])

STEP 4: Read samples
└─ sample, timestamp = inlet.pull_sample()

STEP 5: Extract features
└─ features = extract_10_features(window)

STEP 6: Classify gesture
└─ gesture = model.predict(features)

YOUR STREAMS:
├─ BioSignal-Raw-uV: Raw, noisy (debug only)
└─ BioSignal-Processed: Clean, filtered (use this!)

KEY POINTS:
✅ Always read from BioSignal-Processed
✅ Use 1-second windows (512 samples)
✅ Check for None before processing
✅ Handle timeouts gracefully
✅ Use 50% window overlap
✅ Validate data quality

YOU'RE READY TO EXTRACT FEATURES! 🚀
```

---

**Status:** ✅ Complete guide to reading your LSL streams!

Now you can connect to your EMG processor and start extracting features! 📊
