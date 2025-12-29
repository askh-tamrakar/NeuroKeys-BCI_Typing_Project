/* eslint-disable no-restricted-globals */

// Game Constants (Defaults, will be overridden by settings)
let SETTINGS = {
    GRAVITY: 0.4,
    JUMP_STRENGTH: -10,
    GROUND_OFFSET: 60,
    DINO_WIDTH: 44,
    DINO_HEIGHT: 47,
    OBSTACLE_WIDTH: 20,
    OBSTACLE_MIN_HEIGHT: 40,
    OBSTACLE_MAX_HEIGHT: 60,
    GAME_SPEED: 5, // Derived
    SPAWN_INTERVAL: 1150,
    CANVAS_WIDTH: 800,
    CANVAS_HEIGHT: 376,
    CYCLE_DURATION: 100,
    JUMP_DISTANCE: 150,
    ENABLE_TREES: true,
};

// Game State
let canvas = null;
let ctx = null;
let animationId = null;
let lastTime = 0;

let gameState = 'ready'; // ready, playing, paused, gameOver
let score = 0;
let highScore = 0;
let dinoY = 0;
let velocity = 0;
let obstacles = [];
let lastSpawnTimestamp = 0;
let distance = 0;
let gameTime = 0; // 0-1 for day/night cycle

// Visuals State
let clouds = [];
let trees = [];
let stars = [];

// Eye State (for animation)
let eyeState = 'open'; // open, blink, double-blink
let eyeStateTimer = null;

// --- Initialization ---

function initVisuals() {
    // Init clouds
    clouds = [];
    for (let i = 0; i < 15; i++) {
        const depth = 0.15 + Math.random() * 0.85;
        clouds.push({
            x: Math.random() * SETTINGS.CANVAS_WIDTH,
            y: Math.random() * 150 + 20,
            width: (60 + Math.random() * 40) * depth,
            speed: (0.1 + Math.random() * 0.1) * depth,
            depth: depth
        });
    }
    clouds.sort((a, b) => a.depth - b.depth);

    // Init trees
    trees = [];
    const treeCount = Math.floor(SETTINGS.CANVAS_WIDTH / 60) + 5;
    for (let i = 0; i < treeCount; i++) {
        const depth = 0.4 + Math.random() * 0.6;
        const scale = depth;
        trees.push({
            x: Math.random() * SETTINGS.CANVAS_WIDTH * 1.2,
            height: (50 + Math.random() * 70) * scale,
            width: (25 + Math.random() * 25) * scale,
            type: Math.random() > 0.5 ? 'round' : 'pine',
            depth: depth,
            speedFactor: 0.5 * depth
        });
    }
    trees.sort((a, b) => a.depth - b.depth);

    // Init stars
    stars = [];
    for (let i = 0; i < 50; i++) {
        stars.push({
            x: Math.random() * SETTINGS.CANVAS_WIDTH,
            y: Math.random() * SETTINGS.CANVAS_HEIGHT / 2,
            size: Math.random() * 2 + 1,
            blinkOffset: Math.random() * Math.PI
        });
    }
}

// --- Logic ---

