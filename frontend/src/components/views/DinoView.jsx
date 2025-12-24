import React, { useState, useEffect, useRef } from 'react'
import '../../styles/DinoView.css'

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
        DINO_WIDTH: 44,
        DINO_HEIGHT: 47,
        OBSTACLE_WIDTH: 20,
        OBSTACLE_MIN_HEIGHT: 40,
        OBSTACLE_MAX_HEIGHT: 60,
        GAME_SPEED: 1.8,
        SPAWN_INTERVAL: 1150,
        CANVAS_WIDTH: 800,
        CANVAS_HEIGHT: 376,
        CYCLE_DURATION: 100,
        JUMP_DISTANCE: 150,
    }

    const [settings, setSettings] = useState(() => {
        const saved = localStorage.getItem('dino_settings')
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
    const canvasRef = useRef(null)
    const animationRef = useRef(null)
    const gameStateRef = useRef('ready')
    const dinoYRef = useRef(0)
    const velocityRef = useRef(0)
    const obstaclesRef = useRef([])
    const scoreRef = useRef(0)
    const lastSpawnRef = useRef(0)
    const blinkPressTimeRef = useRef(0)
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

    // Listen for WebSocket Events (Blinks)
    useEffect(() => {
        if (!wsEvent) return;

        if (wsEvent.event === 'BLINK') {
            logEvent("👁️ Blink Signal Recv")
            console.log("🦖 Dino: Blink Signal Received via Logic Pipeline!");
            handleEOGBlink();
        }
    }, [wsEvent]);

    // Handle EOG blink detection
    const handleEOGBlink = () => {
        const now = Date.now()
        const timeSinceLastPress = now - blinkPressTimeRef.current

        if ( 75 < timeSinceLastPress && timeSinceLastPress < 400) {
            handleDoublePress()
        } else {
            handleSinglePress()
        }
        
        // Log raw interval for debugging
        logEvent(`⏱️ Interval: ${timeSinceLastPress}ms`)

        console.log(" timeSinceLastPress ", timeSinceLastPress);
        blinkPressTimeRef.current = now
    }

    // Keyboard controls (hidden from UI but still functional for testing)
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.code === 'Space' || e.key === ' ') {
                e.preventDefault()
                const now = Date.now()
                const timeSinceLastPress = now - blinkPressTimeRef.current

                if (timeSinceLastPress < 500) {
                    handleDoublePress()
                } else {
                    handleSinglePress()
                }
                blinkPressTimeRef.current = now
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [])

    // Single press - Jump
    const handleSinglePress = () => {
        logEvent("🦘 Jump Triggered")
        // Eye blink animation
        triggerSingleBlink()

        const currentState = gameStateRef.current
        const { JUMP_STRENGTH } = settingsRef.current

        if (currentState === 'ready') {
            setGameState('playing')
            setScore(0)
            scoreRef.current = 0
            dinoYRef.current = 0
            velocityRef.current = 0
            obstaclesRef.current = []
            velocityRef.current = 0
            obstaclesRef.current = []
            lastSpawnRef.current = Date.now()
            distanceRef.current = 0
            // Don't reset gameTimeRef to allow day/night to continue or we could reset it. 
            // Let's keep it continuous or reset. Continuous is fine.
        } else if (currentState === 'playing' && Math.abs(dinoYRef.current) < 0.1) {
            // Jump uses direct Y-velocity from settings
            const { JUMP_STRENGTH } = settingsRef.current
            velocityRef.current = JUMP_STRENGTH
        } else if (currentState === 'gameOver') {
            // Restart game
            setGameState('playing')
            setScore(0)
            scoreRef.current = 0
            dinoYRef.current = 0
            velocityRef.current = 0
            obstaclesRef.current = []
            obstaclesRef.current = []
            lastSpawnRef.current = Date.now()
            distanceRef.current = 0
        }
    }

    // Double press - Pause/Resume
    const handleDoublePress = () => {
        logEvent("⏯️ Pause/Resume Triggered")
        // Double eye blink animation
        triggerDoubleBlink()

        const currentState = gameStateRef.current
        if (currentState === 'playing') {
            setGameState('paused')
        } else if (currentState === 'paused') {
            setGameState('playing')
        }
    }

    // Eye blink animations 
    // Single blink
    const triggerSingleBlink = () => {
        setEyeState('blink')
        if (leftEyeRef.current && rightEyeRef.current) {
            leftEyeRef.current.classList.remove('blink', 'double-blink')
            rightEyeRef.current.classList.remove('blink', 'double-blink')
            void leftEyeRef.current.offsetWidth // Force reflow
            leftEyeRef.current.classList.add('blink')
            rightEyeRef.current.classList.add('blink')
        }
        setTimeout(() => {
            setEyeState('open')
            if (leftEyeRef.current && rightEyeRef.current) {
                leftEyeRef.current.classList.remove('blink')
                rightEyeRef.current.classList.remove('blink')
            }
        }, 300)
    }

    // Double blink
    const triggerDoubleBlink = () => {
        setEyeState('double-blink')
        if (leftEyeRef.current && rightEyeRef.current) {
            leftEyeRef.current.classList.remove('blink', 'double-blink')
            rightEyeRef.current.classList.remove('blink', 'double-blink')
            void leftEyeRef.current.offsetWidth // Force reflow
            leftEyeRef.current.classList.add('double-blink')
            rightEyeRef.current.classList.add('double-blink')
        }
        setTimeout(() => {
            setEyeState('open')
            if (leftEyeRef.current && rightEyeRef.current) {
                leftEyeRef.current.classList.remove('double-blink')
                rightEyeRef.current.classList.remove('double-blink')
            }
        }, 600)
    }

    // Draw dinosaur
    const drawDino = (ctx, x, y, color, eyeColor) => {
        const { DINO_WIDTH, DINO_HEIGHT } = settingsRef.current

        ctx.save()
        ctx.fillStyle = color

        // Scale factor relative to default size
        const scaleX = DINO_WIDTH / 44
        const scaleY = DINO_HEIGHT / 47

        // Helper to scale coordinates (Rounded for crisp pixel art)
        const sX = (v) => Math.floor(x + (v * scaleX))
        const sY = (v) => Math.floor(y + (v * scaleY))
        const sW = (v) => Math.floor(v * scaleX)
        const sH = (v) => Math.floor(v * scaleY)

        // Note: Using a simplified scaler for drawing to match custom dimensions 
        // Logic below uses explicit offsets which might look stretched if aspect ratio changes heavily
        // For now, simply scaling the draw commands

        // Body
        ctx.fillRect(Math.floor(x + 6 * scaleX), Math.floor(y + 20 * scaleY), Math.ceil(25 * scaleX), Math.ceil(17 * scaleY))

        // Head
        ctx.fillRect(Math.floor(x + 31 * scaleX), Math.floor(y + 14 * scaleY), Math.ceil(13 * scaleX), Math.ceil(13 * scaleY))

        // Neck
        ctx.fillRect(Math.floor(x + 25 * scaleX), Math.floor(y + 17 * scaleY), Math.ceil(6 * scaleX), Math.ceil(10 * scaleY))

        // Tail
        ctx.beginPath()
        ctx.moveTo(Math.floor(x + 6 * scaleX), Math.floor(y + 25 * scaleY))
        ctx.lineTo(Math.floor(x), Math.floor(y + 32 * scaleY))
        ctx.lineTo(Math.floor(x + 6 * scaleX), Math.floor(y + 32 * scaleY))
        ctx.fill()

        // Eye
        ctx.fillStyle = eyeColor
        if (eyeState === 'open') {
            ctx.fillRect(Math.floor(x + 36 * scaleX), Math.floor(y + 18 * scaleY), Math.ceil(2 * scaleX), Math.ceil(2 * scaleY))
        } else {
            ctx.fillRect(Math.floor(x + 36 * scaleX), Math.floor(y + 19 * scaleY), Math.ceil(2 * scaleX), Math.ceil(1 * scaleY))
        }

        // Legs (animated)
        ctx.fillStyle = color
        const legOffset = Math.floor(Date.now() / 100) % 2 === 0 ? 0 : 2

        // Front leg
        ctx.fillRect(Math.floor(x + 24 * scaleX), Math.floor(y + 37 * scaleY), Math.ceil(4 * scaleX), Math.ceil((10 - legOffset) * scaleY))

        // Back leg
        ctx.fillRect(Math.floor(x + 14 * scaleX), Math.floor(y + 37 * scaleY), Math.ceil(4 * scaleX), Math.ceil((10 + legOffset) * scaleY))

        // Arms
        ctx.fillRect(Math.floor(x + 28 * scaleX), Math.floor(y + 24 * scaleY), Math.ceil(2 * scaleX), Math.ceil(6 * scaleY))

        ctx.restore()
    }

    // Draw cactus
    const drawCactus = (ctx, x, y, width, height, color, borderColor) => {
        ctx.save()
        ctx.fillStyle = color
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2

        // Main trunk
        const trunkWidth = Math.floor(width * 0.6)
        const trunkX = Math.floor(x + (width - trunkWidth) / 2)
        const trunkH = Math.floor(height)
        const _y = Math.floor(y)

        ctx.fillRect(trunkX, _y, trunkWidth, trunkH)
        ctx.strokeRect(trunkX, _y, trunkWidth, trunkH)

        // Left arm
        const armHeight = Math.floor(height * 0.4)
        const armWidth = Math.floor(width * 0.3)
        const leftArmX = Math.floor(trunkX - armWidth)
        const leftArmY = Math.floor(y + height * 0.3)
        const armConnW = Math.floor(trunkWidth * 0.3)

        ctx.fillRect(leftArmX, leftArmY, armWidth, armHeight)
        ctx.strokeRect(leftArmX, leftArmY, armWidth, armHeight)
        ctx.fillRect(leftArmX + armWidth, leftArmY, armConnW, armWidth)
        ctx.strokeRect(leftArmX + armWidth, leftArmY, armConnW, armWidth)

        // Right arm
        const rightArmX = Math.floor(trunkX + trunkWidth)
        const rightArmY = Math.floor(y + height * 0.5)
        const rightArmH = Math.floor(armHeight * 0.8)

        ctx.fillRect(rightArmX, rightArmY, armWidth, rightArmH)
        ctx.strokeRect(rightArmX, rightArmY, armWidth, rightArmH)
        ctx.fillRect(Math.floor(trunkX + trunkWidth * 0.7), rightArmY, armConnW, armWidth)
        ctx.strokeRect(Math.floor(trunkX + trunkWidth * 0.7), rightArmY, armConnW, armWidth)

        ctx.restore()
    }

    // --- Visual Helpers ---

    // Simplified to just return theme background since we want strict theme colors now
    const getSkyColor = (time, themeBg) => {
        return themeBg
    }



    const drawPixelCircle = (ctx, cx, cy, radius, color) => {
        ctx.fillStyle = color
        const r = Math.floor(radius)
        const _cx = Math.floor(cx)
        const _cy = Math.floor(cy)
        // Simple circle approximation using blocks
        // We will draw it row by row
        for (let y = -r; y <= r; y++) {
            for (let x = -r; x <= r; x++) {
                if (x * x + y * y <= r * r) {
                    // Make it blocky: round to nearest 2 pixels or just draw 1x1 rect depending on scale
                    // To make it look "pixel art", we can just fill rect
                    ctx.fillRect(_cx + x, _cy + y, 1, 1)
                }
            }
        }
    }

    // Helper for "big pixel" drawing (e.g. 4x4 blocks)
    const drawBlockyCircle = (ctx, cx, cy, size, color, pixelSize = 4) => {
        ctx.fillStyle = color
        const radius = Math.floor(size / 2)

        for (let y = -radius; y <= radius; y++) {
            for (let x = -radius; x <= radius; x++) {
                // Determine if this block is inside the circle
                if (x * x + y * y <= radius * radius) {
                    ctx.fillRect(Math.floor(cx + x * pixelSize), Math.floor(cy + y * pixelSize), pixelSize, pixelSize)
                }
            }
        }
    }

    const drawSky = (ctx, width, height, time, primaryColor, textColor, bgColor, surfaceColor, borderColor, mutedColor) => {
        // Background
        ctx.fillStyle = getSkyColor(time, bgColor)
        ctx.fillRect(0, 0, width, height)

        const centerX = width / 2
        const centerY = height + 100
        const radius = width * 0.6

        // Sun
        if (time > 0.05 && time < 0.65) {
            const sunAngle = ((time - 0.1) / 0.5) * Math.PI // 0 to PI
            const sunX = centerX - Math.cos(sunAngle) * radius
            const sunY = centerY - Math.sin(sunAngle) * radius * 0.9

            // Draw Pixel Art Sun
            // Core
            drawBlockyCircle(ctx, sunX, sunY, 14, primaryColor, 4)
            // Rays (simple blocks around)
            ctx.fillStyle = primaryColor
            // ctx.fillRect(sunX - 2, sunY - 40, 4, 10) // etc... simplify for now
        }

        // Moon
        if (time > 0.55 || time < 0.15) {
            let moonTime = time - 0.6
            if (moonTime < 0) moonTime += 1
            const moonAngle = (moonTime / 0.5) * Math.PI
            const moonX = centerX - Math.cos(moonAngle) * radius
            const moonY = centerY - Math.sin(moonAngle) * radius * 0.9

            // Draw Pixel Art Moon (Crescent-ish or just square-ish circle)
            drawBlockyCircle(ctx, moonX, moonY, 12, textColor, 4)

            // Crater
            ctx.fillStyle = bgColor
            ctx.fillRect(moonX - 12, moonY - 8, 8, 8)
            ctx.fillRect(moonX + 4, moonY + 8, 4, 4)
        }

        // Stars (Night only)
        if (time > 0.6 || time < 0.1) {
            const baseOpacity = (time > 0.7 || time < 0.05) ? 1 : 0.5
            ctx.fillStyle = mutedColor // Stars are subtle now
            starsRef.current.forEach(star => {
                const flicker = Math.sin(Date.now() / 200 + star.blinkOffset) * 0.3 + 0.7
                if (Math.random() > 0.1) { // Slight noise
                    ctx.globalAlpha = baseOpacity * flicker
                    const s = Math.ceil(star.size) // Make sure it's integer for crisp edges
                    // Star shape: Cross or Dot
                    if (s > 2) {
                        ctx.fillRect(star.x - s, star.y, s * 3, s)
                        ctx.fillRect(star.x, star.y - s, s, s * 3)
                    } else {
                        ctx.fillRect(star.x, star.y, s * 2, s * 2)
                    }
                }
            })
            ctx.globalAlpha = 1.0
        }

        // Clouds (Always visible but tinted)
        // Use mutedColor for clouds so they are distinct but background
        ctx.fillStyle = mutedColor
        ctx.globalAlpha = 0.4 // Subtle

        cloudsRef.current.forEach(cloud => {
            // Pixel Art Cloud: 3 overlapping rectangles
            const w = Math.floor(cloud.width)
            const h = Math.floor(w * 0.4)
            const cx = Math.floor(cloud.x)
            const cy = Math.floor(cloud.y)

            // Base
            ctx.fillRect(cx, cy, w, h)
            // Top hump
            ctx.fillRect(Math.floor(cx + w * 0.2), Math.floor(cy - h * 0.6), Math.ceil(w * 0.4), Math.ceil(h * 0.8))
            // Smaller hump
            ctx.fillRect(Math.floor(cx + w * 0.5), Math.floor(cy - h * 0.4), Math.ceil(w * 0.3), Math.ceil(h * 0.6))

            // Update cloud pos
            cloud.x -= cloud.speed
            if (cloud.x + w < 0) {
                cloud.x = width + Math.random() * 100
                cloud.y = Math.random() * 100 + 20
            }
        })
        ctx.globalAlpha = 1.0
    }

    const drawTrees = (ctx, width, groundY, mutedColor) => {
        ctx.fillStyle = mutedColor
        // Trees are background, so maybe 0.7 alpha?
        ctx.globalAlpha = 0.5
        treesRef.current.forEach(tree => {
            const tx = Math.floor(tree.x)
            const ty = Math.floor(groundY - tree.height)
            const tw = Math.floor(tree.width)
            const th = Math.floor(tree.height)

            if (tx + tw > 0 && tx < width) {
                // Trunk
                const trunkW = Math.max(4, Math.floor(tw * 0.3))
                ctx.fillRect(Math.floor(tx + (tw - trunkW) / 2), ty + Math.floor(th * 0.5), trunkW, Math.floor(th * 0.5))

                // Foliage
                if (tree.type === 'pine') {
                    // Triangle-ish (stepped)
                    ctx.fillRect(tx, ty + Math.floor(th * 0.2), tw, Math.floor(th * 0.3))
                    ctx.fillRect(Math.floor(tx + tw * 0.1), ty, Math.ceil(tw * 0.8), Math.floor(th * 0.4))
                } else {
                    // Round-ish
                    ctx.fillRect(tx, ty, tw, Math.floor(th * 0.6))
                    ctx.fillRect(Math.floor(tx - tw * 0.2), ty + Math.floor(th * 0.1), Math.ceil(tw * 1.4), Math.floor(th * 0.4))
                }
            }
        })
        ctx.globalAlpha = 1.0
    }

    const drawTerrain = (ctx, width, height, groundY, surfaceColor, borderColor, mutedColor) => {
        // Draw below ground area
        const groundHeight = height - groundY

        ctx.fillStyle = surfaceColor // Use surface color for ground body
        ctx.fillRect(0, Math.floor(groundY), width, Math.floor(groundHeight))

        // Top grass/dirt line
        ctx.fillStyle = borderColor
        ctx.fillRect(0, Math.floor(groundY), width, 10)

        // Random stone speckles pattern (simple static)
        ctx.fillStyle = mutedColor // Speckles are muted, not border color (too harsh)
        // Just draw some deterministic noise if we wanted, but static random rects are cheaper
        // For scrolling effect, we need an offset.
        // Let's rely on a global offset or simply texture pattern.
        // Since we don't have a camera x scroll variable for terrain texturing, we can just make it static or subtle.
        // Let's make it static for now as requested "static" but wait, user said "make the apear below the Eye Blink Tracker... static".
        // He said "add terrain". Let's add some static variation.

        // We will make 3 layers of "stones" that technically don't scroll with dino (since dino moves in place),
        // BUT the obstacles move lefter. The terrain should technically move left too if we want realism.
        // But the user request implies just "terrain below ground". 
        // We can use a simple shifting pattern based on time if we want.
        // Dino game usually has static ground texture that scrolls.
        // Let's simulate scrolling texture using Date.now() or a ref for distance.

        // We actually map obstacle speed. Let's reuse that.
        // We don't have a 'distance traveled' ref easily accessible here but we can approximate with time * speed.
        // Actually, we can just use a simple scrolling offset ref if we want perfect sync.
        // For this version, let's keep it static-ish or simple repeating pattern.

        // Let's create a scrolling pattern using distanceRef
        const offset = distanceRef.current % 100

        ctx.save()
        ctx.beginPath()
        for (let i = -100; i < width + 100; i += 50) {
            ctx.rect(Math.floor(i - offset + 10), Math.floor(groundY + 15), 10, 8)
            ctx.rect(Math.floor(i - offset + 35), Math.floor(groundY + 30), 6, 6)
        }
        ctx.fill()
        ctx.restore()
    }
    // Game loop
    useEffect(() => {
        let lastTime = Date.now()



        const gameLoop = () => {
            const now = Date.now()
            const deltaTime = now - lastTime
            lastTime = now

            const currentState = gameStateRef.current
            const currentSettings = settingsRef.current

            // Destructure settings
            const {
                GRAVITY, JUMP_STRENGTH, JUMP_DISTANCE, SPAWN_INTERVAL,
                OBSTACLE_WIDTH, OBSTACLE_MIN_HEIGHT, OBSTACLE_MAX_HEIGHT,
                GROUND_OFFSET, CANVAS_WIDTH, CANVAS_HEIGHT,
                DINO_WIDTH, DINO_HEIGHT
            } = currentSettings

            // Derive GAME_SPEED to satisfy the Parabolic Path defined by Strength (Y) and Distance (X)
            // Range d = (2 * vx * vy) / g  =>  vx = (d * g) / (2 * vy)
            // Ensure divisor is non-zero
            const vy = Math.abs(JUMP_STRENGTH)
            const GAME_SPEED = vy > 0 ? (JUMP_DISTANCE * GRAVITY) / (2 * vy) : 5

            if (currentState === 'playing') {
                // Update dino physics (dinoYRef is distance above ground, 0 = on ground)
                const oldVelocity = velocityRef.current
                const oldY = dinoYRef.current

                velocityRef.current += GRAVITY
                dinoYRef.current += velocityRef.current

                // Keep dino on or above ground (dinoYRef should not go below 0)
                if (dinoYRef.current >= 0) {
                    if (oldY < 0) {
                        console.log('🛬 LANDING: Y went from', oldY.toFixed(2), 'to', dinoYRef.current.toFixed(2), '→ reset to 0')
                    }
                    dinoYRef.current = 0
                    velocityRef.current = 0
                }

                // Update obstacles
                obstaclesRef.current = obstaclesRef.current
                    .map((o) => ({ ...o, x: o.x - GAME_SPEED }))
                    .filter((o) => o.x > - OBSTACLE_WIDTH - 20)

                // Spawn new obstacle
                if (now - lastSpawnRef.current > SPAWN_INTERVAL) {
                    lastSpawnRef.current = now
                    const height = OBSTACLE_MIN_HEIGHT + Math.random() * (OBSTACLE_MAX_HEIGHT - OBSTACLE_MIN_HEIGHT)
                    obstaclesRef.current.push({
                        x: CANVAS_WIDTH,
                        y: 0, // obstacles are on ground
                        width: OBSTACLE_WIDTH + Math.random() * 10,
                        height: height,
                    })
                }

                // Update score
                scoreRef.current += 1
                setScore(scoreRef.current)

                // Collision detection (more forgiving hitbox)
                const groundY = CANVAS_HEIGHT - GROUND_OFFSET
                const dinoX = 75
                const dinoLeft = dinoX + 10
                const dinoRight = dinoX + DINO_WIDTH - 10
                const dinoTop = groundY - DINO_HEIGHT - dinoYRef.current + 5
                const dinoBottom = groundY - dinoYRef.current - 5

                for (const obs of obstaclesRef.current) {
                    const obsLeft = obs.x + 5
                    const obsRight = obs.x + obs.width - 5
                    const obsTop = groundY - obs.height
                    const obsBottom = groundY

                    if (
                        dinoRight > obsLeft &&
                        dinoLeft < obsRight &&
                        dinoBottom > obsTop &&
                        dinoTop < obsBottom
                    ) {
                        // Collision detected
                        setGameState('gameOver')
                        // Game loop will stop updating time, so time stops
                        if (scoreRef.current > highScore) {
                            setHighScore(scoreRef.current)
                            localStorage.setItem('dino_highscore', scoreRef.current.toString())
                        }
                        break
                    }
                }

                // Update distance for parallax
                distanceRef.current += GAME_SPEED

                // Update trees (Parallax with depth)
                treesRef.current.forEach(tree => {
                    tree.x -= GAME_SPEED * tree.speedFactor
                    if (tree.x + tree.width < -100) { // Wrap around
                        tree.x = CANVAS_WIDTH + Math.random() * 100
                        // Randomize properties again for variety on respawn
                        const depth = 0.4 + Math.random() * 0.6
                        tree.depth = depth
                        tree.speedFactor = 0.5 * depth
                        tree.height = (50 + Math.random() * 70) * depth
                        tree.width = (25 + Math.random() * 25) * depth
                        tree.type = Math.random() > 0.5 ? 'round' : 'pine'

                        // We strictly need to re-sort if we want perfect Z-ordering but
                        // re-sorting every frame is expensive and popping creates issues.
                        // Just letting them wrap is fine for background noise.
                    }
                })
            }


            // Draw game
            const canvas = canvasRef.current
            if (canvas) {
                const ctx = canvas.getContext('2d')
                const width = canvas.width
                const height = canvas.height

                // Get settings again in case canvas dims changed (though they are props)
                const { GROUND_OFFSET, DINO_HEIGHT } = settingsRef.current

                // Clear canvas
                ctx.clearRect(0, 0, width, height)

                // Get theme colors from CSS variables
                const styles = getComputedStyle(document.documentElement)
                const bgColor = styles.getPropertyValue('--bg').trim()
                const surfaceColor = styles.getPropertyValue('--surface').trim() // Main card bg
                const textColor = styles.getPropertyValue('--text').trim()
                const primaryColor = styles.getPropertyValue('--primary').trim()
                const borderColor = styles.getPropertyValue('--border').trim()
                const mutedColor = styles.getPropertyValue('--muted').trim() || '#888'
                const accentColor = styles.getPropertyValue('--accent').trim() || primaryColor

                // Background
                // Update Time only if playing
                if (currentState === 'playing') {
                    const dt = deltaTime // ms
                    const currentDuration = settingsRef.current.CYCLE_DURATION * 1000 // Convert to ms
                    gameTimeRef.current = (gameTimeRef.current + dt / currentDuration) % 1.0
                }

                // Background (Sky)
                drawSky(ctx, width, height, gameTimeRef.current, primaryColor, textColor, bgColor, surfaceColor, borderColor, mutedColor)

                // Parallax Trees (Behind terrain)
                const groundY = height - GROUND_OFFSET
                drawTrees(ctx, width, groundY, mutedColor)

                // Terrain
                drawTerrain(ctx, width, height, groundY, surfaceColor, borderColor, mutedColor)

                // Ground line (Visual enhancement)
                ctx.strokeStyle = borderColor
                ctx.lineWidth = 2
                ctx.beginPath()
                ctx.moveTo(0, groundY)
                ctx.lineTo(width, groundY)
                ctx.stroke()

                // Draw dino
                const dinoX = 75
                const dinoDrawY = groundY - DINO_HEIGHT + dinoYRef.current
                // Dino body = Primary, Eye = BgColor (contrast)
                drawDino(ctx, dinoX, dinoDrawY, primaryColor, bgColor)

                // Draw cacti
                obstaclesRef.current.forEach((obs) => {
                    const obsDrawY = groundY - obs.height
                    // Cacti = Accent Color (stand out against surface/sky)
                    drawCactus(ctx, obs.x, obsDrawY, obs.width, obs.height, surfaceColor, borderColor)
                })

                // Draw score
                ctx.fillStyle = textColor
                ctx.font = 'bold 20px monospace'
                ctx.textAlign = 'right'
                ctx.fillText(`Score: ${Math.floor(scoreRef.current / 10)}`, width - 20, 40)
                ctx.fillText(`Best: ${Math.floor(highScore / 10)}`, width - 20, 70)

                // Draw state messages
                ctx.textAlign = 'center'
                ctx.font = 'bold 24px sans-serif'
                if (currentState === 'ready') {
                    ctx.fillText('Blink to Start!', width / 2, height / 2 - 40)
                    ctx.font = '16px sans-serif'
                    ctx.fillText('Single blink = Jump', width / 2, height / 2)
                    ctx.fillText('Double blink = Pause/Resume', width / 2, height / 2 + 30)
                } else if (currentState === 'paused') {
                    ctx.fillStyle = primaryColor
                    ctx.fillText('PAUSED', width / 2, height / 2)
                    ctx.font = '16px sans-serif'
                    ctx.fillStyle = textColor
                    ctx.fillText('Double blink to resume', width / 2, height / 2 + 30)
                } else if (currentState === 'gameOver') {
                    ctx.fillStyle = primaryColor
                    ctx.fillText('GAME OVER!', width / 2, height / 2 - 20)
                    ctx.font = '16px sans-serif'
                    ctx.fillStyle = textColor
                    ctx.fillText(`Final Score: ${Math.floor(scoreRef.current / 10)}`, width / 2, height / 2 + 10)
                    ctx.fillText('Blink to restart', width / 2, height / 2 + 40)
                }
            }

            animationRef.current = requestAnimationFrame(gameLoop)
        }

        animationRef.current = requestAnimationFrame(gameLoop)
        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current)
            }
        }
    }, [eyeState, highScore])

    const handleSettingChange = (key, value) => {
        setSettings(prev => ({
            ...prev,
            [key]: parseFloat(value)
        }))
    }

    const handleSaveSettings = () => {
        localStorage.setItem('dino_settings', JSON.stringify(settings))
        setSavedMessage('Saved!')
        setTimeout(() => setSavedMessage(''), 2000)
    }

    return (
        <div className="h-[calc(100vh-100px)] overflow-hidden">
            <div className="flex gap-6 flex-wrap lg:flex-nowrap h-full">
                {/* Main game area */}
                <div className="flex-1 min-w-0 h-full flex flex-col justify-center">
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                        <div className="flex justify-between items-center mb-6">
                            <h2 className="text-2xl font-bold text-text flex items-center gap-3">
                                <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
                                EOG Dino Game
                            </h2>
                            <button
                                onClick={() => setShowSettings(!showSettings)}
                                className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${showSettings ? 'bg-primary text-bg' : 'bg-bg text-muted border border-border hover:text-text'}`}
                            >
                                ⚙️ Tuner
                            </button>
                        </div>

                        <div className="space-y-4">
                            {/* Game info */}
                            <div className="bg-bg/50 backdrop-blur-sm rounded-xl p-4 border border-border relative mt-8">
                                {/* Eye Tracker (Absolute Positioned on Top Border) */}
                                <div className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 -top-[1px] z-10 w-full flex justify-center gap-32 pointer-events-none">
                                    {/* Left Eye */}
                                    <div className="eye w-24 h-24 bg-surface rounded-full border-4 border-border relative overflow-hidden flex justify-center items-center shadow-sm" ref={leftEyeRef}>
                                        <div className="pupil w-8 h-8 bg-text rounded-full"></div>
                                    </div>
                                    {/* Right Eye */}
                                    <div className="eye w-24 h-24 bg-surface rounded-full border-4 border-border relative overflow-hidden flex justify-center items-center shadow-sm" ref={rightEyeRef}>
                                        <div className="pupil w-8 h-8 bg-text rounded-full"></div>
                                    </div>
                                </div>

                                <div className="flex justify-between items-end pt-4 px-4">
                                    <div className="text-left">
                                        <div className="text-muted text-sm font-medium">Status</div>
                                        <div className="text-text font-bold text-lg capitalize">{gameState}</div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-muted text-sm font-medium">EOG Sensor</div>
                                        <div className={`text-sm font-bold ${wsData ? 'text-green-500' : 'text-red-500'}`}>
                                            {wsData ? 'Connected' : 'Disconnected'}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Canvas */}
                            <div className="bg-bg rounded-xl border-2 border-border overflow-hidden shadow-lg">
                                <canvas
                                    ref={canvasRef}
                                    width={settings.CANVAS_WIDTH}
                                    height={settings.CANVAS_HEIGHT}
                                    className="w-full"
                                    style={{ imageRendering: 'crisp-edges' }}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Sidebar */}
                <div className="w-full lg:w-80 space-y-6 h-full overflow-y-auto no-scrollbar pb-6">

                    {/* Eye Controls Panel */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-4">
                        <h3 className="text-sm font-bold text-text uppercase tracking-wider mb-3">Controls</h3>
                        <div className="space-y-2 text-sm text-text">
                            <div className="flex justify-between">
                                <span className="text-muted">1x Blink</span>
                                <span className="font-bold text-primary">Jump</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-muted">2x Blink</span>
                                <span className="font-bold text-primary">Pause / Resume</span>
                            </div>
                        </div>
                        
                        <div className="mt-4 pt-3 border-t border-border">
                            <div className="flex justify-between items-center text-xs">
                                <span className="text-muted font-medium uppercase tracking-wider">Input Status</span>
                                <span className={`font-bold ${wsData ? 'text-green-500' : 'text-red-500'}`}>
                                    {wsData ? 'ACTIVE' : 'OFFLINE'}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Event Log Panel */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-4">
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="text-sm font-bold text-text uppercase tracking-wider">Event Log</h3>
                            <button
                                onClick={() => setEventLogs([])}
                                className="text-xs text-muted hover:text-red-400"
                            >
                                Clear
                            </button>
                        </div>
                        <div className="bg-bg/50 rounded-lg p-2 h-32 overflow-y-auto font-mono text-xs space-y-1 border border-border/50">
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
                                        Reset
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-6">
                                <div className="space-y-3">
                                    <h4 className="text-xs font-bold text-primary border-b border-border pb-1">Physics</h4>
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
                                    <SettingInput label="Day Cycle (s)" value={settings.CYCLE_DURATION} onChange={(v) => handleSettingChange('CYCLE_DURATION', v)} min="10" max="300" step="5" />
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Tips */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                        <h3 className="text-xl font-bold text-text mb-4">💡 Tips</h3>
                        <ul className="space-y-2 text-muted text-sm">
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-1">•</span>
                                <span>Easy mode: slower speed for comfortable EOG control</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-1">•</span>
                                <span>Practice your blink timing for better control</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-1">•</span>
                                <span>Watch the eye tracker for blink confirmation</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-1">•</span>
                                <span>Adjust EOG threshold in settings if needed</span>
                            </li>
                        </ul>
                    </div>
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
