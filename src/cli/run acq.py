"""
Unified Acquisition Runner
--------------------------
Headless (non-GUI) version of the acquisition pipeline.
This script:

1. Connects to the serial device
2. Reads raw packets
3. Parses them to channel 0 / channel 1
4. Loads sensor_config.json
5. Routes channels through EMG / EOG / EEG filters
6. Streams filtered values through LSL
7. Saves raw + filtered data to JSON

Run:
    python run_acquisition.py
"""

import time
import json
from pathlib import Path
from datetime import datetime

from acquisition.serial_reader import SerialPacketReader
from acquisition.packet_parser import PacketParser
from acquisition.lsl_streams import LSLStreamer
from processing.filter_router import FilterRouter


CONFIG_PATH = "config/sensor_config.json"
SAVE_FOLDER = Path("data/sessions")


class AcquisitionRunner:

    def __init__(self):
        self.port = None
        self.baud = 230400
        self.reader = None
        self.parser = PacketParser()
        self.router = FilterRouter(CONFIG_PATH)

        self.lsl = None
        self.running = False

        self.log = []
        self.session_start = None

    # -------------------------------------------------------------
    # SELECT PORT
    # -------------------------------------------------------------
    def select_port(self):
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()

        if not ports:
            print("❌ No COM ports found.")
            return False

        print("\nAvailable Ports:")
        for i, p in enumerate(ports):
            print(f"  [{i}] {p.device}  ({p.description})")

        idx = int(input("\nSelect port index: "))
        self.port = ports[idx].device
        return True

    # -------------------------------------------------------------
    # CONNECT DEVICE
    # -------------------------------------------------------------
    def connect(self):
        print(f"\nConnecting to {self.port} ...")
        self.reader = SerialPacketReader(self.port, self.baud)

        if not self.reader.connect():
            print("❌ Failed to connect.")
            return False

        self.reader.start()

        # Setup LSL Output (2 channels)
        self.lsl = LSLStreamer(
            name="BioSignals",
            channel_types=["CH0", "CH1"]
        )

        print("✅ Connected and listening.\n")
        return True

    # -------------------------------------------------------------
    # START SESSION
    # -------------------------------------------------------------
    def start_session(self):
        print("Starting acquisition...")
        self.running = True
        self.session_start = datetime.now()
        SAVE_FOLDER.mkdir(parents=True, exist_ok=True)

        # Ask the hardware to begin sending
        try:
            self.reader.send_command("START")
        except:
            pass

        # Main loop
        try:
            while self.running:
                pkt = self.reader.get_packet(timeout=0.1)
                if pkt is None:
                    continue

                parsed = self.parser.parse(pkt)

                # Process filtering through router
                filtered = self.router.process(
                    parsed.ch0_raw,
                    parsed.ch1_raw
                )

                # LSL stream
                self.lsl.push_sample([filtered["ch0"], filtered["ch1"]])

                # Log data entry
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "seq": parsed.counter,
                    "ch0_raw": parsed.ch0_raw,
                    "ch1_raw": parsed.ch1_raw,
                    "ch0_filtered": filtered["ch0"],
                    "ch1_filtered": filtered["ch1"],
                    "ch0_type": self.router.channel_types[0],
                    "ch1_type": self.router.channel_types[1]
                }
                self.log.append(entry)

                # Show lightweight live output
                print(
                    f"SEQ={parsed.counter:4d}  "
                    f"CH0({self.router.channel_types[0]}): {filtered['ch0']:8.2f} uV  "
                    f"CH1({self.router.channel_types[1]}): {filtered['ch1']:8.2f} uV",
                    end="\r"
                )

        except KeyboardInterrupt:
            print("\n🛑 Stopping by user...")

        self.stop()

    # -------------------------------------------------------------
    # STOP + SAVE
    # -------------------------------------------------------------
    def stop(self):
        self.running = False

        # try to stop hardware stream
        try:
            self.reader.send_command("STOP")
        except:
            pass

        time.sleep(0.2)
        self.reader.disconnect()

        self.save_session()

    # -------------------------------------------------------------
    # SAVE SESSION
    # -------------------------------------------------------------
    def save_session(self):
        timestamp = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
        filename = SAVE_FOLDER / f"session_{timestamp}.json"

        session_data = {
            "session_start": self.session_start.isoformat(),
            "duration_sec": (datetime.now() - self.session_start).total_seconds(),
            "channel_0_type": self.router.channel_types[0],
            "channel_1_type": self.router.channel_types[1],
            "sampling_rate": self.router.sampling_rate,
            "data": self.log
        }

        with open(filename, "w") as f:
            json.dump(session_data, f, indent=2)

        print(f"\n\n💾 Session saved to: {filename}\n")


# ============================================================
# MAIN EXECUTION
# ============================================================
if __name__ == "__main__":

    app = AcquisitionRunner()

    print("\n========== Unified Acquisition ==========")

    if not app.select_port():
        exit()

    if not app.connect():
        exit()

    app.start_session()
