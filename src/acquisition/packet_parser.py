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
    ch2_raw: int
    ch3_raw: int
    timestamp: datetime

    def to_dict(self):
        return asdict(self)


class PacketParser:
    def __init__(self, packet_len: int = 12):
        self.packet_len = packet_len
        # Format: B (Sync1), B (Sync2), B (Counter), >H (CH0), >H (CH1), >H (CH2), >H (CH3), B (End)
        # We skip sync bytes (2) and unpack from Counter
        self._struct_fmt = ">BHHHH" # Counter, CH0, CH1, CH2, CH3

    def parse(self, packet_bytes: bytes) -> Packet:
        if not packet_bytes or len(packet_bytes) != self.packet_len:
            # Try to be flexible if we receive 8 bytes (old firmware) or 12 bytes (new)
            if len(packet_bytes) == 8:
                 # Fallback for 2-channel packet
                 counter, ch0, ch1 = struct.unpack_from(">BHH", packet_bytes, 2)
                 return Packet(counter=int(counter), ch0_raw=int(ch0), ch1_raw=int(ch1), ch2_raw=0, ch3_raw=0, timestamp=datetime.now())
            raise ValueError(f"Invalid packet length: {len(packet_bytes)} (Expected {self.packet_len})")
        
        # Unpack starting from index 2 (counter)
        counter, ch0, ch1, ch2, ch3 = struct.unpack_from(self._struct_fmt, packet_bytes, 2)
        return Packet(
            counter=int(counter), 
            ch0_raw=int(ch0), 
            ch1_raw=int(ch1), 
            ch2_raw=int(ch2), 
            ch3_raw=int(ch3), 
            timestamp=datetime.now()
        )

    def parse_batch(self, batch_bytes: List[bytes]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Parse a list of byte packets into numpy arrays for speed.
        Returns (counters, ch0_raw, ch1_raw, ch2_raw, ch3_raw)
        """
        n = len(batch_bytes)
        counters = np.zeros(n, dtype=np.uint8)
        ch0_raw = np.zeros(n, dtype=np.uint16)
        ch1_raw = np.zeros(n, dtype=np.uint16)
        ch2_raw = np.zeros(n, dtype=np.uint16)
        ch3_raw = np.zeros(n, dtype=np.uint16)

        for i, pkt in enumerate(batch_bytes):
            if len(pkt) == 12:
                c, r0, r1, r2, r3 = struct.unpack_from(self._struct_fmt, pkt, 2)
                counters[i] = c
                ch0_raw[i] = r0
                ch1_raw[i] = r1
                ch2_raw[i] = r2
                ch3_raw[i] = r3
            elif len(pkt) == 8:
                 # Support mixed packets or old firmware during transition
                 c, r0, r1 = struct.unpack_from(">BHH", pkt, 2)
                 counters[i] = c
                 ch0_raw[i] = r0
                 ch1_raw[i] = r1
                 # Ch2/3 remain 0

        return counters, ch0_raw, ch1_raw, ch2_raw, ch3_raw
