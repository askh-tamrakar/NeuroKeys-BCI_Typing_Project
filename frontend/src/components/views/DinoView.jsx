import React, { useState, useEffect, useRef } from 'react'
import '../../styles/views/DinoView.css'
import CameraPanel from '../ui/CameraPanel'
import CustomSelect from '../ui/CustomSelect'
import Counter from '../ui/Counter'
import CountUp from '../ui/CountUp'

export default function DinoView({ wsData, wsEvent, isPaused }) {
    // Game state
    const [gameState, setGameState] = useState('ready') // ready, playing, paused, gameOver
    const [score, setScore] = useState(0)
    const [highScore, setHighScore] = useState(
        parseInt(localStorage.getItem('dino_highscore')) || 0
    )
    const [eyeState, setEyeState] = useState('open') // open, blink, double-blink
    const [showSettings, setShowSettings] = useState(false)

    // Game settings (easy mode default)
    const DEFAULT_SETTINGS = {
        GRAVITY: 0.4,
        JUMP_STRENGTH: -10,
        GROUND_OFFSET: 60,
        DINO_WIDTH: 62,
        DINO_HEIGHT: 66,
        OBSTACLE_WIDTH: 28,
        OBSTACLE_MIN_HEIGHT: 56,
        OBSTACLE_MAX_HEIGHT: 84,
        GAME_SPEED: 1.8,
        SPAWN_INTERVAL: 1150,
        CANVAS_WIDTH: 800,
        CANVAS_HEIGHT: 376,
        CYCLE_DURATION: 100,
        JUMP_DISTANCE: 150,
        ENABLE_TREES: true,
        ENABLE_MANUAL_CONTROLS: true,
        CONTROL_CHANNEL: 'ch3',
        OBSTACLE_BONUS_FACTOR: 0.025,
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
    const logEvent = (msg) => {
        const time = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
        setEventLogs(prev => [`[${time}] ${msg}`, ...prev].slice(0, 50))
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
    const handleEOGBlink = () => {
        const now = Date.now()
        const timeSinceLastPress = now - blinkPressTimeRef.current

        if (timeSinceLastPress < 400 && timeSinceLastPress > 75) {
            handleDoublePress()
        } else {
            handleSinglePress()
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

    // --- Worker Bridge ---
    const workerRef = useRef(null)
    const [canvasResetKey, setCanvasResetKey] = useState(0)

    // Initialize Worker
    useEffect(() => {
        if (!canvasRef.current) return

        let worker = null
        try {
            // Create worker
            worker = new Worker(new URL('../../workers/game.worker.js', import.meta.url))
            workerRef.current = worker

            // Get OffscreenCanvas
            const offscreen = canvasRef.current.transferControlToOffscreen()

            // Get theme colors
            const styles = getComputedStyle(document.documentElement)
            const theme = {
                bg: styles.getPropertyValue('--bg').trim(),
                surface: styles.getPropertyValue('--surface').trim(),
                text: styles.getPropertyValue('--text').trim(),
                primary: styles.getPropertyValue('--primary').trim(),
                border: styles.getPropertyValue('--border').trim(),
                muted: styles.getPropertyValue('--muted').trim(),
                accent: styles.getPropertyValue('--accent').trim()
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
                            bushSprites: bushSprites // Pass array
                        }
                    }, [offscreen, ...bushSprites]); // Transfer all bitmaps
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
                            theme: theme
                        }
                    }, [offscreen]);
                });

            // Listen to worker
            worker.onmessage = (e) => {
                const { type, score, highScore: newHigh } = e.data
                if (type === 'GAME_OVER') {
                    setGameState('gameOver')
                    if (score !== undefined) scoreRef.current = score
                } else if (type === 'HIGHSCORE_UPDATE') {
                    setHighScore(newHigh)
                    localStorage.setItem('dino_highscore', newHigh.toString())
                } else if (type === 'SCORE_UPDATE') {
                    setScore(score)
                }
            }
        } catch (err) {
            console.warn("Canvas transfer failed, retrying with fresh DOM node...", err)
            setCanvasResetKey(prev => prev + 1)
        }

        return () => {
            if (worker) worker.terminate()
        }
    }, [canvasResetKey])

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
    const handleSinglePress = () => {
        logEvent("🦘 Jump Triggered")
        triggerSingleBlink()

        if (workerRef.current) {
            console.log("[DinoView] Sending 'jump' to worker. Ref:", workerRef.current)
            workerRef.current.postMessage({ type: 'INPUT', payload: { action: 'jump' } })
        } else {
            console.warn("[DinoView] Worker ref is missing!")
        }

        // Optimistic state update for UI status
        if (gameStateRef.current === 'ready' || gameStateRef.current === 'gameOver') {
            setGameState('playing')
        }
    }

    const handleDoublePress = () => {
        logEvent("⏯️ Pause/Resume Triggered")
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
                    handleEOGBlink() // Use the same unified logic for consistency
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
                                <span className="status-dot"></span>
                                EOG Dino Game
                            </h2>
                            <button
                                onClick={() => setShowSettings(!showSettings)}
                                className={`tuner-button ${showSettings ? 'active' : 'inactive'}`}
                            >
                                ⚙️ Tuner
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
                                            <span className="stat-label">Status</span>
                                            <div className={`stat-value-status ${gameState === 'playing' ? 'playing' : 'default'}`}>
                                                {gameState}
                                            </div>
                                        </div>
                                        <div className="stat-block stat-block-start">
                                            <span className="stat-label">Score</span>
                                            <Counter value={Math.floor(score / 10)} fontSize={48} places={[10000, 1000, 100, 10, 1]} className="stat-counter-large" />
                                        </div>
                                    </div>

                                    {/* Right Side: Best & Sensor */}
                                    <div className="stat-group-right">
                                        <div className="stat-block stat-block-end">
                                            <span className="stat-label">Best</span>
                                            <CountUp
                                                from={0}
                                                to={Math.floor(highScore / 10)}
                                                duration={2}
                                                separator=","
                                                className="text-text font-mono font-bold text-3xl leading-none"
                                            />
                                        </div>
                                        <div className="stat-block stat-block-end mb-1">
                                            <span className="stat-label">Sensor</span>
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
                <div className="game-sidebar">
                    {/* Camera Panel */}
                    <CameraPanel />

                    {/* Eye Controls Panel */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-4">
                        <h3 className="text-sm font-bold text-text uppercase tracking-wider mb-3">Controls</h3>
                        <div className="space-y-2 text-sm text-text">
                            <div className="flex justify-between">
                                <span className="text-muted">Blink ONCE</span>
                                <span className="font-bold text-primary">Jump</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-muted">Blink TWICE</span>
                                <span className="font-bold text-primary">Pause / Resume</span>
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
                                <span className="text-muted font-medium uppercase tracking-wider">Input Status</span>
                                <span className={`font-bold ${wsData ? 'text-green-500' : 'text-red-500'}`}>
                                    {wsData ? 'ACTIVE' : 'OFFLINE'}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Event Log Panel */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-4 ">
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="text-sm font-bold text-text uppercase tracking-wider">Event Log</h3>
                            <button
                                onClick={() => setEventLogs([])}
                                className="text-xs text-muted hover:text-red-400"
                            >
                                Clear
                            </button>
                        </div>
                        <div className="bg-bg/50 rounded-lg p-2 h-32 overflow-y-auto font-mono text-xs space-y-1 border border-border/50 scrollbar-thin scrollbar-thumb-border hover:scrollbar-thumb-primary/50 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
                            {eventLogs.length === 0 ? (
                                <div className="text-muted italic text-center py-4">No events yet...</div>
                            ) : (
                                eventLogs.map((log, i) => (
                                    <div key={i} className="text-muted hover:text-text transition-colors border-b border-border/20 last:border-0 pb-0.5">
                                        {log}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Settings Panel (Moved here) */}
                    {showSettings && (
                        <div className="card bg-surface border border-border shadow-card rounded-2xl p-4 animate-fade-in">
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="text-sm font-bold text-text uppercase tracking-wider">Game Constants</h3>
                                <div className="flex gap-2 items-center">
                                    {savedMessage && <span className="text-xs text-green-500 font-bold animate-fade-in">{savedMessage}</span>}
                                    <button
                                        onClick={handleSaveSettings}
                                        className="text-xs bg-primary text-bg px-2 py-1 rounded font-bold hover:opacity-90"
                                    >
                                        Save
                                    </button>
                                    <button
                                        onClick={() => setSettings(DEFAULT_SETTINGS)}
                                        className="text-xs text-red-400 hover:text-red-300 underline"
                                    >
                                        Reset Config
                                    </button>
                                </div>
                            </div>

                            <div className="mb-4 bg-bg rounded p-2 border border-border">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="text-muted">Highscore: {Math.floor(highScore / 10)}</span>
                                    <button
                                        onClick={() => {
                                            localStorage.setItem('dino_highscore', '0')
                                            setHighScore(0)
                                            setSavedMessage('Score Reset!')
                                            setTimeout(() => setSavedMessage(''), 2000)
                                        }}
                                        className="text-red-400 hover:text-red-300 font-bold uppercase tracking-wide text-[10px] border border-red-900/50 px-2 py-0.5 rounded bg-red-900/10"
                                    >
                                        Reset Score
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-6">
                                <div className="space-y-3">
                                    <h4 className="text-xs font-bold text-primary border-b border-border pb-1">Controls</h4>

                                    <SettingToggle label="Manual Controls (Space)" value={settings.ENABLE_MANUAL_CONTROLS} onChange={(v) => handleSettingChange('ENABLE_MANUAL_CONTROLS', v)} />

                                    <h4 className="text-xs font-bold text-primary border-b border-border pb-1 mt-4">Physics</h4>
                                    <SettingInput label="Gravity" value={settings.GRAVITY} onChange={(v) => handleSettingChange('GRAVITY', v)} min="0.1" max="2.0" step="0.05" />
                                    <SettingInput label="Jump Strength (Y)" value={settings.JUMP_STRENGTH} onChange={(v) => handleSettingChange('JUMP_STRENGTH', v)} min="-20" max="-5" step="0.5" />
                                    <SettingInput label="Jump Distance (X)" value={settings.JUMP_DISTANCE} onChange={(v) => handleSettingChange('JUMP_DISTANCE', v)} min="100" max="600" step="10" />
                                    {/* Derived Speed Display */}
                                    <div className="flex justify-between text-xs text-muted pt-2 opacity-75">
                                        <span>Derived Game Speed</span>
                                        <span>{((settings.JUMP_DISTANCE * settings.GRAVITY) / (2 * Math.abs(settings.JUMP_STRENGTH))).toFixed(1)}</span>
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    <h4 className="text-xs font-bold text-primary border-b border-border pb-1">Dimensions</h4>
                                    <SettingInput label="Dino Width" value={settings.DINO_WIDTH} onChange={(v) => handleSettingChange('DINO_WIDTH', v)} min="20" max="100" step="2" />
                                    <SettingInput label="Dino Height" value={settings.DINO_HEIGHT} onChange={(v) => handleSettingChange('DINO_HEIGHT', v)} min="20" max="100" step="2" />
                                    <SettingInput label="Ground Offset" value={settings.GROUND_OFFSET} onChange={(v) => handleSettingChange('GROUND_OFFSET', v)} min="20" max="150" step="5" />
                                </div>
                                <div className="space-y-3">
                                    <h4 className="text-xs font-bold text-primary border-b border-border pb-1">Obstacles</h4>
                                    <SettingInput label="Spawn Interval" value={settings.SPAWN_INTERVAL} onChange={(v) => handleSettingChange('SPAWN_INTERVAL', v)} min="500" max="3000" step="50" />
                                    <SettingInput label="Obs Width" value={settings.OBSTACLE_WIDTH} onChange={(v) => handleSettingChange('OBSTACLE_WIDTH', v)} min="10" max="50" step="2" />
                                    <SettingInput label="Obs Max Height" value={settings.OBSTACLE_MAX_HEIGHT} onChange={(v) => handleSettingChange('OBSTACLE_MAX_HEIGHT', v)} min="30" max="100" step="5" />
                                </div>
                                <div className="space-y-3">
                                    <h4 className="text-xs font-bold text-primary border-b border-border pb-1">Environment</h4>
                                    <SettingToggle label="Enable Trees" value={settings.ENABLE_TREES} onChange={(v) => handleSettingChange('ENABLE_TREES', v)} />
                                    <SettingInput label="Obstacle Bonus" value={settings.OBSTACLE_BONUS_FACTOR} onChange={(v) => handleSettingChange('OBSTACLE_BONUS_FACTOR', v)} min="0" max="2.0" step="0.005" />
                                    <SettingInput label="Day Cycle (s)" value={settings.CYCLE_DURATION} onChange={(v) => handleSettingChange('CYCLE_DURATION', v)} min="10" max="300" step="5" />
                                </div>
                            </div>
                        </div>
                    )}


                </div>
            </div>
        </div>
    )
}

// Helper outside component to avoid remounting on render (fixes slider focus)
const SettingInput = ({ label, value, onChange, min, max, step }) => (
    <div className="flex flex-col gap-1">
        <div className="flex justify-between text-xs text-muted">
            <span>{label}</span>
            <span>{value}</span>
        </div>
        <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(parseFloat(e.target.value))}
            className="w-full accent-primary h-2 bg-surface border border-border rounded-lg appearance-none cursor-pointer"
        />
    </div>
)

const SettingToggle = ({ label, value, onChange }) => (
    <div className="flex justify-between items-center py-1">
        <span className="text-xs text-muted">{label}</span>
        <button
            onClick={() => onChange(!value)}
            className={`w-8 h-4 rounded-full relative transition-colors ${value ? 'bg-primary' : 'bg-border'}`}
        >
            <div className={`w-3 h-3 bg-white rounded-full absolute top-0.5 transition-transform ${value ? 'translate-x-4' : 'translate-x-1'}`} />
        </button>
    </div>
)

const SettingSelect = ({ label, value, options, onChange }) => (
    <div className="flex justify-between items-center py-1 gap-2">
        <span className="text-xs text-muted">{label}</span>
        <div className="w-40">
            <CustomSelect
                value={value}
                onChange={onChange}
                options={options}
            />
        </div>
    </div>
)