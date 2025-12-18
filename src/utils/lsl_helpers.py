"""
lsl_helpers.py
---------------
Utility helpers for extracting metadata from LSL streams.
Used by filter_router and processing modules.

Features:
✔ Extract channel names
✔ Extract channel types
✔ Extract sampling rate and stream metadata
✔ Safe-access helpers with graceful fallback
"""

from typing import List, Dict, Optional

try:
    from pylsl import StreamInfo, StreamInlet
except ImportError:
    StreamInfo = None
    StreamInlet = None
    print("⚠️ pylsl not installed — lsl_helpers will be inert.")


# -----------------------------------------------------------
# METADATA EXTRACTION HELPERS
# -----------------------------------------------------------

def get_channel_names(info: "StreamInfo") -> List[str]:
    """
    Extract channel labels from LSL stream metadata.
    """
    try:
        ch = info.desc().child("channels").first_child()
        names = []

        while ch.name() == "channel":
            label = ch.child_value("label")
            names.append(label if label else f"ch_{len(names)}")
            ch = ch.next_sibling()

        return names

    except Exception:
        return []


def get_channel_types(info: "StreamInfo") -> List[str]:
    """
    Extract channel types (EMG/EOG/EEG/etc.)
    """
    try:
        ch = info.desc().child("channels").first_child()
        types = []

        while ch.name() == "channel":
            ch_type = ch.child_value("type")
            types.append(ch_type if ch_type else "UNKNOWN")
            ch = ch.next_sibling()

        return types

    except Exception:
        return []


def get_sampling_rate(info: "StreamInfo") -> float:
    """
    Returns nominal sampling rate.
    """
    try:
        return info.nominal_srate()
    except Exception:
        return 0.0


def get_stream_metadata(info: "StreamInfo") -> Dict:
    """
    Extract key stream metadata into a dict.
    """
    return {
        "name": info.name() if info else None,
        "type": info.type() if info else None,
        "source_id": info.source_id() if info else None,
        "channel_count": info.channel_count() if info else None,
        "srate": get_sampling_rate(info),
        "channel_names": get_channel_names(info),
        "channel_types": get_channel_types(info),
    }


# -----------------------------------------------------------
# SIMPLE VALIDATION HELPERS
# -----------------------------------------------------------

def has_required_metadata(info: "StreamInfo") -> bool:
    """
    Validate that channel labels + channel types are present.
    """
    try:
        names = get_channel_names(info)
        types = get_channel_types(info)
        return len(names) > 0 and len(types) > 0
    except Exception:
        return False


def wait_for_stream(name: str, timeout: float = 5.0) -> Optional["StreamInlet"]:
    """
    Wait until an LSL stream appears with the given name.
    Returns a StreamInlet or None if timeout.
    """
    if StreamInfo is None:
        return None

    import time
    from pylsl import resolve_byprop, StreamInlet

    t0 = time.time()
    inlet = None

    while time.time() - t0 < timeout:
        results = resolve_byprop("name", name, timeout=0.2)
        if results:
            inlet = StreamInlet(results[0])
            break

    return inlet


# -----------------------------------------------------------
# ROUTING HELPER USED BY filter_router
# -----------------------------------------------------------

def build_channel_route(info: "StreamInfo") -> Dict[int, Dict]:
    """
    Build a per-channel routing metadata dictionary.

    Example output:
    {
        0: { "name": "EEG_0", "type": "EEG" },
        1: { "name": "EOG_1", "type": "EOG" }
    }
    """
    names = get_channel_names(info)
    types = get_channel_types(info)

    route = {}
    for idx, (label, ch_type) in enumerate(zip(names, types)):
        route[idx] = {
            "name": label,
            "type": ch_type,
        }

    return route
