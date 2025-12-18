"""
logging_cfg.py
--------------
Centralized logging configuration for the entire EMG/EOG/EEG pipeline.

Features:
✔ Console logging (INFO+)
✔ Rotating file logging for persistent debug logs
✔ Uniform formatting across modules
✔ Optional colorized console output
✔ Thread-safe
"""

import logging
import logging.handlers
import os
from pathlib import Path

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "pipeline.log"

ENABLE_COLORS = True  # Toggle ANSI console colors


# ---------------------------------------------------
# Colored Log Formatter
# ---------------------------------------------------
class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[37m",
        "INFO": "\033[36m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[91m",
    }
    RESET = "\033[0m"

    def format(self, record):
        level = record.levelname
        if ENABLE_COLORS and level in self.COLORS:
            levelname_color = f"{self.COLORS[level]}{level}{self.RESET}"
            record.levelname = levelname_color
        return super().format(record)


# ---------------------------------------------------
# Build Logger
# ---------------------------------------------------
def _build_logger():
    """Create and configure global logger only once."""
    logger = logging.getLogger("biosignals")
    if logger.handlers:  # Already initialized
        return logger

    logger.setLevel(logging.DEBUG)

    # ---- Console ----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    console_format = ColorFormatter(
        "[%(levelname)s] %(asctime)s — %(name)s — %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)

    # ---- Rotating File Handler ----
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=3 * 1024 * 1024,    # 3 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(funcName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)

    # Register
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


# ---------------------------------------------------
# Public Access Function
# ---------------------------------------------------
def get_logger(module_name: str):
    """
    Returns a logger instance bound to a module.

    Usage:
        from utils.logging_cfg import get_logger
        log = get_logger(__name__)
        log.info("Hello!")
    """
    logger = _build_logger()
    return logger.getChild(module_name)
