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

    // Game settings (easy mode)
    const GRAVITY = 0.45
    const JUMP_STRENGTH = -11
    const GROUND_OFFSET = 65
    const DINO_WIDTH = 44
    const DINO_HEIGHT = 47
    const OBSTACLE_WIDTH = 20
    const OBSTACLE_MIN_HEIGHT = 40
    const OBSTACLE_MAX_HEIGHT = 60
    const GAME_SPEED = 3
    const SPAWN_INTERVAL = 1150
    const CANVAS_WIDTH = 800
    const CANVAS_HEIGHT = 376

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

    // Sync refs with state
    useEffect(() => {
        gameStateRef.current = gameState
    }, [gameState])

    useEffect(() => {
        scoreRef.current = score
    }, [score])

    // Listen for WebSocket Events (Blinks)
    useEffect(() => {
        if (!wsEvent) return;

        if (wsEvent.event === 'BLINK') {
            console.log("🦖 Dino: Blink Event Received via Logic Pipeline!");
            handleEOGBlink();
        }
    }, [wsEvent]);

    // EOG sensor integration REMOVED - Controlled via external PyAutoGUI keypresses
    // useEffect(() => {
    //     if (!wsData || isPaused) return
    //
    //     let payload = null
    //     try {
    //         payload = typeof wsData === 'string' ? JSON.parse(wsData) : wsData
    //         if (wsData.data && typeof wsData.data === 'string') payload = JSON.parse(wsData.data)
    //     } catch {
    //         return
    //     }
    //
    //     // Detect EOG signal patterns for jump/pause
    //     if (payload?.window && payload.window.length > 0) {
    //         const eogChannel = payload.window[0] // Assuming first channel is EOG
    //         if (eogChannel && eogChannel.length > 0) {
    //             const avgSignal = eogChannel.reduce((a, b) => a + b, 0) / eogChannel.length
    //
    //             // Detect blink (threshold-based, adjust as needed)
    //             if (Math.abs(avgSignal) > 100) {
    //                 handleEOGBlink()
    //             }
    //         }
    //     }
    // }, [wsData, isPaused])

    // Handle EOG blink detection
    const handleEOGBlink = () => {
        const now = Date.now()
        const timeSinceLastBlink = now - blinkPressTimeRef.current

        if (timeSinceLastBlink < 500) {
            // Double blink detected
            handleDoublePress()
        } else {
            // Single blink
            handleSinglePress()
        }

        blinkPressTimeRef.current = now
    }

    function inc_percent(value, percent) {
        value += value * (percent / 100)
        return value
    }

    // Keyboard controls (hidden from UI but still functional for testing)
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Debug log to verify if events are reaching the component
            console.log('Detected Key:', e.code, e.key)

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
        // Eye blink animation
        triggerSingleBlink()

        const currentState = gameStateRef.current

        if (currentState === 'ready') {
            setGameState('playing')
            setScore(0)
            scoreRef.current = 0
            dinoYRef.current = 0
            velocityRef.current = 0
            obstaclesRef.current = []
            lastSpawnRef.current = Date.now()
        } else if (currentState === 'playing' && Math.abs(dinoYRef.current) < 0.1) {
            velocityRef.current = JUMP_STRENGTH
        } else if (currentState === 'gameOver') {
            // Restart game
            setGameState('playing')
            setScore(0)
            scoreRef.current = 0
            dinoYRef.current = 0
            velocityRef.current = 0
            obstaclesRef.current = []
            lastSpawnRef.current = Date.now()
        }
    }

    // Double press - Pause/Resume
    const handleDoublePress = () => {
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
    const drawDino = (ctx, x, y, color, textColor) => {
        ctx.save()
        ctx.fillStyle = color

        // Body
        ctx.fillRect(x + 6, y + 20, 25, 17)

        // Head
        ctx.fillRect(x + 31, y + 14, 13, 13)

        // Neck
        ctx.fillRect(x + 25, y + 17, 6, 10)

        // Tail
        ctx.beginPath()
        ctx.moveTo(x + 6, y + 25)
        ctx.lineTo(x, y + 32)
        ctx.lineTo(x + 6, y + 32)
        ctx.fill()

        // Eye
        ctx.fillStyle = textColor
        if (eyeState === 'open') {
            ctx.fillRect(x + 36, y + 18, 2, 2)
        } else {
            ctx.fillRect(x + 36, y + 19, 2, 1)
        }

        // Legs (animated)
        ctx.fillStyle = color
        const legOffset = Math.floor(Date.now() / 100) % 2 === 0 ? 0 : 2

        // Front leg
        ctx.fillRect(x + 24, y + 37, 4, 10 - legOffset)

        // Back leg
        ctx.fillRect(x + 14, y + 37, 4, 10 + legOffset)

        // Arms
        ctx.fillRect(x + 28, y + 24, 2, 6)

        ctx.restore()
    }

    // Draw cactus
    const drawCactus = (ctx, x, y, width, height, color, borderColor) => {
        ctx.save()
        ctx.fillStyle = color
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2

        // Main trunk
        const trunkWidth = width * 0.6
        const trunkX = x + (width - trunkWidth) / 2
        ctx.fillRect(trunkX, y, trunkWidth, height)
        ctx.strokeRect(trunkX, y, trunkWidth, height)

        // Left arm
        const armHeight = height * 0.4
        const armWidth = width * 0.3
        const leftArmX = trunkX - armWidth
        const leftArmY = y + height * 0.3
        ctx.fillRect(leftArmX, leftArmY, armWidth, armHeight)
        ctx.strokeRect(leftArmX, leftArmY, armWidth, armHeight)
        ctx.fillRect(leftArmX + armWidth, leftArmY, trunkWidth * 0.3, armWidth)
        ctx.strokeRect(leftArmX + armWidth, leftArmY, trunkWidth * 0.3, armWidth)

        // Right arm
        const rightArmX = trunkX + trunkWidth
        const rightArmY = y + height * 0.5
        ctx.fillRect(rightArmX, rightArmY, armWidth, armHeight * 0.8)
        ctx.strokeRect(rightArmX, rightArmY, armWidth, armHeight * 0.8)
        ctx.fillRect(trunkX + trunkWidth * 0.7, rightArmY, trunkWidth * 0.3, armWidth)
        ctx.strokeRect(trunkX + trunkWidth * 0.7, rightArmY, trunkWidth * 0.3, armWidth)

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
                } else if (Math.abs(oldY - dinoYRef.current) > 1) {
                    console.log('📊 Physics: Y:', oldY.toFixed(2), '→', dinoYRef.current.toFixed(2), '| Vel:', oldVelocity.toFixed(2), '→', velocityRef.current.toFixed(2))
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
                        if (scoreRef.current > highScore) {
                            setHighScore(scoreRef.current)
                            localStorage.setItem('dino_highscore', scoreRef.current.toString())
                        }
                        break
                    }
                }
            }

            // Draw game
            const canvas = canvasRef.current
            if (canvas) {
                const ctx = canvas.getContext('2d')
                const width = canvas.width
                const height = canvas.height

                // Clear canvas
                ctx.clearRect(0, 0, width, height)

                // Get theme colors from CSS variables
                const styles = getComputedStyle(document.documentElement)
                const bgColor = styles.getPropertyValue('--bg').trim()
                const surfaceColor = styles.getPropertyValue('--surface').trim()
                const textColor = styles.getPropertyValue('--text').trim()
                const primaryColor = styles.getPropertyValue('--primary').trim()
                const borderColor = styles.getPropertyValue('--border').trim()

                // Background
                ctx.fillStyle = bgColor
                ctx.fillRect(0, 0, width, height)

                // Ground line
                const groundY = height - GROUND_OFFSET
                ctx.strokeStyle = borderColor
                ctx.lineWidth = 2
                ctx.beginPath()
                ctx.moveTo(0, groundY)
                ctx.lineTo(width, groundY)
                ctx.stroke()

                // Draw dino (dinoYRef is distance above ground, subtract it to move dino up)
                const dinoX = 75
                const dinoDrawY = groundY - DINO_HEIGHT + dinoYRef.current
                drawDino(ctx, dinoX, dinoDrawY, primaryColor, textColor)

                // Draw cacti
                obstaclesRef.current.forEach((obs) => {
                    const obsDrawY = groundY - obs.height
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

    return (
        <div className="space-y-6">
            <div className="flex gap-6 flex-wrap lg:flex-nowrap">
                {/* Main game area */}
                <div className="flex-1 min-w-0">
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                        <h2 className="text-2xl font-bold text-text mb-6 flex items-center gap-3">
                            <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
                            EOG Dino Game
                        </h2>

                        <div className="space-y-4">
                            {/* Game info */}
                            <div className="bg-bg/50 backdrop-blur-sm rounded-xl p-4 border border-border">
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                                    <div>
                                        <div className="text-muted text-sm font-medium">Status</div>
                                        <div className="text-text font-bold text-lg capitalize">{gameState}</div>
                                    </div>
                                    <div>
                                        <div className="text-muted text-sm font-medium">Score</div>
                                        <div className="text-primary font-bold text-lg">{Math.floor(score / 10)}</div>
                                    </div>
                                    <div>
                                        <div className="text-muted text-sm font-medium">Best</div>
                                        <div className="text-primary font-bold text-lg">{Math.floor(highScore / 10)}</div>
                                    </div>
                                    <div>
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
                                    width={CANVAS_WIDTH}
                                    height={CANVAS_HEIGHT}
                                    className="w-full"
                                    style={{ imageRendering: 'crisp-edges' }}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Eye tracker panel */}
                <div className="w-full lg:w-80">
                    <div className="eye-tracker">
                        <h3>Eye Blink Tracker</h3>

                        <div className="eyes-container">
                            <div className="eye" ref={leftEyeRef}>
                                <div className="pupil"></div>
                            </div>
                            <div className="eye" ref={rightEyeRef}>
                                <div className="pupil"></div>
                            </div>
                        </div>

                        <div className="blink-info">
                            <strong>Controls:</strong><br />
                            <strong>Single blink</strong> → Jump<br />
                            <strong>Double blink</strong> → Pause/Resume<br />
                            <br />
                            <strong>Input Mode:</strong><br />
                            {wsData ? '✓ EOG Sensor Active' : '✗ EOG Sensor Disconnected'}
                        </div>
                    </div>

                    {/* Tips */}
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-6 mt-6">
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
