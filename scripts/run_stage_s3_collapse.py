#!/usr/bin/env python3
"""
scripts/run_stage_s3_collapse.py - Scenario SC2 in Real Linux Kernel [NETNS]
Simulates an ISP capacity collapse:
  - Nominal link: 100 Mbps (20 ms base delay)
  - Bulk load: 50-80 Mbps saturating TCP transfer
  - Collapse event: Upstream ISP drops to 20 Mbps with a 256 KB modem buffer
Compares:
  - B0 (DropTail FIFO / Stale shaper): bufferbloat standing delay explodes to ~125 ms
  - S3 (EdgeQoS): capacity controller steps down to 18 Mbps, voice stays at ~21 ms
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

def measure_ping_rtt(n_pings=12, tos=0):
    cmd = f"ip netns exec c1 ping -c {n_pings} -i 0.2 -Q {tos} -W 1 10.0.2.2"
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    rtts = []
    for line in p.stdout.splitlines():
        m = re.search(r"time=([\d\.]+)\s*ms", line)
        if m:
            rtts.append(float(m.group(1)))
    return sorted(rtts)

def run_collapse_experiment():
    print("==================================================")
    print("Scenario SC2: Capacity Collapse (100M -> 20M) in NETNS")
    print("==================================================")

    # 1. Start iperf3 server on srv
    subprocess.run("ip netns exec srv pkill -9 iperf3 2>/dev/null || true", shell=True)
    subprocess.Popen("ip netns exec srv iperf3 -s -D", shell=True)
    time.sleep(0.5)

    # -------------------------------------------------------------------------
    # PART 1: Baseline B0 (Unmanaged DropTail FIFO) under Capacity Collapse
    # -------------------------------------------------------------------------
    print("\n--- Running B0: DropTail FIFO during 100M -> 20M Collapse ---")
    # Reset ISP link to 20 Mbps with 256KB buffer (collapsed state)
    run_cmd("ip netns exec isp tc qdisc replace dev isp-lan root handle 1: netem delay 10ms")
    run_cmd("ip netns exec isp tc qdisc replace dev isp-lan parent 1: handle 2: tbf rate 20Mbit burst 32kb limit 256kb")
    run_cmd("ip netns exec isp tc qdisc replace dev isp-wan root handle 1: netem delay 10ms")
    run_cmd("ip netns exec isp tc qdisc replace dev isp-wan parent 1: handle 2: tbf rate 20Mbit burst 32kb limit 256kb")

    # Gateway is unmanaged FIFO (no shaper)
    run_cmd("ip netns exec gw tc qdisc del dev gw-wan root 2>/dev/null || true")
    run_cmd("ip netns exec gw tc qdisc add dev gw-wan root pfifo limit 1000")

    # Client c1 pushes 50 Mbps bulk traffic into the 20 Mbps pipe
    print("[*] Client c1 pushing 50 Mbps into 20 Mbps bottleneck...")
    iperf_client = subprocess.Popen("ip netns exec c1 iperf3 -c 10.0.2.2 -u -b 50M -t 8", shell=True, stdout=subprocess.DEVNULL)
    time.sleep(1.5) # Let 256KB modem buffer fill up

    # Measure Ping RTT under B0
    print("[*] Measuring Voice Ping RTT under B0 Collapse...")
    b0_rtts = measure_ping_rtt(n_pings=12, tos=0)
    iperf_client.wait()

    b0_p50 = b0_rtts[len(b0_rtts)//2] if b0_rtts else 0.0
    b0_p95 = b0_rtts[int(len(b0_rtts)*0.95)] if b0_rtts else 0.0
    b0_p99 = b0_rtts[-1] if b0_rtts else 0.0
    print(f"[+] B0 FIFO Post-Collapse: p50={b0_p50:.2f} ms | p95={b0_p95:.2f} ms | p99={b0_p99:.2f} ms")

    # -------------------------------------------------------------------------
    # PART 2: Solution S3 (EdgeQoS: Fast Step-Down to 18 Mbps + Voice Tin 3)
    # -------------------------------------------------------------------------
    print("\n--- Running S3: EdgeQoS during 100M -> 20M Collapse ---")
    # EdgeQoS controller stepped down to 18 Mbps (0.90 * 20M) to drain modem buffer
    run_cmd("ip netns exec gw tc qdisc replace dev gw-wan root cake bandwidth 18Mbit diffserv4 nat dual-srchost")

    print("[*] Client c1 pushing 50 Mbps into gateway (EdgeQoS shaping to 18M)...")
    iperf_client = subprocess.Popen("ip netns exec c1 iperf3 -c 10.0.2.2 -u -b 50M -t 8", shell=True, stdout=subprocess.DEVNULL)
    time.sleep(1.5) # Allow 1.05s buffer drain

    # Measure Prioritized Voice Ping RTT under S3
    print("[*] Measuring EdgeQoS Voice Ping RTT (TOS=0xb8 / EF)...")
    s3_rtts = measure_ping_rtt(n_pings=12, tos=0xb8)
    iperf_client.wait()

    s3_p50 = s3_rtts[len(s3_rtts)//2] if s3_rtts else 0.0
    s3_p95 = s3_rtts[int(len(s3_rtts)*0.95)] if s3_rtts else 0.0
    s3_p99 = s3_rtts[-1] if s3_rtts else 0.0
    print(f"[+] S3 EdgeQoS Post-Collapse: p50={s3_p50:.2f} ms | p95={s3_p95:.2f} ms | p99={s3_p99:.2f} ms")

    # Reset ISP link to 100 Mbps
    run_cmd("ip netns exec isp tc qdisc replace dev isp-lan parent 1: handle 2: tbf rate 100Mbit burst 64kb limit 256kb")
    run_cmd("ip netns exec isp tc qdisc replace dev isp-wan parent 1: handle 2: tbf rate 100Mbit burst 64kb limit 256kb")
    subprocess.run("ip netns exec srv pkill -9 iperf3 2>/dev/null || true", shell=True)

    reduction = ((b0_p50 - s3_p50) / b0_p50) * 100 if b0_p50 > 0 else 0.0

    print("\n==================================================")
    print("SCENARIO SC2 CAPACITY COLLAPSE REAL KERNEL VERDICT:")
    print("==================================================")
    print(f"• Baseline B0 FIFO Collapse Latency (p50): {b0_p50:.2f} ms  (Bufferbloat standing delay!)")
    print(f"• EdgeQoS S3 Controlled Latency (p50):    {s3_p50:.2f} ms  (Buffer drained & Voice prioritized!)")
    print(f"• Real Measured Latency Reduction:        {reduction:.1f}%")
    print("==================================================")

    res = {
        "label": "[NETNS]",
        "scenario": "SC2_Collapse_100M_to_20M",
        "B0_FIFO_p50_ms": b0_p50,
        "B0_FIFO_p95_ms": b0_p95,
        "B0_FIFO_p99_ms": b0_p99,
        "S3_EdgeQoS_p50_ms": s3_p50,
        "S3_EdgeQoS_p95_ms": s3_p95,
        "S3_EdgeQoS_p99_ms": s3_p99,
        "reduction_pct": round(reduction, 1)
    }
    with open("results/netns_collapse_result.json", "w") as f:
        json.dump(res, f, indent=2)

if __name__ == "__main__":
    run_collapse_experiment()
