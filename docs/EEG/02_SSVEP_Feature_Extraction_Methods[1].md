# Feature Extraction for SSVEP & BCI Systems

## Table of Contents
1. [SSVEP Fundamentals](#ssvep-fundamentals)
2. [Power Spectral Density Method](#psd-method)
3. [Canonical Correlation Analysis (CCA)](#cca-method)
4. [Filter Bank CCA (FBCCA)](#fbcca-method)
5. [Multi-Channel Feature Fusion](#channel-fusion)
6. [Harmonic Analysis](#harmonics)
7. [Feature Comparison for SSVEP](#comparison)
8. [Implementation Considerations](#implementation)
9. [Troubleshooting Low Classification Accuracy](#troubleshooting)
10. [Performance Optimization](#optimization)

---

## SSVEP Fundamentals {#ssvep-fundamentals}

### What Happens During SSVEP?

When a subject gazes at a flickering stimulus:

1. **Stimulus presented**: LED flashes at frequency \(f\) Hz (e.g., 10 Hz)
2. **Visual system responds**: Brain's visual cortex oscillates at same frequency
3. **EEG shows oscillation**: Recording from occipital electrodes (O1, O2) captures this
4. **Signal characteristics**:
   - Contains fundamental frequency (10 Hz)
   - Contains harmonics (20 Hz, 30 Hz, etc.)
   - Much stronger than baseline noise

### Why This is Useful for BCI

✅ **Objective**: Purely stimulus-driven, doesn't require active motor control
✅ **Fast**: SSVEP appears almost immediately (~140ms latency)
✅ **Natural**: Works with most people, minimal training
✅ **Multiple targets**: Can have 4-10 independent frequencies
✅ **High ITR**: Information Transfer Rate 25-40 bits/minute

### Frequency Selection

**Key considerations for your 6-target system**:

```
Recommended frequencies: 8, 10, 12, 14, 16, 18 Hz

Why these?
- 8-18 Hz range has optimal SNR (signal-to-noise ratio)
- Spacing avoids harmonic conflicts
  - 10 Hz and 20 Hz harmonics don't overlap
  - 10 Hz and 15 Hz do overlap (avoid!)
- Far from typical EEG interference (50/60 Hz powerline)
- Comfortable for subject (not too fast flicker)

Avoid:
- < 6 Hz: Too slow, uncomfortable
- > 30 Hz: Weak SNR, unsafe (photosensitive epilepsy risk)
- Too close spacing: Harmonics create confusion
```

---

## Power Spectral Density Method {#psd-method}

### The Concept

**Simple approach**: Compute FFT, find which frequency has highest power

```
Step 1: Convert signal to frequency domain (FFT)
Step 2: Find magnitude at each stimulus frequency
Step 3: Pick frequency with highest magnitude
Step 4: That's the attended target!
```

### Mathematical Framework

#### FFT Computation

For a signal window of N samples sampled at \(f_s\) Hz:

1. **Raw FFT**:
   \[ X[k] = \sum_{n=0}^{N-1} x[n] e^{-j2\pi kn/N} \]

2. **Magnitude**:
   \[ |X[k]| = \sqrt{X_{\text{real}}^2 + X_{\text{imag}}^2} \]

3. **Power**:
   \[ P[k] = |X[k]|^2 \]

#### Frequency Resolution

\[ \Delta f = \frac{f_s}{N} \]

**Example**: 512 Hz sampling, 512 samples
- Window duration: 512/512 = 1 second
- Frequency resolution: 512/512 = 1 Hz
- Can distinguish 10 Hz and 11 Hz ✓
- Cannot distinguish 10.0 Hz and 10.1 Hz ✗

#### SNR Calculation

Signal-to-Noise Ratio at each frequency:

\[ \text{SNR}[f_i] = \frac{\text{Power at } f_i}{\text{Average power in adjacent 2 Hz}} \]

**Feature vector**: \( [SNR_8Hz, SNR_{10Hz}, SNR_{12Hz}, SNR_{14Hz}, SNR_{16Hz}, SNR_{18Hz}] \)

### Including Harmonics

Typical SSVEP contains multiple harmonics:

```
Stimulus at 10 Hz produces:
- Fundamental (1×): 10 Hz
- 2nd Harmonic (2×): 20 Hz
- 3rd Harmonic (3×): 30 Hz
- 4th Harmonic (4×): 40 Hz
```

**Feature extraction with harmonics**:

```
For each stimulus frequency f:
    power_f1 = magnitude at f
    power_f2 = magnitude at 2f
    power_f3 = magnitude at 3f
    total_power = weighted_sum(power_f1, power_f2, power_f3)

Features = [total_power_8Hz, total_power_10Hz, ...]
```

**Typical weights**: [1.0, 0.8, 0.6] (harmonics contribute less)

### Advantages of PSD Method

✅ **Simple**: Easy to understand and implement
✅ **Fast**: O(N log N) due to FFT
✅ **Interpretable**: Directly shows frequency power
✅ **Robust**: Works in most conditions

### Limitations of PSD Method

❌ **Spectral leakage**: FFT artifacts reduce accuracy
❌ **Ignores spatial information**: Doesn't use O1/O2 correlation
❌ **Amplitude dependent**: Strong noise can mask weaker signals
❌ **Accuracy**: 70-80% on 6-target systems

### Practical Implementation Considerations

#### Window Function

Apply before FFT to reduce spectral leakage:

```
Windowed_signal = raw_signal × window_function

Common windows:
- Hann: smooth, general purpose
- Hamming: similar to Hann
- Blackman: maximum leakage reduction
```

#### Epoch Length Trade-off

```
0.5 second epoch:
- Fast (real-time friendly)
- Poor frequency resolution
- Accuracy: ~70%

1.0 second epoch:
- Good balance
- Better frequency resolution
- Accuracy: ~80%

2.0 second epoch:
- Excellent frequency resolution
- Slow for real-time
- Accuracy: ~85%

For SSVEP BCI: Use 1.0-1.2 seconds
```

#### Preprocessing Pipeline

```
Raw Signal (512 Hz)
    ↓
Notch Filter (50 Hz for power line)
    ↓
Bandpass Filter (6-30 Hz)
    ↓
Segment into epochs (1.0 second windows)
    ↓
Apply window function (Hann)
    ↓
FFT
    ↓
Extract power at stimulus frequencies + harmonics
    ↓
Classify: argmax(power)
```

---

## Canonical Correlation Analysis (CCA) {#cca-method}

### The Key Insight

**Problem with PSD**: Ignores information in how O1 and O2 are correlated

**CCA solution**: Find maximum correlation between EEG and known reference signals

### Mathematical Foundation

#### What is Correlation?

Measures how similar two signals are:
- \( \rho = 1 \): Perfect positive correlation (same pattern)
- \( \rho = 0 \): No correlation (random)
- \( \rho = -1 \): Perfect negative correlation (opposite)

#### CCA Concept

For each stimulus frequency, we know:
- **What signal we expect**: Sin and cos waves at that frequency
- **What signal we recorded**: O1 and O2 channels
- **Question**: How correlated are they?

**Answer**: If highly correlated → Subject attended that frequency!

### CCA Algorithm

#### Reference Signal Generation

For each stimulus frequency \(f\):

```
y_f = [sin(2πf·t₀), cos(2πf·t₀),
       sin(2π·2f·t₀), cos(2π·2f·t₀),
       sin(2π·3f·t₀), cos(2π·3f·t₀),
       ...]

where:
- t₀, t₁, ..., tₙ = sample times
- 2f, 3f = harmonics
- Include 3-4 harmonics typically
```

**Result**: Reference signal matrix of dimension N × (2 × num_harmonics)

#### EEG Data Matrix

For two channels (O1, O2):

```
X = [O1_samples; O2_samples]  (dimension: 2 × N)
```

#### CCA Correlation Calculation

Find maximum correlation:

\[ \rho_f = \max_{\text{weights}} \text{corr}(X · \text{weights}, y_f) \]

This is solved via eigenvalue decomposition (details complex, but algorithms handle it)

#### Classification Decision

```
For each stimulus frequency f ∈ {8, 10, 12, 14, 16, 18} Hz:
    Compute reference signal y_f
    Compute CCA correlation ρ_f with recorded X
    
Attended_frequency = argmax(ρ_f)
```

### CCA Advantages

✅ **Channel fusion**: Uses both O1 and O2 synergistically
✅ **Spatial filtering**: Removes noise in spatial direction
✅ **Harmonic aware**: Automatically uses harmonics
✅ **Better accuracy**: 84-93% on 6-target systems
✅ **Subject-independent**: No calibration needed (sometimes)

### CCA Limitations

❌ **Complex**: Requires linear algebra understanding
❌ **Computational cost**: More expensive than FFT
❌ **Less interpretable**: Hard to understand what's happening
❌ **Requires multiple channels**: Single channel reduces effectiveness

### CCA vs FFT/PSD

| Aspect | FFT/PSD | CCA |
|--------|---------|-----|
| **Accuracy** | 75-80% | 84-93% |
| **Speed** | Very fast | Medium |
| **Interpretability** | Easy | Difficult |
| **Channels used** | Single | Multiple |
| **Calibration** | Optional | Helpful |

---

## Filter Bank CCA (FBCCA) {#fbcca-method}

### The Innovation

**CCA limitation**: Uses one fixed frequency band

**FBCCA solution**: Apply CCA separately to multiple frequency sub-bands, then combine

### The Why

Different frequency bands contain different information:

```
6-14 Hz band: Contains fundamental + some harmonics
10-22 Hz band: Contains 2nd harmonic + fundamental
14-26 Hz band: Contains 2nd and 3rd harmonics
18-30 Hz band: High frequency harmonics, but noisy
```

**Key insight**: Combining information from multiple bands gives better discrimination

### FBCCA Algorithm

```
Step 1: Define filter banks
    FB1: 6-14 Hz
    FB2: 10-22 Hz
    FB3: 14-26 Hz
    FB4: 18-30 Hz

Step 2: For each filter bank:
    Filter signal: x_fb = bandpass_filter(X, FB)
    
    For each stimulus frequency f:
        Compute CCA correlation ρ_f,fb
    
Step 3: Combine correlations
    weighted_sum_f = Σ_fb (weight_fb × ρ_f,fb)
    
Step 4: Classify
    Attended_f = argmax(weighted_sum_f)
```

### Weighting Strategy

Different bands have different signal quality:

```
Weight by harmonic sensitivity:

Band 1 (6-14 Hz):
  - Contains fundamental strongly
  - Weight: High for low frequencies
  
Band 2 (10-22 Hz):
  - Contains 2nd harmonic
  - Weight: Medium
  
Band 3 (14-26 Hz):
  - Contains 3rd harmonic
  - Weight: Lower (harmonics weaker)
```

**Typical learned weights**: [0.5, 0.3, 0.15, 0.05]

### FBCCA Performance

**Accuracy comparison**:
- FFT/PSD: 70-80%
- CCA: 84-93%
- **FBCCA: 92-98%**

**Why the improvement?**
- Combines multi-scale information
- Reduces noise effect (averaging across bands)
- Captures full harmonic content

---

## Multi-Channel Feature Fusion {#channel-fusion}

### Using O1 and O2 Channels

Your system has TWO channels: O1 (left occipital) and O2 (right occipital)

#### Why Two Channels?

```
Visual stimulus in left visual field:
  → Projects to right hemisphere
  → Strong signal in O2

Visual stimulus in right visual field:
  → Projects to left hemisphere  
  → Strong signal in O1

Central stimulus:
  → Activates both hemispheres
  → Signal in both O1 and O2
```

#### Feature Fusion Strategies

**Strategy 1: Separate Features**
```
Features = [CCA_O1, CCA_O2]
Classify using both features
Advantage: Captures spatial information
```

**Strategy 2: Bipolar Reference**
```
Signal = O1 - O2
Compute CCA on this derived signal
Advantage: Increases signal differences
```

**Strategy 3: Average**
```
Signal = (O1 + O2) / 2
Advantage: Noise reduction (averaging)
```

**Strategy 4: Weighted Average**
```
Signal = w1×O1 + w2×O2
Find optimal weights (typically w1≈w2, but can adapt per subject)
```

### Multi-Harmonic Integration

Don't just use fundamental frequency!

```
For stimulus at 10 Hz:

Extract power/CCA at:
- 10 Hz (fundamental)
- 20 Hz (2× harmonic)
- 30 Hz (3× harmonic)
- 40 Hz (4× harmonic)

Combine with learned weights:
Total_score_10Hz = w1×power_10Hz + w2×power_20Hz + 
                   w3×power_30Hz + w4×power_40Hz

Typically: [1.0, 0.8, 0.6, 0.4]
(Harmonics contribute, but less than fundamental)
```

### Subject-Specific Adaptation

**Calibration Phase** (5-10 minutes):
1. Record baseline from each subject
2. Compute optimal weights for that subject
3. Learn subject-specific patterns

**Result**: Typically +10-20% accuracy improvement

---

## Harmonic Analysis {#harmonics}

### Why Harmonics Matter in SSVEP

```
Stimulus at 10 Hz flicker:

Time domain waveform:
  [1, 0, 1, 0, 1, 0, ...] (square wave)
  
Frequency domain (Fourier):
  Fundamental: 10 Hz (strongest)
  2nd harmonic: 20 Hz (80% of fundamental)
  3rd harmonic: 30 Hz (60% of fundamental)
  4th harmonic: 40 Hz (40% of fundamental)
  ...
```

**Why?** Square waves contain odd AND even harmonics (sine waves only have fundamentals)

### Harmonic Exploitation

#### Using Harmonics in CCA

```
For 10 Hz stimulus:

Traditional CCA:
  Reference = sin(10Hz), cos(10Hz)
  
Harmonic-aware CCA:
  Reference = [sin(10Hz), cos(10Hz),
               sin(20Hz), cos(20Hz),
               sin(30Hz), cos(30Hz),
               sin(40Hz), cos(40Hz)]
               
Result: Captures ALL frequency content
        Accuracy improves significantly
```

#### Harmonic Weights

Not all harmonics are equally important:

```
Optimal weights (learned from data):
- 1st harmonic (1×f):  1.0 (strongest)
- 2nd harmonic (2×f):  0.8
- 3rd harmonic (3×f):  0.6
- 4th harmonic (4×f):  0.4

Why declining weights?
- Weaker SNR at higher harmonics
- More noise and interference
```

### Inter-harmonic Interference

**Warning**: When frequencies have overlapping harmonics, confusion increases

```
Two SSVEP frequencies: 10 Hz and 20 Hz

10 Hz harmonics: 10, 20, 30, 40, 50, 60, 70, 80, ...
20 Hz harmonics: 20, 40, 60, 80, ...

COLLISION at: 20, 40, 60, 80 Hz!
Result: Hard to distinguish these frequencies!

Solution: Use frequencies that avoid harmonic overlap
Recommended set: 8, 10, 12, 14, 16, 18 Hz
(No major harmonic collisions)
```

---

## Feature Comparison for SSVEP {#comparison}

### Method Accuracy Benchmark

Based on published research with 6 SSVEP targets:

```
Method                    Accuracy    Latency    Complexity
────────────────────────────────────────────────────────────
FFT/PSD                   70-80%      100ms      Very Low
Correlation (simple)      75-82%      120ms      Low
CCA (basic)               84-93%      200ms      Medium
FBCCA                     92-98%      300ms      High
Deep Learning (CNN)       95-99%      400ms      Very High
```

### Decision Matrix: Which Method to Use?

**Use FFT/PSD if**:
- ✓ Speed is critical (mobile, embedded systems)
- ✓ Simple implementation needed
- ✓ Subject comfort important (avoid delays)
- ✗ Accuracy can be 70-80%

**Use CCA if**:
- ✓ Good accuracy needed (84-93%)
- ✓ Medium processing power available
- ✓ Multiple channels available
- ✗ Slightly slower than FFT

**Use FBCCA if**:
- ✓ Maximum accuracy needed (92-98%)
- ✓ Multiple frequency bands valuable
- ✓ Processing power not critical
- ✗ More complex to implement

**Use Deep Learning if**:
- ✓ Large training dataset available
- ✓ Complex patterns need learning
- ✗ Slower real-time processing
- ✗ Black-box (harder to debug)

### For Your SSVEP Project

**Recommended**: Start with **CCA**, upgrade to **FBCCA** if accuracy insufficient

```
Implementation roadmap:

Phase 1: FFT/PSD
  - Quick proof of concept
  - Validate system works
  - Debug hardware

Phase 2: CCA
  - Implement multi-channel fusion
  - Add harmonic support
  - Target: 85%+ accuracy

Phase 3: FBCCA
  - Add frequency sub-bands
  - Optimize weights
  - Target: 93%+ accuracy

Phase 4: Subject Calibration
  - Individual templates
  - Adapt weights per subject
  - Target: 95%+ accuracy
```

---

## Implementation Considerations {#implementation}

### Epoch Duration Selection

**Critical parameter**: How long to analyze before making decision

```
Epoch: 0.5 second
- Pros: Fast (real-time responsive)
- Cons: Poor frequency resolution
- Accuracy: ~70%
- Best for: High-speed applications

Epoch: 0.8 second
- Pros: Good speed/accuracy balance
- Cons: Moderate frequency resolution
- Accuracy: ~80-85%
- Best for: Most BCI applications

Epoch: 1.0 second
- Pros: Optimal balance
- Cons: Slightly slower
- Accuracy: ~85-90%
- Best for: Standard implementation

Epoch: 2.0 second
- Pros: Best frequency resolution
- Cons: Slow (user sees 2-second delay)
- Accuracy: ~92-95%
- Best for: Critical applications (medical)
```

**For your SSVEP**: Recommend 1.0-1.2 second epochs

### Temporal Dynamics

```
Even after stimulus onset, brain needs time to:
1. See the stimulus (~50ms)
2. Process visual information (~100ms)
3. Generate EEG response (~90ms)
Total latency: ~240ms

Therefore: Epoch should START ~250ms after stimulus change,
           not at stimulus onset
```

### Channel Quality Assessment

Before classification, validate electrode quality:

```
Check:
1. Impedance < 10 kΩ (ideally < 50 kΩ)
2. Baseline noise < 5 μV RMS
3. No artifacts (eye blinks, muscle tension)
4. SNR > 3 dB

If any fails: Adjust electrode, clean skin, retry
```

### Real-Time Processing Pipeline

```
Incoming data (512 Hz = 1 sample every 1.95 ms)
        ↓
Collect into buffer (1.0 second = 512 samples)
        ↓
WHEN buffer full:
  ├─ Apply notch filter (50 Hz)
  ├─ Apply bandpass (6-30 Hz)
  ├─ Compute features (FFT or CCA)
  ├─ Classify
  ├─ Send output command
  └─ Clear buffer, start new
        ↓
Total latency: ~50ms filtering + 100ms feature extraction 
             + 50ms classification = 200ms typical
```

---

## Troubleshooting Low Classification Accuracy {#troubleshooting}

### Diagnosis Flowchart

```
Accuracy < 80%?
    ↓
Check 1: Electrode Quality
  - Impedance test: < 10 kΩ?
  - Visual inspection: Clean contact?
  - If bad: Clean electrode, reapply gel
    ↓ (if still bad)
    Try different electrode location
    
Check 2: Signal Quality
  - Baseline noise < 5 μV?
  - No excessive artifacts?
  - If noisy: Reduce muscle tension,
    check for powerline interference
    ↓
Check 3: Stimulus Design
  - Frequencies correct? (8, 10, 12, 14, 16, 18 Hz)
  - All LEDs same brightness?
  - Refresh rate ≥ 60 Hz?
  - No flicker in camera?
  - If issue: Adjust stimulus intensity/timing
    ↓
Check 4: Feature Extraction
  - Epoch length 1+ second?
  - Using harmonics?
  - Proper filtering applied?
  - If weak: Try CCA instead of FFT
    ↓
Check 5: Subject Factors
  - Eyes properly open and focused?
  - Head position steady?
  - Subject alert/engaged?
  - If issue: Retrain subject, check comfort
```

### Common Issues and Solutions

#### Issue 1: Accuracy High in Calibration, Low in Test

**Problem**: Overfitting to calibration data

**Solution**:
- Use more diverse calibration data
- Don't over-train on specific session
- Cross-validate properly

#### Issue 2: Accuracy High for Some Targets, Low for Others

**Problem**: Harmonic collision or frequency response variation

**Solution**:
- Check for harmonic overlaps
- Verify LED brightness uniform
- Adjust frequency spacing
- Use frequency-specific weights

#### Issue 3: Accuracy Degrades Over Session

**Problem**: Fatigue, electrode movement, impedance change

**Solution**:
- Check electrode impedance periodically
- Recalibrate after 20-30 minutes
- Take breaks (5-10 minute rest)
- Use subject-specific adaptation

#### Issue 4: Poor Performance with New Subject

**Problem**: Individual differences in brain response

**Solution**:
- Perform calibration (5-10 min per subject)
- Learn subject-specific weights
- Adjust frequency set if needed (8-18 Hz might not be optimal for all)

---

## Performance Optimization {#optimization}

### Speed Optimization

**Goal**: Minimize latency for responsive BCI

```
Bottleneck Analysis (typical):

Filtering:          50 ms (necessary)
FFT computation:   100 ms (fast algorithm)
Feature extraction: 50 ms
Classification:     10 ms
─────────────────────────
Total:            210 ms

Optimization strategies:

1. Reduce epoch length: 1.0s → 0.8s (-20%)
2. Use fast FFT library: SciPy vs custom (-30%)
3. Hardware acceleration: GPU (-50%)
4. Pre-compute reference signals (-5%)
5. Parallel processing (-40%)

Result: 210ms → 100ms possible
```

### Accuracy Optimization

**Goal**: Maximize classification rate

```
Method                Addition      Accuracy boost
────────────────────────────────────────────────
FFT baseline          -             70-80%
+ harmonics          3-4 freq       +5%
+ channel fusion     O1+O2          +3-5%
+ CCA                better method  +5-8%
+ FBCCA              sub-bands      +5-8%
+ subject cal.       learned weights +10-20%
────────────────────────────────────────────────
Total potential:     FFT→FBCCA+cal  +30-50%
```

### Energy Optimization

**For wearable/portable systems**:

```
Strategy: Use simpler method that's "good enough"

Option 1: Full FBCCA
- Accuracy: 95%
- Power: 200 mW
- Latency: 300ms

Option 2: Optimized CCA
- Accuracy: 88%
- Power: 50 mW
- Latency: 150ms

Option 3: Fast FFT
- Accuracy: 75%
- Power: 20 mW
- Latency: 50ms

Choose based on application needs!
```

### Robustness Optimization

**Make system work reliably across conditions**:

```
Challenges:
1. Different subjects
2. Different sessions
3. Different electrode placements
4. Different levels of attention

Solutions:
1. Subject-specific calibration
2. Adaptive thresholding
3. Electrode impedance checking
4. Confidence scoring
```

**Confidence Score Implementation**:

```
confidence = (max_correlation - 2nd_max_correlation) / max_correlation

Classify only if confidence > threshold (e.g., 0.15)
Otherwise: Request retrial
```

**Result**: Better accuracy when confident, fewer false positives

---

## Summary: Feature Extraction Strategy for SSVEP

### Recommended Implementation Path

**For your 6-target SSVEP system with O1, O2 electrodes:**

1. **Start with**: Basic FFT/PSD (validation)
2. **Quick implementation**: Single-channel, 1.0s epochs
3. **Production version**: Multi-channel CCA with harmonics
4. **Advanced**: FBCCA with subject calibration
5. **Final optimization**: FBCCA + confidence scoring + per-target weighting

### Expected Performance

```
Implementation Level    Accuracy    Implementation Time    Complexity
─────────────────────────────────────────────────────────────────
Basic FFT             70-75%       2 hours                Low
FFT + harmonics       80-85%       4 hours                Low
Multi-ch CCA          87-91%       8 hours                Medium
FBCCA                 93-95%       12 hours               High
FBCCA + calibration   95-98%       16 hours               Very High
```

### Key Takeaways

1. **FFT is entry point**: Simple, understand fundamentals
2. **CCA exploits spatial information**: Significantly better
3. **Harmonics are essential**: Double the feature information
4. **Subject calibration is powerful**: 10-20% boost
5. **FBCCA best overall**: But most complex
6. **Epoch length critical**: 1.0-1.2 seconds optimal

---

## Implementation Checklist

- [ ] Electrode impedance < 10 kΩ
- [ ] Signal baseline noise verified
- [ ] Stimulus frequencies selected (8, 10, 12, 14, 16, 18 Hz)
- [ ] LED brightness uniform across all 6 boxes
- [ ] Display refresh rate ≥ 60 Hz
- [ ] Data collection working (512 Hz, 8-byte packets)
- [ ] Preprocessing pipeline implemented (notch + bandpass)
- [ ] Feature extraction method coded (start with FFT)
- [ ] Classifier trained on validation data
- [ ] Test accuracy validated on held-out test set
- [ ] Real-time latency measured
- [ ] Subject comfort assessed
- [ ] Error handling implemented
- [ ] Documentation complete

