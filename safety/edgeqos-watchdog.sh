#!/usr/bin/env bash
# safety/edgeqos-watchdog.sh - Independent Supervisor Heartbeat Watchdog
# Monitors /run/edgeqos.heartbeat every 1.0 second.
# If daemon stales (> 3.0s), immediately flushes nftables priority sets
# and resets CAKE shaper to conservative safe bandwidth.

HB=/run/edgeqos.heartbeat
SAFE_RATE=20
MAXAGE=3

echo "[*] EdgeQoS Watchdog initialized (Deadline=${MAXAGE}s)..."

while true; do
    now=$(date +%s)
    hb=$(stat -c %Y "$HB" 2>/dev/null || echo 0)
    diff=$(( now - hb ))

    if (( diff > MAXAGE )) && [[ ! -e /run/edgeqos.safe ]]; then
        echo "[!] Watchdog ALERT: Daemon heartbeat missing for ${diff}s! Entering failsafe state..."
        # Flush priority sets
        for s in promo_rt promo_vid promo_blk lease_rt; do
            nft flush set inet edgeqos "$s" 2>/dev/null || true
        done
        # Lock CAKE shaper to safe rate
        tc qdisc change dev eth0 root cake bandwidth "${SAFE_RATE}mbit" diffserv4 wash 2>/dev/null || true
        tc qdisc change dev eth1 root cake bandwidth "${SAFE_RATE}mbit" diffserv4 wash 2>/dev/null || true
        touch /run/edgeqos.safe
        logger -t edgeqos-watchdog "Failsafe safe-state applied: rate=${SAFE_RATE}Mbit"
    elif (( diff <= MAXAGE )); then
        rm -f /run/edgeqos.safe 2>/dev/null || true
    fi
    sleep 1
done
