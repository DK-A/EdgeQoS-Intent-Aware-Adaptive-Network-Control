"""
sim/traffic_generator.py - Discrete-Event Traffic Generators
"""

import random
from typing import List, Generator, Tuple
from sim.packet import SimPacket

def generate_voip_probe(flow_id: str = "voip_probe", duration_sec: float = 30.0,
                        start_time: float = 0.0, pps: int = 50, size_bytes: int = 160) -> List[SimPacket]:
    packets = []
    pkt_id = 0
    interval = 1.0 / pps
    t = start_time
    while t < (start_time + duration_sec):
        # Add 1-2 ms realistic jitter
        jitter = random.gauss(0.0, 0.001)
        actual_t = max(0.0, t + jitter)
        pkt = SimPacket(
            pkt_id=pkt_id,
            flow_id=flow_id,
            traffic_class="Realtime",
            size_bytes=size_bytes,
            creation_time=actual_t,
            dscp=0 # Initially 0, classified later
        )
        packets.append(pkt)
        pkt_id += 1
        t += interval
    return packets

def generate_bulk_tcp_stream(flow_id: str, duration_sec: float, start_time: float,
                             target_rate_bps: float = 90_000_000.0) -> List[SimPacket]:
    """Generates aggressive TCP bulk stream."""
    packets = []
    pkt_id = 0
    t = start_time
    pkt_size = 1500
    interval = (pkt_size * 8.0) / target_rate_bps
    while t < (start_time + duration_sec):
        pkt = SimPacket(
            pkt_id=pkt_id,
            flow_id=flow_id,
            traffic_class="Bulk",
            size_bytes=pkt_size,
            creation_time=t,
            dscp=0
        )
        packets.append(pkt)
        pkt_id += 1
        t += interval
    return packets

def generate_video_stream(flow_id: str, duration_sec: float, start_time: float) -> List[SimPacket]:
    """Generates chunked video stream (bursts of 1450B packets)."""
    packets = []
    pkt_id = 0
    t = start_time
    while t < (start_time + duration_sec):
        # 1-second chunk burst (10 Mbps burst rate for 0.2s, then 0.8s idle)
        burst_duration = 0.20
        burst_rate = 12_000_000.0
        interval = (1450 * 8.0) / burst_rate
        burst_end = t + burst_duration
        while t < burst_end:
            pkt = SimPacket(
                pkt_id=pkt_id,
                flow_id=flow_id,
                traffic_class="Stream",
                size_bytes=1450,
                creation_time=t,
                dscp=0
            )
            packets.append(pkt)
            pkt_id += 1
            t += interval
        t += 0.80 # Buffer sleep interval
    return packets

def generate_rogue_mimic_flow(flow_id: str, duration_sec: float, start_time: float) -> List[SimPacket]:
    """Generates flow that mimics VoIP for first 10 packets, then blasts 50 Mbps bulk."""
    packets = []
    pkt_id = 0
    t = start_time
    # First 10 packets: VoIP-like (160B, 20ms)
    for _ in range(10):
        pkt = SimPacket(
            pkt_id=pkt_id,
            flow_id=flow_id,
            traffic_class="Realtime", # Pretends to be realtime!
            size_bytes=160,
            creation_time=t,
            dscp=0
        )
        packets.append(pkt)
        pkt_id += 1
        t += 0.020

    # Remaining duration: Aggressive 50 Mbps bulk flood
    interval = (1500 * 8.0) / 50_000_000.0
    while t < (start_time + duration_sec):
        pkt = SimPacket(
            pkt_id=pkt_id,
            flow_id=flow_id,
            traffic_class="Bulk", # Actually greedy bulk!
            size_bytes=1500,
            creation_time=t,
            dscp=0
        )
        packets.append(pkt)
        pkt_id += 1
        t += interval
    return packets
