#!/usr/bin/env bash
# dataplane/cake_down.sh - Remove CAKE and restore unmanaged interface state
set -euo pipefail

WAN=${1:-eth0}
LAN=${2:-eth1}

echo "[*] Removing qdiscs from $WAN and $LAN..."
sudo tc qdisc del dev "$WAN" root 2>/dev/null || true
sudo tc qdisc del dev "$LAN" root 2>/dev/null || true

echo "[+] Interfaces restored to default state."
