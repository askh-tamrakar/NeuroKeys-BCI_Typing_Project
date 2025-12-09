"""
run_eog.py
--------------------------------
Runs EOG-only processing using:
- acquisition.serial_reader
- acquisition.packet_parser
- processing.filter_router
- processing.eog

Automatically routes ONLY EOG channels into the EOG filter pipeline.

Run:
    python run_eog.py
"""

import time
from datetime import datetime

# Acquisition modules
from acquisition.serial_reader import SerialPacketReader
from acquisition.packet_parser import PacketParser
from acquisition.packet_config import PacketConfig

# Router + Filters
from processing.filter_router import FilterRouter


def main():
    print("\n===== EOG PROCESSING PIPELINE STARTED =====\n")

    # Load configuration
    cfg = PacketConfig()

    # Create acquisition system
    reader = SerialPacketReader(
        port="COM5",                   # Change if needed
        baud=cfg.BAUD_RATE,
        packet_config=cfg
    )

    parser = PacketParser(cfg)

    # Create filter router with ONLY EOG active
    router = FilterRouter(active_filters=["EOG"])

    # Connect to hardware
    if not reader.connect():
        print("❌ Serial connection failed.")
        return

    reader.start()
    print("🔌 Serial acquisition started.\n")
    print("📡 Waiting for EOG packets...\n")

    try:
        while True:

            raw_packet = reader.get_packet(timeout=0.1)
            if raw_packet is None:
                continue

            # Convert binary packet → dictionary
            pkt = parser.parse(raw_packet)

            # Prepare sample
            sample = {
                "timestamp": datetime.now().isoformat(),
                "channels": {
                    "ch0": {
                        "raw": pkt.ch0_raw,
                        "signal_type": "EOG"
                    },
                    "ch1": {
                        "raw": pkt.ch1_raw,
                        "signal_type": "EOG"
                    }
                }
            }

            # Route EOG data
            processed = router.route(sample)

            # Print filtered EOG results
            if processed["EOG"]:
                print("EOG:", processed["EOG"])

    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")

    finally:
        reader.stop()
        reader.disconnect()
        print("🔌 Serial disconnected.")
        print("===== EOG PROCESSING COMPLETE =====")


if __name__ == "__main__":
    main()
