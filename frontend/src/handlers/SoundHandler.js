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
}

export const soundHandler = new SoundHandler();
