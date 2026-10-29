#!/usr/bin/env bash
# Baseline B3: Static CAKE diffserv4 tuned to correct nominal rate (95 Mbit)
IF=${1:-eth0}
RATE=${2:-95}
sudo tc qdisc replace dev "$IF" root cake bandwidth "${RATE}mbit" diffserv4 dual-srchost wash
echo "[+] Baseline B3 (Static CAKE diffserv4 correctly tuned) applied on $IF at ${RATE}Mbit"
