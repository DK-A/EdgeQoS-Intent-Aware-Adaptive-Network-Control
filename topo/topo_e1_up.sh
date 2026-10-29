#!/usr/bin/env bash
# topo/topo_e1_up.sh - Network namespace testbed (E1)
# Namespaces: c1, c2 (LAN clients) -> sw (LAN bridge) -> gw (EdgeQoS) -> isp (Bottleneck emulator) -> srv (Internet)
set -euo pipefail

echo "[*] Creating network namespaces..."
for n in c1 c2 sw gw isp srv; do
    ip netns add "$n" 2>/dev/null || true
done

mk() {
    ip link add "$1" type veth peer name "$2"
    ip link set "$1" netns "$3"
    ip link set "$2" netns "$4"
}

echo "[*] Connecting veth pairs..."
mk c1-sw  sw-c1  c1 sw
mk c2-sw  sw-c2  c2 sw
mk gw-lan sw-gw  gw sw
mk gw-wan isp-gw gw isp
mk isp-srv srv-isp isp srv

echo "[*] Setting up LAN bridge in sw..."
ip netns exec sw ip link add br0 type bridge
for i in sw-c1 sw-c2 sw-gw; do
    ip netns exec sw ip link set "$i" master br0
done

echo "[*] Assigning IP addresses..."
ip netns exec c1  ip addr add 192.168.50.10/24 dev c1-sw
ip netns exec c2  ip addr add 192.168.50.11/24 dev c2-sw
ip netns exec gw  ip addr add 192.168.50.1/24  dev gw-lan
ip netns exec gw  ip addr add 10.0.0.2/30      dev gw-wan
ip netns exec isp ip addr add 10.0.0.1/30      dev isp-gw
ip netns exec isp ip addr add 10.0.1.1/30      dev isp-srv
ip netns exec srv ip addr add 10.0.1.2/30      dev srv-isp

# Three reflector endpoints on srv (for capacity controller RTT probing)
ip netns exec srv ip addr add 10.0.1.3/32 dev srv-isp 2>/dev/null || true
ip netns exec srv ip addr add 10.0.1.4/32 dev srv-isp 2>/dev/null || true

for n in c1 c2 sw gw isp srv; do
    ip netns exec "$n" ip link set lo up
done

for p in "c1 c1-sw" "c2 c2-sw" "sw sw-c1" "sw sw-c2" "sw sw-gw" "sw br0" \
         "gw gw-lan" "gw gw-wan" "isp isp-gw" "isp isp-srv" "srv srv-isp"; do
    set -- $p
    ip netns exec "$1" ip link set "$2" up
done

echo "[*] Setting default routes..."
ip netns exec c1 ip route add default via 192.168.50.1
ip netns exec c2 ip route add default via 192.168.50.1
ip netns exec gw ip route add default via 10.0.0.1
ip netns exec srv ip route add default via 10.0.1.1

for n in gw isp; do
    ip netns exec "$n" sysctl -qw net.ipv4.ip_forward=1
done

# Disable hardware offloads on veths to prevent GSO 64KB burst distortion in emulated queues
for p in "isp isp-gw" "isp isp-srv" "srv srv-isp" "c1 c1-sw" "c2 c2-sw"; do
    set -- $p
    ip netns exec "$1" ethtool -K "$2" gso off tso off gro off 2>/dev/null || true
done

echo "[+] E1 virtual testbed successfully initialized."
