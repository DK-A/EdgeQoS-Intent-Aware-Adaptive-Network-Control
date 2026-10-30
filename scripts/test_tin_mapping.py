#!/usr/bin/env python3
"""
scripts/test_tin_mapping.py - Stage S1: Kernel Primitive Truth Test T-TIN
Executes inside a network namespace to verify tc-cake diffserv4 tin mapping on this exact Linux kernel.
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

def test_tin_mapping():
    print("[*] Running T-TIN kernel verification...")
    # Clean any stale test namespaces
    run_cmd("ip netns del ns_tin 2>/dev/null || true")

    # 1. Create namespace
    run_cmd("ip netns add ns_tin")
    
    # 2. Create veth pair
    run_cmd("ip link add veth_a type veth peer name veth_b")
    run_cmd("ip link set veth_b netns ns_tin")

    # 3. Configure IPs
    run_cmd("ip addr add 192.168.99.1/24 dev veth_a")
    run_cmd("ip link set veth_a up")
    run_cmd("ip netns exec ns_tin ip addr add 192.168.99.2/24 dev veth_b")
    run_cmd("ip netns exec ns_tin ip link set veth_b up")

    # 4. Attach CAKE diffserv4 to veth_a
    run_cmd("tc qdisc add dev veth_a root cake bandwidth 100Mbit diffserv4")

    # Test DSCPs:
    # 0 = CS0 (Best Effort)
    # 8 = CS1 (Bulk)
    # 46 = EF (Voice)
    # 40 = CS5 (Voice)
    # 34 = AF41 (Video)
    # 32 = CS4 (Video / Voice check)
    dscps = {
        "CS0": 0,
        "CS1": 8,
        "AF41": 34,
        "CS4": 32,
        "EF": 46,
        "CS5": 40
    }

    results = {}
    
    for name, dscp_val in dscps.items():
        # Read baseline qdisc stats
        stats_pre = json.loads(run_cmd("tc -s -j qdisc show dev veth_a"))[0]
        tins_pre = stats_pre.get("tins", [])

        # Send 10 UDP packets with TOS = dscp_val << 2
        tos_byte = (dscp_val << 2) & 0xff
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos_byte)
        for _ in range(10):
            s.sendto(b"EDGEQOS_TIN_TEST", ("192.168.99.2", 9999))
        s.close()
        time.sleep(0.05)

        # Read post stats
        stats_post = json.loads(run_cmd("tc -s -j qdisc show dev veth_a"))[0]
        tins_post = stats_post.get("tins", [])

        # Detect which tin incremented
        mapped_tin_idx = None
        mapped_tin_name = None
        for idx, (t_pre, t_post) in enumerate(zip(tins_pre, tins_post)):
            pkts_diff = t_post.get("sent_packets", 0) - t_pre.get("sent_packets", 0)
            if pkts_diff >= 10:
                mapped_tin_idx = idx
                mapped_tin_name = t_post.get("tin", f"tin_{idx}")
                break
        
        results[name] = {
            "dscp_decimal": dscp_val,
            "tos_hex": hex(tos_byte),
            "tin_index": mapped_tin_idx,
            "tin_name": mapped_tin_name
        }

    # Cleanup
    run_cmd("ip link del veth_a 2>/dev/null || true")
    run_cmd("ip netns del ns_tin 2>/dev/null || true")

    # Format Markdown Document
    md = [
        "# EdgeQoS: Observed CAKE diffserv4 Tin Mapping (T-TIN)",
        f"*Kernel: {run_cmd('uname -r').strip()} · Measured on host via real kernel tc-cake*\n",
        "| DSCP Name | DSCP Value (Dec) | IPv4 TOS Byte | Observed Tin Index | Observed Tin Name | Target Tin Category |",
        "| :---: | :---: | :---: | :---: | :---: | :---: |"
    ]
    for name, data in results.items():
        category = "Voice" if "Voice" in str(data['tin_name']) else ("Video" if "Video" in str(data['tin_name']) else ("Bulk" if "Bulk" in str(data['tin_name']) else "BestEffort"))
        md.append(f"| **{name}** | `{data['dscp_decimal']}` | `{data['tos_hex']}` | `{data['tin_index']}` | **{data['tin_name']}** | {category} |")
    
    md_content = "\n".join(md) + "\n"
    with open("docs/tin_map_observed.md", "w") as f:
        f.write(md_content)
    
    print("[+] T-TIN Complete! Wrote docs/tin_map_observed.md:")
    print(md_content)

if __name__ == "__main__":
    test_tin_mapping()
