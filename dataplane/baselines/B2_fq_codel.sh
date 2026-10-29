#!/usr/bin/env bash
# Baseline B2: Shaped FQ-CoDel
IF=${1:-eth0}
RATE=${2:-95}

sudo tc qdisc del dev "$IF" root 2>/dev/null || true
sudo tc qdisc add dev "$IF" root handle 1: htb default 10
sudo tc class add dev "$IF" parent 1: classid 1:10 htb rate "${RATE}mbit" ceil "${RATE}mbit"
sudo tc qdisc add dev "$IF" parent 1:10 fq_codel
echo "[+] Baseline B2 (Shaped FQ-CoDel) applied on $IF at ${RATE}Mbit"
