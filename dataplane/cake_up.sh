#!/usr/bin/env bash
# dataplane/cake_up.sh - Attach CAKE diffserv4 to WAN (upload) and LAN (download)
set -euo pipefail

WAN=${1:-eth0}
LAN=${2:-eth1}
C_UP=${3:-95}   # Default: 95 Mbit (for 100M link)
C_DN=${4:-95}

echo "[*] Configuring CAKE diffserv4 on WAN ($WAN) at ${C_UP}Mbit..."
sudo tc qdisc replace dev "$WAN" root cake bandwidth "${C_UP}mbit" diffserv4 dual-srchost nat wash

echo "[*] Configuring CAKE diffserv4 on LAN ($LAN) at ${C_DN}Mbit..."
sudo tc qdisc replace dev "$LAN" root cake bandwidth "${C_DN}mbit" diffserv4 dual-dsthost wash

echo "[+] CAKE diffserv4 successfully attached."
