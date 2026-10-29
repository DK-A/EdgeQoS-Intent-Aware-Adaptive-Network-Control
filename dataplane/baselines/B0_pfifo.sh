#!/usr/bin/env bash
# Baseline B0: Unmanaged FIFO (pfifo_fast / pfifo limit 10000)
# C15: Explicitly configure pfifo to prevent distro default fq_codel from masking bufferbloat
IF=${1:-eth0}
sudo tc qdisc replace dev "$IF" root pfifo limit 10000
echo "[+] Baseline B0 (pfifo limit 10000) applied on $IF"
