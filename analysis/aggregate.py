"""
analysis/aggregate.py - Performance Metric Evaluation Table Generator
Aggregates baseline and EdgeQoS benchmark data into a comprehensive comparison table.
"""

import json
import numpy as np
from sim.queue_models import FIFOQueue, PRIOQueue, CAKEDiffserv4Queue
from sim.traffic_generator import generate_voip_probe, generate_bulk_tcp_stream, generate_rogue_mimic_flow
from sim.network_env import NetworkSimulator

def run_extended_evaluation():
    print("==========================================================================")
    print("COMPREHENSIVE PERFORMANCE EVALUATION: BASELINES VS. EDGEQOS (S3)")
    print("==========================================================================")

    # 1. SC1: Saturated 100M Link (90M Bulk + VoIP Call)
    # 2. SC2: Capacity Collapse 100M -> 20M at t=5.0s
    # Metrics: p50, p95, p99, Jitter, Settling Time, Demotion Time, Min Bulk Goodput

    scenarios_data = {}

    # --- SC1 Execution ---
    sc1_results = {}
    configs_sc1 = [
        ("B0 (DropTail FIFO)", lambda: FIFOQueue(limit_bytes=262144), False, False),
        ("B1 (Static Port PRIO)", lambda: PRIOQueue(limit_bytes=262144), False, False),
        ("B3 (Static CAKE 95M)", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), False, False),
        ("S3 (EdgeQoS Guarded)", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), True, True),
    ]

    for name, q_factory, eq_ctrl, eq_guard in configs_sc1:
        voip = generate_voip_probe("call", duration_sec=10.0, pps=50)
        bulk = generate_bulk_tcp_stream("bulk", duration_sec=10.0, start_time=0.2, target_rate_bps=95e6)
        sim = NetworkSimulator(q_factory(), modem_buffer_bytes=262144, initial_link_rate_bps=100e6,
                               enable_edgeqos_control=eq_ctrl, enable_guard=eq_guard)
        out = sim.run(voip + bulk)
        rtts = [p.rtt_ms for p in out["packets"] if p.flow_id == "call"]
        bulk_pkts = [p for p in out["packets"] if p.flow_id == "bulk"]
        bulk_goodput_mbps = (sum(p.size_bytes for p in bulk_pkts) * 8.0 / 10.0) / 1e6

        sc1_results[name] = {
            "p50_ms": float(np.percentile(rtts, 50)),
            "p95_ms": float(np.percentile(rtts, 95)),
            "p99_ms": float(np.percentile(rtts, 99)),
            "jitter_ms": float(np.mean([abs(rtts[i+1] - rtts[i]) for i in range(len(rtts)-1)])),
            "bulk_goodput_mbps": float(bulk_goodput_mbps),
            "drops": out["dropped_gw"] + out["dropped_modem"]
        }

    # --- SC2 Collapse Execution ---
    sc2_results = {}
    configs_sc2 = [
        ("B0 (DropTail FIFO)", lambda: FIFOQueue(limit_bytes=262144), False, False),
        ("B4 (Stale CAKE 95M on 20M Link)", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), False, False),
        ("S3 (EdgeQoS Guarded)", lambda: CAKEDiffserv4Queue(shaper_rate_bps=95e6), True, True),
    ]

    for name, q_factory, eq_ctrl, eq_guard in configs_sc2:
        voip = generate_voip_probe("call", duration_sec=14.0, pps=50)
        bulk = generate_bulk_tcp_stream("bulk", duration_sec=14.0, start_time=0.2, target_rate_bps=90e6)
        sim = NetworkSimulator(q_factory(), modem_buffer_bytes=262144, initial_link_rate_bps=100e6,
                               enable_edgeqos_control=eq_ctrl, enable_guard=eq_guard)
        out = sim.run(voip + bulk, capacity_step_time=5.0, capacity_step_rate=20e6)

        # Separate into transient window (t in [5.0, 7.0]) and steady-state settled window (t > 7.0)
        transient_rtts = [p.rtt_ms for p in out["packets"] if p.flow_id == "call" and 5.0 <= p.creation_time <= 7.0]
        steady_rtts = [p.rtt_ms for p in out["packets"] if p.flow_id == "call" and p.creation_time > 7.0]

        # Calculate settling time T_settle: time from t=5.0 until RTT <= 30ms and stays <= 30ms
        call_pkts = [p for p in out["packets"] if p.flow_id == "call" and p.creation_time >= 5.0]
        t_settle = 0.0
        settled = False
        for p in call_pkts:
            if p.rtt_ms <= 30.0:
                # check if next 10 pkts stay <= 30ms
                idx = call_pkts.index(p)
                sub = call_pkts[idx:idx+15]
                if all(sp.rtt_ms <= 30.0 for sp in sub) and len(sub) >= 10:
                    t_settle = p.creation_time - 5.0
                    settled = True
                    break
        if not settled:
            t_settle = float("inf") # Never settled!

        sc2_results[name] = {
            "transient_peak_rtt_ms": float(np.max(transient_rtts)) if transient_rtts else 0.0,
            "steady_p50_ms": float(np.percentile(steady_rtts, 50)) if steady_rtts else 0.0,
            "steady_p95_ms": float(np.percentile(steady_rtts, 95)) if steady_rtts else 0.0,
            "steady_p99_ms": float(np.percentile(steady_rtts, 99)) if steady_rtts else 0.0,
            "settling_time_sec": t_settle if t_settle != float("inf") else "> 9.0s (Never Settled)"
        }

    return sc1_results, sc2_results

def print_evaluation_tables(sc1, sc2):
    print("\n" + "="*85)
    print("TABLE 1: SCENARIO SC1 - 100 Mbps LINK WITH 95 Mbps BULK SATURATION + CONCURRENT VOIP")
    print("="*85)
    print(f"{'Configuration':<30} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'p99 (ms)':<9} | {'Jitter':<9} | {'Bulk Goodput':<12}")
    print("-" * 85)
    for cfg, m in sc1.items():
        print(f"{cfg:<30} | {m['p50_ms']:<9.2f} | {m['p95_ms']:<9.2f} | {m['p99_ms']:<9.2f} | {m['jitter_ms']:<9.3f} | {m['bulk_goodput_mbps']:<7.1f} Mbps")

    print("\n" + "="*85)
    print("TABLE 2: SCENARIO SC2 - CAPACITY COLLAPSE (100 Mbps -> 20 Mbps at t = 5.0s)")
    print("="*85)
    print(f"{'Configuration':<32} | {'Peak Delay':<11} | {'Settling Time':<15} | {'Steady p50':<11} | {'Steady p99':<11}")
    print("-" * 85)
    for cfg, m in sc2.items():
        settle_str = f"{m['settling_time_sec']:.2f} s" if isinstance(m['settling_time_sec'], float) else str(m['settling_time_sec'])
        print(f"{cfg:<32} | {m['transient_peak_rtt_ms']:<7.2f} ms | {settle_str:<15} | {m['steady_p50_ms']:<7.2f} ms | {m['steady_p99_ms']:<7.2f} ms")

if __name__ == "__main__":
    sc1, sc2 = run_extended_evaluation()
    print_evaluation_tables(sc1, sc2)

    with open("results/performance_evaluation.json", "w") as f:
        json.dump({"SC1": sc1, "SC2": sc2}, f, indent=2)
    print("\n[+] Full evaluation table written to results/performance_evaluation.json")
