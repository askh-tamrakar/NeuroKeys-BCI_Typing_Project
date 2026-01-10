/* eslint-disable no-restricted-globals */
import { calculateDayNightColors } from '../game/ColorMechanics.js';

// Game Constants (Defaults, will be overridden by settings)
let SETTINGS = {
    GRAVITY: 0.4,
    JUMP_STRENGTH: -10,
    GROUND_OFFSET: 60,
    DINO_WIDTH: 62,
    DINO_HEIGHT: 66,
    OBSTACLE_WIDTH: 28,
    OBSTACLE_MIN_HEIGHT: 56,
    OBSTACLE_MAX_HEIGHT: 84,
    GAME_SPEED: 5,
    SPAWN_INTERVAL: 1150,
    CANVAS_WIDTH: 800,
    CANVAS_HEIGHT: 376,
    CYCLE_DURATION: 100,
    JUMP_DISTANCE: 150,
    JUMP_DISTANCE: 150,
    ENABLE_TREES: true,
    OBSTACLE_BONUS_FACTOR: 0.015,

    // Visual Customization (Defaults)
    ENABLE_TREES: true,
    TREES_DENSITY: 1.0,
    TREES_SIZE: 1.0,
    TREES_LAYERS: 1,

    ENABLE_CLOUDS: true,
    CLOUDS_DENSITY: 1.0,
    CLOUDS_SIZE: 1.0,
    CLOUDS_LAYERS: 1,

    ENABLE_STARS: true,
    STARS_DENSITY: 1.0,
    STARS_SIZE: 1.0,
    STARS_LAYERS: 1,

    ENABLE_BUSHES: true,
    BUSHES_DENSITY: 1.0,
    BUSHES_SIZE: 1.0,
    BUSHES_LAYERS: 3,

    ENABLE_DAY_NIGHT_CYCLE: true,
    FIXED_TIME: 0.25
};

// Game State
let canvas = null;
let ctx = null;
let animationId = null;
let lastTime = 0;

let gameState = 'ready';
let score = 0;
let highScore = 0;
let dinoY = 0;
let velocity = 0;
let obstacles = [];
let lastSpawnTimestamp = 0;
let distance = 0;
let gameTime = 0;
let moonPhase = 0; // 0 to 1
let lastSentScore = 0;
let obstaclesPassed = 0;
let scoreMultiplier = 1.0;

// Visuals State
let clouds = [];
let trees = [];
let bushes = [];
let extraBushes = []; // Additional foreground/background bushes
let stars = [];
let bushSprites = []; // Array of ImageBitmaps

// Eye State (for animation)
let eyeState = 'open'; // open, blink, double-blink
let eyeStateTimer = null;

// Dynamic Element Colors
let CURRENT_COLORS = {
    sky: '#fff',
    tree: '#ccc',
    cloud: '#fff',
    sun: '#ff0',
    moon: '#fff'
};

// --- Initialization ---

// Bush Pixel Matrices (0 = empty, 1 = pixel)
// Removed procedural variants