function resetGame() {
    gameState = 'playing';
    score = 0;
    dinoY = 0;
    velocity = 0;
    obstacles = [];
    lastSpawnTimestamp = Date.now();
    distance = 0;
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

        if (gameState === 'playing') gameState = 'paused';
        else if (gameState === 'paused') gameState = 'playing';
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

        // Score
        score += 1 * timeFactor; // Score based on distance/time

        // Collisions
        const groundY = SETTINGS.CANVAS_HEIGHT - SETTINGS.GROUND_OFFSET;
        const dinoX = 75;
        const dinoLeft = dinoX + 10;
        const dinoRight = dinoX + SETTINGS.DINO_WIDTH - 10;
        const dinoTop = groundY - SETTINGS.DINO_HEIGHT - dinoY + 5;
        const dinoBottom = groundY - dinoY - 5;

        for (const obs of obstacles) {
            const obsLeft = obs.x + 5;
            const obsRight = obs.x + obs.width - 5;
            const obsTop = groundY - obs.height;
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

        // Day/Night Cycle
        gameTime = (gameTime + deltaTime / (SETTINGS.CYCLE_DURATION * 1000)) % 1.0;

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
    accent: '#3b82f6'
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
    ctx.fillStyle = COLORS.bg; // Or dynamic sky color
    ctx.fillRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height + 100;
    const radius = width * 0.6;

    // Sun
    if (gameTime > 0.05 && gameTime < 0.65) {
        const sunAngle = ((gameTime - 0.1) / 0.5) * Math.PI;
        const sunX = centerX - Math.cos(sunAngle) * radius;
        const sunY = centerY - Math.sin(sunAngle) * radius * 0.9;
        drawBlockyCircle(sunX, sunY, 14, COLORS.primary, 4);
    }

    // Moon
    if (gameTime > 0.55 || gameTime < 0.15) {
        let moonTime = gameTime - 0.6;
        if (moonTime < 0) moonTime += 1;
        const moonAngle = (moonTime / 0.5) * Math.PI;
        const moonX = centerX - Math.cos(moonAngle) * radius;
        const moonY = centerY - Math.sin(moonAngle) * radius * 0.9;
        drawBlockyCircle(moonX, moonY, 12, COLORS.text, 4);
        ctx.fillStyle = COLORS.bg;
        ctx.fillRect(moonX - 12, moonY - 8, 8, 8);
        ctx.fillRect(moonX + 4, moonY + 8, 4, 4);
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
                ctx.fillRect(star.x, star.y, s * 2, s * 2);
            }
        });
        ctx.globalAlpha = 1.0;
    }

    // Clouds
    ctx.fillStyle = COLORS.muted;
    ctx.globalAlpha = 0.4;
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
    ctx.fillStyle = COLORS.muted;
    ctx.globalAlpha = 0.5;
    trees.forEach(tree => {
        const tx = Math.floor(tree.x);
        const ty = Math.floor(groundY - tree.height);
        const tw = Math.floor(tree.width);
        const th = Math.floor(tree.height);

        if (tx + tw > 0 && tx < width) {
            const trunkW = Math.max(4, Math.floor(tw * 0.3));
            ctx.fillRect(Math.floor(tx + (tw - trunkW) / 2), ty + Math.floor(th * 0.5), trunkW, Math.floor(th * 0.5));
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

function drawDino(x, y) {
    const { DINO_WIDTH, DINO_HEIGHT } = SETTINGS;
    const scaleX = DINO_WIDTH / 44;
    const scaleY = DINO_HEIGHT / 47;

    ctx.save();
    ctx.fillStyle = COLORS.primary;

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
    ctx.fillStyle = COLORS.primary;
    const legOffset = Math.floor(Date.now() / 100) % 2 === 0 ? 0 : 2;
    ctx.fillRect(Math.floor(x + 24 * scaleX), Math.floor(y + 37 * scaleY), Math.ceil(4 * scaleX), Math.ceil((10 - legOffset) * scaleY));
    ctx.fillRect(Math.floor(x + 14 * scaleX), Math.floor(y + 37 * scaleY), Math.ceil(4 * scaleX), Math.ceil((10 + legOffset) * scaleY));

    // Arms
    ctx.fillRect(Math.floor(x + 28 * scaleX), Math.floor(y + 24 * scaleY), Math.ceil(2 * scaleX), Math.ceil(6 * scaleY));

    ctx.restore();
}

function drawCactus(x, y, width, height) {
    ctx.save();
    ctx.fillStyle = COLORS.primary; // Cactus color (using primary/green-ish usually, but using theme primary here)

    const trunkWidth = Math.floor(width * 0.6);
    const trunkX = Math.floor(x + (width - trunkWidth) / 2);

    // Main Trunk
    ctx.fillRect(trunkX, y, trunkWidth, height);

    // Left Arm
    if (height > 30) {
        const armY = y + Math.floor(height * 0.4);
        const armH = Math.floor(height * 0.25);
        const armW = Math.floor(width * 0.2);
        ctx.fillRect(trunkX - armW, armY + armH / 2, armW, armH / 2); // connector
        ctx.fillRect(trunkX - armW, armY, armW, armH); // upright
    }

    // Right Arm
    if (height > 45) {
        const armY = y + Math.floor(height * 0.2);
        const armH = Math.floor(height * 0.2);
        const armW = Math.floor(width * 0.2);
        ctx.fillRect(trunkX + trunkWidth, armY + armH / 2, armW, armH / 2); // connector
        ctx.fillRect(trunkX + trunkWidth + armW - armW, armY - armH / 2, armW, armH); // upright
    }

    ctx.restore();
}

function draw() {
    if (!ctx) return;

    const width = SETTINGS.CANVAS_WIDTH;
    const height = SETTINGS.CANVAS_HEIGHT;
    const groundY = height - SETTINGS.GROUND_OFFSET;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Background
    drawSky(width, height);
    drawTrees(width, groundY);

    // Ground
    ctx.fillStyle = COLORS.surface;
    ctx.fillRect(0, Math.floor(groundY), width, height - groundY);
    ctx.fillStyle = COLORS.border;
    ctx.fillRect(0, Math.floor(groundY), width, 10);

    // Terrain pattern
    const offset = distance % 100;
    ctx.fillStyle = COLORS.muted;
    for (let i = -100; i < width + 100; i += 50) {
        ctx.fillRect(Math.floor(i - offset + 10), Math.floor(groundY + 15), 10, 8);
    }

    // Dino
    const dinoYPos = groundY - SETTINGS.DINO_HEIGHT + dinoY;
    drawDino(75, dinoYPos);

    // Obstacles
    obstacles.forEach(obs => {
        drawCactus(obs.x, groundY - obs.height, obs.width, obs.height);
    });

    // Score & UI
    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 20px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`Score: ${Math.floor(score / 10)}`, width - 20, 40);
    ctx.fillText(`HI: ${Math.floor(highScore / 10)}`, width - 20, 70);

    if (gameState === 'ready') {
        ctx.textAlign = 'center';
        ctx.font = 'bold 24px sans-serif';
        ctx.fillText('Blink to Start!', width / 2, height / 2 - 20);
    } else if (gameState === 'gameOver') {
        ctx.textAlign = 'center';
        ctx.font = 'bold 24px sans-serif';
        ctx.fillStyle = COLORS.primary;
        ctx.fillText('GAME OVER!', width / 2, height / 2 - 20);
        ctx.fillStyle = COLORS.text;
        ctx.font = '16px sans-serif';
        ctx.fillText('Blink to restart', width / 2, height / 2 + 20);
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
            // Theme colors if passed
            if (payload.theme) {
                Object.assign(COLORS, payload.theme);
            }
            highScore = payload.highScore || 0;
            initVisuals();
            lastTime = Date.now();
            loop();
            break;

        case 'SETTINGS':
            Object.assign(SETTINGS, payload);
            if (payload.highScore !== undefined) highScore = payload.highScore;
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
