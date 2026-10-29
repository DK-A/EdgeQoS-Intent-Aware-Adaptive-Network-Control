#!/usr/bin/env bash
# env/setup_pi.sh - Target gateway setup for Raspberry Pi 4B (E2)
set -euo pipefail

echo "[*] Configuring CPU frequency governor to 'performance' for benchmark reproducibility..."
if [ -d /sys/devices/system/cpu/cpu0/cpufreq ]; then
    for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        echo performance | sudo tee "$g" > /dev/null
    done
    echo "[+] CPU governor set to performance."
else
    echo "[!] cpufreq directory not found, skipping governor pinning."
fi

echo "[*] Disabling unattended background noise..."
sudo systemctl stop apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true

echo "[*] Configuring networking sysctls..."
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -w net.netfilter.nf_conntrack_acct=1
sudo sysctl -w net.netfilter.nf_conntrack_timestamp=1

echo "[*] Checking thermal state..."
if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd measure_temp
    vcgencmd get_throttled
fi

echo "[*] EdgeQoS Raspberry Pi 4B environment setup complete."