function initVisuals() {
    // Init clouds
    clouds = [];
    if (SETTINGS.ENABLE_CLOUDS) {
        const cloudCount = Math.floor(15 * SETTINGS.CLOUDS_DENSITY);

        // Loop through layers to distribute clouds
        const layers = Math.max(1, SETTINGS.CLOUDS_LAYERS);
        for (let l = 0; l < layers; l++) {
            // Depth from 0.15 (far) to 1.0 (near)
            // Layer 0 is far, Layer N is near? or vice versa.
            // Let's say l=0 is far.
            const t = layers > 1 ? l / (layers - 1) : 0.5;
            const depthBase = 0.15 + t * 0.85;

            // Add variance within layer
            const countPerLayer = Math.ceil(cloudCount / layers);
            for (let i = 0; i < countPerLayer; i++) {
                const depth = depthBase + (Math.random() * 0.1 - 0.05); // Small jitter
                clouds.push({
                    x: Math.random() * SETTINGS.CANVAS_WIDTH,
                    y: Math.random() * 150 + 20,
                    width: (60 + Math.random() * 40) * depth * SETTINGS.CLOUDS_SIZE,
                    speed: (0.1 + Math.random() * 0.1) * depth,
                    depth: depth
                });
            }
        }
        clouds.sort((a, b) => a.depth - b.depth);
    }

    // Init trees
    trees = [];
    if (SETTINGS.ENABLE_TREES) {
        const baseTreeCount = Math.floor(SETTINGS.CANVAS_WIDTH / 60) + 5;
        const treeCount = Math.ceil(baseTreeCount * SETTINGS.TREES_DENSITY);

        const layers = Math.max(1, SETTINGS.TREES_LAYERS);
        for (let l = 0; l < layers; l++) {
            const t = layers > 1 ? l / (layers - 1) : 0.5;
            // Trees usually are background, so depth 0.4 to 1.0
            const depthBase = 0.4 + t * 0.6;

            const countPerLayer = Math.ceil(treeCount / layers);
            for (let i = 0; i < countPerLayer; i++) {
                const depth = Math.min(1.0, Math.max(0.1, depthBase + (Math.random() * 0.1 - 0.05)));
                const size = SETTINGS.TREES_SIZE;

                trees.push({
                    x: Math.random() * SETTINGS.CANVAS_WIDTH * 1.5, // Spread wider
                    height: (50 + Math.random() * 70) * depth * size,
                    width: (25 + Math.random() * 25) * depth * size,
                    type: Math.random() > 0.5 ? 'round' : 'pine',
                    depth: depth,
                    speedFactor: 0.5 * depth
                });
            }
        }
        trees.sort((a, b) => a.depth - b.depth);
    }

    // Init bushes (Layered Sprites)
    bushes = [];
    if (SETTINGS.ENABLE_BUSHES && bushSprites && bushSprites.length > 0) {
        const MAX_POTENTIAL_LAYERS = 10; // Fixed reference for normalization
        const userLayers = Math.max(0, Math.min(MAX_POTENTIAL_LAYERS, SETTINGS.BUSHES_LAYERS));

        for (let l = 0; l < userLayers; l++) {
            // Normalized layer position (0 = back, 1 = front)
            // We divide by (MAX - 1) so that layer 0 is always 0.0 and layer 9 is always 1.0
            // This ensures that reducing the count keeps the BACK layers (low t) and removes FRONT layers (high t)
            const t = l / (MAX_POTENTIAL_LAYERS - 1);

            // Interpolate params
            // Scale: 0.5 -> 2.5
            const baseScale = 0.5 + t * 2.0;

            // Speed: Slower now (0.2 -> 1.2 instead of 0.4 -> 2.5)
            const baseSpeed = 0.2 + t * 1.0;
            // yOff:
            const baseYOff = 5 + t * 55;

            // Count logic
            const baseCount = Math.max(1, Math.floor(5 - t * 4));
            const count = Math.floor((Math.floor(SETTINGS.CANVAS_WIDTH / (250 - t * 100)) + baseCount) * SETTINGS.BUSHES_DENSITY);

            for (let i = 0; i < count; i++) {
                bushes.push({
                    x: Math.random() * SETTINGS.CANVAS_WIDTH,
                    yOffset: baseYOff,
                    variant: Math.floor(Math.random() * bushSprites.length),
                    scale: baseScale * (0.8 + Math.random() * 0.4) * SETTINGS.BUSHES_SIZE,
                    speedFactor: baseSpeed,
                    layer: l // 0 is back
                });
            }
        }
        bushes.sort((a, b) => a.layer - b.layer);
    }

    // Clear extraBushes
    extraBushes = [];

    // Init stars
    stars = [];
    if (SETTINGS.ENABLE_STARS) {
        const starCount = Math.floor(50 * SETTINGS.STARS_DENSITY);

        const layers = Math.max(1, SETTINGS.STARS_LAYERS);

        for (let l = 0; l < layers; l++) {
            // Stars are just distant points, but let's vary size/opacity layers?
            // Or just use layers to spawn MORE stars effectively?
            // The user asked for "layers" for stars. Let's interpret as depth planes affecting parallax or just count.
            // Stars usually don't parallax much unless they are 3d.
            // We can just add more stars per layer.

            const countPerLayer = Math.ceil(starCount / layers);
            for (let i = 0; i < countPerLayer; i++) {
                stars.push({
                    x: Math.random() * SETTINGS.CANVAS_WIDTH,
                    y: Math.random() * SETTINGS.CANVAS_HEIGHT / 2,
                    size: (Math.random() * 2 + 1) * SETTINGS.STARS_SIZE,
                    blinkOffset: Math.random() * Math.PI
                });
            }
        }
    }
}

// --- Logic ---

function resetGame() {
    gameState = 'playing';
    score = 0;
    lastSentScore = 0;
    dinoY = 0;
    velocity = 0;
    obstacles = [];
    lastSpawnTimestamp = Date.now();
    distance = 0;
    obstaclesPassed = 0;
    scoreMultiplier = 1.0;
    self.postMessage({ type: 'SCORE_UPDATE', score: 0 });
}

function handleInput(action) {
    console.log("[Worker] Input received:", action, "State:", gameState, "Y:", dinoY)
    if (action === 'jump') {
        // Trigger Blink Animation
        eyeState = 'blink';
        if (eyeStateTimer) clearTimeout(eyeStateTimer);
        eyeStateTimer = setTimeout(() => { eyeState = 'open'; }, 300);

        if (gameState === 'ready' || gameState === 'gameOver') {
            console.log("[Worker] Resetting game")
            resetGame();
        } else if (gameState === 'playing' && dinoY === 0) { // Only jump if on ground (checking exact 0 approx)
            // Jump logic
            console.log("[Worker] Jumping! Strength:", SETTINGS.JUMP_STRENGTH)
            velocity = SETTINGS.JUMP_STRENGTH;
        } else {
            console.log("[Worker] Jump ignored. State:", gameState, "Y:", dinoY)
        }
    } else if (action === 'pause') {
        // Trigger Double Blink Animation
        eyeState = 'double-blink';
        if (eyeStateTimer) clearTimeout(eyeStateTimer);
        eyeStateTimer = setTimeout(() => { eyeState = 'open'; }, 600);

        if (gameState === 'playing') {
            gameState = 'paused';
            self.postMessage({ type: 'STATE_UPDATE', payload: 'paused' });
        } else if (gameState === 'paused') {
            gameState = 'playing';
            self.postMessage({ type: 'STATE_UPDATE', payload: 'playing' });
        }
    }
}

