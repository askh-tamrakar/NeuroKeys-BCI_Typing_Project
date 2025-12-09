"""
test_parser.py
--------------
A JSON-based metadata parser for testing channel configurations.

This script validates and prints:
✔ Channel definitions
✔ Filter definitions
✔ Mapping between channels and filters
✔ Required fields (type, filters, bandpass, notch, etc.)

Run:
    python test_parser.py
"""

import json
import os
from pathlib import Path

CONFIG_PATH = Path("src/utils/sensor_config.json")


# -----------------------------------------------------
# JSON LOADER
# -----------------------------------------------------
def load_json_config(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        return json.load(f)


# -----------------------------------------------------
# VALIDATION HELPERS
# -----------------------------------------------------
def validate_channel_structure(ch_id, ch_data):
    required = ["type", "filters"]

    for key in required:
        if key not in ch_data:
            raise ValueError(f"Channel {ch_id} missing required field '{key}'")

    if not isinstance(ch_data["filters"], list):
        raise TypeError(f"Channel {ch_id} filters must be a list")

    print(f"✔ Channel {ch_id} validated")


def validate_filter_structure(name, fdata):
    if "type" not in fdata:
        raise ValueError(f"Filter '{name}' missing filter type")

    if fdata["type"] == "bandpass":
        if not all(k in fdata for k in ("low", "high")):
            raise ValueError(f"Bandpass filter '{name}' missing low/high")

    if fdata["type"] == "notch":
        if not all(k in fdata for k in ("freq", "q")):
            raise ValueError(f"Notch filter '{name}' missing freq/q")

    print(f"✔ Filter '{name}' validated")


# -----------------------------------------------------
# PARSER - BUILD ROUTE MAP
# -----------------------------------------------------
def parse_to_metadata(config):
    """
    Convert JSON into a structured metadata map:
    {
        channel_id: {
            "type": "EMG",
            "filters": [{"name": "notch_50", ...}, ...]
        }
    }
    """

    channels = config.get("channels", {})
    filters = config.get("filters", {})

    metadata = {}

    for ch_id, ch_data in channels.items():
        validate_channel_structure(ch_id, ch_data)

        filt_list = []
        for fname in ch_data["filters"]:
            if fname not in filters:
                raise ValueError(f"Filter '{fname}' referenced by channel {ch_id} not found in filters")

            validate_filter_structure(fname, filters[fname])
            filt_list.append({
                "name": fname,
                **filters[fname]
            })

        metadata[int(ch_id)] = {
            "type": ch_data["type"],
            "filters": filt_list
        }

    return metadata


# -----------------------------------------------------
# MAIN EXECUTION (for manual testing)
# -----------------------------------------------------
if __name__ == "__main__":
    print("📄 Loading sensor_config.json...\n")

    config = load_json_config(CONFIG_PATH)

    print("🔍 Parsing and validating config...\n")
    metadata = parse_to_metadata(config)

    print("\n======================================")
    print(" FINAL PARSED METADATA (TEST OUTPUT)")
    print("======================================\n")

    for ch_id, info in metadata.items():
        print(f"Channel {ch_id}:")
        print(f"  Type: {info['type']}")
        print(f"  Filters:")
        for f in info["filters"]:
            print(f"    - {f['name']} ({f['type']}) | params: "
                  f"{ {k: v for k, v in f.items() if k not in ['name','type']} }")
        print()
