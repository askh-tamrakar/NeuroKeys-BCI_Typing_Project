# Feature Extraction - Complete Theoretical Guide

## Table of Contents
1. [Fundamental Concepts](#fundamental-concepts)
2. [Why Feature Extraction Matters](#why-feature-extraction-matters)
3. [Feature Extraction in Time Domain](#feature-extraction-in-time-domain)
4. [Feature Extraction in Frequency Domain](#feature-extraction-in-frequency-domain)
5. [Feature Extraction in EOG Signals](#feature-extraction-in-eog-signals)
6. [Feature Engineering Principles](#feature-engineering-principles)
7. [Statistical Features](#statistical-features)
8. [Morphological Features](#morphological-features)
9. [Temporal Features](#temporal-features)

---

## Fundamental Concepts

### What is a Feature?

A **feature** is a measurable property or characteristic of raw data that is informative for solving a problem.

**Example:**
```
Raw EOG Signal: [1.2, 1.5, 2.8, 3.5, 2.1, 0.8, 0.5, 1.1, ...]
                 ↓
Features:      Amplitude: 3.5 mV
               Duration: 200 ms
               Rise Time: 50 ms
               Fall Time: 150 ms
```

### Raw Data vs Features

**Raw Data:**
- Complete but noisy
- High dimensional (512 samples/second)
- Contains irrelevant information
- Hard to interpret

**Features:**
- Condensed and meaningful
- Low dimensional (5-20 features)
- Highlights relevant patterns
- Easier to interpret

### Why Convert Raw Data to Features?

```
Raw Signal (512 Hz, 1 minute = 30,720 samples)
    ↓
Too much data, hard to interpret
    ↓
Feature Extraction
    ↓
Key Characteristics (e.g., 15 features per event)
    ↓
Easier to analyze, classify, and act upon
```

---

## Why Feature Extraction Matters

### The Curse of Dimensionality

**Problem:**
```
Raw EOG @ 512 Hz for 10 seconds = 5,120 data points per channel

To train a classifier:
- Memory required: exponential with dimensions
- Training time: increases dramatically
- Risk of overfitting: higher
- Noise impact: magnified

Example:
1 dimension: Easy to separate
10 dimensions: Manageable
5,120 dimensions: Intractable!
```

### Information Compression

**Goal:** Preserve important information while reducing data volume

```
Compression Ratio = Original Dimensions / Feature Dimensions
                  = 5,120 / 10 = 512:1

Example:
Raw: 5,120 samples (512 Hz × 10 sec)
Features: 10 meaningful values
Information preserved: ~95%
Compression: 512x reduction ✓
```

### Pattern Recognition

**Real-world example - Eye Blink Detection:**

Without Features:
```
Raw signal: [1.2, 1.3, 1.5, 2.1, 3.2, 3.8, 3.5, 2.2, 1.1, 0.9, ...]
Question: "Is this a blink?"
Answer: Very hard to tell from raw numbers
```

With Features:
```
Feature Set:
├─ Amplitude: 3.8 µV (high)
├─ Duration: 180 ms (normal)
├─ Rise Time: 45 ms (normal)
├─ Fall Time: 135 ms (normal)
├─ Symmetry: Rise/Fall = 0.33 (normal range)

Question: "Is this a blink?"
Answer: YES! (matches blink signature)
```

---

## Feature Extraction in Time Domain

### What is Time Domain?

Time domain analysis examines how signals change over time.

```
Time (seconds) →  0    1    2    3    4    5
Signal Values →   1.0  1.5  2.8  3.5  2.1  0.8
                  
We directly measure properties AS TIME PASSES
```

### Time Domain Features for Signals

#### 1. **Amplitude Features**

**Peak (Maximum) Value**
```
Definition: Highest voltage reached during the event
Purpose: Indicates signal strength/intensity
Range: -∞ to +∞ (depends on signal)

Example:
Signal: [0.5, 1.2, 2.8, 3.5, 2.1, 0.8]
Peak: 3.5 (index 3)

Why important:
- Strong peak = likely real event
- Weak peak = might be noise
```

**Trough (Minimum) Value**
```
Definition: Lowest voltage reached during the event
Purpose: For bipolar signals, shows negative swing

Example:
Signal: [0.5, 1.2, 2.8, 3.5, 2.1, 0.8, -0.5, 0.2]
Trough: -0.5

Why important:
- Some signals go negative (EMG)
- Monitors full range of movement
```

**Peak-to-Peak (Range)**
```
Definition: Difference between max and min
Formula: Peak-to-Peak = Max - Min

Example:
Signal: [0.5, 1.2, 2.8, 3.5, 2.1, 0.8, -0.5, 0.2]
Max: 3.5
Min: -0.5
Peak-to-Peak: 3.5 - (-0.5) = 4.0

Why important:
- Measures total signal excursion
- Independent of baseline
- Better than raw peak alone
```

#### 2. **Statistical Features**

**Mean (Average)**
```
Definition: Sum of all values divided by count
Formula: Mean = Σ(x_i) / N

Example:
Signal: [1, 2, 3, 4, 5]
Mean: (1+2+3+4+5)/5 = 3

Why important for EOG:
- Represents baseline/resting position
- Normal eyes at rest: ~0 µV
- Blink baseline shift: detectable
```

**Standard Deviation (Spread)**
```
Definition: How spread out values are from mean
Formula: StdDev = √(Σ(x_i - mean)²/N)

Example:
Signal 1: [1, 1, 1, 1, 1] → StdDev = 0 (flat)
Signal 2: [1, 2, 3, 4, 5] → StdDev = 1.4 (varied)

Why important:
- Low StdDev: quiet, steady signal
- High StdDev: active, dynamic signal
- Indicates signal activity level
```

**Variance**
```
Definition: Square of standard deviation
Formula: Variance = StdDev²

Example:
Signal: [1, 2, 3, 4, 5]
Variance: 2.0
StdDev: √2 ≈ 1.4

Why important:
- Measures signal power/energy
- Higher variance = stronger signal
- Used in signal quality assessment
```

#### 3. **Temporal Features**

**Duration**
```
Definition: How long an event lasts
Formula: Duration = End Time - Start Time

Example:
Eye blink:
├─ Start: 0 ms
├─ End: 200 ms
└─ Duration: 200 ms

Expected ranges:
- Normal blink: 100-400 ms
- Too short (< 100 ms): likely noise
- Too long (> 400 ms): artifact or saccade
```

**Rise Time**
```
Definition: Time from start to peak
Formula: Rise Time = Peak Time - Start Time

Example:
Signal starts increasing at: 0 ms
Reaches peak at: 45 ms
Rise Time: 45 ms

Why important:
- Fast rise (< 30 ms): abrupt event (blink)
- Slow rise (> 100 ms): gradual movement (saccade)
- Indicates event type
```

**Fall Time**
```
Definition: Time from peak to end
Formula: Fall Time = End Time - Peak Time

Example:
Peak at: 45 ms
Signal returns to baseline at: 200 ms
Fall Time: 155 ms

Why important:
- Blinks: asymmetric (slower fall than rise)
- Ratio Fall/Rise distinguishes event types
```

**Rise Velocity**
```
Definition: How quickly signal increases
Formula: Rise Velocity = Peak Amplitude / Rise Time

Example:
Peak: 3.5 µV
Rise Time: 50 ms
Rise Velocity: 3.5 / 50 = 0.07 µV/ms

Typical values:
- Blink: 0.05-0.1 µV/ms (relatively fast)
- Saccade: < 0.05 µV/ms (slow)
```

**Fall Velocity**
```
Definition: How quickly signal decreases
Formula: Fall Velocity = Peak Amplitude / Fall Time

Example:
Peak: 3.5 µV
Fall Time: 155 ms
Fall Velocity: 3.5 / 155 = 0.023 µV/ms

Typical patterns:
- Blinks: Fast rise, slower fall
- Ratio asymmetry indicates event type
```

#### 4. **Morphological Features**

**Symmetry / Asymmetry**
```
Definition: Comparison of rise vs fall
Formula: Asymmetry = Rise Time / Fall Time

Example:
Rise Time: 50 ms
Fall Time: 150 ms
Asymmetry: 50/150 = 0.33 (asymmetric)

Interpretation:
- Ratio 0.5-1.5: Normal (symmetric)
- Ratio < 0.5: Rise fast, fall slow (typical blink)
- Ratio > 1.5: Rise slow, fall fast (artifact)

Eye blink signature:
Typical asymmetry: 0.2-0.4 (fast up, slow down)
```

**Skewness**
```
Definition: Asymmetry of distribution around mean
Formula: Skew = Σ((x_i - mean)³) / (N × StdDev³)

Interpretation:
- Skew = 0: Perfectly symmetric
- Skew > 0: Right-skewed (tail on right)
- Skew < 0: Left-skewed (tail on left)

Blink pattern:
Typical skew: -0.5 to 0.5 (nearly symmetric)
High skew: indicates artifact
```

**Kurtosis**
```
Definition: Peakedness of distribution
Formula: Kurtosis = Σ((x_i - mean)⁴) / (N × StdDev⁴)

Interpretation:
- High kurtosis: Sharp peaks (blink)
- Low kurtosis: Rounded peaks (noise)

Blink pattern:
Typical kurtosis: > 1 (peak-like)
Noise pattern: < 0.5 (rounded)
```

---

## Feature Extraction in Frequency Domain

### What is Frequency Domain?

Frequency domain analysis examines what frequencies are present in a signal.

```
Time Domain:        Frequency Domain:
Signal over time    Signal decomposed into frequencies

Time (s) →          Frequency (Hz) →
Amplitude ↑         Power ↑
    |               |
    /\              |     ___
   /  \     VS      |    |   |
  /    \            |    |   |
 /      \           |____|___|____
────────────        0   0.5  1  2  3  4  5
```

### Frequency Domain Features

#### 1. **Spectral Power**

**Total Power**
```
Definition: Sum of power across all frequencies
Formula: Total Power = Σ(Spectrum)

Example:
Frequency components:
├─ 0.5 Hz: 100 units
├─ 1 Hz: 200 units
├─ 1.5 Hz: 150 units
└─ 2 Hz: 50 units
Total Power: 500 units

Why important:
- Indicates overall signal energy
- Noise has lower total power
- Real events have characteristic power
```

**Spectral Peak Frequency**
```
Definition: Frequency with highest power
Example:
Spectrum analysis of eye blink:
├─ 0.5 Hz: 100
├─ 1 Hz: 300 ← PEAK
├─ 1.5 Hz: 200
└─ 2 Hz: 50

Peak frequency: 1 Hz

Why important:
- Blinks have peak around 0.5-2 Hz
- Muscle artifacts peak at 20-50 Hz
- Identifies signal type
```

**Spectral Centroid**
```
Definition: "Center of mass" of frequency spectrum
Formula: Centroid = Σ(frequency × power) / Σ(power)

Example:
Spectrum:
├─ 0.5 Hz: power 100
├─ 1 Hz: power 200
└─ 1.5 Hz: power 100

Centroid = (0.5×100 + 1×200 + 1.5×100) / (100+200+100)
         = 400 / 400 = 1.0 Hz

Why important:
- Blinks centered around 1 Hz
- Saccades centered higher (5-10 Hz)
- Quick classification
```

#### 2. **Spectral Distribution**

**Spectral Spread**
```
Definition: How spread out frequencies are
Formula: Spread = √(Σ(freq - centroid)² × power) / Σ(power))

Example:
Narrow spectrum: frequencies close together
├─ High concentration at 1 Hz
├─ Centroid: 1 Hz
└─ Spread: 0.1 Hz

Wide spectrum: frequencies spread out
├─ Mixed 0.5, 1, 2, 3 Hz
├─ Centroid: 1.5 Hz
└─ Spread: 0.8 Hz

Why important:
- Pure blinks: narrow spectrum
- Noise/artifacts: wide spectrum
- Quality indicator
```

**Bandwidth**
```
Definition: Range of frequencies with significant power
Example:
Signal 1 (Blink):
├─ Significant power: 0.5-2 Hz
└─ Bandwidth: 1.5 Hz

Signal 2 (Muscle artifact):
├─ Significant power: 20-100 Hz
└─ Bandwidth: 80 Hz

Why important:
- Different event types have different bandwidths
- Helps discriminate between signals
```

#### 3. **Energy Features**

**Signal Energy**
```
Definition: Total energy = Sum of squared signal values
Formula: Energy = Σ(x_i²)

Example:
Signal: [1, 2, 3]
Energy: 1² + 2² + 3² = 1 + 4 + 9 = 14

Why important:
- Energy increases with amplitude
- Energy persists with longer duration
- Characterizes signal strength
```

**Energy Concentration**
```
Definition: Percent of energy in frequency band
Example:
Total energy: 1000 units
Energy in 0.5-2 Hz: 800 units
Concentration: 800/1000 = 80%

Typical patterns:
- Blinks: 80-90% in 0.5-2 Hz band
- Noise: < 50% in that band
```

---

## Feature Extraction in EOG Signals

### Characteristics of EOG Signals

```
EOG (ElectroOculoGram) Signal Properties:
├─ Frequency Range: 0.1-10 Hz (main components)
├─ Amplitude Range: 50-500 µV (normal range)
├─ Event Types:
│  ├─ Blinks: 100-400 ms duration
│  ├─ Saccades: 50-150 ms duration
│  ├─ Smooth pursuit: variable
│  └─ Fixation: low amplitude, steady
├─ Sampling Rate: 250-1000 Hz (we use 512 Hz)
└─ Signal-to-Noise Ratio: 5-20 dB
```

### Eye Movement Types

#### 1. **Blinks**

```
Characteristics:
├─ Duration: 100-400 ms (typically 150-200 ms)
├─ Amplitude: 50-300 µV
├─ Rise Time: 30-70 ms (fast)
├─ Fall Time: 100-200 ms (slower - asymmetric)
├─ Shape: Sharp peak, rounded tail
├─ Frequency: 0.5-2 Hz main component
└─ Feature: Biphasic (up then down)

Key distinguishing features:
- High amplitude relative to baseline
- Clear on/off pattern
- Fast rise, slow fall (20-40% rise time ratio)
- Bilateral (both eyes together)
```

#### 2. **Saccades** (Rapid eye movements)

```
Characteristics:
├─ Duration: 50-150 ms (faster than blinks)
├─ Amplitude: 100-500 µV (can be large)
├─ Rise Time: 20-40 ms (very fast)
├─ Fall Time: 30-70 ms (fast)
├─ Shape: Sharp peaks in both directions
├─ Frequency: 5-10 Hz main component
└─ Pattern: Can be multidirectional

Key distinguishing features:
- Faster than blinks (less than 150 ms)
- More symmetric rise/fall
- Can occur in any direction
- Higher frequency content than blinks
```

#### 3. **Smooth Pursuit**

```
Characteristics:
├─ Duration: Variable (> 500 ms)
├─ Amplitude: Varies with target
├─ Shape: Smooth, continuous
├─ Frequency: < 1 Hz (slow movements)
└─ Pattern: Follows visual target

Key distinguishing features:
- Smooth curve (not jagged peaks)
- Low frequency content
- Continuous motion (not punctuated)
- Correlates with head/target movement
```

### EOG-Specific Features

#### **1. Horizontal vs Vertical Components**

```
EOG Electrode Placement:
├─ Horizontal (Ch0):
│  ├─ Left electrode: outer canthus
│  └─ Right electrode: medial
│  └─ Sensitive to left/right eye movements
│
└─ Vertical (Ch1):
   ├─ Upper electrode: above eye
   └─ Lower electrode: below eye
   └─ Sensitive to up/down eye movements

Feature extraction implications:
- Horizontal blinks: mainly Ch0
- Vertical blinks: mainly Ch1
- Saccades: appear in both channels
```

#### **2. Blink Detection Features**

```
Critical Feature Set for Blink Detection:

1. Amplitude Features:
   ├─ Peak amplitude: 50-300 µV
   ├─ Baseline shift: < 20 µV
   └─ Signal-to-noise ratio: > 5 dB

2. Temporal Features:
   ├─ Duration: 100-400 ms
   ├─ Rise time: 30-70 ms
   ├─ Fall time: 100-200 ms
   └─ Rise/fall ratio: 0.2-0.5

3. Morphological Features:
   ├─ Symmetry: 0.2-0.5 (rise/fall)
   ├─ Skewness: -0.5 to 0.5
   └─ Kurtosis: > 1.0

4. Spectral Features:
   ├─ Peak frequency: 0.5-2 Hz
   ├─ Energy concentration: > 80%
   └─ Bandwidth: 0.5-2.5 Hz

5. Event Features:
   ├─ Regularity: blinks occur ~15-30 per minute
   ├─ Refractory period: minimum 300 ms between blinks
   └─ Bilateral correlation: both eyes move together
```

---

## Feature Engineering Principles

### Principle 1: Relevance

**Definition:** Features should be predictive of the target.

```
Example - Blink Detection:
Relevant Features:
├─ Duration (100-400 ms is typical)
├─ Amplitude (strong signal)
├─ Rise time velocity (fast)

Irrelevant Features:
├─ Average voltage over 1 hour (not predictive)
├─ Sample #47 value (random data point)
├─ Day of week (no correlation)

Feature selection method:
Only include features that correlate with blinks
```

### Principle 2: Independence

**Definition:** Features should provide unique information.

```
Example:
Feature Set 1 (Redundant):
├─ Peak value: 3.5
├─ Maximum value: 3.5 ← Same as peak!
└─ Highest point: 3.5 ← Still same!
Problem: Contains same information 3 times

Feature Set 2 (Independent):
├─ Peak amplitude: 3.5
├─ Rise time: 50 ms
└─ Fall time: 150 ms
Benefit: Each provides unique information
```

### Principle 3: Efficiency

**Definition:** Features should be simple to compute.

```
Simple Feature (Good):
Peak = max(signal)
├─ Computation time: O(n) - linear
├─ Memory required: O(1) - constant
└─ Interpretability: Easy

Complex Feature (Overkill):
Wavelet Transform with 10 decomposition levels
├─ Computation time: O(n log n)
├─ Memory required: O(n)
└─ Interpretability: Hard

Balance: Effectiveness vs Efficiency
```

### Principle 4: Robustness

**Definition:** Features should be stable despite noise/variations.

```
Robust Feature:
Duration (measured in ms)
├─ Slightly noisy signal: still 180-200 ms
├─ Different amplitudes: duration unchanged
├─ Different baseline: duration still valid
├─ Minor artifacts: minimal impact

Fragile Feature:
Single sample value: x[47]
├─ Sensitive to noise
├─ Changes with tiny perturbations
├─ Unreliable

Strategy: Use aggregated features, not single points
```

### Principle 5: Interpretability

**Definition:** Features should be understandable.

```
Interpretable:
├─ "Peak amplitude: 3.5 µV" ✓ Clear meaning
├─ "Duration: 200 ms" ✓ Obvious
├─ "Rise time: 50 ms" ✓ Understandable

Non-interpretable:
├─ "PCA component 1: 0.527" ? What does this mean?
├─ "Wavelet coefficient[4]: -123" ? Not obvious
└─ "ICA source 3: 0.891" ? Hard to interpret

Balance: Accuracy vs Interpretability
```

---

## Statistical Features

### Group 1: Central Tendency

**Mean (Average)**
```
Captures: Where the signal is centered
Formula: μ = Σ(x_i) / N

Interpretation:
- Mean = 0: Signal centered at baseline
- Mean > 0: Signal shifted upward
- Mean < 0: Signal shifted downward

Example - Blink:
├─ First 50ms (rising): mean = +1.5 µV
├─ Peak 50-100ms: mean = +2.8 µV
└─ Recovery 100-200ms: mean = +1.0 µV
```

**Median**
```
Captures: Middle value (robust to outliers)
Formula: Sort values, take middle one

vs Mean:
├─ Mean affected by outliers
├─ Median robust to outliers

Example:
Signal: [1, 2, 3, 4, 100]
Mean: (1+2+3+4+100)/5 = 22 (skewed by 100)
Median: 3 (ignores 100)
```

**Mode**
```
Captures: Most frequent value
Formula: Value that appears most often

Useful for:
- Detecting baseline values
- Finding most common state

Example:
Signal mostly at 0 with occasional peaks
Mode: 0 (the resting state)
```

### Group 2: Dispersion/Spread

**Range**
```
Captures: Span from min to max
Formula: Range = max - min

Simple but useful:
- Large range: active signal
- Small range: quiet signal

Limitation: Only depends on 2 values
```

**Interquartile Range (IQR)**
```
Captures: Spread of middle 50% of data
Formula: IQR = Q3 - Q1 (75th percentile - 25th)

Robust alternative to range:
- Ignores extreme outliers
- Better representation of typical spread

Example:
Signal: [1, 2, 3, 4, 5, 6, 7, 8, 100]
Range: 99 (affected by outlier 100)
IQR: ~4 (Q1=2.5, Q3=6.5)
```

**Coefficient of Variation**
```
Captures: Relative variability (StdDev/Mean)
Formula: CV = σ / μ × 100%

Normalized comparison:
- Allows comparing different signals
- Independent of scale

Example:
Signal 1: Mean=10, StdDev=2 → CV = 20%
Signal 2: Mean=100, StdDev=20 → CV = 20% (same relative variation)
```

### Group 3: Shape

**Skewness (Asymmetry)**
```
Captures: Asymmetry of distribution
Formula: γ = E[(X - μ)³] / σ³

Interpretation:
- Skewness ≈ 0: Symmetric
- Skewness > 0: Right tail (positive skew)
- Skewness < 0: Left tail (negative skew)

EOG Example:
Blink: Skewness ≈ -0.3 (slightly left-skewed)
Artifact: Skewness > 1 (strongly right-skewed)
```

**Kurtosis (Peakedness)**
```
Captures: Concentration around mean
Formula: κ = E[(X - μ)⁴] / σ⁴

Interpretation:
- Kurtosis = 3: Normal (baseline)
- Kurtosis > 3: Peaked (sharp)
- Kurtosis < 3: Flat (rounded)

EOG Example:
Blink: Kurtosis > 4 (sharp peak)
Noise: Kurtosis < 2 (rounded)
```

---

## Morphological Features

### What is Morphology?

Morphology = Shape and form of the signal

```
Without examining shape:
├─ Raw values: [0, 1, 2, 3, 2, 1, 0]
├─ Mean: 1.3
├─ StdDev: 1.1
└─ No indication of shape

With morphology:
├─ Shape: Single peak (unimodal)
├─ Symmetry: Symmetric around peak
├─ Steepness: Steep rise and fall
└─ Smooth: No oscillations
```

### Morphological Feature Categories

#### 1. **Peak/Trough Characteristics**

**Peak Count**
```
Definition: Number of local maxima
Example:
Signal: [0, 1, 0.5, 1.5, 0, 0.8, 0.3, 0]
         Peak at index 1
         Peak at index 3
         Peak at index 5
Peak Count: 3

Interpretation:
- Single peak: Isolated event (blink)
- Multiple peaks: Oscillation or artifact
```

**Peak Width (at half-height)**
```
Definition: Width of peak at 50% of peak height
Formula:
1. Find peak height
2. Find 50% of that height
3. Measure width at that level

Example:
├─ Peak height: 4.0
├─ Half-height: 2.0
├─ Width at half-height: 60 ms

Interpretation:
- Wide peak: Slow, gradual event
- Narrow peak: Fast, sharp event
```

**Peak Prominence**
```
Definition: How much peak stands out from background
Formula: Prominence = Peak Height - minimum enclosing valley

Example:
Peak at 4.0 with surrounding values:
├─ Left valley: 1.0
├─ Right valley: 1.2
├─ Prominence: 4.0 - 1.2 = 2.8

Interpretation:
- High prominence: Clear, significant event
- Low prominence: Subtle or noisy
```

#### 2. **Curvature and Smoothness**

**Smoothness (Second Derivative)**
```
Definition: Measure of how much signal curves
Formula: Smoothness = Σ(second_derivative)

Example:
Smooth signal: [0, 1, 2, 3, 2, 1, 0]
├─ First derivative: [1, 1, 1, -1, -1, -1]
├─ Second derivative: [0, 0, -2, 0, 0]
└─ Smoothness: Relatively low

Jagged signal: [0, 1, 0, 2, 0, 1, 0]
├─ More changes in direction
└─ Higher smoothness measure

Interpretation:
- Smooth: Real physiological signal
- Jagged: Electrical noise
```

**Concavity**
```
Definition: Whether curve bends up or down
Formula: Based on second derivative sign

Concave up (∪): Second derivative > 0
Concave down (∩): Second derivative < 0

Example - Blink:
├─ Rising phase (0-50ms): Concave down
├─ Peak: Changes direction
└─ Falling phase (50-200ms): Concave up

Pattern recognition:
The changing concavity characterizes the shape
```

#### 3. **Symmetry and Regularity**

**Symmetry Index**
```
Definition: How symmetric is the signal around peak
Formula: Symmetry = Rise_Profile × Fall_Profile alignment

Example:
Rise: [0.5, 1.0, 1.5, 2.0]
Fall: [2.0, 1.5, 1.0, 0.5]
Symmetry Index: 1.0 (perfectly symmetric)

Typical patterns:
- Blinks: 0.3-0.5 (asymmetric, rise fast, fall slow)
- EMG artifacts: 0.6-0.9 (more symmetric)
```

**Periodicity**
```
Definition: Does signal repeat regularly?
Formula: Autocorrelation analysis

Periodic signal:
├─ Period: 2 seconds
├─ Pattern repeats consistently
└─ High autocorrelation at lag = period

Aperiodic signal:
├─ No regular pattern
├─ Low autocorrelation at all lags

EOG context:
- Blinks: Semi-periodic (15-30/minute)
- Saccades: Aperiodic (depend on task)
```

---

## Temporal Features

### What is Temporal?

Temporal = Related to time and dynamics

```
Static: "What is the peak value?" → 3.5 µV
Temporal: "How quickly does it reach the peak?" → 50 ms
          "How does it change over time?" → Trajectory
```

### Temporal Feature Categories

#### 1. **Velocity and Acceleration**

**Velocity (First Derivative)**
```
Definition: Rate of change
Formula: v(t) = dx/dt ≈ (x[t] - x[t-1]) / Δt

Example:
Signal: [0, 1, 3, 4, 2, 0]
Velocity: [-, 1, 2, 1, -2, -2]

Interpretation:
- Positive velocity: Signal increasing
- Negative velocity: Signal decreasing
- Magnitude: Speed of change

EOG meaning:
- High velocity = fast eye movement
- Low velocity = slow drift
```

**Acceleration (Second Derivative)**
```
Definition: Rate of change of velocity
Formula: a(t) = dv/dt ≈ (v[t] - v[t-1]) / Δt

Example:
Velocity: [1, 2, 1, -2, -2]
Acceleration: [-, 1, -1, -3, 0]

Interpretation:
- Positive acceleration: speeding up
- Negative acceleration: slowing down

EOG meaning:
- Blinks: Strong acceleration at onset
- Saccades: Different acceleration profile
```

**Jerk (Third Derivative)**
```
Definition: Rate of change of acceleration
Formula: j(t) = da/dt

Used for:
- Distinguishing different movement types
- Quality assessment
- Artifact detection

EOG applications:
- High jerk: Artifact or EMG
- Low jerk: Natural eye movement
```

#### 2. **Latency and Timing**

**Reaction Latency**
```
Definition: Time from stimulus to response
Example:
├─ Flash appears at: t=0 ms
├─ Eye starts moving at: t=150 ms
├─ Reaction latency: 150 ms

Typical ranges:
- Visual stimulus: 100-300 ms
- Auditory stimulus: 150-350 ms
- Spontaneous blink: N/A (no stimulus)

Diagnostic value:
- Normal latency: Good neural response
- Delayed latency: Neurological issue
```

**Time to Peak**
```
Definition: How long to reach maximum
Formula: Time_to_Peak = Peak_Index × Sampling_Period

Example:
├─ Peak at sample 25
├─ Sampling rate: 512 Hz = 1.95 ms/sample
├─ Time to peak: 25 × 1.95 = 49 ms

Expected ranges:
- Blink: 30-70 ms
- Saccade: 20-40 ms
```

**Total Duration**
```
Definition: Time from event start to end
Formula: Duration = End_Time - Start_Time

Detection method:
- Find where signal crosses threshold
- Start: first crossing above threshold
- End: last crossing above threshold
- Duration: End - Start

Example:
├─ Above threshold from 50ms to 250ms
├─ Duration: 200 ms

Validation:
- If duration < 100ms: artifact
- If duration > 400ms: not a blink
- If 100-400ms: likely blink
```

#### 3. **Energy Distribution Over Time**

**Energy Concentration**
```
Definition: When most energy occurs
Formula: Integral of squared signal in time windows

Example:
Event: 200ms duration
├─ First 50ms: 20% of energy
├─ Middle 100ms: 60% of energy ← Peak
├─ Last 50ms: 20% of energy

Typical pattern:
- Energy concentrated in middle = coherent event
- Energy spread throughout = noise
```

**Instantaneous Power**
```
Definition: Power at each moment in time
Formula: Power(t) = Signal(t)²

Example:
Signal: [0.1, 0.5, 1.0, 0.5, 0.1]
Power: [0.01, 0.25, 1.0, 0.25, 0.01]

Interpretation:
- Peaks in power indicate event strength
- Power envelope shows event dynamics

Dynamic analysis:
Track how power evolves during event
```

---

## Integration: Complete Feature Set for Eye Blink Detection

### Comprehensive Feature Extraction

```
BLINK EVENT: T0 to T_end

TEMPORAL FEATURES:
├─ Duration: T_end - T0 = 180 ms
├─ Rise time: T_peak - T0 = 50 ms
├─ Fall time: T_end - T_peak = 130 ms
└─ Rise/fall ratio: 50/130 = 0.38

AMPLITUDE FEATURES:
├─ Peak amplitude: 3.5 µV
├─ Baseline amplitude: 0.1 µV
├─ Net amplitude: 3.4 µV
├─ Peak-to-peak: 0.4 µV (for biphasic)
└─ Signal-to-noise: 35:1 = 34.9 dB

VELOCITY FEATURES:
├─ Rise velocity: 3.5/50 = 0.07 µV/ms
├─ Fall velocity: 3.5/130 = 0.027 µV/ms
├─ Max velocity: 0.15 µV/ms
└─ Acceleration: 0.003 µV/ms²

SHAPE FEATURES:
├─ Symmetry index: 0.38 (asymmetric)
├─ Skewness: -0.35 (left-skewed)
├─ Kurtosis: 2.8 (slightly peaked)
└─ Concavity: Changing

SPECTRAL FEATURES:
├─ Peak frequency: 1.0 Hz
├─ Bandwidth: 0.5-2.0 Hz
├─ Energy in band: 85%
└─ Spectral centroid: 1.1 Hz

STATISTICAL FEATURES:
├─ Mean: 1.2 µV
├─ StdDev: 1.5 µV
├─ Variance: 2.25 µV²
├─ Min: -0.1 µV
├─ Max: 3.5 µV
└─ Range: 3.6 µV

TOTAL FEATURES: ~25 meaningful descriptors
Compression ratio: 512 samples → 25 features = 20:1
```

### Feature Vector Representation

```
Feature Vector for Classification:
X = [Duration, Rise_Time, Fall_Time, Amplitude, 
     Rise_Velocity, Fall_Velocity, Symmetry, Peak_Freq,
     Energy_Band, Mean, StdDev, Skewness, Kurtosis,
     ...]

Example for Blink:
X_blink = [180, 50, 130, 3.5, 0.07, 0.027, 0.38, 1.0,
           0.85, 1.2, 1.5, -0.35, 2.8, ...]

Example for Saccade:
X_saccade = [75, 30, 45, 2.8, 0.09, 0.062, 0.67, 5.0,
             0.45, 0.8, 2.1, 0.12, 1.9, ...]

Classifier task:
Use X to distinguish blinks from other events
```

---

## Conclusion

Feature extraction is the bridge between raw signal data and meaningful information.

**Key takeaways:**

1. **Purpose:** Reduce dimensionality while preserving information
2. **Categories:** Temporal, spectral, statistical, morphological
3. **Trade-offs:** Accuracy vs. Simplicity, Robustness vs. Specificity
4. **Design:** Balance relevance, independence, efficiency, robustness, interpretability
5. **Application:** EOG signals have specific features that characterize eye movements

**Next Step:** Use these features to build classifiers and detectors!
