"""
ml/collect/generator.py - Physical Transport Flow Generator
Generates realistic transport-layer flows adhering to actual protocol dynamics:
- Realtime: 50 pps VoIP (G.711/Opus) & Gaming UDP (small packets, 20ms fixed interval +- jitter)
- Stream: Adaptive video streaming chunks (burst of 1400-1500B packets, then silent sleep)
- Bulk: Greedy TCP CUBIC/BBR file transfers (continuous 1500B MTU downstream, small ACKs upstream)
- Other: Web browsing (interactive request-response, variable sizes, early FIN/RST)
"""

import random
import time
from typing import List, Tuple
from daemon.edgeqosd.features import FlowPacketRecord, extract_zero_dpi_features

CLASS_REALTIME = 0
CLASS_STREAM = 1
CLASS_BULK = 2
CLASS_OTHER = 3

CLASS_NAMES = {
    CLASS_REALTIME: "Realtime",
    CLASS_STREAM: "Stream",
    CLASS_BULK: "Bulk",
    CLASS_OTHER: "Other"
}

def generate_realtime_flow(base_time: float = 0.0, n_packets: int = 10) -> List[FlowPacketRecord]:
    """Generates VoIP / Gaming flow: 50 pps, 60-250B packets, ~20ms interval."""
    records = []
    t = base_time
    # Handshake / Initial setup packet
    proto = 17 # UDP
    for i in range(n_packets):
        is_forward = random.choice([True, False]) # Bi-directional symmetric conversation
        length = random.randint(70, 220)
        records.append(FlowPacketRecord(timestamp=t, proto=proto, length=length, is_forward=is_forward))
        # 20ms nominal interval with 1-3ms jitter
        jitter = random.gauss(0.0, 0.002)
        interval = max(0.005, 0.020 + jitter)
        t += interval
    return records

def generate_stream_flow(base_time: float = 0.0, n_packets: int = 10) -> List[FlowPacketRecord]:
    """Generates Adaptive Video Streaming flow: Segment chunk bursts of MTU packets."""
    records = []
    t = base_time
    proto = 6 # TCP (TLS/HTTPS video) or UDP (QUIC)
    # First packet: client GET request forward
    records.append(FlowPacketRecord(timestamp=t, proto=proto, length=random.randint(300, 600), is_forward=True, tcp_flags=0x18))
    t += random.uniform(0.015, 0.030) # RTT delay
    # Subsequent packets in chunk burst: large MTU segments downstream
    for i in range(1, n_packets):
        if i % 4 == 0:
            # Client ACK upstream
            records.append(FlowPacketRecord(timestamp=t, proto=proto, length=random.randint(52, 66), is_forward=True, tcp_flags=0x10))
            t += random.uniform(0.0005, 0.002)
        else:
            # Video payload segment downstream
            length = random.choice([1350, 1420, 1480, 1500])
            records.append(FlowPacketRecord(timestamp=t, proto=proto, length=length, is_forward=False, tcp_flags=0x10))
            t += random.uniform(0.0001, 0.0008)
    return records

def generate_bulk_flow(base_time: float = 0.0, n_packets: int = 10) -> List[FlowPacketRecord]:
    """Generates Bulk File Transfer: Monolithic TCP download saturating line rate."""
    records = []
    t = base_time
    proto = 6 # TCP
    # TCP 3-way handshake
    records.append(FlowPacketRecord(timestamp=t, proto=proto, length=60, is_forward=True, tcp_flags=0x02)) # SYN
    t += random.uniform(0.010, 0.025)
    records.append(FlowPacketRecord(timestamp=t, proto=proto, length=60, is_forward=False, tcp_flags=0x12)) # SYN-ACK
    t += random.uniform(0.0002, 0.001)
    records.append(FlowPacketRecord(timestamp=t, proto=proto, length=54, is_forward=True, tcp_flags=0x10)) # ACK
    t += random.uniform(0.001, 0.005)
    # Bulk data packets: saturated 1500B
    for i in range(3, n_packets):
        if i % 3 == 0:
            records.append(FlowPacketRecord(timestamp=t, proto=proto, length=54, is_forward=True, tcp_flags=0x10))
            t += random.uniform(0.0002, 0.0008)
        else:
            records.append(FlowPacketRecord(timestamp=t, proto=proto, length=1500, is_forward=False, tcp_flags=0x10))
            t += random.uniform(0.00005, 0.0002)
    return records

def generate_other_flow(base_time: float = 0.0, n_packets: int = 10) -> List[FlowPacketRecord]:
    """Generates Web / API short interactive flow: Small exchanges, moderate sizes."""
    records = []
    t = base_time
    proto = random.choice([6, 17])
    for i in range(n_packets):
        is_forward = (i % 2 == 0)
        length = random.randint(150, 900)
        records.append(FlowPacketRecord(timestamp=t, proto=proto, length=length, is_forward=is_forward))
        t += random.uniform(0.010, 0.150)
    return records

def generate_dataset(n_samples_per_class: int = 500, random_seed: int = 42) -> Tuple[List[List[float]], List[int], List[int]]:
    """
    Generates balanced dataset across 4 classes with session grouping for GroupKFold.
    Returns: (X, y, groups)
    """
    random.seed(random_seed)
    X = []
    y = []
    groups = []

    generators = [
        (CLASS_REALTIME, generate_realtime_flow),
        (CLASS_STREAM, generate_stream_flow),
        (CLASS_BULK, generate_bulk_flow),
        (CLASS_OTHER, generate_other_flow)
    ]

    session_id = 0
    for label, gen in generators:
        for i in range(n_samples_per_class):
            if i % 10 == 0:
                session_id += 1 # 10 flows per session/host
            records = gen(base_time=0.0, n_packets=10)
            feats = extract_zero_dpi_features(records, n_packets=10)
            X.append(feats)
            y.append(label)
            groups.append(session_id)

    return X, y, groups
