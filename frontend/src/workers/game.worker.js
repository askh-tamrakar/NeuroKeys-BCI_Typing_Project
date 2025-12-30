/* eslint-disable no-restricted-globals */

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
    OBSTACLE_BONUS_FACTOR: 0.1,
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

// --- Initialization ---

// Bush Pixel Matrices (0 = empty, 1 = pixel)
// Removed procedural variants

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

    // Init bushes (Layered Sprites)
    bushes = [];
    if (bushSprites && bushSprites.length > 0) {

        const layers = [
            { count: 5, scale: 0.6, speed: 0.8, yOff: 5, layer: 0 },
            { count: 4, scale: 0.9, speed: 1.0, yOff: 15, layer: 1 },
            { count: 3, scale: 1.2, speed: 1.2, yOff: 25, layer: 2 }
        ];

        layers.forEach(layerConfig => {
            const count = Math.floor(SETTINGS.CANVAS_WIDTH / 150) + layerConfig.count;
            for (let i = 0; i < count; i++) {
                bushes.push({
                    x: Math.random() * SETTINGS.CANVAS_WIDTH,
                    yOffset: layerConfig.yOff,
                    variant: Math.floor(Math.random() * bushSprites.length),
                    scale: layerConfig.scale * (0.9 + Math.random() * 0.2),
                    speedFactor: layerConfig.speed,
                    layer: layerConfig.layer
                });
            }
        });

        // Sort by layer so back draws first
        bushes.sort((a, b) => a.layer - b.layer);
    }

    // Init Visual Bushes (Layers 3 & 4)
    extraBushes = [];
    const extraLayers = [
        { count: 3, scale: 0.5, speed: 0.4, yOff: 0, layer: 3 },
        { count: 2, scale: 1.8, speed: 1.6, yOff: 45, layer: 4 },
        { count: 1, scale: 2.2, speed: 1.95, yOff: 60, layer: 5 }
    ];

    extraLayers.forEach(layerConfig => {
        const count = Math.floor(SETTINGS.CANVAS_WIDTH / 250) + layerConfig.count;
        for (let i = 0; i < count; i++) {
            extraBushes.push({
                x: Math.random() * SETTINGS.CANVAS_WIDTH,
                variant: Math.floor(Math.random() * (bushSprites.length || 1)),
                scale: layerConfig.scale,
                speedFactor: layerConfig.speed,
                yOffset: layerConfig.yOff,
                layer: layerConfig.layer
            });
        }
    });

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
    berry: '#ef4444' // Red berry
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
    const radius = width * 0.6;
    // Ensure the sun/moon arc peaks at y=50 (visible)
    const centerY = Math.max(height + 100, radius * 0.9 + 50);

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
    ctx.fillStyle = COLORS.surface; // Fill with surface color
    ctx.strokeStyle = COLORS.border; // Outline with border color
    ctx.lineWidth = 2;

    // Main trunk
    const trunkWidth = Math.floor(width * 0.6);
    const trunkX = Math.floor(x + (width - trunkWidth) / 2);
    const trunkH = Math.floor(height);
    const _y = Math.floor(y);

    ctx.fillRect(trunkX, _y, trunkWidth, trunkH);
    ctx.strokeRect(trunkX, _y, trunkWidth, trunkH);

    // Left arm
    const armHeight = Math.floor(height * 0.4);
    const armWidth = Math.floor(width * 0.3);
    const leftArmX = Math.floor(trunkX - armWidth);
    const leftArmY = Math.floor(y + height * 0.3);
    const armConnW = Math.floor(trunkWidth * 0.3);

    ctx.fillRect(leftArmX, leftArmY, armWidth, armHeight);
    ctx.strokeRect(leftArmX, leftArmY, armWidth, armHeight);
    ctx.fillRect(leftArmX + armWidth, leftArmY, armConnW, armWidth);
    ctx.strokeRect(leftArmX + armWidth, leftArmY, armConnW, armWidth);

    // Right arm
    const rightArmX = Math.floor(trunkX + trunkWidth);
    const rightArmY = Math.floor(y + height * 0.5);
    const rightArmH = Math.floor(armHeight * 0.8);

    ctx.fillRect(rightArmX, rightArmY, armWidth, rightArmH);
    ctx.strokeRect(rightArmX, rightArmY, armWidth, rightArmH);
    ctx.fillRect(Math.floor(trunkX + trunkWidth * 0.7), rightArmY, armConnW, armWidth);
    ctx.strokeRect(Math.floor(trunkX + trunkWidth * 0.7), rightArmY, armConnW, armWidth);

    ctx.restore();
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
        ctx.fillStyle = COLORS.surface;
        ctx.fillRect(0, Math.floor(groundY), width, height - groundY);
        // Draw the main line in PRIMARY color as requested ("primary color line")
        ctx.fillStyle = COLORS.primary;
        ctx.fillRect(0, Math.floor(groundY), width, 4);

        // Draw Bushes (Standard Layers 0-2)
        drawBushes(groundY);

        // Dino
        const dinoYPos = groundY - SETTINGS.DINO_HEIGHT + dinoY;
        drawDino(75, dinoYPos);

        // Obstacles
        obstacles.forEach(obs => {
            drawCactus(obs.x, groundY - obs.height, obs.width, obs.height);
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
        } else if (gameState === 'gameOver') {
            ctx.textAlign = 'center';
            ctx.font = 'bold 24px sans-serif';
            ctx.fillStyle = COLORS.primary;
            ctx.fillText('GAME OVER!', width / 2, height / 2 - 20);
            ctx.fillStyle = COLORS.text;
            ctx.font = '16px sans-serif';
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

        case 'RESIZE':
            if (canvas) {
                const { width, height } = payload;
                canvas.width = width;
                canvas.height = height;
                SETTINGS.CANVAS_WIDTH = width;
                SETTINGS.CANVAS_HEIGHT = height;
                // Force redraw immediately if paused/ready so it doesn't look broken
                if (gameState !== 'playing') draw();
            }
            break;

        case 'STOP':
            cancelAnimationFrame(animationId);
            break;
    }
};
