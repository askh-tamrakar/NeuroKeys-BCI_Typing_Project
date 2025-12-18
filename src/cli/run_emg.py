"""
run_emg.py
--------------------------------
Runs EMG-only processing using:
- acquisition.serial_reader
- acquisition.packet_parser
- processing.filter_router
- processing.emgenvelope

This script subscribes to ALL channels coming from acquisition,
but automatically routes ONLY EMG channels to the EMG filter.

Run:
    python run_emg.py
"""

import time
from datetime import datetime

# Acquisition Modules
from acquisition.serial_reader import SerialPacketReader
from acquisition.packet_parser import PacketParser

# Router + Filters
from processing.filter_router import FilterRouter

# Packet configuration
from acquisition.packet_config import PacketConfig


def main():
    print("\n===== EMG PROCESSING PIPELINE STARTED =====\n")

    # Load acquisition config
    cfg = PacketConfig()

    # Create acquisition objects
    reader = SerialPacketReader(
        port="COM5",
        baud=cfg.BAUD_RATE,
        packet_config=cfg
    )

    parser = PacketParser(cfg)

    # Create filter router with ONLY EMG active
    router = FilterRouter(active_filters=["EMG"])

    # Connect to hardware
    if not reader.connect():
        print("❌ Failed to connect to serial device.")
        return

    reader.start()
    print("🔌 Serial acquisition started.\n")

    print("📡 Waiting for EMG packets...\n")

    try:
        while True:
            raw_packet = reader.get_packet(timeout=0.1)
            if raw_packet is None:
                continue

            # Parse → get values
            pkt = parser.parse(raw_packet)

            # Convert to dict for router
            sample = {
                "timestamp": datetime.now().isoformat(),
                "channels": {
                    "ch0": {
                        "raw": pkt.ch0_raw,
                        "signal_type": "EMG"   # Force-mapped here
                    },
                    "ch1": {
                        "raw": pkt.ch1_raw,
                        "signal_type": "EMG"
                    }
                }
            }

            # Route into EMG filter pipeline
            processed = router.route(sample)

            # If filtered data available → print
            if processed["EMG"]:
                print("EMG:", processed["EMG"])

    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")

    finally:
        reader.stop()
        reader.disconnect()
        print("🔌 Serial disconnected.")
        print("===== EMG PROCESSING COMPLETE =====")


if __name__ == "__main__":
    main()
