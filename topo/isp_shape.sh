#!/usr/bin/env bash
# topo/isp_shape.sh - Emulates upstream ISP bottleneck and modem buffer (BUF)
# Usage: ./isp_shape.sh RATE_MBIT DELAY_MS BUF_BYTES
set -euo pipefail

R=${1:?Rate in Mbit required}
D=${2:-10}            # One-way base propagation delay (ms)
BUF=${3:-262144}      # Buffer in bytes (default: 256KB = 262,144 bytes)

echo "[*] Applying ISP shape: Rate=${R}Mbit, Delay=${D}ms, Buffer=${BUF}Bytes..."
for IF in isp-gw isp-srv; do
    ip netns exec isp tc qdisc replace dev "$IF" root handle 1: netem delay "${D}ms"
    ip netns exec isp tc qdisc replace dev "$IF" parent 1:1 handle 10: tbf rate "${R}mbit" burst 128kb limit "$BUF"
done
echo "[+] ISP emulator updated."
