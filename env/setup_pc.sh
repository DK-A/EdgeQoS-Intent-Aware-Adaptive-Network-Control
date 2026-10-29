#!/usr/bin/env bash
# env/setup_pc.sh - Host environment configuration for EdgeQoS E1 testbed
set -euo pipefail

echo "[*] Checking and loading required kernel modules..."
sudo modprobe sch_cake 2>/dev/null || echo "[WARN] sch_cake not built-in, ensure kernel >= 4.19"
sudo modprobe nfnetlink_log 2>/dev/null || true
sudo modprobe nf_conntrack 2>/dev/null || true

echo "[*] Configuring sysctl forward & conntrack accounting..."
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -w net.netfilter.nf_conntrack_acct=1
sudo sysctl -w net.netfilter.nf_conntrack_timestamp=1

echo "[*] EdgeQoS PC environment setup complete."
