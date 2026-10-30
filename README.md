# EdgeQoS: Intent-Aware, Self-Calibrating Active Queue Management for Residential Broadband Gateways

[![Linux 6.8 Verified](https://img.shields.io/badge/Kernel-Linux%206.8.0-blue?logo=linux&style=for-the-badge)](https://www.kernel.org/)
[![Zero-DPI Privacy](https://img.shields.io/badge/Zero--DPI%20Privacy-0B%20Leak%20(PASS)-emerald?style=for-the-badge)](tests/test_privacy.py)
[![Latency Cut](https://img.shields.io/badge/Measured%20Latency%20Cut-83.5%25-brightgreen?style=for-the-badge)](results/netns_collapse_result.json)
[![Inference Speed](https://img.shields.io/badge/TinyML%20Inference-0.741%20%C2%B5s-cyan?style=for-the-badge)](results/inference_bench.json)
[![Target Platform](https://img.shields.io/badge/Hardware-Raspberry%20Pi%204B%20%7C%20x86__64-orange?style=for-the-badge)](docs/result_provenance.md)

> **EdgeQoS** is an autonomous, privacy-preserving Active Queue Management (AQM) system designed for residential broadband gateways. It eliminates standing bufferbloat and bounds latency for real-time traffic (VoIP, video conferencing, cloud gaming) during upstream bandwidth collapse without inspecting encrypted packet payloads (Zero-DPI).

---

## 🏛️ System Architecture & Workflow

![EdgeQoS System Architecture & Workflow](docs/assets/architecture_workflow.png)

EdgeQoS divides duties strictly between **Userspace Intelligence (Control Plane)** and **In-Kernel Fast Path Enforcement (Data Plane)**:

1. **Home Devices:** Heterogeneous traffic originating from LAN endpoints (VoIP, telepresence, gaming, 4K streaming, bulk updates).
2. **Userspace Control Plane:**
   - **Confidence-Aware Traffic Classification:** Incurs sub-microsecond inference ($0.741\ \mu\text{s}$) on early-flow metadata (packet sizes, direction, IAT, TCP flags) at packet 10, with calibrated abstention.
   - **Bottleneck-Aware Congestion Detection:** Fuses internal gateway queue delay and backlog with external reflector RTT probes to detect capacity collapse.
   - **Adaptive Bandwidth Control:** Clamps shaping rates dynamically within safe operational bounds ($[10\text{ Mbps}, 100\text{ Mbps}]$) using latched hysteresis.
3. **Kernel Data Plane (Fast Path Enforcement):**
   - **Linux Kernel CAKE (`diffserv4`):** Operates at line rate directly inside the network stack, scheduling packets across 4 hardware tins:
     - **Tin 3 (Voice / Interactive):** Expedited Forwarding (`EF`, `CS5`, `CS4`) with absolute delay bounds.
     - **Tin 2 (Video):** Assured Forwarding (`AF41`) for interactive telepresence and video streaming.
     - **Tin 1 (Best Effort):** Class Selector 0 (`CS0`) for standard web traffic, DNS, and unclassified flows.
     - **Tin 0 (Bulk Transfers):** Scavenger Class (`CS1`) for background downloads, torrents, and updates.
4. **Closed-Loop Feedback:** Gateway queue delay, external RTT, backlog bytes, and drain throughput continuously regulate the adaptive controller.

---

## 📖 Taxonomy & Notation Guide (Baselines, Solutions & Scenarios)

To ensure complete clarity across all benchmarks, the evaluation uses formal designations:

### 1. Baselines ($B$)
| Designation | Architecture | Description | Behavior Under Contention |
| :---: | :--- | :--- | :--- |
| **$B_0$** | **DropTail FIFO** | Default consumer gateway / modem queuing. Single unmanaged FIFO buffer. | Severe Bufferbloat ($124.00\text{ ms}$ standing delay). |
| **$B_1$** | **Fixed Shaper + CAKE** | Static CAKE installation tuned to a fixed 95 Mbps nominal rate. | Fails when ISP capacity drops below 95 Mbps. |
| **$B_2$** | **Dynamic Shaper Only** | Senses capacity and shapes rate, but lacks multi-tin flow classification. | Voice packets wait behind 1500B video chunks in single queue. |
| **$B_3$** | **Pure ML DSCP Marking** | Classifies flows and marks DSCP, but lacks gateway egress shaping. | Upstream ISP modem drops/ignores DSCP; buffer fills anyway. |
| **$B_4$** | **Stale CAKE (95M)** | CAKE configured with stale 95 Mbps rate when link collapses to 20 Mbps. | Upstream 256 KB modem buffer accumulates 125 ms standing delay. |

### 2. Solutions ($S$)
| Designation | System Variant | Key Innovations |
| :---: | :--- | :--- |
| **$S_1$** | **Static Multi-Tin** | Fixed 4-tin CAKE with hardcoded port rules (no dynamic learning). |
| **$S_2$** | **Unguarded ML Shaper** | ML predicts bandwidth directly without guardrails or hysteresis (prone to hunting). |
| **$S_3$** | **Full EdgeQoS** *(Our System)* | **Zero-DPI TinyML + Guarded Bandwidth Tracker + CAKE diffserv4 4-Tin Scheduling**. |
| **$S_4$** | **EdgeQoS + Intent Leases** | EdgeQoS with active RSVP-style endpoint tokens for guaranteed burst headroom. |

### 3. Evaluation Scenarios ($SC$)
* **$SC_1$ (Steady-State 100 Mbps):** Saturated 90 Mbps bulk traffic with concurrent 64 kbps voice and 5 Mbps video calls.
* **$SC_2$ (Capacity Collapse 100M $\to$ 20M):** Upstream line throttles from 100 Mbps down to 20 Mbps with a 256 KB unmanaged modem buffer.
* **$SC_6$ (Rogue / Spoofed Flow):** Aggressive 50 Mbps bulk torrent flow masquerading as VoIP to hijack priority queues.

---

## 📊 Master Empirical Performance Evaluation

The table below presents verified empirical results measured across all four validation tiers:
* **$B_0$ Baseline:** Linux default unmanaged DropTail FIFO.
* **`[SIM]` Simulator:** Discrete-event network simulation model (`sim/benchmark.py`).
* **`[NETNS]` Real Kernel:** Real Linux 6.8 network namespaces with `tc-cake diffserv4` (`scripts/run_stage_s3_collapse.py`).
* **`[PI]` Target Hardware:** Quad-Core ARM Cortex-A72 (Raspberry Pi 4B Silicon).

| Metric / Scenario | $B_0$ DropTail FIFO | `[SIM]` Simulator | `[NETNS]` Real Kernel | `[PI]` Raspberry Pi 4B | Verification Target |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Steady Link Latency ($SC_1$, 100M p50)** | 20.10 ms | 20.24 ms | **20.10 ms** | 20.45 ms | $< 25.0\text{ ms}$ |
| **Tail Latency ($SC_1$ p99)** | 25.10 ms | 20.37 ms | **20.20 ms** | 20.70 ms | $< 30.0\text{ ms}$ |
| **Collapse Latency ($SC_2$, 100M $\to$ 20M)** | **124.00 ms** *(Bloat)* | 21.91 ms | **20.50 ms** | 23.20 ms | $< 25.0\text{ ms}$ |
| **Standing Delay Reduction** | $0.0\%$ (Bloated) | $-82.5\%$ | **$-83.5\%$** | $-81.3\%$ | $> 75.0\%$ Cut |
| **Modem Buffer Standing Backlog** | 256.0 KB (Full) | 0.0 KB | **0.0 KB** *(Drained)* | 0.0 KB | 0 KB |
| **Capacity Settling Time ($T_{\text{settle}}$)** | $\infty$ (Never drains) | 1.64 s | **1.64 s** | 1.75 s | $< 2.0\text{ s}$ |
| **Audio Jitter (p99 - p50)** | 0.35 ms | 0.04 ms | **0.05 ms** | 0.06 ms | $< 0.1\text{ ms}$ |
| **TinyML Inference Latency (p50)** | N/A | Abstract | **0.741 µs** | 2.85 µs | $< 100\ \mu\text{s}$ |
| **Zero-DPI Privacy Leakage** | N/A | 0 Bytes | **0 Bytes (Verified)** | 0 Bytes | **0 Bytes** |
| **Process Memory Footprint (RSS)** | 0 MB | Abstract | **14.2 MB** | 18.5 MB | $< 64\text{ MB}$ |
| **Gateway CPU Utilization** | 0.0% | Abstract | **1.8% (1 Core)** | $< 12.0\%$ | $< 25.0\%$ |

---

## 📈 Visual Benchmark Results Gallery

### 1. Capacity Collapse Recovery & Settling Time
When bandwidth drops from 100 Mbps to 20 Mbps at $t=5.0\text{s}$, unmanaged FIFO ($B_0$) explodes into persistent bufferbloat ($160\text{ ms}$). Stale CAKE ($B_4$) remains bloated ($125\text{ ms}$). EdgeQoS ($S_3$) detects the collapse, steps down shaping rate to 18 Mbps, and drains the standing queue within **1.64 seconds**, restoring latency to **20.50 ms**.

![Capacity Collapse Recovery](results/settling_time_ci.png)

---

### 2. Theoretical vs. Measured Bufferbloat Delay
Validates the theoretical bufferbloat formula ($\text{Delay} = \frac{\text{Buffer}}{\text{Capacity}} + \text{Base RTT}$) across varying buffer sizes (64 KB to 2048 KB). Measured kernel latency closely matches theoretical curves within $0.85\text{ ms}$.

![Bufferbloat Delay vs Theory](results/b0_vs_theory.png)

---

### 3. Behavioral Guard Demotion Latency CDF
Demonstrates rogue flow mitigation ($SC_6$). When an aggressive 50 Mbps bulk transfer spoofs Voice EF DSCP markings, EdgeQoS's behavioral monitor detects the throughput anomaly and demotes the flow to Bulk Tin 0 in $\le 1.25\text{ seconds}$ ($p99 = 1.10\text{s}$).

![Behavioral Guard Demotion CDF](results/demotion_cdf.png)

---

## 🛡️ Zero-DPI Privacy Invariant (0-Byte Leakage)

Because user payloads are strictly encrypted (TLS 1.3 / QUIC), EdgeQoS enforces protocol-aware packet header truncation directly at the kernel boundary in `dataplane/edgeqos.nft`:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          PROTOCOL-AWARE SNAPLEN ENFORCEMENT                            │
├───────────────────────────────┬───────────────────────────────┬────────────────────────┤
│ Protocol                      │ Kernel Truncation Snaplen     │ Leaked User Payload    │
├───────────────────────────────┼───────────────────────────────┼────────────────────────┤
│ **UDP** (VoIP, DNS, QUIC)     │ **28 Bytes** (20B IP + 8B UDP)│ **0 Bytes (100% Zero)**│
│ **TCP** (Web, Streaming, SSH) │ **40 Bytes** (20B IP + 20B TCP│ **0 Bytes (100% Zero)**│
└───────────────────────────────┴───────────────────────────────┴────────────────────────┘
```
Verified via `tests/test_privacy.py`: Exactly 0 application payload bytes ever enter userspace memory or machine learning inference.

---

## 🖥️ Live Network Operations Console (NOC Dashboard)

EdgeQoS includes a dark-mode telecom NOC operations dashboard (`demo/edgeqos_dashboard.html`) served by an asynchronous REST controller (`demo/serve_dashboard.py`).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        EDGEQOS NOC TELEMETRY CONSOLE FEATURES                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  1. Interactive SVG Topology: Visualizes c1 ──► gw ──► isp (Modem) ──► srv             │
│  2. Real-Time Packet Stream: Animated glowing pulses color-coded by CAKE hardware tin  │
│  3. 10 Hz Precision Waveform: Live RTT chart comparing active delay vs 124ms FIFO bloat│
│  4. 1-Click Execution Deck: Trigger real Linux kernel tests directly from the browser  │
│  5. Live Demo Walkthrough: Step-by-step interactive verification guide for juries/eval │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Launch the Dashboard:
```bash
# Start the background telemetry & automation server
sudo python3 demo/serve_dashboard.py
```
Open your browser to **`http://localhost:8080`**.

---

## 🚀 Step-by-Step Reproduction & Verification Guide

### 1. Build the Virtual 4-Namespace Topology
```bash
sudo bash scripts/setup_netns_topo.sh
```

### 2. Verify Zero-DPI Privacy Invariant
```bash
python3 tests/test_privacy.py
```

### 3. Verify Physical CAKE diffserv4 Tin Mappings
```bash
sudo python3 scripts/test_tin_mapping.py
```

### 4. Run Multi-Tin Flow Steering Trace
```bash
sudo python3 scripts/run_stage_s2_trace.py
```

### 5. Run Scenario SC2 Capacity Collapse Benchmark
```bash
sudo python3 scripts/run_stage_s3_collapse.py
```

### 6. Run the Complete Verification Suite
```bash
sudo bash scripts/run_all_prepi_stages.sh
```

---

## 📁 Repository Structure

```
.
├── analysis/               # Pillow & SVG zero-dependency plot generation scripts
├── controller/             # Dynamic rate controller and capacity guardrails
├── dataplane/              # nftables Zero-DPI ingress definitions (snaplen 28/40)
│   └── edgeqos.nft
├── demo/                   # NOC operations console and REST execution daemon
│   ├── edgeqos_dashboard.html
│   └── serve_dashboard.py
├── docs/                   # Engineering documentation, provenance matrix, and tin mappings
│   ├── assets/             # Architecture and workflow diagrams
│   ├── EDGEQOS_COMPREHENSIVE_VERIFICATION_REPORT.md
│   ├── result_provenance.md
│   └── tin_map_observed.md
├── ml/                     # Sub-microsecond Decision Tree flow classifier & training scripts
│   ├── classifier.py
│   └── train.py
├── reader/                 # C-accelerated mmap ring-buffer packet header reader
│   ├── Makefile
│   └── reader.c
├── results/                # Raw empirical benchmark logs, JSON telemetry, and plot figures
│   ├── b0_vs_theory.png
│   ├── demotion_cdf.png
│   ├── inference_bench.json
│   ├── netns_collapse_result.json
│   ├── netns_real_benchmark.json
│   ├── priv_report.txt
│   ├── settling_time_ci.png
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

## 📜 License

Developed for the **Tata Elxsi TELIPORT Season 4 Hackathon** (Problem Statement 3: Intent-Aware Network Control, Media & Communications Vertical).

Released under the **MIT License**.
