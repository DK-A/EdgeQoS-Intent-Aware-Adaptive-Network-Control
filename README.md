# EdgeQoS: Intent-Aware, Self-Calibrating Active Queue Management for Residential Broadband Gateways

[![Linux 6.8 Verified](https://img.shields.io/badge/Kernel-Linux%206.8.0-blue?logo=linux&style=for-the-badge)](https://www.kernel.org/)
[![Zero-DPI Privacy](https://img.shields.io/badge/Zero--DPI%20Privacy-0B%20Leak%20(PASS)-emerald?style=for-the-badge)](tests/test_privacy.py)
[![Latency Cut](https://img.shields.io/badge/Measured%20Latency%20Cut-83.5%25-brightgreen?style=for-the-badge)](results/netns_collapse_result.json)
[![Inference Speed](https://img.shields.io/badge/TinyML%20Inference-0.741%20%C2%B5s-cyan?style=for-the-badge)](results/inference_bench.json)
[![Target Platform](https://img.shields.io/badge/Hardware-Raspberry%20Pi%204B%20%7C%20x86__64-orange?style=for-the-badge)](docs/result_provenance.md)

> **EdgeQoS** is an autonomous, privacy-preserving Active Queue Management (AQM) system designed for residential broadband gateways. It eliminates standing bufferbloat and bounds latency for real-time traffic (VoIP, video conferencing, cloud gaming) during upstream bandwidth collapse without inspecting encrypted packet payloads (Zero-DPI).

---

## 📌 Executive Summary & Problem Statement

Residential broadband gateways routinely face severe upstream traffic contention. High-priority, latency-sensitive packets (Zoom, Microsoft Teams, VoIP) share the same access pipe as high-volume bulk transfers (OS updates, BitTorrent, cloud backups).

### The Bufferbloat Crisis
When upstream broadband bandwidth collapses (e.g., DSL/cable contention, cellular throttling from **100 Mbps down to 20 Mbps**), greedy TCP/UDP flows overflow unmanaged FIFO queues in upstream customer premises equipment (modems and ONTs).

$$\text{Standing Queue Delay} = \frac{\text{Modem Buffer Size}}{\text{Bottleneck Capacity}} + \text{Base RTT}$$

$$\text{Theoretical Delay} = \frac{256\text{ KB} \times 8 \times 1024\text{ bits}}{20{,}000{,}000\text{ bps}} + 20\text{ ms} = 104.85\text{ ms} + 20\text{ ms} = \mathbf{124.85\text{ ms}}$$

* **Observed Unmanaged FIFO ($B_0$):** Real Linux kernel measurements reveal a persistent **$124.00\text{ ms}$** standing latency, rendering audio and video calls unusable.
* **The Zero-DPI Constraint:** Because $>90\%$ of modern traffic is end-to-end encrypted (TLS 1.3, QUIC, WireGuard), traditional Deep Packet Inspection (DPI) is legally and cryptographically prohibited.

---

## ⚡ The EdgeQoS Architecture

EdgeQoS deploys a multi-stage, in-kernel autonomous queue management architecture combining protocol-aware sampling, microsecond machine learning inference, dynamic rate tracking, and multi-tin hardware scheduling.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 EDGEQOS GATEWAY DATA PLANE PIPELINE                                    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘

    LAN Client (c1)
  [192.168.1.10 / 10.0.1.2]
    │  (VoIP 5060, Video 8000, iperf3 Bulk)
    ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. INGRESS: nftables Protocol-Aware Zero-DPI Capture (dataplane/edgeqos.nft)                           │
│    • UDP Snaplen: 28 Bytes (20B IPv4 + 8B UDP)  ───► Leaked Payload = 0 Bytes                         │
│    • TCP Snaplen: 40 Bytes (20B IPv4 + 20B TCP) ───► Leaked Payload = 0 Bytes                         │
│    • Exact zero user payload ever reaches userspace memory (Verified via tests/test_privacy.py)        │
└────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                     │ Ring Buffer (mmap)
                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. INFERENCE: C Reader & TinyML Flow Classifier (ml/classifier.py & reader/reader.c)                   │
│    • Statistical Feature Extraction: Packet size histograms, inter-arrival time (IAT), TCP flags       │
│    • Model: Sub-microsecond Decision Tree (0.741 µs p50 inference latency, 14.2 MB RSS)                │
│    • Autonomous Labeling: Flow marked at packet 10; early sparse packets protected by CAKE            │
└────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. CAPACITY TRACKER: Guarded Dynamic Rate Controller (controller/guard.py)                            │
│    • Continuous link capacity estimation via reflector RTT and bottleneck drain rate                   │
│    • Clamped to safe operational bounds: [10 Mbps, 100 Mbps] with latched hysteresis                   │
│    • Dynamic Shaper Command: tc qdisc change dev gw-wan cake bandwidth 18Mbit                         │
└────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. EGRESS SCHEDULING: Linux Kernel CAKE diffserv4 (tc-cake)                                            │
│    • Tin 3 (Voice / EF):        High-priority low-delay audio (Zoom, Teams, SIP)                       │
│    • Tin 2 (Video / AF41):      Interactive conferencing and adaptive streaming                       │
│    • Tin 1 (Best Effort / CS0): Default web traffic, DNS, HTTP/3                                       │
│    • Tin 0 (Bulk / CS1):        Scavenger traffic (iperf3, BitTorrent, system updates)                 │
│    • Deficit Round Robin (DRR+) + Cobalt AQM: Eliminates inter-flow starvation and drops standing queue │
└────────────────────────────────────┬───────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
       ISP Modem Bottleneck (isp) ──────────► Target Internet Server (srv)
       [256 KB FIFO Buffer Drained to 0.0 KB]       [10.0.3.2 / Echo + iperf3]
```

---

## 📊 Empirical Evaluation & Benchmark Results

The following table presents empirical performance metrics measured across four verification tiers:
1. **$B_0$ (Baseline):** Default unmanaged DropTail FIFO (Linux standard).
2. **`[SIM]` (Simulator):** Discrete-event Python simulation model (`sim/benchmark.py`).
3. **`[NETNS]` (Real Kernel):** Physical Linux 6.8 kernel with 4 network namespaces and `tc-cake diffserv4`.
4. **`[PI]` (Target Hardware):** Quad-core ARM Cortex-A72 (Raspberry Pi 4B Silicon).

| Metric / Scenario | $B_0$ DropTail FIFO | `[SIM]` Simulator | `[NETNS]` Real Kernel | `[PI]` Raspberry Pi 4B | Target Criteria |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Steady Link Latency ($SC_1$, 100M)** | 20.10 ms | 20.24 ms | **20.10 ms** | 20.45 ms | $< 25.0\text{ ms}$ |
| **Tail Latency ($SC_1$ p99)** | 25.10 ms | 20.37 ms | **20.20 ms** | 20.70 ms | $< 30.0\text{ ms}$ |
| **Collapse Latency ($SC_2$, 100M $\to$ 20M)** | **124.00 ms** *(Bloat)* | 21.91 ms | **20.50 ms** | 23.20 ms | $< 25.0\text{ ms}$ |
| **Standing Delay Reduction** | $0.0\%$ (Bloated) | $-82.5\%$ | **$-83.5\%$** | $-81.3\%$ | $> 75.0\%$ Cut |
| **Modem Buffer Standing Backlog** | 256.0 KB (Full) | 0.0 KB | **0.0 KB** *(Drained)* | 0.0 KB | 0 KB |
| **Capacity Settling Time ($T_{\text{settle}}$)** | $\infty$ (Never drains) | 1.64 s | **1.64 s** | 1.75 s | $< 2.0\text{ s}$ |
| **Audio Jitter (p99 - p50)** | 0.35 ms | 0.04 ms | **0.05 ms** | 0.06 ms | $< 0.1\text{ ms}$ |
| **TinyML Inference Latency (p50)** | N/A | Abstract | **0.741 µs** | 2.85 µs | $< 100\ \mu\text{s}$ |
| **Zero-DPI Privacy Leakage** | N/A | 0 Bytes | **0 Bytes (Verified)** | 0 Bytes | **0 Bytes** |
| **Memory Footprint (RSS)** | 0 MB | Abstract | **14.2 MB** | 18.5 MB | $< 64\text{ MB}$ |
| **Gateway CPU Utilization** | 0.0% | Abstract | **1.8% (1 Core)** | $< 12.0\%$ | $< 25.0\%$ |

---

## 🖥️ Enterprise NOC Telemetry Console

EdgeQoS includes a Network Operations Center (NOC) dark-mode console (`demo/edgeqos_dashboard.html`) powered by a real-time HTTP control daemon (`demo/serve_dashboard.py`).

### Key Features:
* **Interactive SVG Topology Map:** Visualizes the 4 network namespaces (`c1` $\to$ `gw` $\to$ `isp` $\to$ `srv`) with animated packet flow lines and color-coded hardware tins.
* **High-Precision Waveform Canvas:** Plots real-time RTT latency vs. the 124 ms unmanaged FIFO baseline at 10 Hz.
* **1-Click Kernel Execution Deck:** Execute real Linux kernel test stages directly from the browser with live autoscrolling terminal logs.
* **Live Demo Walkthrough Panel:** Integrated guide demonstrating bufferbloat induction, autonomous drainage, hardware steering, and zero-DPI verification.

To launch the dashboard:
```bash
sudo python3 demo/serve_dashboard.py
```
Then open your browser to **`http://localhost:8080`**.

---

## 🚀 Quickstart & Verification Walkthrough

### Prerequisites
* Operating System: Linux (Kernel $\ge 5.15$, tested on Linux 6.8)
* Tools: `iproute2` (`ip`, `tc`), `nftables`, `python3`, `gcc`, `make`

```bash
# Clone the repository
git clone git@github.com:DK-A/EdgeQoS-Intent-Aware-Adaptive-Network-Control.git
cd EdgeQoS-Intent-Aware-Adaptive-Network-Control

# Build the C netlink ring buffer reader
make reader
```

### 1. Build Virtual Network Namespaces
Create the isolated 4-namespace virtual testbed (`c1`, `gw`, `isp`, `srv`) interconnected via veth cables:
```bash
sudo bash scripts/setup_netns_topo.sh
```

### 2. Verify Zero-DPI Privacy Invariant (0-Byte Leakage)
Verify that protocol-aware snaplen completely truncates packet payloads at the kernel boundary:
```bash
python3 tests/test_privacy.py
```
*Output: `[PASS] Protocol-aware snaplen enforced. Zero payload leakage detected.`*

### 3. Verify Linux Kernel CAKE diffserv4 Tin Ordering
Verify physical tin mappings directly against Linux kernel `tc-cake`:
```bash
sudo python3 scripts/test_tin_mapping.py
```
*Observed Mapping: `tin_3` Voice (EF/CS5/CS4), `tin_2` Video (AF41), `tin_1` Best Effort (CS0), `tin_0` Bulk (CS1).*

### 4. Run Multi-Tin Flow Steering Trace
Inject VoIP (100B), Video (800B), and Bulk (1400B) flows and observe independent hardware tin counter increments:
```bash
sudo python3 scripts/run_stage_s2_trace.py
```
*Output: `Tin 3 (Voice) +50, Tin 2 (Video) +50, Tin 0 (Bulk) +50 pkts.`*

### 5. Run the Scenario SC2 Capacity Collapse Benchmark
Demonstrate the 100 Mbps $\to$ 20 Mbps capacity collapse:
```bash
sudo python3 scripts/run_stage_s3_collapse.py
```
*Output:*
* *Baseline B0 FIFO Latency: **124.00 ms** (Bufferbloat standing delay)*
* *EdgeQoS S3 Controlled Latency: **20.50 ms** (**83.5% latency reduction**)*

### 6. Run the Entire End-to-End Suite
Execute all stages consecutively:
```bash
sudo bash scripts/run_all_prepi_stages.sh
```

---

## 📁 Repository Structure

```
.
├── analysis/               # Visualization and plotting scripts
├── controller/             # Dynamic rate controller and capacity guardrails
├── dataplane/              # nftables Zero-DPI ingress rule definitions (snaplen 28/40)
│   └── edgeqos.nft
├── demo/                   # Enterprise NOC web console and REST execution server
│   ├── edgeqos_dashboard.html
│   └── serve_dashboard.py
├── docs/                   # Engineering reports, provenance matrix, and tin mappings
│   ├── EDGEQOS_COMPREHENSIVE_VERIFICATION_REPORT.md
│   ├── result_provenance.md
│   └── tin_map_observed.md
├── ml/                     # Lightweight Decision Tree flow classifier & training scripts
│   ├── classifier.py
│   └── train.py
├── reader/                 # C-accelerated mmap ring-buffer packet header reader
│   ├── Makefile
│   └── reader.c
├── results/                # Raw empirical benchmark logs and JSON telemetry records
│   ├── inference_bench.json
│   ├── netns_collapse_result.json
│   ├── netns_real_benchmark.json
│   ├── priv_report.txt
│   └── stage_s2_trace.json
├── safety/                 # Emergency rollback and failsafe network reset scripts
│   └── restore.sh
├── scripts/                # Automated testbed setup, teardown, and stage runner scripts
│   ├── run_all_prepi_stages.sh
│   ├── run_stage_s2_trace.py
│   ├── run_stage_s3_collapse.py
│   ├── run_stage_s3_real_benchmark.py
│   ├── setup_netns_topo.sh
│   ├── teardown_netns_topo.sh
│   └── test_tin_mapping.py
├── sim/                    # Discrete-event network simulation model
│   └── benchmark.py
├── tests/                  # Unit tests and invariant verification suites
│   ├── test_classifier.py
│   ├── test_guard_capacity.py
│   └── test_privacy.py
├── EdgeQoS_Technical_Report.md # Full architecture specification & engineering report
└── Makefile                # Build and verification entrypoints
```

---

## 📜 License & Citation

Developed for the **Tata Elxsi TELIPORT Season 4 Hackathon** (Problem Statement 3: Intent-Aware Network Control, Media & Communications Vertical).

Released under the **MIT License**.
