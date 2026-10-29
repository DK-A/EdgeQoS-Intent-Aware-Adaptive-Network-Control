#!/usr/bin/env bash
# safety/restore.sh - ExecStopPost lifecycle clean restoration
echo "[*] Restoring interfaces to clean unmanaged state..."
tc qdisc del dev eth0 root 2>/dev/null || true
tc qdisc del dev eth1 root 2>/dev/null || true
nft flush table inet edgeqos 2>/dev/null || true
rm -f /run/edgeqos.heartbeat /run/edgeqos.safe
echo "[+] Restoration complete."
