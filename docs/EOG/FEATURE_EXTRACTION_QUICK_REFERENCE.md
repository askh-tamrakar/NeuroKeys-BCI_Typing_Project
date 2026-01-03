# Feature Extraction - Quick Reference Guide

## What is Feature Extraction?

**Definition:** The process of transforming raw signal data into meaningful, compact measurements that represent the essential characteristics of the data.

```
Raw Signal (512 samples)
    ↓
Feature Extraction
    ↓
Feature Vector (10-20 numbers)
```

---

## Why Does It Matter?

| Without Features | With Features |
|---|---|
| 512 data points per event | 15 meaningful values |
| Hard to interpret | Easy to understand |
| High-dimensional problem | Low-dimensional problem |
| Noisy and complex | Clean and simplified |
| Difficult to classify | Simple to classify |

---

## Main Categories of Features

### 1. **Temporal Features** (Time-Based)
What happens over time?

```
Duration:           How long is the event? (e.g., 200 ms)
Rise Time:          How fast does it go up? (e.g., 50 ms)
Fall Time:          How fast does it come down? (e.g., 150 ms)
Velocity:           Speed of change (e.g., 0.07 µV/ms)
Acceleration:       Rate of velocity change
Peak Timing:        When does the peak occur?
```

### 2. **Amplitude Features** (Signal Strength)
How strong is the signal?

```
Peak Amplitude:     Highest value (e.g., 3.5 µV)
Baseline:           Resting value (e.g., 0.1 µV)
Range:              Min to max span (e.g., 3.4 µV)
RMS:                Root mean square (e.g., 2.1 µV)
Signal-to-Noise:    Ratio of signal to noise (e.g., 35:1)
```

### 3. **Statistical Features** (Distribution)
What does the data distribution look like?

```
Mean:               Average value (0.8 µV)
Median:             Middle value (0.7 µV)
Std Deviation:      How spread out (1.5 µV)
Variance:           Spread squared (2.25 µV²)
Skewness:           Asymmetry (-0.35)
Kurtosis:           Peakedness (2.8)
```

### 4. **Spectral Features** (Frequency)
What frequencies are present?

```
Peak Frequency:     Most common frequency (e.g., 1.0 Hz)
Bandwidth:          Range of frequencies (e.g., 0.5-2 Hz)
Spectral Power:     Energy at each frequency
Spectral Centroid:  "Center" of frequency distribution
Energy in Band:     Percent of energy in band (e.g., 82%)
```

### 5. **Shape Features** (Morphology)
What does it look like?

```
Symmetry:           Is it symmetric? (e.g., 0.33 = asymmetric)
Peak Width:         How wide is the peak? (e.g., 80 ms)
Concavity:          Does it curve? (up/down)
Peak Count:         How many peaks? (e.g., 1 = single peak)
Smoothness:         Is it jagged or smooth?
```

---

## Feature Extraction for Eye Blinks

### Key Characteristics
```
Duration:           100-400 ms (typically 150-200 ms)
Amplitude:          50-300 µV
Rise Time:          30-70 ms (relatively fast)
Fall Time:          100-200 ms (slower than rise)
Asymmetry Ratio:    0.2-0.4 (fast rise, slow fall)
Peak Frequency:     0.5-2 Hz (low frequency)
Symmetry:           Clearly asymmetric
```

### Feature Vector Example
```
Feature Set for One Blink Event:
[
  Duration=180ms,              # Temporal
  RiseTime=50ms,              # Temporal
  FallTime=130ms,             # Temporal
  PeakAmplitude=3.5µV,        # Amplitude
  Baseline=0.1µV,             # Amplitude
  SNR=35dB,                   # Amplitude
  RiseVelocity=0.07µV/ms,    # Velocity
  Mean=1.2µV,                 # Statistical
  StdDev=1.5µV,              # Statistical
  Skewness=-0.35,             # Statistical
  Kurtosis=2.8,               # Statistical
  PeakFrequency=1.0Hz,        # Spectral
  Bandwidth=1.5Hz,            # Spectral
  EnergyInBand=82%,           # Spectral
  Asymmetry=0.38,             # Shape
  PeakWidth=80ms,             # Shape
  Smoothness=0.45             # Shape
]

Total: 17 features
```

---

## Feature Extraction Steps

### Step 1: Acquire Raw Signal
```
Arduino → USB → Computer
512 samples/second
Raw ADC values (0-16383)
```

### Step 2: Detect Events
```
Scan for peaks above baseline
Mark event boundaries
Extract ~500ms window around event
```

### Step 3: Extract Features
```
For each event window, calculate:
├─ All temporal features
├─ All amplitude features
├─ All statistical features
├─ All spectral features
└─ All shape features
```

### Step 4: Select Important Features
```
Remove redundant features
Remove irrelevant features
Keep discriminative features
Result: 10-15 most important features
```

### Step 5: Normalize/Scale
```
Put all features on same scale
├─ Duration: 100-400 ms → 0-1
├─ Amplitude: 0-5 µV → 0-1
├─ All other features → 0-1 or mean=0, std=1
```

