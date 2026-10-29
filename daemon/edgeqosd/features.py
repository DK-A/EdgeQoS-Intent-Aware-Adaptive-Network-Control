"""
daemon/edgeqosd/features.py - Zero-DPI Early-Flow Feature Extractor
Extracts transport metadata from first N <= 10 packets of a flow.
Never inspects or stores payload bytes.
"""

import math
from typing import List, Dict, Any, Optional

class FlowPacketRecord:
    __slots__ = ("timestamp", "proto", "length", "is_forward", "tcp_flags")
    def __init__(self, timestamp: float, proto: int, length: int, is_forward: bool, tcp_flags: int = 0):
        self.timestamp = timestamp
        self.proto = proto
        self.length = length
        self.is_forward = is_forward
        self.tcp_flags = tcp_flags

class EarlyFlowBuffer:
    def __init__(self, max_packets: int = 10, timeout_sec: float = 2.0):
        self.max_packets = max_packets
        self.timeout_sec = timeout_sec
        self.records: List[FlowPacketRecord] = []
        self.start_time: Optional[float] = None
        self.is_complete = False

    def add_packet(self, record: FlowPacketRecord) -> bool:
        """Adds a packet. Returns True if flow reached max_packets."""
        if self.is_complete:
            return False
        if self.start_time is None:
            self.start_time = record.timestamp
        self.records.append(record)
        if len(self.records) >= self.max_packets:
            self.is_complete = True
            return True
        return False

    def is_timed_out(self, current_time: float) -> bool:
        if self.start_time is None:
            return False
        return (current_time - self.start_time) > self.timeout_sec

def extract_zero_dpi_features(records: List[FlowPacketRecord], n_packets: int = 10) -> List[float]:
    """
    Extracts 22-dimensional Zero-DPI feature vector from first N records:
    - 10 sign-coded packet lengths (+ for forward, - for reverse)
    - 9 log10 inter-arrival times in microseconds
    - 1 protocol flag (1.0 for UDP, 0.0 for TCP)
    - 1 forward direction ratio
    - 1 forward packet mean length
    """
    feats = [0.0] * 22
    total = len(records)
    if total == 0:
        return feats

    # Lengths (indices 0..9)
    fwd_count = 0
    fwd_len_sum = 0
    for i in range(min(total, n_packets)):
        r = records[i]
        signed_len = float(r.length if r.is_forward else -r.length)
        feats[i] = signed_len
        if r.is_forward:
            fwd_count += 1
            fwd_len_sum += r.length

    # Inter-arrival times (indices 10..18)
    for i in range(min(total - 1, n_packets - 1)):
        dt = max(0.0, records[i+1].timestamp - records[i].timestamp)
        # Convert to microseconds and apply log10(dt_us + 1.0)
        dt_us = dt * 1e6
        feats[10 + i] = math.log10(dt_us + 1.0)

    # L4 Protocol (index 19)
    feats[19] = 1.0 if records[0].proto == 17 else 0.0

    # Directionality ratio (index 20)
    feats[20] = float(fwd_count) / float(min(total, n_packets))

    # Mean forward length (index 21)
    feats[21] = float(fwd_len_sum / fwd_count) if fwd_count > 0 else 0.0

    return feats
