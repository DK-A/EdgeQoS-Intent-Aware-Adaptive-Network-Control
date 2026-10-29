#!/usr/bin/env bash
# topo/teardown.sh - Clean teardown of E1 namespaces and interfaces
set -euo pipefail

echo "[*] Tearing down E1 network namespaces..."
for n in c1 c2 sw gw isp srv; do
    ip netns del "$n" 2>/dev/null || true
done
echo "[+] Teardown complete."
