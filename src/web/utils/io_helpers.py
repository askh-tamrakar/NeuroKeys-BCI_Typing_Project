# src/utils/io_helpers.py
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env

DATA_ROOT = Path(os.getenv("DATA_ROOT", "./data"))
RAW_DIR = Path(os.getenv("RAW_DIR", str(DATA_ROOT / "raw")))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", str(DATA_ROOT / "processed")))

def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
