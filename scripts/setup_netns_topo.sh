#!/usr/bin/env bash
# scripts/setup_netns_topo.sh - Stage S0/S2: 4-Namespace Linux Kernel Testbed
# c1 (Client) <-> gw (EdgeQoS Gateway) <-> isp (Bottleneck) <-> srv (Server)
set -euo pipefail

echo "[*] Cleaning any existing test namespaces..."
for ns in c1 gw isp srv; do
    ip netns del "$ns" 2>/dev/null || true
done

echo "[*] Creating network namespaces: c1, gw, isp, srv..."
ip netns add c1
ip netns add gw
ip netns add isp
ip netns add srv

echo "[*] Creating veth cable pairs..."
# c1 <-> gw (LAN)
ip link add c1-eth0 type veth peer name gw-lan
ip link set c1-eth0 netns c1
ip link set gw-lan netns gw

# gw <-> isp (WAN)
ip link add gw-wan type veth peer name isp-lan
ip link set gw-wan netns gw
ip link set isp-lan netns isp

# isp <-> srv (Internet)
ip link add isp-wan type veth peer name srv-eth0
ip link set isp-wan netns isp
ip link set srv-eth0 netns srv

echo "[*] Configuring IP addresses and bringing links up..."
# c1
ip netns exec c1 ip addr add 192.168.1.10/24 dev c1-eth0
ip netns exec c1 ip link set lo up
ip netns exec c1 ip link set c1-eth0 up
ip netns exec c1 ip route add default via 192.168.1.1

# gw
ip netns exec gw ip addr add 192.168.1.1/24 dev gw-lan
ip netns exec gw ip addr add 10.0.1.1/24 dev gw-wan
ip netns exec gw ip link set lo up
ip netns exec gw ip link set gw-lan up
ip netns exec gw ip link set gw-wan up
ip netns exec gw sysctl -qw net.ipv4.ip_forward=1
ip netns exec gw ip route add default via 10.0.1.2

# isp
ip netns exec isp ip addr add 10.0.1.2/24 dev isp-lan
ip netns exec isp ip addr add 10.0.2.1/24 dev isp-wan
ip netns exec isp ip link set lo up
ip netns exec isp ip link set isp-lan up
ip netns exec isp ip link set isp-wan up
ip netns exec isp sysctl -qw net.ipv4.ip_forward=1
ip netns exec isp ip route add 192.168.1.0/24 via 10.0.1.1
ip netns exec isp ip route add 10.0.0.0/16 via 10.0.2.2 2>/dev/null || true

# srv
ip netns exec srv ip addr add 10.0.2.2/24 dev srv-eth0
ip netns exec srv ip link set lo up
ip netns exec srv ip link set srv-eth0 up
ip netns exec srv ip route add default via 10.0.2.1

echo "[*] Disabling hardware offloads (TSO/GSO/GRO) on emulator links..."
for iface in c1-eth0; do ip netns exec c1 ethtool -K "$iface" tso off gso off gro off 2>/dev/null || true; done
for iface in gw-lan gw-wan; do ip netns exec gw ethtool -K "$iface" tso off gso off gro off 2>/dev/null || true; done
for iface in isp-lan isp-wan; do ip netns exec isp ethtool -K "$iface" tso off gso off gro off 2>/dev/null || true; done
for iface in srv-eth0; do ip netns exec srv ethtool -K "$iface" tso off gso off gro off 2>/dev/null || true; done

echo "[*] Configuring ISP bottleneck emulator (100 Mbps, 20ms RTT, 256KB buffer)..."
# Ingress and egress on isp
ip netns exec isp tc qdisc replace dev isp-wan root handle 1: netem delay 10ms
ip netns exec isp tc qdisc replace dev isp-wan parent 1: handle 2: tbf rate 100Mbit burst 64kb limit 256kb

ip netns exec isp tc qdisc replace dev isp-lan root handle 1: netem delay 10ms
ip netns exec isp tc qdisc replace dev isp-lan parent 1: handle 2: tbf rate 100Mbit burst 64kb limit 256kb

echo "[*] Verifying end-to-end ping from Client (c1) to Server (srv)..."
ip netns exec c1 ping -c 3 -W 2 10.0.2.2

echo "[+] SUCCESS: 4-Namespace Testbed is fully operational!"
