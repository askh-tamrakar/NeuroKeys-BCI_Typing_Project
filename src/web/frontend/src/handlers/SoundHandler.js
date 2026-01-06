import { Howl, Howler } from 'howler';

class SoundHandler {
    constructor() {
        // --- Howler Sounds (New) ---
        // Dino Game
        this.jumpSound = new Howl({ src: ['/sounds/jump.wav', '/sounds/jump.mp3'], volume: 0.5 });
        this.collisionSound = new Howl({ src: ['/sounds/collision.mp3'], volume: 0.7 });
        this.scoreSound = new Howl({ src: ['/sounds/score.mp3'], volume: 0.3 });
        this.bgMusic = new Howl({
            src: ['/sounds/background.wav', '/sounds/background.mp3'],
            loop: true,
            volume: 0.2,
            html5: true
        });

        // Rock Paper Scissors
        this.clickSound = new Howl({ src: ['/sounds/click.mp3'], volume: 0.5 });
        this.winSound = new Howl({ src: ['/sounds/win.mp3'], volume: 0.7 });
        this.loseSound = new Howl({ src: ['/sounds/lose.mp3'], volume: 0.7 });
        this.drawSound = new Howl({ src: ['/sounds/draw.mp3'], volume: 0.5 });

        this.isMuted = false;


        // --- Native Audio Context (Restored) ---
        this.ctx = null;
        this.masterGain = null;
        this.initialized = false;
        this.enabled = true;
    }

    // --- Native Audio Methods ---
    init() {
        if (this.initialized) return;
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
            this.masterGain = this.ctx.createGain();
            this.masterGain.gain.value = 0.3; // Master volume
            this.masterGain.connect(this.ctx.destination);
            this.initialized = true;
            console.log('SoundHandler (Native) initialized');
        } catch (e) {
            console.error('Web Audio API not supported', e);
        }
    }

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

    playHover() {
        // Original native hover sound
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
            oscillator.frequency.setValueAtTime(300, now);
            oscillator.frequency.exponentialRampToValueAtTime(600, now + 0.1);
        } else {
            oscillator.frequency.setValueAtTime(600, now);
            oscillator.frequency.exponentialRampToValueAtTime(300, now + 0.1);
        }
        gainNode.gain.setValueAtTime(0.3, now);
        gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
        oscillator.start(now);
        oscillator.stop(now + 0.1);
    }

    playSliderTick() {
        this.playTone(200, 'triangle', 0.03, 0.15);
    }

    playConnectionZap() {
        if (!this.enabled || !this.initialized) {
            this.init();
            if (!this.initialized) return;
        }
        this.resume();
        const now = this.ctx.currentTime;
        const mainGain = this.ctx.createGain();
        mainGain.connect(this.masterGain);

        // Zap
        const zapOsc = this.ctx.createOscillator();
        const zapGain = this.ctx.createGain();
        zapOsc.type = 'sawtooth';
        zapOsc.frequency.setValueAtTime(120, now);
        zapOsc.frequency.exponentialRampToValueAtTime(50, now + 0.15);

        // Modulator
        const modulator = this.ctx.createOscillator();
        const modGain = this.ctx.createGain();
        modulator.frequency.value = 50;
        modGain.gain.value = 500;
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

        // Noise
        const bufferSize = this.ctx.sampleRate * 0.2;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;
        const noiseGain = this.ctx.createGain();
        noiseGain.gain.setValueAtTime(0.3, now);
        noiseGain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
        const highpass = this.ctx.createBiquadFilter();
        highpass.type = 'highpass';
        highpass.frequency.value = 1000;
        noise.connect(highpass);
        highpass.connect(noiseGain);
        noiseGain.connect(mainGain);
        noise.start(now);

        // Hum
        const humOsc = this.ctx.createOscillator();
        const humGain = this.ctx.createGain();
        humOsc.type = 'square';
        humOsc.frequency.setValueAtTime(55, now);
        humGain.gain.setValueAtTime(0.1, now);
        humGain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
        humOsc.connect(humGain);
        humGain.connect(mainGain);
        humOsc.start(now);
        humOsc.stop(now + 0.3);
    }

    // --- Howler Game Methods ---
    playJump() { this.jumpSound.play(); }
    playCollision() { this.collisionSound.play(); }
    playScore() { this.scoreSound.play(); }
    startMusic() { if (!this.bgMusic.playing()) this.bgMusic.play(); }
    stopMusic() { this.bgMusic.stop(); }

    // --- Howler RPS Methods ---
    playClick() { this.clickSound.play(); }
    playWin() { this.winSound.play(); }
    playLose() { this.loseSound.play(); }
    playDraw() { this.drawSound.play(); }

    // --- System ---
    toggleMute() {
        this.isMuted = !this.isMuted;
        Howler.mute(this.isMuted);
        // Also mute native context
        if (this.masterGain) {
            this.masterGain.gain.value = this.isMuted ? 0 : 0.3;
        }
        return this.isMuted;
    }

    getMuteStatus() { return this.isMuted; }
}

export const soundHandler = new SoundHandler();
export default soundHandler;
