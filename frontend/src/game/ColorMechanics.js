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
        moonDay, moonNight
    } = themeColors;

    let t = 0;

    // Default: Night
    let sky = night;
    let tree = treeNight;
    let cloud = cloudNight;
    let sun = sunNight; // Sunset color
    let moon = moonNight;

    // Transition Logic
    if (time >= 0.05 && time < 0.20) {
        // Sunrise (Night -> Day)
        t = (time - 0.05) / 0.15;
        sky = lerpColor(night, day, t);
        tree = lerpColor(treeNight, treeDay, t);
        cloud = lerpColor(cloudNight, cloudDay, t);
        sun = lerpColor(sunNight, sunDay, t);
        moon = lerpColor(moonNight, moonDay, t);
    }
    else if (time >= 0.20 && time < 0.55) {
        // Day
        sky = day;
        tree = treeDay;
        cloud = cloudDay;
        sun = sunDay;
        moon = moonDay;
    }
    else if (time >= 0.55 && time < 0.70) {
        // Sunset (Day -> Night)
        t = (time - 0.55) / 0.15;
        sky = lerpColor(day, night, t);
        tree = lerpColor(treeDay, treeNight, t);
        cloud = lerpColor(cloudDay, cloudNight, t);
        // Sun turns from bright to orange/red
        sun = lerpColor(sunDay, sunNight, t);
        moon = lerpColor(moonDay, moonNight, t);
    }
    else {
        // Night
        sky = night;
        tree = treeNight;
        cloud = cloudNight;
        sun = sunNight;
        moon = moonNight;
    }

    return { sky, tree, cloud, sun, moon };
}