function updatePhysics(deltaTime) {
    // Target 60 FPS (approx 16.67ms per frame)
    const timeFactor = Math.min(deltaTime / 16.67, 3.0); // Cap at 3x speed to prevent tunneling on huge lag spikes

    // Recalculate derived speed
    const vy = Math.abs(SETTINGS.JUMP_STRENGTH);
    const GRAVITY = SETTINGS.GRAVITY;
    // Prevent div by zero
    const derivedSpeed = vy > 0 ? (SETTINGS.JUMP_DISTANCE * GRAVITY) / (2 * vy) : 5;
    const GAME_SPEED = derivedSpeed * timeFactor;
    const APPLIED_GRAVITY = GRAVITY * timeFactor;

    // Day/Night Cycle
    if (SETTINGS.ENABLE_DAY_NIGHT_CYCLE) {
        gameTime = (gameTime + deltaTime / (SETTINGS.CYCLE_DURATION * 1000)) % 1.0;
    } else {
        gameTime = SETTINGS.FIXED_TIME !== undefined ? SETTINGS.FIXED_TIME : 0.25;
    }

    // Moon Phase Cycle
    if (SETTINGS.ENABLE_AUTO_MOON_CYCLE) {
        const dayDuration = SETTINGS.CYCLE_DURATION || 100;
        const daysPerCycle = SETTINGS.MOON_CYCLE_DAYS || 30; // 30 days for full cycle (15 days to full)
        const duration = dayDuration * daysPerCycle;

        moonPhase = (moonPhase + deltaTime / (duration * 1000)) % 1.0;
    } else {
        moonPhase = SETTINGS.MOON_PHASE !== undefined ? SETTINGS.MOON_PHASE : 0.5;
    }

    // Update Dynamic Colors using Module
    CURRENT_COLORS = calculateDayNightColors(gameTime, COLORS);

    if (gameState === 'playing') {
        // Dino Physics
        velocity += APPLIED_GRAVITY;
        dinoY += velocity * timeFactor; // Apply velocity scaled by time

        if (dinoY >= 0) {
            dinoY = 0;
            velocity = 0;
        }

        // Obstacles
        obstacles = obstacles
            .map(o => ({ ...o, x: o.x - GAME_SPEED }))
            .filter(o => o.x > -SETTINGS.OBSTACLE_WIDTH - 20);

        // Spawn
        const now = Date.now();
        if (now - lastSpawnTimestamp > SETTINGS.SPAWN_INTERVAL) { // Interval should technically be time-based too, but wall-clock is fine
            lastSpawnTimestamp = now;
            const height = SETTINGS.OBSTACLE_MIN_HEIGHT + Math.random() * (SETTINGS.OBSTACLE_MAX_HEIGHT - SETTINGS.OBSTACLE_MIN_HEIGHT);
            obstacles.push({
                x: SETTINGS.CANVAS_WIDTH,
                y: 0,
                width: SETTINGS.OBSTACLE_WIDTH + Math.random() * 10,
                height: height
            });
        }

        // Check for passed obstacles
        obstacles.forEach(obs => {
            if (!obs.passed && obs.x + obs.width < 75) { // 75 is Dino X position
                obs.passed = true;
                obstaclesPassed++;
                scoreMultiplier = 1.0 + (obstaclesPassed * SETTINGS.OBSTACLE_BONUS_FACTOR);
                // Optional: Log or visual feedback could go here
            }
        });

        // Score
        score += (1 * timeFactor) * scoreMultiplier; // Score based on distance/time * multiplier

        const displayScore = Math.floor(score / 10);
        if (displayScore > lastSentScore) {
            lastSentScore = displayScore;
            self.postMessage({ type: 'SCORE_UPDATE', score: score });
        }

        // Collisions
        // Collisions
        const groundY = SETTINGS.CANVAS_HEIGHT - SETTINGS.GROUND_OFFSET;
        const dinoX = 75;

        // Use proportional hitboxes so scaling works as expected
        const dinoPadX = SETTINGS.DINO_WIDTH * 0.25; // 25% padding on each side (was ~10px on 44px)
        const dinoPadY = SETTINGS.DINO_HEIGHT * 0.15; // 15% padding on top/bottom

        const dinoLeft = dinoX + dinoPadX;
        const dinoRight = dinoX + SETTINGS.DINO_WIDTH - dinoPadX;

        // dinoY is negative when going UP. groundY is the baseline.
        // Visual Top: groundY + dinoY - HEIGHT
        // Visual Bottom: groundY + dinoY
        // Hitbox Top = Visual Top + PadY (moved down)
        // Hitbox Bottom = Visual Bottom - PadY (moved up)

        const dinoTop = groundY + dinoY - SETTINGS.DINO_HEIGHT + dinoPadY;
        const dinoBottom = groundY + dinoY - dinoPadY;

        for (const obs of obstacles) {
            // Proportional obstacle hitbox
            const obsPad = obs.width * 0.2; // 20% padding (was ~5px on 20px)

            const obsLeft = obs.x + obsPad;
            const obsRight = obs.x + obs.width - obsPad;
            const obsTop = groundY - obs.height; // Top is hard (cactus spikes), maybe keep it tight?
            const obsBottom = groundY;

            if (dinoRight > obsLeft && dinoLeft < obsRight && dinoBottom > obsTop && dinoTop < obsBottom) {
                gameState = 'gameOver';
                if (score > highScore) {
                    highScore = score;
                    self.postMessage({ type: 'HIGHSCORE_UPDATE', highScore });
                }
                self.postMessage({ type: 'GAME_OVER', score });
            }
        }

        // Environment
        distance += GAME_SPEED;

        distance += GAME_SPEED;

        // Day/Night Cycle moved up

        // Trees
        if (SETTINGS.ENABLE_TREES) {
            trees.forEach(tree => {
                tree.x -= GAME_SPEED * tree.speedFactor;
                if (tree.x + tree.width < -100) {
                    tree.x = SETTINGS.CANVAS_WIDTH + Math.random() * 100;
                    tree.depth = 0.4 + Math.random() * 0.6;
                    tree.speedFactor = 0.5 * tree.depth;
                    tree.height = (50 + Math.random() * 70) * tree.depth;
                    tree.width = (25 + Math.random() * 25) * tree.depth;
                    tree.type = Math.random() > 0.5 ? 'round' : 'pine';
                }
            });
        }

        // Bushes (Move with parallax)
        bushes.forEach(bush => {
            bush.x -= GAME_SPEED * bush.speedFactor;
            if (bush.x < -100) { // Offscreen 
                // Recycle
                bush.x = SETTINGS.CANVAS_WIDTH + Math.random() * 200;
                // Keep layer properties (scale, yOff, speed) consistent for this object, just randomize variant
                bush.variant = Math.floor(Math.random() * (bushSprites.length || 1));
            }
        });

        // Visual Bushes (Move with parallax)
        extraBushes.forEach(bush => {
            bush.x -= GAME_SPEED * bush.speedFactor;
            if (bush.x < -100) {
                bush.x = SETTINGS.CANVAS_WIDTH + Math.random() * 400; // More sparse
                bush.variant = Math.floor(Math.random() * (bushSprites.length || 1));
            }
        });
    }
}

