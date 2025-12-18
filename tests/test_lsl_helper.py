"""
lsl_helpers.py
---------------
Robust helpers for discovering, opening, and parsing LSL streams.

Upgraded Features:
✔ Safe extraction of channel names/types from metadata
✔ Fallbacks for missing or malformed LSL metadata
✔ Utility to wait & open a stream (with timeout)
✔ Build routing table used by filter_router.py
✔ Channel lookup helper
✔ Marker stream helpers (future use)
"""

from typing import List, Dict, Optional

try:
    from pylsl import StreamInfo, StreamInlet, resolve_byprop
except ImportError:
    StreamInfo = None
    StreamInlet = None
    resolve_byprop = None
    print("⚠️ pylsl not installed — lsl_helpers will be limited.")


# ----------------------------------------------------------------------
# INTERNAL SAFE HELPERS
# ----------------------------------------------------------------------

def _safe_str(val, default="UNKNOWN"):
    """Convert to string safely."""
    try:
        if val is None:
            return default
        return str(val)
    except Exception:
        return default


def _safe_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default


# ----------------------------------------------------------------------
# CHANNEL METADATA EXTRACTION
# ----------------------------------------------------------------------

def get_channel_names(info: "StreamInfo") -> List[str]:
    """Extract channel labels safely."""
    try:
        channels = info.desc().child("channels").first_child()
    except Exception:
        return []

    out = []
    idx = 0

    while channels and channels.name() == "channel":
        label = channels.child_value("label")
        out.append(label if label else f"ch_{idx}")
        idx += 1
        channels = channels.next_sibling()

    return out


def get_channel_types(info: "StreamInfo") -> List[str]:
    """Extract channel types (EMG/EOG/EEG/etc.) with safety."""
    try:
        channels = info.desc().child("channels").first_child()
    except Exception:
        return []

    out = []
    idx = 0

    while channels and channels.name() == "channel":
        ch_type = channels.child_value("type") or "UNKNOWN"
        out.append(ch_type)
        idx += 1
        channels = channels.next_sibling()

    return out


def get_sampling_rate(info: "StreamInfo") -> float:
    try:
        return info.nominal_srate()
    except Exception:
        return 0.0


# ----------------------------------------------------------------------
# METADATA DICTIONARY (USED BY ROUTER)
# ----------------------------------------------------------------------

def get_stream_metadata(info: "StreamInfo") -> Dict:
    """Return all useful metadata as a dict."""
    return {
        "name": _safe_str(info.name()),
        "type": _safe_str(info.type()),
        "source_id": _safe_str(info.source_id()),
        "srate": get_sampling_rate(info),
        "channel_count": _safe_int(info.channel_count()),
        "channel_names": get_channel_names(info),
        "channel_types": get_channel_types(info),
    }


# ----------------------------------------------------------------------
# DISCOVERY / CONNECTION
# ----------------------------------------------------------------------

def wait_for_stream(name: str, timeout: float = 5.0) -> Optional["StreamInlet"]:
    """
    Blocking wait for an LSL stream by name.
    Returns StreamInlet or None on timeout.
    """
    if resolve_byprop is None:
        return None

    import time
    start = time.time()

    while time.time() - start < timeout:
        found = resolve_byprop("name", name, timeout=0.2)
        if found:
            return StreamInlet(found[0])

    return None


def resolve_and_open_stream(name: str, timeout: float = 6.0) -> Optional["StreamInlet"]:
    """
    Higher-level wrapper to:
    - wait for stream
    - open inlet
    - validate metadata
    """
    inlet = wait_for_stream(name, timeout=timeout)

    if inlet is None:
        print(f"❌ No LSL stream named '{name}' found.")
        return None

    try:
        info = inlet.info()
        names = get_channel_names(info)
        types = get_channel_types(info)

        if not names or not types:
            print("⚠️ Warning: LSL stream missing full metadata (labels/types).")

        print(f"✅ Connected to LSL stream '{info.name()}' ({info.type()})")
        return inlet

    except Exception as e:
        print(f"❌ Failed to open stream inlet: {e}")
        return None


# ----------------------------------------------------------------------
# ROUTING TABLE CREATION (USED BY filter_router.py)
# ----------------------------------------------------------------------

def build_channel_route(info: "StreamInfo") -> Dict[int, Dict]:
    """
    Builds routing metadata dictionary for each channel:
    {
        0: {"name": "EMG_0", "type": "EMG"},
        1: {"name": "EOG_1", "type": "EOG"},
        ...
    }
    """
    names = get_channel_names(info)
    types = get_channel_types(info)
    count = min(len(names), len(types))

    route = {}

    for idx in range(count):
        route[idx] = {
            "name": names[idx],
            "type": types[idx],
        }

    return route


# ----------------------------------------------------------------------
# CHANNEL LOOKUP UTIL (for run_emg, run_eog, etc.)
# ----------------------------------------------------------------------

def safe_get_channel(info: "StreamInfo", target_type: str) -> List[int]:
    """
    Returns indices of channels matching a given type.
    Example:
        safe_get_channel(info, "EMG")  → [0, 2]
    """
    types = get_channel_types(info)
    out = [idx for idx, t in enumerate(types) if t.upper() == target_type.upper()]
    return out

