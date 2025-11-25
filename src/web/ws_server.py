import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio, json, joblib
# src/web/ws_server.py
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import joblib
import numpy as np
import websockets

# local import - ensure Python path is set so this resolves (run from project root or use PYTHONPATH)
from preprocessing.features import extract_features

# --- CONFIG ---
HOST = "0.0.0.0"
PORT = 8765
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "simple_rf.joblib")
# Set to True after you have a trained model at MODEL_PATH
LOAD_MODEL = False

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ws_server")

# --- model (loaded lazily) ---
_model = None  # type: Optional[Any]


def load_model(path: str) -> Optional[Any]:
    if not LOAD_MODEL:
        logger.info("Model loading disabled (LOAD_MODEL=False). Running in NOMODEL mode.")
        return None
    if not os.path.exists(path):
        logger.warning("Model path does not exist: %s", path)
        return None
    try:
        m = joblib.load(path)
        logger.info("Loaded model from %s", path)
        return m
    except Exception as e:
        logger.exception("Failed to load model: %s", e)
        return None


async def run_feature_extraction(data: np.ndarray, fs: float) -> np.ndarray:
    """
    Offload feature extraction to a thread so we don't block the event loop.
    """
    return await asyncio.to_thread(extract_features, data, fs)


async def run_model_predict_proba(model: Any, feats: np.ndarray) -> Dict[str, Any]:
    """
    Offload model inference to a thread. Returns dict with 'label' and 'prob'.
    """
    if model is None:
        return {"label": "NOMODEL", "prob": 0.0}
    # Use to_thread to call sklearn-like predict_proba safely
    probs = await asyncio.to_thread(model.predict_proba, feats)
    probs = probs[0]
    classes = getattr(model, "classes_", None)
    if classes is None:
        # fallback: use argmax index
        idx = int(np.argmax(probs))
        label = str(idx)
    else:
        label = str(classes[int(np.argmax(probs))])
    confidence = float(np.max(probs))
    return {"label": label, "prob": confidence}


async def handler(ws: websockets.WebSocketServerProtocol, path: str) -> None:
    """
    Expected incoming payload (JSON):
    {
        "data": [[ch1_sample1, ch2_sample1, ...], [ch1_sample2, ch2_sample2, ...], ...],
        "fs": 250,
        "modality": "EEG"  # optional
    }
    """
    logger.info("Client connected: %s", ws.remote_address)
    try:
        async for msg in ws:
            try:
                payload = json.loads(msg)
                raw = payload.get("data")
                if raw is None:
                    raise ValueError("missing 'data' field in payload")

                # ensure numpy array; expecting shape (n_samples, n_channels) or similar
                data = np.array(raw)
                fs = float(payload.get("fs", 250))

                # extract features in background thread
                feats = await run_feature_extraction(data, fs)
                feats = np.asarray(feats).reshape(1, -1)

                # model inference in background thread
                pred = await run_model_predict_proba(_model, feats)

                # timestamp in ms (wall-clock)
                timestamp_ms = int(time.time() * 1000)

                out = {
                    "source": payload.get("modality", "unknown"),
                    "pred": {"label": pred["label"], "prob": pred["prob"]},
                    "timestamp": timestamp_ms,
                }
                await ws.send(json.dumps(out))
            except Exception as e:
                logger.exception("Error handling message: %s", e)
                await ws.send(json.dumps({"error": str(e)}))
    except websockets.ConnectionClosedOK:
        logger.info("Connection closed normally: %s", ws.remote_address)
    except websockets.ConnectionClosedError as e:
        logger.warning("Connection closed with error: %s -- %s", ws.remote_address, e)
    except Exception as e:
        logger.exception("Unhandled handler exception: %s", e)
    finally:
        logger.info("Client disconnected: %s", ws.remote_address)


async def main() -> None:
    global _model
    _model = load_model(MODEL_PATH)

    logger.info("Starting WebSocket server on %s:%d", HOST, PORT)
    # Use async context manager so the server shuts down cleanly on cancellation
    async with websockets.serve(handler, HOST, PORT):
        logger.info("WebSocket server listening on %s:%d", HOST, PORT)
        # run forever until cancelled
        await asyncio.Future()


if __name__ == "__main__":
    # On Windows sometimes selector policy is needed for compatibility with some libs;
    # asyncio.run(...) is the recommended way to start the loop.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received; exiting.")
    except Exception:
        logger.exception("Fatal error in server.")