// --- Drawing ---

// Colors (Hardcoded equivalent of CSS variables for simplicity, or we can pass theme in settings)
const COLORS = {
    bg: '#ffffff', // Theme agnostic default, will try to pass from main if needed
    surface: '#f3f4f6',
    text: '#111827',
    primary: '#3b82f6',
    border: '#e5e7eb',
    muted: '#9ca3af',
    accent: '#3b82f6',
    bushLight: '#a7f3d0', // Very light green
    bush: '#4ade80',  // Light green
    bushDark: '#16a34a', // Darker green
    berry: '#ef4444', // Red berry
    day: '#ffffff',   // Default Day
    night: '#000000', // Default Night
    treeDay: '#2ecc71',
    treeNight: '#0e1512',
    cloudDay: '#cccccc', // Neutral Grey Default
    cloudNight: '#444444', // Neutral Dark Grey Default
    sunDay: '#F1C40F',
    sunNight: '#D35400',
    moonDay: '#ffffff',
    moonDay: '#ffffff',
    moonNight: '#CFE9DB',
    // Semantic Defaults
    dinoDay: '#2C2C2C',
    dinoNight: '#ffffff',
    obstacleDay: '#5D4037',
    obstacleNight: '#8D6E63',
    groundDay: '#e0e0e0',
    groundNight: '#1b1b1b',
    groundLineDay: '#5D4037',
    groundLineNight: '#8D6E63',
    skyDay: '#f8fafc',
    skyNight: '#0f172a',
    obstacleBorder: '#e5e7eb' // Default
};



function drawPixelCircle(cx, cy, radius, color) {
    ctx.fillStyle = color;
    const r = Math.floor(radius);
    for (let y = -r; y <= r; y++) {
        for (let x = -r; x <= r; x++) {
            if (x * x + y * y <= r * r) {
                ctx.fillRect(Math.floor(cx + x), Math.floor(cy + y), 1, 1);
            }
        }
    }
}

function drawBlockyCircle(cx, cy, size, color, pixelSize = 4) {
    ctx.fillStyle = color;
    const radius = Math.floor(size / 2);
    for (let y = -radius; y <= radius; y++) {
        for (let x = -radius; x <= radius; x++) {
            if (x * x + y * y <= radius * radius) {
                ctx.fillRect(Math.floor(cx + x * pixelSize), Math.floor(cy + y * pixelSize), pixelSize, pixelSize);
            }
        }
    }
}

