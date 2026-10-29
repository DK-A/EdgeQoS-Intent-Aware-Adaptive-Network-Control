"""
sim/packet.py - Simulation Packet and Flow Primitives
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class SimPacket:
    pkt_id: int
    flow_id: str
    traffic_class: str       # "Realtime", "Stream", "Bulk", "Other"
    size_bytes: int
    creation_time: float     # Creation timestamp
    dscp: int = 0            # 0=CS0 (BE), 46=EF (Voice), 34=AF41 (Video), 8=CS1 (Bulk)
    dropped: bool = False
    dequeued_time: float = 0.0
    received_time: float = 0.0

    @property
    def rtt_ms(self) -> float:
        return (self.received_time - self.creation_time) * 1000.0

    def __lt__(self, other):
        if not isinstance(other, SimPacket):
            return NotImplemented
        return self.pkt_id < other.pkt_id
