#!/usr/bin/env bash
# scripts/teardown_netns_topo.sh - Clean up namespace testbed
for ns in c1 gw isp srv ns_tin; do
    ip netns del "$ns" 2>/dev/null || true
done
echo "[+] All test namespaces removed."