function drawSky(width, height) {
    // Use Pre-Calculated Dynamic Color
    const skyColor = CURRENT_COLORS.sky;
    ctx.fillStyle = skyColor;
    ctx.fillRect(0, 0, width, height);

    // Update bg color reference so partial clears or other elements that rely on "bg" match
    COLORS.bg = skyColor;

    const centerX = width / 2;
    const radius = width * 0.6;
    const centerY = Math.max(height + 100, radius * 0.9 + 50);

    // Sun
    if (gameTime > 0.05 && gameTime < 0.65) {
        const sunAngle = ((gameTime - 0.1) / 0.5) * Math.PI;
        const sunX = centerX - Math.cos(sunAngle) * radius;
        const sunY = centerY - Math.sin(sunAngle) * radius * 0.9;
        // Dynamic Sun Color
        drawBlockyCircle(sunX, sunY, 28, CURRENT_COLORS.sun, 2);
    }

    // Moon
    if (gameTime > 0.55 || gameTime < 0.15) {
        let moonTime = gameTime - 0.6;
        if (moonTime < 0) moonTime += 1;
        const moonAngle = (moonTime / 0.5) * Math.PI;
        const moonX = centerX - Math.cos(moonAngle) * radius;
        const moonY = centerY - Math.sin(moonAngle) * radius * 0.9;
        const moonSize = 24;

        // Draw Base Moon (Full)
        // If phases enabled, we might mask it.
        // But simpler to draw full moon then draw 'sky' colored shadow over it.
        drawBlockyCircle(moonX, moonY, moonSize, CURRENT_COLORS.moon, 2);

        if (SETTINGS.ENABLE_MOON_PHASES) {
            // Phase Logic (0 = New, 0.5 = Full, 1 = New)
            // We want to simulate the shadow moving across.
            // Simplified "Retro" Phase: A sliding rectangular shadow or offset circle?
            // Let's use an offset circle of "Sky Color" to bite into the moon.


            const phase = moonPhase;

            ctx.fillStyle = skyColor;

            if (phase === 0.5) {
                // Full Moon - No Shadow (maybe small craters?)
                // Optional: visual interest
            } else if (Math.abs(phase - 0.5) > 0.45) {
                // New Moon (mostly hidden)
                drawBlockyCircle(moonX, moonY, moonSize - 2, skyColor, 2); // Hide center
            } else {
                // Crescent / Gibbous
                // Calculate shadow position
                // Phase 0..0.5 (Waxing) -> Shadow moves Right to Left (revealing)
                // Phase 0.5..1 (Waning) -> Shadow moves Right to Left (hiding)?

                // Let's model it as a shadow circle moving.
                // Full Moon (0.5) -> Shadow is far away.
                // New Moon (0/1) -> Shadow is on top.

                let shadowOffset = 0;

                // 0.0 (New) -> Shadow at 0
                // 0.25 (Half) -> Shadow at roughly radius
                // 0.5 (Full) -> Shadow at 2*radius (gone)

                // Let's simply slide a "Sky Color" circle across.
                // range: -2.5*radius to 2.5*radius?

                // Normalize phase to -1 (New) to 0 (Full) to 1 (New)? No.
                // Let's stick to 0..1

                // 0.5 is target.
                // If phase < 0.5 (Waxing): Shadow is on Left, moving Left?
                // Actually, standard is:
                // New (0) -> Waxing Crescent -> First Quarter (0.25) -> Waxing Gibbous -> Full (0.5)

                // Implementation:
                // Shadow X offset.
                // For 0 (New): Shadow matches Moon X.
                // For 0.25 (Half): Shadow is offset by radius/2?
                // For 0.5 (Full): Shadow is completely off.

                const relativePhase = (phase - 0.5) * 2; // -1 (New) to 0 (Full) to 1 (New) ??
                // No, Input 0 -> -1. Input 0.5 -> 0. Input 1 -> 1.

                // If we want a simple "slide from right":
                // Shadow starts at Right, moves Left?

                // Let's try Offset = f(phase).
                // 0 (New) -> Offset 0
                // 0.25 -> Offset Radius (covers half?)
                // 0.5 -> Offset 2*Radius (covers none)

                // Actually, let's just make it look cool.
                // Use a shadow offset driven by a cosine of the phase?

                // Strategy: A second "Sky" circle that eclipses the moon.
                // Offset defined by phase.
                // Phase 0: Offset 0.
                // Phase 0.5: Offset infinity (or large).

                // Better visual for retro: 
                // 0.0-0.5: Shadow moves LEFT to RIGHT (revealing moon? no, covering).
                // Let's assume shadow comes from left.

                // Let's use a simpler mapping: 
                // Phase is "amount of light".
                // We draw the shadow circle at an offset.

                // Let's use `Math.cos(phase * 2 * PI)` logic.
                // Shift = moonSize * 2 * (percentage)

                let shift = 0;

                if (phase < 0.5) {
                    // Waxing (0 -> 0.5). Shadow is moving OUT to the LEFT? 
                    // 0: Shadow centered. 0.5: Shadow far left.
                    // shift = -moonSize * 2 * (phase / 0.5); // 0 -> -2*size

                    // Better:
                    // 0 (New) -> Shadow on top (offset 0)
                    // 0.25 (Half) -> Shadow offset by radius (-12)
                    // 0.5 (Full) -> Shadow offset by diameter (-48)
                    shift = - (phase / 0.5) * (moonSize * 2.5);
                } else {
                    // Waning (0.5 -> 1.0). Shadow comes in from RIGHT.
                    // 0.5: Shadow far right.
                    // 1.0: Shadow centered.
                    // Normalized p: (phase - 0.5) / 0.5 => 0..1
                    const p = (phase - 0.5) / 0.5; // 0 to 1
                    // 0 -> 2.5*size
                    // 1 -> 0
                    shift = (1 - p) * (moonSize * 2.5);
                }

                // Draw Shadow Circle
                // We use blocky circle for shadow too to match style
                drawBlockyCircle(moonX + shift, moonY, moonSize, skyColor, 2);
            }
        } else {
            // Default "Classic" Moon Details (Pixel Cutouts)
            ctx.fillStyle = skyColor;
            ctx.fillRect(moonX - 12, moonY - 8, 8, 8);
            ctx.fillRect(moonX + 4, moonY + 8, 4, 4);
        }
    }

    // Stars
    if (gameTime > 0.6 || gameTime < 0.1) {
        ctx.fillStyle = COLORS.muted;
        const baseOpacity = (gameTime > 0.7 || gameTime < 0.05) ? 1 : 0.5;
        stars.forEach(star => {
            const flicker = Math.sin(Date.now() / 200 + star.blinkOffset) * 0.3 + 0.7;
            if (Math.random() > 0.1) {
                ctx.globalAlpha = baseOpacity * flicker;
                const s = Math.ceil(star.size);
                // Star shape: Cross or Dot
                if (s > 2) {
                    ctx.fillRect(star.x - s, star.y, s * 3, s);
                    ctx.fillRect(star.x, star.y - s, s, s * 3);
                } else {
                    ctx.fillRect(star.x, star.y, s * 2, s * 2);
                }
            }
        });
        ctx.globalAlpha = 1.0;
    }

    // Clouds
    ctx.fillStyle = CURRENT_COLORS.cloud;
    ctx.globalAlpha = 0.6; // Slightly more opacity for dynamic colored clouds
    clouds.forEach(cloud => {
        const w = Math.floor(cloud.width);
        const h = Math.floor(w * 0.4);
        const cx = Math.floor(cloud.x);
        const cy = Math.floor(cloud.y);

        ctx.fillRect(cx, cy, w, h);
        ctx.fillRect(Math.floor(cx + w * 0.2), Math.floor(cy - h * 0.6), Math.ceil(w * 0.4), Math.ceil(h * 0.8));
        ctx.fillRect(Math.floor(cx + w * 0.5), Math.floor(cy - h * 0.4), Math.ceil(w * 0.3), Math.ceil(h * 0.6));

        cloud.x -= cloud.speed;
        if (cloud.x + w < 0) {
            cloud.x = width + Math.random() * 100;
            cloud.y = Math.random() * 100 + 20;
        }
    });
    ctx.globalAlpha = 1.0;
}

