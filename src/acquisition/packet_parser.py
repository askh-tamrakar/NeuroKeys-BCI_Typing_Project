from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple
from datetime import datetime
import struct
import numpy as np

@dataclass
class Packet:
    counter: int
    ch0_raw: int
    ch1_raw: int
    timestamp: datetime

    def to_dict(self):
        return asdict(self)


class PacketParser:
    def __init__(self, packet_len: int = 8):
        self.packet_len = packet_len
        # Format: B (Sync1), B (Sync2), B (Counter), >H (CH0), >H (CH1), B (End)
        # We skip sync bytes and end byte for speed
        self._struct_fmt = ">BHH" # Counter, CH0, CH1

    def parse(self, packet_bytes: bytes) -> Packet:
        if not packet_bytes or len(packet_bytes) != self.packet_len:
            raise ValueError(f"Invalid packet length")
        
        # Unpack starting from index 2 (counter)
        counter, ch0, ch1 = struct.unpack_from(self._struct_fmt, packet_bytes, 2)
        return Packet(counter=int(counter), ch0_raw=int(ch0), ch1_raw=int(ch1), timestamp=datetime.now())

    def parse_batch(self, batch_bytes: List[bytes]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Parse a list of byte packets into numpy arrays for speed.
        Returns (counters, ch0_raw, ch1_raw)
        """
        n = len(batch_bytes)
        counters = np.zeros(n, dtype=np.uint8)
        ch0_raw = np.zeros(n, dtype=np.uint16)
        ch1_raw = np.zeros(n, dtype=np.uint16)

        for i, pkt in enumerate(batch_bytes):
            c, r0, r1 = struct.unpack_from(self._struct_fmt, pkt, 2)
            counters[i] = c
            ch0_raw[i] = r0
            ch1_raw[i] = r1

        return counters, ch0_raw, ch1_raw
