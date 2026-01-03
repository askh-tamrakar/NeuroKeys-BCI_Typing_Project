class SoundHandler {
    constructor() {
        this.ctx = null;
        this.masterGain = null;
        this.initialized = false;
        this.enabled = true;
    }

    init() {
        if (this.initialized) return;

        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
            this.masterGain = this.ctx.createGain();
            this.masterGain.gain.value = 0.3; // Master volume
            this.masterGain.connect(this.ctx.destination);
            this.initialized = true;
            console.log('SoundHandler initialized');
        } catch (e) {
            console.error('Web Audio API not supported', e);
        }
    }

    // Ensure context is running (needed for Chrome autoplay policy)
    async resume() {
        if (!this.initialized) this.init();
        if (this.ctx && this.ctx.state === 'suspended') {
            await this.ctx.resume();
        }
    }

    playTone(freq, type, duration, volume = 0.5) {
        if (!this.enabled || !this.initialized) return;
        this.resume();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = type;
        osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

        gain.gain.setValueAtTime(volume, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.ctx.currentTime + duration);
    }

    playClick() {
        // Soothing soft click (sine wave, quick decay)
        this.playTone(600, 'sine', 0.1, 0.2);
    }

    playHover() {
        // Very subtle high pitch tick
        this.playTone(800, 'triangle', 0.05, 0.05);
    }

    playToggle(isOn) {
        if (!this.enabled || !this.initialized) return;
        this.resume();

        const now = this.ctx.currentTime;
        const oscillator = this.ctx.createOscillator();
        const gainNode = this.ctx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(this.masterGain);

        oscillator.type = 'sine';

        if (isOn) {
            // Rising pitch (ON)
            oscillator.frequency.setValueAtTime(300, now);
            oscillator.frequency.exponentialRampToValueAtTime(600, now + 0.1);
        } else {
            // Falling pitch (OFF)
            oscillator.frequency.setValueAtTime(600, now);
            oscillator.frequency.exponentialRampToValueAtTime(300, now + 0.1);
        }

        gainNode.gain.setValueAtTime(0.3, now);
        gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

        oscillator.start(now);
        oscillator.stop(now + 0.1);
    }

    playSliderTick() {
        // Wooden/mechanical tick
        this.playTone(200, 'triangle', 0.03, 0.15);
    }

    playConnectionZap() {
        if (!this.enabled || !this.initialized) {
            this.init(); // Auto-init if needed
            if (!this.initialized) return;
        }
        this.resume();

        const now = this.ctx.currentTime;
        const mainGain = this.ctx.createGain();
        mainGain.connect(this.masterGain);

        // 1. The "Zap" (Sawtooth burst)
        const zapOsc = this.ctx.createOscillator();
        const zapGain = this.ctx.createGain();
        zapOsc.type = 'sawtooth';
        zapOsc.frequency.setValueAtTime(120, now);
        zapOsc.frequency.exponentialRampToValueAtTime(50, now + 0.15); // Quick drop

        // Jitter/Modulate the zap frequency for "sparking" effect
        const modulator = this.ctx.createOscillator();
        const modGain = this.ctx.createGain();
        modulator.frequency.value = 50; // Fast rumble
        modGain.gain.value = 500; // Deep modulation
        modulator.connect(modGain);
        modGain.connect(zapOsc.frequency);
        modulator.start(now);
        modulator.stop(now + 0.2);

        zapGain.gain.setValueAtTime(0.4, now);
        zapGain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);

        zapOsc.connect(zapGain);
        zapGain.connect(mainGain);
        zapOsc.start(now);
        zapOsc.stop(now + 0.2);

        // 2. White Noise Burst (The "Frizz")
        const bufferSize = this.ctx.sampleRate * 0.2; // 0.2 seconds
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;
        const noiseGain = this.ctx.createGain();
        noiseGain.gain.setValueAtTime(0.3, now);
        noiseGain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

        // Highpass filter to keep only the "crackle"
        const highpass = this.ctx.createBiquadFilter();
        highpass.type = 'highpass';
        highpass.frequency.value = 1000;

        noise.connect(highpass);
        highpass.connect(noiseGain);
        noiseGain.connect(mainGain);
        noise.start(now);

        // 3. Electrical Hum (Mains hum connection)
        const humOsc = this.ctx.createOscillator();
        const humGain = this.ctx.createGain();
        humOsc.type = 'square';
        humOsc.frequency.setValueAtTime(55, now); // Between 50Hz and 60Hz
        humGain.gain.setValueAtTime(0.1, now);
        humGain.gain.exponentialRampToValueAtTime(0.01, now + 0.3); // Longer tail

        humOsc.connect(humGain);
        humGain.connect(mainGain);
        humOsc.start(now);
        humOsc.stop(now + 0.3);
    }
}

export const soundHandler = new SoundHandler();