function drawTrees(width, groundY) {
    if (!SETTINGS.ENABLE_TREES) return;
    ctx.fillStyle = CURRENT_COLORS.tree;
    ctx.globalAlpha = 0.8; // Better visibility
    trees.forEach(tree => {
        const tx = Math.floor(tree.x);
        const tw = Math.floor(tree.width);
        const th = Math.floor(tree.height);
        // Correct calculation:
        // ty (top) = groundY - th.
        // trunkY starts at middle of tree height visually.
        // We ensure total height reaches bottom.
        const ty = Math.floor(groundY - th);

        if (tx + tw > 0 && tx < width) {
            const trunkW = Math.max(4, Math.floor(tw * 0.3));

            const trunkReqH = Math.floor(th * 0.5); // Desired trunk height
            // But we must ensure it touches groundY exactly.
            // Top part height = th - trunkReqH
            // Top part draws at ty
            // Trunk draws at ty + (th - trunkReqH)

            const topH = th - trunkReqH;

            // Draw Trunk
            ctx.fillRect(Math.floor(tx + (tw - trunkW) / 2), ty + topH, trunkW, trunkReqH);

            // Draw Leaves (Top)
            if (tree.type === 'pine') {
                ctx.fillRect(tx, ty + Math.floor(th * 0.2), tw, Math.floor(th * 0.3));
                ctx.fillRect(Math.floor(tx + tw * 0.1), ty, Math.ceil(tw * 0.8), Math.floor(th * 0.4));
            } else {
                ctx.fillRect(tx, ty, tw, Math.floor(th * 0.6));
                ctx.fillRect(Math.floor(tx - tw * 0.2), ty + Math.floor(th * 0.1), Math.ceil(tw * 1.4), Math.floor(th * 0.4));
            }
        }
    });
    ctx.globalAlpha = 1.0;
}

function drawBushes(groundY) {
    if (!bushSprites || bushSprites.length === 0) return;

    try {
        bushes.forEach(bush => {
            const sprite = bushSprites[bush.variant];
            if (!sprite) return;

            const bx = Math.floor(bush.x);
            // Height calculation based on sprite aspect ratio if possible
            const sW = sprite.width;
            const sH = sprite.height;

            const drawW = Math.floor(sW * bush.scale);
            const drawH = Math.floor(sH * bush.scale);

            // groundY is the top of the ground line
            const by = Math.floor(groundY - drawH + bush.yOffset);

            if (bx + drawW > -50 && bx < SETTINGS.CANVAS_WIDTH + 50) {
                ctx.globalAlpha = bush.layer === 0 ? 0.7 : 1.0; // Dim back layer
                ctx.drawImage(sprite, bx, by, drawW, drawH);
                ctx.globalAlpha = 1.0;
            }
        });
    } catch (err) {
        console.error("Error drawing bushes:", err);
    }
}

function drawDino(x, y) {
    const { DINO_WIDTH, DINO_HEIGHT } = SETTINGS;
    const scaleX = DINO_WIDTH / 44;
    const scaleY = DINO_HEIGHT / 47;

    ctx.save();
    ctx.fillStyle = CURRENT_COLORS.dino;

    // Body
    ctx.fillRect(Math.floor(x + 6 * scaleX), Math.floor(y + 20 * scaleY), Math.ceil(25 * scaleX), Math.ceil(17 * scaleY));
    // Head
    ctx.fillRect(Math.floor(x + 31 * scaleX), Math.floor(y + 14 * scaleY), Math.ceil(13 * scaleX), Math.ceil(13 * scaleY));
    // Neck
    ctx.fillRect(Math.floor(x + 25 * scaleX), Math.floor(y + 17 * scaleY), Math.ceil(6 * scaleX), Math.ceil(10 * scaleY));
    // Tail
    ctx.beginPath();
    ctx.moveTo(Math.floor(x + 6 * scaleX), Math.floor(y + 25 * scaleY));
    ctx.lineTo(Math.floor(x), Math.floor(y + 32 * scaleY));
    ctx.lineTo(Math.floor(x + 6 * scaleX), Math.floor(y + 32 * scaleY));
    ctx.fill();

    // Eye
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(Math.floor(x + 36 * scaleX), Math.floor(y + (eyeState === 'open' ? 18 : 19) * scaleY), Math.ceil(2 * scaleX), Math.ceil((eyeState === 'open' ? 2 : 1) * scaleY));

    // Legs
    ctx.fillStyle = CURRENT_COLORS.dino;
    const legOffset = Math.floor(Date.now() / 100) % 2 === 0 ? 0 : 2;
    ctx.fillRect(Math.floor(x + 24 * scaleX), Math.floor(y + 37 * scaleY), Math.ceil(4 * scaleX), Math.ceil((10 - legOffset) * scaleY));
    ctx.fillRect(Math.floor(x + 14 * scaleX), Math.floor(y + 37 * scaleY), Math.ceil(4 * scaleX), Math.ceil((10 + legOffset) * scaleY));

    // Arms
    ctx.fillRect(Math.floor(x + 28 * scaleX), Math.floor(y + 24 * scaleY), Math.ceil(2 * scaleX), Math.ceil(6 * scaleY));

    ctx.restore();
}

