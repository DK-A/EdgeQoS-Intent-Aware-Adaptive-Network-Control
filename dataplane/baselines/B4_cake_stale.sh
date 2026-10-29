#!/usr/bin/env bash
# Baseline B4: Static CAKE tuned to STALE link rate (e.g. 95 Mbit shaper on collapsed 20 Mbit link)
IF=${1:-eth0}
STALE_RATE=${2:-95}
sudo tc qdisc replace dev "$IF" root cake bandwidth "${STALE_RATE}mbit" diffserv4 dual-srchost wash
echo "[+] Baseline B4 (Static CAKE with STALE rate) applied on $IF at ${STALE_RATE}Mbit"
