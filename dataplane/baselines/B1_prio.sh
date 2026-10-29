#!/usr/bin/env bash
# Baseline B1: HTB + Static Priority Queueing with u32 L4 port filters (SIP/RTP)
IF=${1:-eth0}
RATE=${2:-95}

sudo tc qdisc del dev "$IF" root 2>/dev/null || true
sudo tc qdisc add dev "$IF" root handle 1: htb default 20
sudo tc class add dev "$IF" parent 1: classid 1:1 htb rate "${RATE}mbit" ceil "${RATE}mbit"
sudo tc class add dev "$IF" parent 1:1 classid 1:10 htb rate 20mbit ceil "${RATE}mbit" prio 1
sudo tc class add dev "$IF" parent 1:1 classid 1:20 htb rate 75mbit ceil "${RATE}mbit" prio 2

# Filter UDP VoIP ports 5060, 3478, 10000-20000 into high priority class 1:10
sudo tc filter add dev "$IF" protocol ip parent 1:0 prio 1 u32 match ip protocol 17 0xff match ip dport 5060 0xffff flowid 1:10
sudo tc filter add dev "$IF" protocol ip parent 1:0 prio 1 u32 match ip protocol 17 0xff match ip dport 3478 0xffff flowid 1:10
echo "[+] Baseline B1 (HTB + static port PRIO) applied on $IF at ${RATE}Mbit"
