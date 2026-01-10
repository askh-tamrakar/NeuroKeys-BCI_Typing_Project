/**
 * ColorMechanics.js
 * Handles day/night cycle color transitions for the Dino game.
 */

// Helper: Linear Interpolation for Hex Colors
export function lerpColor(a, b, amount) {
    const ah = parseInt(a.replace(/#/g, ''), 16),
        ar = ah >> 16, ag = ah >> 8 & 0xff, ab = ah & 0xff,
        bh = parseInt(b.replace(/#/g, ''), 16),
        br = bh >> 16, bg = bh >> 8 & 0xff, bb = bh & 0xff,
        rr = ar + amount * (br - ar),
        rg = ag + amount * (bg - ag),
        rb = ab + amount * (bb - ab);

    return '#' + ((1 << 24) + (rr << 16) + (rg << 8) + rb | 0).toString(16).slice(1);
}

// Calculate all element colors based on game time
export function calculateDayNightColors(time, themeColors) {
    const {
        day, night,
        treeDay, treeNight,
        cloudDay, cloudNight,
        sunDay, sunNight,
        moonDay, moonNight,
        dinoDay, dinoNight,
        obstacleDay, obstacleNight,
        groundDay, groundNight,
        groundLineDay, groundLineNight,
        skyDay, skyNight
    } = themeColors;

    let t = 0;

    // Default: Night
    // Use explicit sky vars if available, else fallback to day/night (generic)
    const sDay = skyDay || day;
    const sNight = skyNight || night;

    let sky = sNight;
    let tree = treeNight;
    let cloud = cloudNight;
    let sun = sunNight;
    let moon = moonNight;

    // Instant Switch Logic for Gameplay Elements (No Fading)
    // Day Phase is roughly 0.2 to 0.7 (including transitions)
    // We'll switch comfortably once sky starts brightening to ensure contrast is valid
    // using a simpler threshold than the full fade window
    const isDay = (time >= 0.18 && time < 0.62);

    let dino = isDay ? (dinoDay || '#2C2C2C') : (dinoNight || '#ffffff');
    let obstacle = isDay ? (obstacleDay || '#5D4037') : (obstacleNight || '#8D6E63');
    let ground = isDay ? (groundDay || '#e0e0e0') : (groundNight || '#1b1b1b');
    let groundLine = isDay ? (groundLineDay || '#5D4037') : (groundLineNight || '#8D6E63');

    // Transition Logic for Environment (Sky, Trees, Clouds, Celestial)
    if (time >= 0.05 && time < 0.20) {
        // Sunrise (Night -> Day)
        t = (time - 0.05) / 0.15;
        sky = lerpColor(sNight, sDay, t);
        tree = lerpColor(treeNight, treeDay, t);
        cloud = lerpColor(cloudNight, cloudDay, t);
        sun = lerpColor(sunNight, sunDay, t);
        moon = lerpColor(moonNight, moonDay, t);
    }
    else if (time >= 0.20 && time < 0.55) {
        // Day
        sky = sDay;
        tree = treeDay;
        cloud = cloudDay;
        sun = sunDay;
        moon = moonDay;
    }
    else if (time >= 0.55 && time < 0.70) {
        // Sunset (Day -> Night)
        t = (time - 0.55) / 0.15;
        sky = lerpColor(sDay, sNight, t);
        tree = lerpColor(treeDay, treeNight, t);
        cloud = lerpColor(cloudDay, cloudNight, t);
        sun = lerpColor(sunDay, sunNight, t);
        moon = lerpColor(moonDay, moonNight, t);
    }
    else {
        // Night
        sky = sNight;
        tree = treeNight;
        cloud = cloudNight;
        sun = sunNight;
        moon = moonNight;
    }

    return { sky, tree, cloud, sun, moon, dino, obstacle, ground, groundLine };
}