### Step 6: Make Decision
```
Input: Feature vector
Classifier: Rule-based or machine learning
Output: "Blink detected" or "Not a blink"
```

---

## Common Feature Selection Methods

### Method 1: Domain Expert Knowledge
```
Example: "I know blinks have duration 100-400ms"
Action: Include Duration as feature ✓
```

### Method 2: Correlation with Target
```
Example: Feature correlates with blink: 0.85 ✓
        Feature correlates with blink: 0.05 ✗
Action: Keep high correlation features
```

### Method 3: Variance Analysis
```
Example: Blinks have high amplitude variance: ✓
        Noise has low amplitude variance: ✓
Action: Amplitude discriminates well, keep it ✓
```

### Method 4: Remove Redundancy
```
Example: Feature A and B are 99% correlated
Action: Keep A, remove B (same information)
```

---

## Feature Validation

### Check 1: Correlation with Target
```
Target: "Is this a blink?"
Feature: Rise Time
Question: Do blinks have different rise time than non-blinks?
Answer: YES ✓ → Keep feature
```

### Check 2: Importance Score
```
Train classifier with feature
Remove feature
Retest classifier
If performance drops significantly: Feature important ✓
If no change: Feature not important ✗
```

### Check 3: Cross-Validation
```
Divide data into 5 folds
Train on 4, test on 1
Repeat 5 times
Average accuracy should be 85%+
```

---

## Real Example: Distinguishing Blinks from Noise

### Blink Event
```
Features:
├─ Duration: 200 ms ← In typical range ✓
├─ Amplitude: 3.5 µV ← Strong signal ✓
├─ Rise Time: 50 ms ← Reasonable ✓
├─ Peak Freq: 1.0 Hz ← Characteristic blink ✓
└─ Asymmetry: 0.33 ← Fast rise, slow fall ✓

Decision: ALL features say BLINK → BLINK ✓
```

### Noise Event
```
Features:
├─ Duration: 20 ms ← Too short ✗
├─ Amplitude: 0.2 µV ← Too weak ✗
├─ Rise Time: 5 ms ← Too fast ✗
├─ Peak Freq: 50 Hz ← Not blink frequency ✗
└─ Asymmetry: 1.0 ← Symmetric ✗

Decision: ALL features say NOT BLINK → NOT BLINK ✓
```

---

## Common Mistakes to Avoid

### Mistake 1: Too Many Features
```
Using 500 features leads to:
├─ Overfitting (memorizes noise)
├─ Slow computation
├─ Poor generalization
Solution: Use 10-20 features max
```

### Mistake 2: Redundant Features
```
Using Peak Amplitude AND Maximum Value:
├─ They're the same thing
├─ No new information
├─ Adds confusion
Solution: Use only one
```

### Mistake 3: Features on Different Scales
```
Duration: 0-400 ms
Amplitude: 0-5 µV
Problem: Duration dominates by 80x
Solution: Normalize all to 0-1 scale
```

### Mistake 4: Noisy Features
```
Using random values as features
├─ Adds noise
├─ Confuses classifier
└─ Reduces accuracy
Solution: Use only meaningful, stable features
```

---

## Quick Decision Tree

```
Is this feature...

Relevant to problem?
├─ NO → Remove
└─ YES → Continue

Correlated with target?
├─ NO (|r| < 0.3) → Remove
└─ YES (|r| > 0.3) → Continue

Redundant with another feature?
├─ YES (|r| > 0.9 with other) → Remove one
└─ NO → Continue

Easy to compute?
├─ NO (complex) → Consider alternatives
└─ YES → Keep

Stable/Robust?
├─ NO (changes with noise) → Remove
└─ YES → KEEP ✓
```

---

## Success Metrics

### Good Feature Set Has:
- ✓ 10-20 features (not too many, not too few)
- ✓ 85%+ accuracy on test data
- ✓ >90% sensitivity (catch real events)
- ✓ <5% false positive rate
- ✓ Easy to interpret
- ✓ Stable across different users
- ✓ Minimal redundancy
- ✓ Robust to noise

### Red Flags:
- ✗ >50 features (overfitting risk)
- ✗ <5 features (underfitting risk)
- ✗ <80% accuracy (not working well)
- ✗ >20% false positive rate (too many false alarms)
- ✗ Hard to interpret
- ✗ Highly redundant features
- ✗ Sensitive to small signal variations

---

## Final Summary

**Feature extraction is:**
1. Converting raw data into meaningful characteristics
2. Reducing dimensionality dramatically (512 → 15)
3. Making the problem interpretable
4. Enabling fast classification
5. The foundation for blink detection

**Key insight:** Rather than trying to classify based on 512 raw samples, we classify based on 15 carefully chosen features. This makes the problem tractable and robust.

**Your goal:** Extract these 15 features from eye blink events, then use them to detect blinks with >90% accuracy and <5% false positives.

---

**Ready to implement? See FEATURE_EXTRACTION_THEORY.md and FEATURE_EXTRACTION_APPLICATIONS.md for complete details!**
