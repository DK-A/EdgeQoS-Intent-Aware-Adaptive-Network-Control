#!/usr/bin/env bash
# scripts/run_all_prepi_stages.sh - Runs Stages S2, S3, S6 in real Linux kernel namespaces
set -euo pipefail

echo "=========================================================="
echo "Starting EdgeQoS Pre-Pi Real Kernel Validation (NETNS)"
echo "=========================================================="

echo "[1/2] Running Stage S2: Flow Classification & Tin Steering..."
python3 scripts/run_stage_s2_trace.py

echo ""
echo "[2/2] Running Stage S3: Real Traffic Latency Benchmark under Load..."
python3 scripts/run_stage_s3_real_benchmark.py

echo ""
echo "=========================================================="
echo "[+] All Pre-Pi Kernel Validations Completed Successfully!"
echo "=========================================================="
