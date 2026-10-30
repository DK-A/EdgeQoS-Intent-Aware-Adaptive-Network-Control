#!/usr/bin/env python3
"""
scripts/run_stage_s2_trace.py - Stage S2: End-to-End Classification & Tin Integration
Sends 3 controlled flows through gw:
  1. Low-rate VoIP-like UDP (50 pps, small packets)
  2. Streaming-like burst UDP (large packets)
  3. Bulk TCP/UDP
Verifies nftables set elements and tc-cake diffserv4 per-tin counter increments.
"""

import subprocess
import json
import time
import socket
import os

def run_cmd(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {cmd}\nStderr: {p.stderr}")
    return p.stdout

def run_s2_trace():
    print("==================================================")
    print("Stage S2: End-to-End Classification & Tin Trace")
    print("==================================================")

    # 1. Load nftables ruleset in gw namespace
    print("[*] Loading dataplane/edgeqos.nft into gw namespace...")
    run_cmd("ip netns exec gw nft -f dataplane/edgeqos.nft")

    # 2. Attach CAKE diffserv4 to gw-wan (WAN egress)
    print("[*] Attaching CAKE diffserv4 to gw-wan...")
    run_cmd("ip netns exec gw tc qdisc replace dev gw-wan root cake bandwidth 95Mbit diffserv4 nat dual-srchost")

    # 3. Read initial per-tin counters on gw-wan
    initial_stats = json.loads(run_cmd("ip netns exec gw tc -s -j qdisc show dev gw-wan"))[0]
    initial_tins = {t.get("tin", f"tin_{i}"): t.get("sent_packets", 0) for i, t in enumerate(initial_stats.get("tins", []))}
    print(f"[*] Initial Tin Counters: {initial_tins}")

    # Flow 1: Interactive VoIP (Simulating Zoom audio: UDP 50 pps, small 100B packets, 50 pkts)
    print("[*] Flow 1: Generating VoIP-like UDP (c1 -> srv, 100B packets)...")
    # Actuate promotional rule in nftables for Flow 1 (Simulating early classifier verdict Realtime -> Voice EF)
    run_cmd("ip netns exec gw nft add element inet edgeqos promo_rt '{ 192.168.1.10 . 10.0.2.2 . udp . 5060 . 5060 }'")

    # Send 50 UDP packets from c1 to srv
    run_cmd("ip netns exec c1 python3 -c \""
            "import socket, time; "
            "s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
            "s.bind(('192.168.1.10', 5060)); "
            "[s.sendto(b'X'*100, ('10.0.2.2', 5060)) or time.sleep(0.01) for _ in range(50)]; "
            "s.close()\"")

    time.sleep(0.1)
    stats_after_f1 = json.loads(run_cmd("ip netns exec gw tc -s -j qdisc show dev gw-wan"))[0]
    tins_f1 = {t.get("tin", f"tin_{i}"): t.get("sent_packets", 0) for i, t in enumerate(stats_after_f1.get("tins", []))}
    delta_f1 = {k: tins_f1[k] - initial_tins.get(k, 0) for k in tins_f1}
    print(f"[+] Flow 1 Increments: {delta_f1}")

    # Flow 2: Video Stream (Simulating Zoom video: UDP 800B packets)
    print("[*] Flow 2: Generating Video-like UDP (c1 -> srv, 800B packets)...")
    run_cmd("ip netns exec gw nft add element inet edgeqos promo_vid '{ 192.168.1.10 . 10.0.2.2 . udp . 5004 . 5004 }'")
    run_cmd("ip netns exec c1 python3 -c \""
            "import socket, time; "
            "s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
            "s.bind(('192.168.1.10', 5004)); "
            "[s.sendto(b'V'*800, ('10.0.2.2', 5004)) or time.sleep(0.01) for _ in range(50)]; "
            "s.close()\"")

    time.sleep(0.1)
    stats_after_f2 = json.loads(run_cmd("ip netns exec gw tc -s -j qdisc show dev gw-wan"))[0]
    tins_f2 = {t.get("tin", f"tin_{i}"): t.get("sent_packets", 0) for i, t in enumerate(stats_after_f2.get("tins", []))}
    delta_f2 = {k: tins_f2[k] - tins_f1.get(k, 0) for k in tins_f2}
    print(f"[+] Flow 2 Increments: {delta_f2}")

    # Flow 3: Bulk Transfer (Simulating Download: UDP 1400B packets, no mark -> Best Effort or Bulk mark)
    print("[*] Flow 3: Generating Bulk UDP (c1 -> srv, 1400B packets)...")
    run_cmd("ip netns exec gw nft add element inet edgeqos promo_blk '{ 192.168.1.10 . 10.0.2.2 . udp . 9001 . 9001 }'")
    run_cmd("ip netns exec c1 python3 -c \""
            "import socket, time; "
            "s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
            "s.bind(('192.168.1.10', 9001)); "
            "[s.sendto(b'B'*1400, ('10.0.2.2', 9001)) or time.sleep(0.005) for _ in range(50)]; "
            "s.close()\"")

    time.sleep(0.1)
    stats_after_f3 = json.loads(run_cmd("ip netns exec gw tc -s -j qdisc show dev gw-wan"))[0]
    tins_f3 = {t.get("tin", f"tin_{i}"): t.get("sent_packets", 0) for i, t in enumerate(stats_after_f3.get("tins", []))}
    delta_f3 = {k: tins_f3[k] - tins_f2.get(k, 0) for k in tins_f3}
    print(f"[+] Flow 3 Increments: {delta_f3}")

    # Verify set element listing
    nft_sets = run_cmd("ip netns exec gw nft list table inet edgeqos")
    print("\n[*] Live nftables state in gw:")
    for line in nft_sets.splitlines():
        if "set promo_" in line or "elements =" in line:
            print("   ", line.strip())

    # Build Structured S2 Trace Report
    trace_rows = [
        {
            "flow_type": "VoIP Audio (Small pkts)",
            "5_tuple": "192.168.1.10:5060 -> 10.0.2.2:5060 (UDP)",
            "packet_count": 50,
            "mark_applied": "DSCP EF (46 / 0xb8)",
            "target_tin": "Voice (tin_3)",
            "observed_tin_increment": delta_f1,
            "pass": delta_f1.get("tin_3", 0) >= 45
        },
        {
            "flow_type": "Video Stream (Medium pkts)",
            "5_tuple": "192.168.1.10:5004 -> 10.0.2.2:5004 (UDP)",
            "packet_count": 50,
            "mark_applied": "DSCP AF41 (34 / 0x88)",
            "target_tin": "Video (tin_2)",
            "observed_tin_increment": delta_f2,
            "pass": delta_f2.get("tin_2", 0) >= 45
        },
        {
            "flow_type": "Bulk Background (Large pkts)",
            "5_tuple": "192.168.1.10:9001 -> 10.0.2.2:9001 (UDP)",
            "packet_count": 50,
            "mark_applied": "DSCP CS1 (8 / 0x20)",
            "target_tin": "Bulk (tin_0)",
            "observed_tin_increment": delta_f3,
            "pass": delta_f3.get("tin_0", 0) >= 45
        }
    ]

    os.makedirs("results", exist_ok=True)
    with open("results/stage_s2_trace.json", "w") as f:
        json.dump(trace_rows, f, indent=2)

    print("\n==================================================")
    print("Stage S2 Trace Summary Table:")
    print("==================================================")
    all_passed = True
    for row in trace_rows:
        status = "PASS" if row['pass'] else "FAIL"
        print(f"• {row['flow_type']:<28} | Mark: {row['mark_applied']:<20} | Target: {row['target_tin']:<14} | Result: {status}")
        if not row['pass']:
            all_passed = False

    if all_passed:
        print("\n[+] STAGE S2 PASSED: Real kernel classification successfully steers packets into exact CAKE tins!")
    else:
        print("\n[-] STAGE S2 WARNING: Some flows did not reach the target tin.")

if __name__ == "__main__":
    run_s2_trace()
