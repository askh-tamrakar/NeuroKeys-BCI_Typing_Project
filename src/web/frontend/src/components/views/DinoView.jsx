import React, { useState, useEffect, useRef } from 'react'
import '../../styles/views/DinoView.css'
import CameraPanel from '../ui/CameraPanel'
import CustomSelect from '../ui/CustomSelect'
import Counter from '../ui/Counter'
import {
    ScanEye, SlidersHorizontal, ArrowUp, Pause, Play, Trash2, Wifi, WifiOff, Save, Skull, Trophy, Keyboard, Eye,
    Gamepad2, Globe, Sparkles, Atom, Ruler, Settings, RotateCcw, ScrollText, Timer, Weight, MoveVertical,
    MoveHorizontal, Maximize, ArrowDownToLine, Grid, Sun, Moon, Cloud, Star, TreePine, Leaf, PlayCircle, Hand,
    Layers, Zap, Clock, ChevronDown, Activity, Hash, Target, Radio, Signal, Circle, Volume2, VolumeX
} from 'lucide-react'
import SoundHandler from '../../handlers/SoundHandler'

export default function DinoView({ wsData, wsEvent, isPaused }) {
    // Game state
    const [gameState, setGameState] = useState('ready') // ready, playing, paused, gameOver
    const [score, setScore] = useState(0)
    const [highScore, setHighScore] = useState(
        parseInt(localStorage.getItem('dino_highscore')) || 0
    )
    const [eyeState, setEyeState] = useState('open') // open, blink, double-blink
    const [showSettings, setShowSettings] = useState(false)
    const [isMuted, setIsMuted] = useState(false)

    // Game settings (easy mode default)
    const DEFAULT_SETTINGS = {
        GRAVITY: 1,
        JUMP_STRENGTH: -16,
        GROUND_OFFSET: 60,
        DINO_WIDTH: 62,
        DINO_HEIGHT: 66,
        OBSTACLE_WIDTH: 28,
        OBSTACLE_MIN_HEIGHT: 56,
        OBSTACLE_MAX_HEIGHT: 84,
        GAME_SPEED: 9.4,
        SPAWN_INTERVAL: 1100,
        CANVAS_WIDTH: 800,
        CANVAS_HEIGHT: 376,
        CYCLE_DURATION: 100,
        JUMP_DISTANCE: 300,
        ENABLE_MANUAL_CONTROLS: true,
        CONTROL_CHANNEL: 'any',
        OBSTACLE_BONUS_FACTOR: 0.015,

        // Visual Customization
        ENABLE_TREES: true,
        TREES_DENSITY: 0.7,
        TREES_SIZE: 1.2,
        TREES_LAYERS: 10,

        ENABLE_CLOUDS: true,
        CLOUDS_DENSITY: 2,
        CLOUDS_SIZE: 0.9,
        CLOUDS_LAYERS: 10,

        ENABLE_STARS: true,
        STARS_DENSITY: 1,
        STARS_SIZE: 1.1,
        STARS_LAYERS: 10,

        ENABLE_BUSHES: true,
        BUSHES_DENSITY: 0.8,
        BUSHES_SIZE: 0.7,
        BUSHES_LAYERS: 7,

        ENABLE_DAY_NIGHT_CYCLE: true,
        FIXED_TIME: 0.25, // Noon default

        ENABLE_MOON_PHASES: true,
        ENABLE_AUTO_MOON_CYCLE: true,
        MOON_CYCLE_DAYS: 30, // Days for full phase cycle (15 days to Full)
        MOON_PHASE: 0.5 // 0.0=New, 0.5=Full, 1.0=New
    }

    const [settings, setSettings] = useState(() => {
        const saved = localStorage.getItem('dino_settings_v6')
        if (saved) {
            try {
                return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) }
            } catch (e) {
                console.error("Failed to parse settings", e)
            }
        }
        return DEFAULT_SETTINGS
    })
    const [savedMessage, setSavedMessage] = useState('')


    // --- Event Logging System ---
    const [eventLogs, setEventLogs] = useState([])
    const logEvent = (msg, type = 'info') => {
        const time = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
        setEventLogs(prev => [{
            id: Date.now() + Math.random(),
            time,
            text: msg,
            type
        }, ...prev].slice(0, 50))
    }

    // Refs for game state (to avoid stale closures)
    const containerRef = useRef(null) // Container for ResizeObserver
    const canvasRef = useRef(null)
    const animationRef = useRef(null)
    const gameStateRef = useRef('ready')
    const dinoYRef = useRef(0)
    const velocityRef = useRef(0)
    const obstaclesRef = useRef([])
    const scoreRef = useRef(0)
    const lastSpawnTimestampRef = useRef(0)
    const blinkPressTimeRef = useRef(0)
    const pendingBlinkTimeoutRef = useRef(null) // New ref for double-blink timer
    const leftEyeRef = useRef(null)
    const rightEyeRef = useRef(null)
    const distanceRef = useRef(0) // Track distance for parallax

    const settingsRef = useRef(DEFAULT_SETTINGS)

    // Visuals Refs
    const gameTimeRef = useRef(0) // 0 to 1 (0=dawn, 0.25=noon, 0.5=dusk, 0.75=midnight)
    // cycleDuration is now in settings
    const cloudsRef = useRef([])
    const treesRef = useRef([]) // Background parallax trees
    const starsRef = useRef([])
    const terrainRef = useRef(null) // Cache for terrain pattern if needed

    // Initialize visuals
    useEffect(() => {
        // Init clouds (multi-layer)
        const clouds = []
        for (let i = 0; i < 15; i++) {
            // More clouds at varying depths
            const depth = 0.15 + Math.random() * 0.85 // 0.15 (very far) to 1.0 (near)
            clouds.push({
                x: Math.random() * DEFAULT_SETTINGS.CANVAS_WIDTH,
                y: Math.random() * 150 + 20,
                width: (60 + Math.random() * 40) * depth, // Smaller if far
                speed: (0.1 + Math.random() * 0.1) * depth, // Slower if far
                depth: depth
            })
        }
        cloudsRef.current = clouds.sort((a, b) => a.depth - b.depth) // Draw far ones first

        // Init trees (background parallax with depth)
        const trees = []
        const treeCount = Math.floor(DEFAULT_SETTINGS.CANVAS_WIDTH / 60) + 5 // Denser trees
        for (let i = 0; i < treeCount; i++) {
            const depth = 0.4 + Math.random() * 0.6 // 0.4 (far) to 1.0 (near-ish background)
            const scale = depth // Size scale
            trees.push({
                x: Math.random() * DEFAULT_SETTINGS.CANVAS_WIDTH * 1.2, // Initial scattering 
                height: (50 + Math.random() * 70) * scale,
                width: (25 + Math.random() * 25) * scale,
                type: Math.random() > 0.5 ? 'round' : 'pine',
                depth: depth,
                speedFactor: 0.5 * depth // Move slower if further away
            })
        }
        // Sor trees by depth so far ones draw first
        treesRef.current = trees.sort((a, b) => a.depth - b.depth)

        // Init stars
        const stars = []
        for (let i = 0; i < 50; i++) {
            stars.push({
                x: Math.random() * DEFAULT_SETTINGS.CANVAS_WIDTH,
                y: Math.random() * DEFAULT_SETTINGS.CANVAS_HEIGHT / 2,
                size: Math.random() * 2 + 1,
                blinkOffset: Math.random() * Math.PI
            })
        }
        starsRef.current = stars
    }, [])

    // Sync refs with state
    useEffect(() => {
        gameStateRef.current = gameState
    }, [gameState])

    useEffect(() => {
        scoreRef.current = score
    }, [score])

    useEffect(() => {
        settingsRef.current = settings
    }, [settings])

    // Handle EOG blink detection
    const handleEOGBlink = (source = 'blink') => {
        const now = Date.now()
        const timeSinceLastPress = now - blinkPressTimeRef.current

        if (timeSinceLastPress < 400 && timeSinceLastPress > 75) {
            handleDoublePress(source)
        } else {
            handleSinglePress(source)
        }

        blinkPressTimeRef.current = now
    }

    // WebSocket Event Listener (Blinks)
    useEffect(() => {
        if (!wsEvent) return;

        // Check channel match (or 'any' bypass)
        const targetCh = settingsRef.current.CONTROL_CHANNEL
        if (targetCh !== 'any' && wsEvent.channel !== targetCh) {
            // console.log(`[Dino] Ignored event ${wsEvent.event} from ${wsEvent.channel} (Target: ${targetCh})`);
            return
        }

        if (wsEvent.event === 'BLINK' || wsEvent.event === 'SingleBlink') {
            console.log("🦖 Dino: Blink Event Received via Logic Pipeline!");
            handleEOGBlink();
        }
    }, [wsEvent]);

    // Track Connection Status Logging
    useEffect(() => {
        if (wsData) {
            logEvent("Sensor Connected", 'connection')
        } else {
            logEvent("Sensor Disconnected", 'disconnect')
        }
    }, [!!wsData]) // Only trigger on boolean flip

    // --- Worker Bridge ---
    const workerRef = useRef(null)
    const observerRef = useRef(null)
    const workerCleanupTimerRef = useRef(null)

    const [canvasResetKey, setCanvasResetKey] = useState(0)

    // Initialize Worker
    useEffect(() => {
        if (!canvasRef.current) return

        // Cancel any pending cleanup (StrictMode handling)
        if (workerCleanupTimerRef.current) {
            clearTimeout(workerCleanupTimerRef.current)
            workerCleanupTimerRef.current = null
        }

        let worker = workerRef.current

        if (!worker) {
            try {
                // Create worker
                worker = new Worker(new URL('../../workers/game.worker.js', import.meta.url), { type: 'module' })
                workerRef.current = worker

                // Get OffscreenCanvas
                const offscreen = canvasRef.current.transferControlToOffscreen()

                // Get theme colors
                const styles = getComputedStyle(document.body)
                const theme = {
                    bg: styles.getPropertyValue('--bg').trim(),
                    surface: styles.getPropertyValue('--surface').trim(),
                    text: styles.getPropertyValue('--text').trim(),
                    primary: styles.getPropertyValue('--primary').trim(),
                    border: styles.getPropertyValue('--border').trim(),
                    muted: styles.getPropertyValue('--muted').trim(),
                    accent: styles.getPropertyValue('--accent').trim(),
                    day: styles.getPropertyValue('--day').trim(),
                    night: styles.getPropertyValue('--night').trim(),
                    treeDay: styles.getPropertyValue('--tree-day').trim(),
                    treeNight: styles.getPropertyValue('--tree-night').trim(),
                    cloudDay: styles.getPropertyValue('--cloud-day').trim(),
                    cloudNight: styles.getPropertyValue('--cloud-night').trim(),
                    sunDay: styles.getPropertyValue('--sun-day').trim(),
                    sunNight: styles.getPropertyValue('--sun-night').trim(),
                    moonDay: styles.getPropertyValue('--moon-day').trim(),
                    moonNight: styles.getPropertyValue('--moon-night').trim(),
                    // New simplified mappings
                    dinoDay: styles.getPropertyValue('--dino').trim(),
                    dinoNight: styles.getPropertyValue('--dino').trim(),
                    obstacleDay: styles.getPropertyValue('--obstacle').trim(),
                    obstacleNight: styles.getPropertyValue('--obstacle').trim(),
                    obstacleBorder: styles.getPropertyValue('--obstacle-border').trim(),
                    groundDay: styles.getPropertyValue('--ground').trim(),
                    groundNight: styles.getPropertyValue('--ground').trim(),
                    groundLineDay: styles.getPropertyValue('--ground-line').trim(),
                    groundLineNight: styles.getPropertyValue('--ground-line').trim(),
                    skyDay: styles.getPropertyValue('--sky-day').trim(),
                    skyNight: styles.getPropertyValue('--sky-night').trim()
                }

                // Load 8 Bush Variants
                const loadBush = (i) => new Promise((resolve, reject) => {
                    const img = new Image();
                    img.src = `/Resources/Dino/bush_${i}.png`;
                    img.onload = () => createImageBitmap(img).then(resolve).catch(reject);
                    img.onerror = reject;
                });

                Promise.all(Array.from({ length: 8 }, (_, i) => loadBush(i + 1)))
                    .then(bushSprites => {
                        // Init Worker with Sprites
                        const width = containerRef.current ? containerRef.current.clientWidth : settingsRef.current.CANVAS_WIDTH;
                        const height = containerRef.current ? containerRef.current.clientHeight : settingsRef.current.CANVAS_HEIGHT;

                        worker.postMessage({
                            type: 'INIT',
                            payload: {
                                canvas: offscreen,
                                settings: {
                                    ...settingsRef.current,
                                    CANVAS_WIDTH: width,
                                    CANVAS_HEIGHT: height
                                },
                                highScore: highScore,
                                theme: theme,
                                bushSprites: bushSprites
                            }
                        }, [offscreen, ...bushSprites]);
                    })
                    .catch(err => {
                        console.warn("Failed to load bush sprites", err);
                        const width = containerRef.current ? containerRef.current.clientWidth : settingsRef.current.CANVAS_WIDTH;
                        const height = containerRef.current ? containerRef.current.clientHeight : settingsRef.current.CANVAS_HEIGHT;

                        // Init without sprites
                        worker.postMessage({
                            type: 'INIT',
                            payload: {
                                canvas: offscreen,
                                settings: {
                                    ...settingsRef.current,
                                    CANVAS_WIDTH: width,
                                    CANVAS_HEIGHT: height
                                },
                                highScore: highScore,
                                theme: theme,
                                bushSprites: []
                            }
                        }, [offscreen]);
                    });

                // --- Setup Resize Observer ---
                if (containerRef.current) {
                    observerRef.current = new ResizeObserver(entries => {
                        for (let entry of entries) {
                            const { width, height } = entry.contentRect;
                            if (width > 0 && height > 0 && workerRef.current) {
                                workerRef.current.postMessage({
                                    type: 'RESIZE',
                                    payload: { width, height }
                                });
                            }
                        }
                    });
                    observerRef.current.observe(containerRef.current);
                }
            } catch (err) {
                console.warn("Canvas transfer failed or Worker init error:", err)
            }
        }

        // Always re-bind events because 'worker' instance is stable but closure might not be?
        if (worker) {
            worker.onmessage = (e) => {
                const { type, score, highScore: newHigh } = e.data
                if (type === 'GAME_OVER') {
                    setGameState('gameOver')
                    SoundHandler.playCollision()
                    SoundHandler.stopMusic()
                    if (score !== undefined) {
                        scoreRef.current = score
                        logEvent(`Game Over! Score: ${Math.floor(score / 10)}`, 'gameover')
                    }
                } else if (type === 'HIGHSCORE_UPDATE') {
                    setHighScore(newHigh)
                    localStorage.setItem('dino_highscore', newHigh.toString())
                    logEvent(`New Highscore: ${Math.floor(newHigh / 10)}!`, 'highscore')
                } else if (type === 'SCORE_UPDATE') {
                    setScore(score)
                    if (score > 0 && score % 100 === 0) SoundHandler.playScore()
                } else if (type === 'STATE_UPDATE') {
                    setGameState(e.data.payload)
                    if (e.data.payload === 'playing') SoundHandler.startMusic()
                }
            }
        }

        // Cleanup
        return () => {
            // Delay cleanup to allow for StrictMode remount re-use
            workerCleanupTimerRef.current = setTimeout(() => {
                if (workerRef.current) {
                    workerRef.current.terminate()
                    workerRef.current = null
                }
                if (observerRef.current) {
                    observerRef.current.disconnect()
                    observerRef.current = null
                }
            }, 100)
        }
    }, [canvasResetKey]);

    // Monitor Theme Changes and Sync to Worker
    useEffect(() => {
        const observer = new MutationObserver((mutations) => {
            let shouldUpdate = false;
            for (const mutation of mutations) {
                if (mutation.type === 'attributes' && (mutation.attributeName === 'class' || mutation.attributeName === 'style')) {
                    shouldUpdate = true;
                    break;
                }
            }

            if (shouldUpdate && workerRef.current) {
                const styles = getComputedStyle(document.body);
                const theme = {
                    bg: styles.getPropertyValue('--bg').trim(),
                    surface: styles.getPropertyValue('--surface').trim(),
                    text: styles.getPropertyValue('--text').trim(),
                    primary: styles.getPropertyValue('--primary').trim(),
                    border: styles.getPropertyValue('--border').trim(),
                    muted: styles.getPropertyValue('--muted').trim(),
                    accent: styles.getPropertyValue('--accent').trim(),
                    day: styles.getPropertyValue('--day').trim(),
                    night: styles.getPropertyValue('--night').trim(),
                    treeDay: styles.getPropertyValue('--tree-day').trim(),
                    treeNight: styles.getPropertyValue('--tree-night').trim(),
                    cloudDay: styles.getPropertyValue('--cloud-day').trim(),
                    cloudNight: styles.getPropertyValue('--cloud-night').trim(),
                    sunDay: styles.getPropertyValue('--sun-day').trim(),
                    sunNight: styles.getPropertyValue('--sun-night').trim(),
                    moonDay: styles.getPropertyValue('--moon-day').trim(),
                    moonNight: styles.getPropertyValue('--moon-night').trim(),
                    // New simplified mappings
                    dinoDay: styles.getPropertyValue('--dino').trim(),
                    dinoNight: styles.getPropertyValue('--dino').trim(),
                    obstacleDay: styles.getPropertyValue('--obstacle').trim(),
                    obstacleNight: styles.getPropertyValue('--obstacle').trim(),
                    obstacleBorder: styles.getPropertyValue('--obstacle-border').trim(),
                    groundDay: styles.getPropertyValue('--ground').trim(),
                    groundNight: styles.getPropertyValue('--ground').trim(),
                    groundLineDay: styles.getPropertyValue('--ground-line').trim(),
                    groundLineNight: styles.getPropertyValue('--ground-line').trim(),
                    skyDay: styles.getPropertyValue('--sky-day').trim(),
                    skyNight: styles.getPropertyValue('--sky-night').trim()
                };
                workerRef.current.postMessage({ type: 'THEME_UPDATE', payload: theme });
            }
        });

        observer.observe(document.body, { attributes: true });
        observer.observe(document.documentElement, { attributes: true });

        return () => observer.disconnect();
    }, []);

    // Handle Resizing (Responsive)
    useEffect(() => {
        if (!workerRef.current || !containerRef.current) return

        const updateSize = () => {
            if (!containerRef.current || !workerRef.current) return
            const { clientWidth, clientHeight } = containerRef.current

            workerRef.current.postMessage({
                type: 'RESIZE',
                payload: {
                    width: clientWidth,
                    height: clientHeight
                }
            })
        }

        const resizeObserver = new ResizeObserver(() => {
            updateSize()
        })

        resizeObserver.observe(containerRef.current)
        updateSize() // Initial

        return () => {
            resizeObserver.disconnect()
        }
    }, [canvasResetKey])

    // Update settings in worker
    useEffect(() => {
        if (workerRef.current) {
            // Exclude canvas dimensions so we don't overwrite the resize observer's values
            // with potentially stale default settings
            const { CANVAS_WIDTH, CANVAS_HEIGHT, ...safeSettings } = settings
            workerRef.current.postMessage({
                type: 'SETTINGS',
                payload: safeSettings
            })
        }
    }, [settings])

    // Sync Highscore reset
    useEffect(() => {
        if (workerRef.current) {
            workerRef.current.postMessage({
                type: 'SETTINGS',
                payload: { highScore }
            })
        }
    }, [highScore])

    // Bridge Inputs
    const handleSinglePress = (source = 'blink') => {
        const text = source === 'keyboard' ? "Spacebar (Jump)" : "Blink Detected (Jump)"
        const type = source === 'keyboard' ? 'keyboard' : 'jump' // 'jump' maps to ArrowUp (which is good for blink too? or use Eye). Let's use 'blink' type for Eye icon.
        // Actually, user wants "Jump Triggered" vs "Blink Detected". 
        // Let's be consistent: 
        // Keyboard: "Spacebar (Jump)" -> Keyboard Icon
        // Blink: "Blink Detected (Jump)" -> Eye Icon 

        logEvent(text, source === 'keyboard' ? 'keyboard' : 'blink')
        triggerSingleBlink()
        SoundHandler.playJump()

        if (workerRef.current) {
            console.log("[DinoView] Sending 'jump' to worker. Ref:", workerRef.current)
            workerRef.current.postMessage({ type: 'INPUT', payload: { action: 'jump' } })
        } else {
            console.warn("[DinoView] Worker ref is missing!")
        }

        // Optimistic state update for UI status
        if (gameStateRef.current === 'ready' || gameStateRef.current === 'gameOver') {
            setGameState('playing')
            SoundHandler.startMusic()
        }
    }

    const handleDoublePress = (source = 'blink') => {
        const text = source === 'keyboard' ? "Spacebar x2 (Pause)" : "Double Blink (Pause)"
        logEvent(text, 'toggle')
        triggerDoubleBlink()

        if (workerRef.current) {
            workerRef.current.postMessage({ type: 'INPUT', payload: { action: 'pause' } })
        }
    }

    // Manual Keyboard Controls
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.code === 'Space') {
                e.preventDefault()
                // Check if manual controls enabled
                console.log("[DinoView] Spacebar pressed. Manual controls:", settings.ENABLE_MANUAL_CONTROLS)
                if (settings.ENABLE_MANUAL_CONTROLS) {
                    handleEOGBlink('keyboard') // Use the same unified logic for consistency
                }
            }
        }
        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [settings])

    // Blink Visuals (Optional - kept for side panel feedback)
    const triggerSingleBlink = () => {
        setEyeState('blink')
        setTimeout(() => setEyeState('open'), 300)
    }
    const triggerDoubleBlink = () => {
        setEyeState('double-blink')
        setTimeout(() => setEyeState('open'), 600)
    }

    const handleSettingChange = (key, value) => {
        setSettings(prev => ({
            ...prev,
            [key]: typeof value === 'string' ? value : (typeof value === 'boolean' ? value : parseFloat(value))
        }))
    }

    const handleSaveSettings = () => {
        localStorage.setItem('dino_settings_v6', JSON.stringify(settings))
        setSavedMessage('Saved!')
        logEvent("Settings Updated", 'settings')
        setTimeout(() => setSavedMessage(''), 2000)
    }

    const handleResetSettings = () => {
        const saved = localStorage.getItem('dino_settings_v6')
        if (saved) {
            try {
                const parsed = JSON.parse(saved)
                setSettings({ ...DEFAULT_SETTINGS, ...parsed })
                setSavedMessage('Reverted!')
                logEvent("Settings Reverted", 'settings')
            } catch (e) {
                console.error("Failed to parse saved settings", e)
                setSettings(DEFAULT_SETTINGS)
                setSavedMessage('Reset to Default')
                logEvent("Corrupt Save - Reset to Default", 'settings')
            }
        } else {
            setSettings(DEFAULT_SETTINGS)
            setSavedMessage('Reset to Default')
            logEvent("No Save - Reset to Default", 'settings')
        }
        setTimeout(() => setSavedMessage(''), 2000)
    }

    return (
        <div className="dino-container">
            <div className="dino-game-wrapper">
                {/* Main game area */}
                <div className="game-main-area">
                    <div className="game-card">
                        <div className="game-header">
                            <h2 className="game-title">
                                <span className={`status-eye ${wsData ? 'connected' : 'disconnected'}`}><ScanEye size={32} /></span>
                                EOG Dino Game
                            </h2>
                            <button
                                onClick={() => {
                                    const muted = SoundHandler.toggleMute()
                                    setIsMuted(muted)
                                }}
                                className={`tuner-button ${isMuted ? 'inactive' : 'active'}`}
                                style={{ marginRight: '8px' }}
                                title="Toggle Sound"
                            >
                                {isMuted ? <VolumeX /> : <Volume2 />}
                            </button>
                            <button
                                onClick={() => setShowSettings(!showSettings)}
                                className={`tuner-button ${showSettings ? 'active' : 'inactive'}`}
                            >
                                <SlidersHorizontal /> Tuner
                            </button>
                        </div>

                        <div className="game-content-stack">
                            {/* Game info */}
                            <div className="game-info-panel">
                                {/* Eye Tracker (Absolute Positioned on Top Border) */}
                                <div className="eyes-container">
                                    {/* Left Eye */}
                                    <div className={`eye ${eyeState !== 'open' ? eyeState : ''}`} ref={leftEyeRef}>
                                        <div className="pupil"></div>
                                    </div>
                                    {/* Right Eye */}
                                    <div className={`eye ${eyeState !== 'open' ? eyeState : ''}`} ref={rightEyeRef}>
                                        <div className="pupil"></div>
                                    </div>

                                    {/* Face Decorations (Eyebrows & Smile) */}
                                    <svg className="face-decoration-svg" style={{ overflow: 'visible', width: '100%', height: '100%' }}>
                                        {/* Left Curve (Border to Top of Eye - Quarter Circle) */}
                                        <path
                                            d="M -160 -16 A 64 64 0 0 1 -96 -62"
                                            fill="none"
                                            stroke="var(--text)"
                                            strokeWidth="3"
                                            strokeLinecap="round"
                                        />
                                        {/* Right Curve (Top of Eye to Border - Quarter Circle) */}
                                        <path
                                            d="M 160 -16 A 64 64 0 0 0 96 -62"
                                            fill="none"
                                            stroke="var(--text)"
                                            strokeWidth="3"
                                            strokeLinecap="round"
                                        />
                                        {/* Smile (Circular Arc) */}
                                        <path
                                            d="M -40 75 A 45 45 0 0 0 40 75"
                                            fill="none"
                                            stroke="var(--text)"
                                            strokeWidth="3"
                                            strokeLinecap="round"
                                        />
                                    </svg>
                                </div>

                                <div className="game-stats-container">
                                    {/* Left Side: Status & Score */}
                                    <div className="stat-group-left">
                                        <div className="stat-block stat-block-start mb-1">
                                            <span className="stat-label flex items-center gap-1"><Activity size={24} /> Status</span>
                                            <div className={`stat-value-status ${gameState}`}>
                                                {gameState}
                                            </div>
                                        </div>
                                        <div className="stat-block-row stat-block-start">
                                            <span className="stat-label flex items-center gap-1"><Target size={24} /> Score :</span>
                                            <Counter value={Math.floor(score / 10)} fontSize={48} digitHeight={75} places={[10000, 1000, 100, 10, 1]} className="stat-counter-large" />
                                        </div>
                                    </div>

                                    {/* Right Side: Best & Sensor */}
                                    <div className="stat-group-right">
                                        <div className="stat-block-row stat-block-end">
                                            <Counter
                                                value={Math.floor(highScore / 10)}
                                                fontSize={48}
                                                digitHeight={75}
                                                places={[10000, 1000, 100, 10, 1]}
                                                className="stat-counter-large"
                                            />
                                            <span className="stat-label flex items-center gap-1">: Best <Trophy size={24} className="text-yellow-500 mb-1" /></span>
                                        </div>
                                        <div className="stat-block stat-block-end mb-1">
                                            <span className="stat-label flex items-center gap-1"><Radio size={24} /> Sensor</span>
                                            <div className={`stat-value-sensor ${wsData ? 'text-green-500' : 'text-red-500'}`}>
                                                {wsData ? 'Connected' : 'Disconnected'}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Canvas */}
                            <div
                                className="dino-canvas-container"
                                ref={containerRef}
                            >
                                <canvas
                                    key={canvasResetKey}
                                    ref={canvasRef}
                                    className="dino-canvas"
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Sidebar */}
                <div className="game-sidebar pr-1.5">
                    <div className="h-[85px] shrink-0" />
                    {/* Camera Panel */}
                    <CameraPanel />

                    {/* Eye Controls Panel */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-4 " style={{ flexShrink: 0 }}>
                        <h3 className="text-sm font-bold text-text uppercase tracking-wider mb-3 flex items-center gap-2"><Gamepad2 size={16} /> Controls</h3>
                        <div className="space-y-2 text-sm text-text">
                            <div className="flex justify-between items-center">
                                <span className="text-muted flex items-center gap-1.5"><Eye size={14} className="text-secondary/70" /> Blink ONCE</span>
                                <span className="font-bold text-primary flex items-center gap-1"><ArrowUp size={12} /> Jump</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-muted flex items-center gap-1.5"><Eye size={14} className="text-secondary/70" /><Eye size={14} className="text-secondary/70 -ml-2" /> Blink TWICE</span>
                                <span className="font-bold text-primary flex items-center gap-1"><Pause size={12} /> Pause/Resume</span>
                            </div>
                        </div>

                        <div className="mt-4 pt-3 border-t border-border space-y-3">
                            <SettingSelect
                                label="Control Channel"
                                value={settings.CONTROL_CHANNEL}
                                options={[
                                    { label: 'Any Channel', value: 'any' },
                                    { label: 'Channel 0', value: 'ch0' },
                                    { label: 'Channel 1', value: 'ch1' },
                                    { label: 'Channel 2', value: 'ch2' },
                                    { label: 'Channel 3', value: 'ch3' },
                                ]}
                                onChange={(v) => handleSettingChange('CONTROL_CHANNEL', v)}
                            />

                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted font-medium uppercase tracking-wider flex items-center gap-1"><Signal size={12} /> Input Status</span>
                                <span className={`font-bold ${wsData ? 'text-green-500' : 'text-red-500'}`}>
                                    {wsData ? 'ACTIVE' : 'OFFLINE'}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Event Log Panel */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-4" style={{ flexShrink: 0 }}>
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="text-sm font-bold text-text uppercase tracking-wider flex items-center gap-2"><ScrollText size={16} /> Event Log</h3>
                            <button
                                onClick={() => setEventLogs([])}
                                className="text-sm text-muted hover:text-red-400 flex items-center gap-1"
                            >
                                <Trash2 size={16} /> Clear
                            </button>
                        </div>
                        <div className="bg-bg/50 rounded-lg p-2 h-32 overflow-y-auto font-mono text-xs space-y-1 border border-border scrollbar-thin scrollbar-thumb-border hover:scrollbar-thumb-primary/50 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
                            {eventLogs.length === 0 ? (
                                <div className="text-muted italic text-center py-4">No events yet...</div>
                            ) : (
                                eventLogs.map((log) => (
                                    <div key={log.id} className="text-muted hover:text-text transition-colors border-b border-border last:border-0 pb-1 mb-1 flex items-start gap-2">
                                        <span className="opacity-50 text-[10px] mt-0.5">{log.time}</span>
                                        <div className="flex-1 flex items-center gap-1.5 break-words min-w-0">
                                            {log.type === 'jump' && <ArrowUp size={12} className="text-primary shrink-0" />}
                                            {log.type === 'blink' && <Eye size={12} className="text-primary shrink-0" />}
                                            {log.type === 'keyboard' && <Keyboard size={12} className="text-muted shrink-0" />}
                                            {log.type === 'toggle' && <div className="flex shrink-0"><Pause size={12} className="text-yellow-500" /><Play size={12} className="text-green-500 -ml-1" /></div>}
                                            {log.type === 'connection' && <Wifi size={12} className="text-green-500 shrink-0" />}
                                            {log.type === 'disconnect' && <WifiOff size={12} className="text-red-500 shrink-0" />}
                                            {log.type === 'settings' && <Save size={12} className="text-blue-400 shrink-0" />}
                                            {log.type === 'gameover' && <Skull size={12} className="text-red-500 shrink-0" />}
                                            {log.type === 'highscore' && <Trophy size={12} className="text-yellow-400 shrink-0" />}
                                            <span>{log.text}</span>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Settings Panel (Moved here) */}
                    {showSettings && (
                        <div className="card bg-surface border border-border shadow-card rounded-2xl p-4 animate-fade-in" style={{ flexShrink: 0 }}>
                            <div className="flex justify-between flex-col gap-2 mb-4">
                                <h3 className="text-sm font-bold text-text uppercase tracking-wider flex items-center gap-2"><Settings size={16} /> Game Constants</h3>
                                <div className="flex gap-2 justify-between">
                                    <span className="flex items-center gap-2">
                                        <button
                                            onClick={handleSaveSettings}
                                            className="text-sm bg-primary text-bg px-2 py-1 rounded font-bold hover:opacity-90 flex items-center gap-1"
                                        >
                                            <Save size={18} /> Save
                                        </button>
                                        {savedMessage && <span className="text-xs text-green-500 font-bold animate-fade-in">{savedMessage}</span>}
                                    </span>

                                    <button
                                        onClick={handleResetSettings}
                                        className="text-sm text-red-400 hover:text-red-300 flex items-center gap-1"
                                    >
                                        <RotateCcw size={18} /> Reset
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <SettingsSection title="Gameplay" icon={Gamepad2} defaultOpen={true}>
                                    <div className="space-y-3 pt-2">
                                        <SettingToggle label="Manual Controls (Space)" value={settings.ENABLE_MANUAL_CONTROLS} onChange={(v) => handleSettingChange('ENABLE_MANUAL_CONTROLS', v)} icon={Hand} />
                                        <SettingInput label="Obstacle Bonus" value={settings.OBSTACLE_BONUS_FACTOR} onChange={(v) => handleSettingChange('OBSTACLE_BONUS_FACTOR', v)} min="0" max="0.5" step="0.005" icon={Zap} />
                                        <div className="flex justify-between items-center text-xs pt-1 border-t border-border">
                                            <span className="text-muted flex items-center gap-1"><Trophy size={10} /> Highscore: {Math.floor(highScore / 10)}</span>
                                            <button
                                                onClick={() => {
                                                    localStorage.setItem('dino_highscore', '0')
                                                    setHighScore(0)
                                                    setSavedMessage('Score Reset!')
                                                    setTimeout(() => setSavedMessage(''), 2000)
                                                }}
                                                className="text-red-400 hover:text-red-300 font-bold uppercase tracking-wide text-[10px] border border-red-900/50 px-2 py-0.5 rounded bg-red-900/10 flex items-center gap-1"
                                            >
                                                <Trash2 size={10} /> Reset
                                            </button>
                                        </div>
                                    </div>
                                </SettingsSection>

                                <SettingsSection title="Environment" icon={Globe}>
                                    <div className="space-y-3 pt-2">
                                        <h5 className="text-[10px] font-bold text-muted uppercase tracking-wider mb-1 flex items-center gap-1"><Sun size={10} /> Day/Night</h5>
                                        <SettingToggle label="Auto Cycle" value={settings.ENABLE_DAY_NIGHT_CYCLE} onChange={(v) => handleSettingChange('ENABLE_DAY_NIGHT_CYCLE', v)} icon={RotateCcw} />
                                        {settings.ENABLE_DAY_NIGHT_CYCLE ? (
                                            <SettingInput label="Duration (s)" value={settings.CYCLE_DURATION} onChange={(v) => handleSettingChange('CYCLE_DURATION', v)} min="10" max="300" step="5" icon={Timer} />
                                        ) : (
                                            <SettingInput label="Fixed Time" value={settings.FIXED_TIME} onChange={(v) => handleSettingChange('FIXED_TIME', v)} min="0" max="1" step="0.05" icon={Clock} />
                                        )}

                                        <h5 className="text-[10px] font-bold text-muted uppercase tracking-wider mb-1 mt-3 flex items-center gap-1"><Moon size={10} /> Moon</h5>
                                        <SettingToggle label="Enable Phases" value={settings.ENABLE_MOON_PHASES} onChange={(v) => handleSettingChange('ENABLE_MOON_PHASES', v)} icon={Moon} />
                                        {settings.ENABLE_MOON_PHASES && (
                                            <>
                                                <SettingToggle label="Auto Cycle" value={settings.ENABLE_AUTO_MOON_CYCLE} onChange={(v) => handleSettingChange('ENABLE_AUTO_MOON_CYCLE', v)} icon={RotateCcw} />
                                                {settings.ENABLE_AUTO_MOON_CYCLE ? (
                                                    <SettingInput label="Days/Cycle" value={settings.MOON_CYCLE_DAYS} onChange={(v) => handleSettingChange('MOON_CYCLE_DAYS', v)} min="1" max="30" step="1" icon={Timer} />
                                                ) : (
                                                    <SettingInput label="Phase (0-1)" value={settings.MOON_PHASE} onChange={(v) => handleSettingChange('MOON_PHASE', v)} min="0" max="1" step="0.05" icon={Circle} />
                                                )}
                                            </>
                                        )}

                                        <h5 className="text-[10px] font-bold text-muted uppercase tracking-wider mb-1 mt-3 flex items-center gap-1"><Grid size={10} /> Elements</h5>
                                        <div className="grid grid-cols-2 gap-2">
                                            <SettingToggle label="Trees" value={settings.ENABLE_TREES} onChange={(v) => handleSettingChange('ENABLE_TREES', v)} icon={TreePine} />
                                            <SettingToggle label="Clouds" value={settings.ENABLE_CLOUDS} onChange={(v) => handleSettingChange('ENABLE_CLOUDS', v)} icon={Cloud} />
                                            <SettingToggle label="Stars" value={settings.ENABLE_STARS} onChange={(v) => handleSettingChange('ENABLE_STARS', v)} icon={Star} />
                                            <SettingToggle label="Bushes" value={settings.ENABLE_BUSHES} onChange={(v) => handleSettingChange('ENABLE_BUSHES', v)} icon={Leaf} />
                                        </div>
                                    </div>
                                </SettingsSection>

                                <SettingsSection title="Visual Details" icon={Sparkles}>
                                    <div className="space-y-4 pt-2">
                                        {/* Trees */}
                                        <div className="bg-bg/50 p-2 rounded border border-border">
                                            <h5 className="text-[10px] font-bold text-primary mb-2 border-b border-border pb-1 flex items-center gap-1"><TreePine size={10} /> Trees Config</h5>
                                            <SettingInput label="Layers" value={settings.TREES_LAYERS} onChange={(v) => handleSettingChange('TREES_LAYERS', v)} min="1" max="15" step="1" icon={Layers} />
                                            <SettingInput label="Density" value={settings.TREES_DENSITY} onChange={(v) => handleSettingChange('TREES_DENSITY', v)} min="0" max="5" step="0.1" icon={Grid} />
                                            <SettingInput label="Size" value={settings.TREES_SIZE} onChange={(v) => handleSettingChange('TREES_SIZE', v)} min="0.5" max="2.0" step="0.1" icon={Maximize} />
                                        </div>

                                        {/* Clouds */}
                                        <div className="bg-bg/50 p-2 rounded border border-border">
                                            <h5 className="text-[10px] font-bold text-primary mb-2 border-b border-border pb-1 flex items-center gap-1"><Cloud size={10} /> Clouds Config</h5>
                                            <SettingInput label="Layers" value={settings.CLOUDS_LAYERS} onChange={(v) => handleSettingChange('CLOUDS_LAYERS', v)} min="1" max="15" step="1" icon={Layers} />
                                            <SettingInput label="Density" value={settings.CLOUDS_DENSITY} onChange={(v) => handleSettingChange('CLOUDS_DENSITY', v)} min="0.1" max="3.0" step="0.1" icon={Grid} />
                                            <SettingInput label="Size" value={settings.CLOUDS_SIZE} onChange={(v) => handleSettingChange('CLOUDS_SIZE', v)} min="0.5" max="1.5" step="0.1" icon={Maximize} />
                                        </div>

                                        {/* Stars & Bushes */}
                                        <div className="bg-bg/50 p-2 rounded border border-border">
                                            <h5 className="text-[10px] font-bold text-primary mb-2 border-b border-border pb-1 flex items-center gap-1"><Star size={10} /> Stars & Bushes</h5>
                                            <SettingInput label="Stars Layers" value={settings.STARS_LAYERS} onChange={(v) => handleSettingChange('STARS_LAYERS', v)} min="1" max="15" step="1" icon={Layers} />
                                            <SettingInput label="Stars Density" value={settings.STARS_DENSITY} onChange={(v) => handleSettingChange('STARS_DENSITY', v)} min="0.1" max="3.0" step="0.1" icon={Grid} />
                                            <div className="h-2" />
                                            <SettingInput label="Bush Layers" value={settings.BUSHES_LAYERS} onChange={(v) => handleSettingChange('BUSHES_LAYERS', v)} min="1" max="10" step="1" icon={Layers} />
                                            <SettingInput label="Bush Density" value={settings.BUSHES_DENSITY} onChange={(v) => handleSettingChange('BUSHES_DENSITY', v)} min="0.1" max="3.0" step="0.1" icon={Grid} />
                                        </div>
                                    </div>
                                </SettingsSection>

                                <SettingsSection title="Physics" icon={Atom}>
                                    <div className="space-y-3 pt-2">
                                        <SettingInput label="Gravity" value={settings.GRAVITY} onChange={(v) => handleSettingChange('GRAVITY', v)} min="0.1" max="2.0" step="0.05" icon={Weight} />
                                        <SettingInput label="Jump Strength" value={settings.JUMP_STRENGTH} onChange={(v) => handleSettingChange('JUMP_STRENGTH', v)} min="-20" max="-5" step="0.5" icon={MoveVertical} />
                                        <SettingInput label="Jump Distance" value={settings.JUMP_DISTANCE} onChange={(v) => handleSettingChange('JUMP_DISTANCE', v)} min="100" max="600" step="10" icon={MoveHorizontal} />
                                        <div className="flex justify-between text-xs text-muted pt-1 opacity-75 border-t border-border mt-2">
                                            <span>Est. Speed</span>
                                            <span className="font-mono">{((settings.JUMP_DISTANCE * settings.GRAVITY) / (2 * Math.abs(settings.JUMP_STRENGTH))).toFixed(1)}</span>
                                        </div>
                                    </div>
                                </SettingsSection>

                                <SettingsSection title="World Dimensions" icon={Ruler}>
                                    <div className="space-y-3 pt-2">
                                        <SettingInput label="Dino W" value={settings.DINO_WIDTH} onChange={(v) => handleSettingChange('DINO_WIDTH', v)} min="20" max="100" step="2" icon={Maximize} />
                                        <SettingInput label="Dino H" value={settings.DINO_HEIGHT} onChange={(v) => handleSettingChange('DINO_HEIGHT', v)} min="20" max="100" step="2" icon={Maximize} />
                                        <SettingInput label="Ground Offset" value={settings.GROUND_OFFSET} onChange={(v) => handleSettingChange('GROUND_OFFSET', v)} min="20" max="150" step="5" icon={ArrowDownToLine} />
                                        <div className="h-1 border-t border-border my-2" />
                                        <SettingInput label="Spawn Interval" value={settings.SPAWN_INTERVAL} onChange={(v) => handleSettingChange('SPAWN_INTERVAL', v)} min="500" max="3000" step="50" icon={Timer} />
                                        <SettingInput label="Obs Width" value={settings.OBSTACLE_WIDTH} onChange={(v) => handleSettingChange('OBSTACLE_WIDTH', v)} min="10" max="50" step="2" icon={Maximize} />
                                        <SettingInput label="Obs Max H" value={settings.OBSTACLE_MAX_HEIGHT} onChange={(v) => handleSettingChange('OBSTACLE_MAX_HEIGHT', v)} min="30" max="100" step="5" icon={Maximize} />
                                    </div>
                                </SettingsSection>
                            </div>
                        </div>
                    )}
                    <div className="spacer-footer-dino" />
                </div>
            </div>
        </div>
    )
}

// --- Helper Components ---

const SettingsSection = ({ title, icon: Icon, children, defaultOpen = false }) => {
    const [isOpen, setIsOpen] = useState(defaultOpen)
    return (
        <div className="border border-border rounded-lg overflow-hidden bg-bg/20">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex justify-between items-center p-2 bg-surface hover:bg-bg/80 transition-colors"
            >
                <div className="flex items-center gap-2">
                    {Icon && <Icon size={14} className="text-primary" />}
                    <span className="text-xs font-bold text-text uppercase tracking-wider">{title}</span>
                </div>
                <ChevronDown size={14} className={`text-muted transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && (
                <div className="p-2 border-t border-border animate-fade-in">
                    {children}
                </div>
            )}
        </div>
    )
}

const SettingInput = ({ label, value, onChange, min, max, step, icon: Icon }) => (
    <div>
        <div className="flex justify-between text-xs text-muted mb-1">
            <div className="flex items-center gap-1.5">
                {Icon && <Icon size={12} className="text-secondary/80" />}
                <span>{label}</span>
            </div>
            <span className="font-mono text-primary">{value}</span>
        </div>
        <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(parseFloat(e.target.value))}
            className="w-full accent-primary h-1.5 bg-surface border border-border rounded-lg appearance-none cursor-pointer"
        />
    </div>
)

const SettingToggle = ({ label, value, onChange, icon: Icon }) => (
    <div className="flex justify-between items-center py-0.5">
        <div className="flex items-center gap-1.5">
            {Icon && <Icon size={12} className="text-secondary/80" />}
            <span className="text-xs text-muted">{label}</span>
        </div>
        <button
            onClick={() => onChange(!value)}
            className={`w-7 h-3.5 rounded-full relative transition-colors ${value ? 'bg-primary' : 'bg-border'}`}
        >
            <div className={`w-2.5 h-2.5 bg-white rounded-full absolute top-0.5 transition-transform ${value ? 'translate-x-3.5' : 'translate-x-0.5'}`} />
        </button>
    </div>
)

const SettingSelect = ({ label, value, options, onChange }) => (
    <div className="flex justify-between items-center py-1 gap-2">
        <span className="text-xs text-muted">{label}</span>
        <div className="w-32">
            <CustomSelect
                value={value}
                onChange={onChange}
                options={options}
            />
        </div>
    </div>
)