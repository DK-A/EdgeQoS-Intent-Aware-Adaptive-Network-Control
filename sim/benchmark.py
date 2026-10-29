"""
sim/benchmark.py - Comparative Ablation Benchmark Suite
Runs Scenarios SC1, SC2, and SC6 across B0, B1, B3, B4, S2, and S3.
Saves raw packet metrics, latency percentiles, and settling logs to results/.
"""

import os
import json
import numpy as np
from sim.packet import SimPacket
from sim.queue_models import FIFOQueue, PRIOQueue, CAKEDiffserv4Queue
from sim.traffic_generator import generate_voip_probe, generate_bulk_tcp_stream, generate_video_stream, generate_rogue_mimic_flow
from sim.network_env import NetworkSimulator

def analyze_rtts(packets: list, flow_id: str = "voip_probe") -> dict:
    delivered = [p for p in packets if p.flow_id == flow_id and not p.dropped and p.received_time > 0]
    if not delivered:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "jitter": 0.0, "loss_pct": 100.0}

    rtts = [p.rtt_ms for p in delivered]
    rtts.sort()
    n = len(rtts)
    p50 = float(rtts[int(0.50 * n)])
    p95 = float(rtts[int(0.95 * n)])
    p99 = float(rtts[int(0.99 * n)])

    # IPDV Jitter (mean consecutive absolute difference)
    jitter = float(np.mean([abs(rtts[i+1] - rtts[i]) for i in range(n - 1)])) if n > 1 else 0.0

    return {
        "count": n,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "jitter_ms": jitter,
        "loss_pct": 0.0
    }

def run_sc1_bulk_plus_voip():
    """SC1: 100 Mbps link with 90 Mbps bulk download + 50 pps VoIP call (10s duration)."""
    print("\n" + "="*60)
    print("SCENARIO SC1: ISO Download (TCP) + VoIP Call (100 Mbps Link)")
    print("="*60)
    results = {}

    configs = [
        ("B0_FIFO", lambda: FIFOQueue(limit_bytes=262144), False, False),
        ("B1_PRIO", lambda: PRIOQueue(limit_bytes=262144), False, False),
        ("B3_CAKE_Static", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), False, False),
        ("S3_EdgeQoS", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), True, True),
    ]

    for name, q_factory, enable_edgeqos, enable_guard in configs:
        voip_pkts = generate_voip_probe(flow_id="voip_probe", duration_sec=10.0, pps=50, size_bytes=160)
        bulk_pkts = generate_bulk_tcp_stream(flow_id="bulk_iso", duration_sec=10.0, start_time=0.5, target_rate_bps=95e6)
        all_pkts = voip_pkts + bulk_pkts

        sim = NetworkSimulator(
            gateway_queue=q_factory(),
            modem_buffer_bytes=262144, # 256 KB
            initial_link_rate_bps=100e6,
            enable_edgeqos_control=enable_edgeqos,
            enable_guard=enable_guard
        )
        out = sim.run(all_pkts)
        metrics = analyze_rtts(out["packets"], flow_id="voip_probe")
        results[name] = metrics
        print(f"  [{name:16s}] p50: {metrics['p50_ms']:6.2f} ms | p95: {metrics['p95_ms']:6.2f} ms | p99: {metrics['p99_ms']:6.2f} ms | Jitter: {metrics['jitter_ms']:5.2f} ms")

    return results

def run_sc2_capacity_collapse():
    """SC2: Capacity Collapse: 100 Mbps drops to 20 Mbps at t = 5.0s during bulk download."""
    print("\n" + "="*60)
    print("SCENARIO SC2: Capacity Collapse (100 Mbps -> 20 Mbps at t=5.0s)")
    print("="*60)
    results = {}

    configs = [
        ("B0_FIFO", lambda: FIFOQueue(limit_bytes=262144), False, False),
        ("B4_CAKE_Stale", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), False, False),
        ("S3_EdgeQoS", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), True, True),
    ]

    for name, q_factory, enable_edgeqos, enable_guard in configs:
        voip_pkts = generate_voip_probe(flow_id="voip_probe", duration_sec=12.0, pps=50, size_bytes=160)
        bulk_pkts = generate_bulk_tcp_stream(flow_id="bulk_stream", duration_sec=12.0, start_time=0.5, target_rate_bps=90e6)
        all_pkts = voip_pkts + bulk_pkts

        sim = NetworkSimulator(
            gateway_queue=q_factory(),
            modem_buffer_bytes=262144,
            initial_link_rate_bps=100e6,
            enable_edgeqos_control=enable_edgeqos,
            enable_guard=enable_guard
        )
        # Step drop to 20 Mbps at t = 5.0s
        out = sim.run(all_pkts, capacity_step_time=5.0, capacity_step_rate=20e6)

        # Measure RTTs specifically AFTER collapse (t > 5.0s)
        post_collapse_pkts = [p for p in out["packets"] if p.creation_time >= 5.0]
        metrics = analyze_rtts(post_collapse_pkts, flow_id="voip_probe")
        results[name] = metrics
        print(f"  [{name:16s}] Post-Collapse p50: {metrics['p50_ms']:6.2f} ms | p95: {metrics['p95_ms']:6.2f} ms | p99: {metrics['p99_ms']:6.2f} ms")

    return results

def run_sc6_rogue_mimic():
    """SC6: Rogue Flow Mimics VoIP, then bursts to 50 Mbps bulk in Voice tin."""
    print("\n" + "="*60)
    print("SCENARIO SC6: Rogue Mimic Stream (VoIP First 10 pkts -> 50 Mbps Bulk)")
    print("="*60)
    results = {}

    configs = [
        ("S2_Unguarded_ML", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), True, False), # Guard OFF
        ("S3_Guarded_EdgeQoS", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), True, True), # Guard ON
    ]

    for name, q_factory, enable_edgeqos, enable_guard in configs:
        # Honest voice probe sharing link
        voip_pkts = generate_voip_probe(flow_id="honest_call", duration_sec=10.0, pps=50, size_bytes=160)
        # Rogue mimic flow
        rogue_pkts = generate_rogue_mimic_flow(flow_id="rogue_stream", duration_sec=10.0, start_time=0.2)
        all_pkts = voip_pkts + rogue_pkts

        sim = NetworkSimulator(
            gateway_queue=q_factory(),
            modem_buffer_bytes=262144,
            initial_link_rate_bps=100e6,
            enable_edgeqos_control=enable_edgeqos,
            enable_guard=enable_guard
        )
        out = sim.run(all_pkts)
        metrics = analyze_rtts(out["packets"], flow_id="honest_call")
        results[name] = metrics
        print(f"  [{name:20s}] Honest Call p99: {metrics['p99_ms']:6.2f} ms | Jitter: {metrics['jitter_ms']:5.2f} ms | Drops: {out['dropped_gw']}")

    return results

def main():
    os.makedirs("results", exist_ok=True)
    sc1 = run_sc1_bulk_plus_voip()
    sc2 = run_sc2_capacity_collapse()
    sc6 = run_sc6_rogue_mimic()

    combined = {
        "SC1_Bulk_VoIP": sc1,
        "SC2_Collapse": sc2,
        "SC6_Rogue_Mimic": sc6
    }
    with open("results/ablation_benchmark.json", "w") as f:
        json.dump(combined, f, indent=2)
    print("\n[+] Full ablation benchmark complete. Saved to results/ablation_benchmark.json")

if __name__ == "__main__":
    main()