const drawCactus = (ctx, x, y, width, height, color, borderColor) => {
    ctx.save()
    ctx.fillStyle = color
    ctx.strokeStyle = borderColor
    ctx.lineWidth = 3

    // Main trunk
    const trunkWidth = Math.floor(width * 0.65)
    const trunkX = Math.floor(x + (width - trunkWidth) / 2)
    const trunkH = Math.floor(height)
    const _y = Math.floor(y)

    ctx.fillRect(trunkX, _y, trunkWidth, trunkH)
    ctx.strokeRect(trunkX, _y, trunkWidth, trunkH)

    // Arms configuration
    const armWidth = Math.floor(width * 0.325)
    const outwardOffset = Math.floor(width * 0.2)

    // Left arm
    const leftArmY = Math.floor(y + height * 0.35)
    const leftArmH = Math.floor(height * 0.35)
    const leftArmX = Math.floor(trunkX - armWidth - outwardOffset)
    const leftVertY = Math.floor(leftArmY - leftArmH + armWidth)

    ctx.beginPath()
    ctx.moveTo(trunkX + 2, leftArmY) // Start inside trunk
    ctx.lineTo(leftArmX + armWidth, leftArmY) // Inner elbow
    ctx.lineTo(leftArmX + armWidth, leftVertY) // Inner top
    ctx.lineTo(leftArmX, leftVertY) // Outer top
    ctx.lineTo(leftArmX, leftArmY + armWidth) // Outer elbow
    ctx.lineTo(trunkX + 2, leftArmY + armWidth) // Back to trunk
    ctx.fill()
    ctx.stroke()

    // Right arm
    const rightArmY = Math.floor(y + height * 0.55)
    const rightArmH = Math.floor(height * 0.3)
    const rightArmX = Math.floor(trunkX + trunkWidth + outwardOffset)
    const rightVertY = Math.floor(rightArmY - rightArmH + armWidth)

    ctx.beginPath()
    ctx.moveTo(trunkX + trunkWidth - 2, rightArmY) // Start inside trunk
    ctx.lineTo(rightArmX, rightArmY) // Inner elbow
    ctx.lineTo(rightArmX, rightVertY) // Inner top
    ctx.lineTo(rightArmX + armWidth, rightVertY) // Outer top
    ctx.lineTo(rightArmX + armWidth, rightArmY + armWidth) // Outer elbow
    ctx.lineTo(trunkX + trunkWidth - 2, rightArmY + armWidth) // Back to trunk
    ctx.fill()
    ctx.stroke()

    ctx.restore()
}

