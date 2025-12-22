let theme = "day";
document.body.classList.add("day");

const BLINK_THRESHOLD = 0.6;
const DOUBLE_BLINK_TIME = 650;

let lastBlinkTime = 0;
let blinkCount = 0;
let lock = false;

function toggleDayNight() {
  theme = theme === "day" ? "night" : "day";
  document.body.classList.remove("day", "night");
  document.body.classList.add(theme);

  lock = true;
  setTimeout(() => lock = false, 800);
}

function handleEOG(eogValue) {
  if (lock) return;

  if (Math.abs(eogValue) > BLINK_THRESHOLD) {
    const now = Date.now();

    blinkCount = (now - lastBlinkTime < DOUBLE_BLINK_TIME) ? blinkCount + 1 : 1;
    lastBlinkTime = now;

    if (blinkCount === 2) {
      toggleDayNight();
      blinkCount = 0;
    }
  }
}
