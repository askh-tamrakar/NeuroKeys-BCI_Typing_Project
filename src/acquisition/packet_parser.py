# src/acquisition/packet_parser.py
"""
Packet dataclass and PacketParser
- Keeps parsing logic isolated for unit tests.
- Packet layout assumed: [SYNC1, SYNC2, CTR, CH0_H, CH0_L, CH1_H, CH1_L, END]
- Returns Packet objects containing raw ADC integers and timestamp.
"""

from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime


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

    def parse(self, packet_bytes: bytes) -> Packet:
        if not packet_bytes or len(packet_bytes) != self.packet_len:
            raise ValueError(f"Invalid packet length: expected {self.packet_len} got {len(packet_bytes) if packet_bytes else 0}")
        # parse according to layout
        counter = packet_bytes[2]
        ch0_raw = (packet_bytes[3] << 8) | packet_bytes[4]
        ch1_raw = (packet_bytes[5] << 8) | packet_bytes[6]
        return Packet(counter=int(counter), ch0_raw=int(ch0_raw), ch1_raw=int(ch1_raw), timestamp=datetime.now())