function draw() {
    if (!ctx) return;

    try {
        const width = SETTINGS.CANVAS_WIDTH;
        const height = SETTINGS.CANVAS_HEIGHT;
        const groundY = height - SETTINGS.GROUND_OFFSET;

        // Clear
        ctx.clearRect(0, 0, width, height);

        // Background
        drawSky(width, height);
        drawTrees(width, groundY);

        // Visual Bushes (Back Layer - Layer 3)
        extraBushes.forEach(bush => {
            if (bush.layer === 3) { // Far back
                const sprite = bushSprites[bush.variant];
                if (sprite) {
                    const drawW = Math.floor(sprite.width * bush.scale);
                    const drawH = Math.floor(sprite.height * bush.scale);
                    const by = Math.floor(groundY - drawH + bush.yOffset);

                    ctx.globalAlpha = 0.6; // Faded for background
                    ctx.drawImage(sprite, Math.floor(bush.x), by, drawW, drawH);
                    ctx.globalAlpha = 1.0;
                }
            }
        });

        // Ground
        ctx.fillStyle = CURRENT_COLORS.ground;
        ctx.fillRect(0, Math.floor(groundY), width, height - groundY);
        // Draw the main line
        ctx.fillStyle = CURRENT_COLORS.groundLine;
        ctx.fillRect(0, Math.floor(groundY), width, 4);

        // Draw Bushes (Standard Layers 0-2)
        drawBushes(groundY);

        // Dino
        const dinoYPos = groundY - SETTINGS.DINO_HEIGHT + dinoY;
        drawDino(75, dinoYPos);

        // Obstacles
        obstacles.forEach(obs => {
            drawCactus(ctx, obs.x, groundY - obs.height, obs.width, obs.height, CURRENT_COLORS.obstacle, COLORS.obstacleBorder);
        });

        // Visual Bushes (Front Layer - Layer 4)
        extraBushes.forEach(bush => {
            if (bush.layer === 4) { // Foreground
                const sprite = bushSprites[bush.variant];
                if (sprite) {
                    const drawW = Math.floor(sprite.width * bush.scale);
                    const drawH = Math.floor(sprite.height * bush.scale);
                    const by = Math.floor(groundY - drawH + bush.yOffset);

                    ctx.globalAlpha = 1.0;
                    ctx.drawImage(sprite, Math.floor(bush.x), by, drawW, drawH);
                }
            } else if (bush.layer === 5) { // Extreme Foreground (Blurry?)
                const sprite = bushSprites[bush.variant];
                if (sprite) {
                    const drawW = Math.floor(sprite.width * bush.scale);
                    const drawH = Math.floor(sprite.height * bush.scale);
                    const by = Math.floor(groundY - drawH + bush.yOffset);

                    ctx.globalAlpha = 1.0;
                    // Optional: expensive filter, sticking to raw draw for perf
                    // ctx.filter = 'blur(2px)'; 
                    ctx.drawImage(sprite, Math.floor(bush.x), by, drawW, drawH);
                    // ctx.filter = 'none';
                }
            }
        });

        if (gameState === 'ready') {
            ctx.textAlign = 'center';
            ctx.font = 'bold 24px sans-serif';
            ctx.fillStyle = COLORS.text;
            ctx.fillText('Blink to Start!', width / 2, height / 2 - 20);
        } else if (gameState === 'paused') {
            // Draw semi-transparent overlay
            ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
            ctx.fillRect(0, 0, width, height);

            ctx.textAlign = 'center';
            ctx.font = 'bold 36px sans-serif';
            ctx.fillStyle = COLORS.primary;
            ctx.fillText('PAUSED', width / 2, height / 2 - 20);

            ctx.fillStyle = 'white'; // White text on dark overlay looks better
            ctx.font = '24px sans-serif';
            ctx.fillText('Double Blink to resume', width / 2, height / 2 + 20);

        } else if (gameState === 'gameOver') {
            ctx.textAlign = 'center';
            ctx.font = 'bold 36px sans-serif';
            ctx.fillStyle = COLORS.primary;
            ctx.fillText('GAME OVER!', width / 2, height / 2 - 20);
            ctx.fillStyle = COLORS.text;
            ctx.font = '24px sans-serif';
            ctx.fillText('Blink to restart', width / 2, height / 2 + 20);
        }
    } catch (err) {
        console.error("[Worker] Draw Error:", err);
    }
}

function loop() {
    const now = Date.now();
    const deltaTime = now - lastTime;
    lastTime = now;

    updatePhysics(deltaTime);
    draw();

    animationId = requestAnimationFrame(loop);
}

// --- Messaging ---

self.onmessage = (e) => {
    const { type, payload } = e.data;

    switch (type) {
        case 'INIT':
            canvas = payload.canvas;
            ctx = canvas.getContext('2d');
            Object.assign(SETTINGS, payload.settings);
            // Ensure canvas matches initial settings
            canvas.width = SETTINGS.CANVAS_WIDTH;
            canvas.height = SETTINGS.CANVAS_HEIGHT;
            // Theme colors if passed
            if (payload.theme) {
                Object.assign(COLORS, payload.theme);
            }
            if (payload.bushSprites) {
                bushSprites = payload.bushSprites;
            }
            highScore = payload.highScore || 0;
            initVisuals();
            lastTime = Date.now();
            loop();
            break;

        case 'THEME_UPDATE':
            if (payload) {
                // Only update keys that exist in payload to avoid overwriting with undefined
                // If payload is the full theme object, just assign
                Object.assign(COLORS, payload);
                // Force a recalculate of CURRENT_COLORS immediately if needed
                CURRENT_COLORS = calculateDayNightColors(gameTime, COLORS);
                // Also update bg immediately if static
                COLORS.bg = CURRENT_COLORS.sky;
            }
            break;

        case 'SETTINGS':
            const oldSettings = { ...SETTINGS };
            Object.assign(SETTINGS, payload);
            if (payload.highScore !== undefined) highScore = payload.highScore;

            // Check if visual settings changed, if so, re-init visuals
            const visualKeys = [
                'TREES_DENSITY', 'TREES_SIZE', 'TREES_LAYERS',
                'CLOUDS_DENSITY', 'CLOUDS_SIZE', 'CLOUDS_LAYERS',
                'STARS_DENSITY', 'STARS_SIZE', 'STARS_LAYERS',
                'BUSHES_DENSITY', 'BUSHES_SIZE', 'BUSHES_LAYERS',
                'ENABLE_TREES', 'ENABLE_CLOUDS', 'ENABLE_STARS', 'ENABLE_BUSHES'
            ];
            const shouldReInit = visualKeys.some(k => payload[k] !== undefined && payload[k] !== oldSettings[k]);

            if (shouldReInit) {
                initVisuals();
            }
            break;

        case 'RESIZE':
            if (canvas && payload.width && payload.height) {
                canvas.width = payload.width;
                canvas.height = payload.height;
                SETTINGS.CANVAS_WIDTH = payload.width;
                SETTINGS.CANVAS_HEIGHT = payload.height;
                // Re-init visuals if needed (e.g. generate more trees/clouds to fill new width)
                initVisuals();
                // Force a draw immediately
                draw();
            }
            break;

        case 'INPUT':
            handleInput(payload.action);
            break;

        case 'RESET_SCORE':
            highScore = 0;
            break;



        case 'STOP':
            cancelAnimationFrame(animationId);
            break;
    }
};
