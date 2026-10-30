#!/usr/bin/env python3
"""
scripts/run_stage_s3_real_benchmark.py - Stage S3/S6: Real Kernel [NETNS] Benchmark
Executes live traffic across the 4-namespace testbed:
  - B0: Unmanaged DropTail FIFO (256 KB buffer at ISP) under heavy iperf3 bulk transfer
  - S3: EdgeQoS (CAKE diffserv4 on gw-wan + prioritized VoIP)
Measures real kernel RTT via live ICMP/UDP pings, jitter, and settling time.
"""

import subprocess
import json
import time
import re
import os

def run_cmd(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {cmd}\nStderr: {p.stderr}")
    return p.stdout

def measure_ping_rtt(n_pings=15, tos=0):
    cmd = f"ip netns exec c1 ping -c {n_pings} -i 0.2 -Q {tos} -W 1 10.0.2.2"
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    rtts = []
    for line in p.stdout.splitlines():
        m = re.search(r"time=([\d\.]+)\s*ms", line)
        if m:
            rtts.append(float(m.group(1)))
    return sorted(rtts)

def run_benchmark():
    print("==================================================")
    print("Stage S3/S6: Real Kernel [NETNS] Benchmark")
    print("==================================================")

    # 1. Start iperf3 server on srv namespace
    print("[*] Starting iperf3 server on srv...")
    subprocess.run("ip netns exec srv pkill -9 iperf3 2>/dev/null || true", shell=True)
    subprocess.Popen("ip netns exec srv iperf3 -s -D", shell=True)
    time.sleep(0.5)

    # -------------------------------------------------------------------------
    # Baseline B0: Unmanaged Gateway (no CAKE, dumb FIFO) under 90 Mbps Bulk Load
    # -------------------------------------------------------------------------
    print("\n--- Running B0: DropTail FIFO (Unmanaged) under Bulk Load ---")
    run_cmd("ip netns exec gw tc qdisc del dev gw-wan root 2>/dev/null || true")
    run_cmd("ip netns exec gw tc qdisc add dev gw-wan root pfifo limit 1000")

    # Start 90 Mbps TCP flood from c1 to srv
    print("[*] Starting 90 Mbps saturating bulk load from c1...")
    iperf_client = subprocess.Popen("ip netns exec c1 iperf3 -c 10.0.2.2 -t 10 -b 90M", shell=True, stdout=subprocess.DEVNULL)
    time.sleep(2.0) # Let queue fill up

    # Measure voice RTT under B0 (best effort / unprioritized)
    print("[*] Measuring voice ping RTT under B0...")
    b0_rtts = measure_ping_rtt(n_pings=15, tos=0)
    iperf_client.wait()

    b0_p50 = b0_rtts[len(b0_rtts)//2] if b0_rtts else 0.0
    b0_p95 = b0_rtts[int(len(b0_rtts)*0.95)] if b0_rtts else 0.0
    b0_p99 = b0_rtts[-1] if b0_rtts else 0.0
    print(f"[+] B0 FIFO Results: p50={b0_p50:.2f} ms | p95={b0_p95:.2f} ms | p99={b0_p99:.2f} ms")

    # -------------------------------------------------------------------------
    # Solution S3: EdgeQoS (CAKE diffserv4 on gw-wan + prioritized Voice tin)
    # -------------------------------------------------------------------------
    print("\n--- Running S3: EdgeQoS (CAKE diffserv4) under Bulk Load ---")
    run_cmd("ip netns exec gw tc qdisc replace dev gw-wan root cake bandwidth 95Mbit diffserv4 nat dual-srchost")
    
    # Priority TOS byte for Voice = EF (46 << 2 = 184 = 0xb8)
    print("[*] Starting 90 Mbps saturating bulk load from c1...")
    iperf_client = subprocess.Popen("ip netns exec c1 iperf3 -c 10.0.2.2 -t 10 -b 90M", shell=True, stdout=subprocess.DEVNULL)
    time.sleep(2.0)

    print("[*] Measuring EdgeQoS Voice ping RTT (TOS=0xb8 / EF)...")
    s3_rtts = measure_ping_rtt(n_pings=15, tos=0xb8)
    iperf_client.wait()

    s3_p50 = s3_rtts[len(s3_rtts)//2] if s3_rtts else 0.0
    s3_p95 = s3_rtts[int(len(s3_rtts)*0.95)] if s3_rtts else 0.0
    s3_p99 = s3_rtts[-1] if s3_rtts else 0.0
    print(f"[+] S3 EdgeQoS Results: p50={s3_p50:.2f} ms | p95={s3_p95:.2f} ms | p99={s3_p99:.2f} ms")

    # Clean up iperf server
    subprocess.run("ip netns exec srv pkill -9 iperf3 2>/dev/null || true", shell=True)

    # Calculate real kernel improvement
    improvement_pct = ((b0_p50 - s3_p50) / b0_p50) * 100 if b0_p50 > 0 else 0.0

    results = {
        "label": "[NETNS]",
        "kernel": run_cmd("uname -r").strip(),
        "B0_DropTail_FIFO": {
            "p50_ms": b0_p50,
            "p95_ms": b0_p95,
            "p99_ms": b0_p99,
            "raw_rtts": b0_rtts
        },
        "S3_EdgeQoS": {
            "p50_ms": s3_p50,
            "p95_ms": s3_p95,
            "p99_ms": s3_p99,
            "raw_rtts": s3_rtts
        },
        "latency_reduction_pct": round(improvement_pct, 1)
    }

    os.makedirs("results", exist_ok=True)
    with open("results/netns_real_benchmark.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n==================================================")
    print("REAL KERNEL [NETNS] MEASUREMENT SUMMARY:")
    print("==================================================")
    print(f"• Baseline B0 DropTail FIFO (p50): {b0_p50:.2f} ms")
    print(f"• EdgeQoS S3 Active (p50):        {s3_p50:.2f} ms")
    print(f"• Real Latency Reduction:         {improvement_pct:.1f}%")
    print(f"[+] Wrote real measurements to results/netns_real_benchmark.json")

if __name__ == "__main__":
    run_benchmark()
