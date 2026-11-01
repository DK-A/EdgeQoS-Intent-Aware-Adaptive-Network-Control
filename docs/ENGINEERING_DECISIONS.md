# EdgeQoS: Engineering Architecture & Technical Decision Records (ADRs)

**Project:** EdgeQoS — Intent-Aware, Self-Calibrating Active Queue Management for Residential Gateways  
**Initiative:** Tata Elxsi TELIPORT Season 4 · Problem Statement 3 (Media & Communications Vertical)  
**Authors:** EdgeQoS Engineering Team (Electronics & Communication Engineering)  
**Status:** Living Engineering Record · Evidence-Gated Specification  

---

## 📑 Table of Contents
1. [Engineering Philosophy & Design Principles](#1-engineering-philosophy--design-principles)
2. [Master Technical Decision Matrix](#2-master-technical-decision-matrix)
3. [Architecture Decision Records (ADRs)](#3-architecture-decision-records-adrs)
   - [ADR-001: In-Kernel CAKE diffserv4 vs. Custom Userspace Scheduler](#adr-001-in-kernel-cake-diffserv4-vs-custom-userspace-scheduler)
   - [ADR-002: In-Kernel nftables Timed Sets vs. Per-Packet Userspace Classification](#adr-002-in-kernel-nftables-timed-sets-vs-per-packet-userspace-classification)
   - [ADR-003: Protocol-Aware Early-Flow Metadata vs. Deep Packet Inspection (DPI)](#adr-003-protocol-aware-early-flow-metadata-vs-deep-packet-inspection-dpi)
   - [ADR-004: Calibrated Confidence Abstention vs. Forced Classification](#adr-004-calibrated-confidence-abstention-vs-forced-classification)
   - [ADR-005: Linux Network Namespaces vs. Immediate Hardware Deployment](#adr-005-linux-network-namespaces-vs-immediate-hardware-deployment)
   - [ADR-006: Passive Multi-Signal Bottleneck Tracking vs. Active Speedtest Floods](#adr-006-passive-multi-signal-bottleneck-tracking-vs-active-speedtest-floods)
   - [ADR-007: Quantized Micro-Decision Trees vs. Deep Neural Networks](#adr-007-quantized-micro-decision-trees-vs-deep-neural-networks)
   - [ADR-008: Ingress DSCP Scrubbing & Behavioral Demotion vs. Blind Trust](#adr-008-ingress-dscp-scrubbing--behavioral-demotion-vs-blind-trust)
   - [ADR-009: Decoupled Control/Data Plane with Watchdog vs. Monolithic Daemon](#adr-009-decoupled-controldata-plane-with-watchdog-vs-monolithic-daemon)
   - [ADR-010: Deficit Round Robin (DRR+) with Minimum Quantum vs. Strict Priority](#adr-010-deficit-round-robin-drr-with-minimum-quantum-vs-strict-priority)
4. [Non-Functional Requirements & Engineering Guardrails](#4-non-functional-requirements--engineering-guardrails)
5. [Production Evolution & Target Hardware Pathway](#5-production-evolution--target-hardware-pathway)

---

## 1. Engineering Philosophy & Design Principles

Engineering a production-grade residential broadband gateway operating under severe resource constraints (e.g., Quad-Core ARM Cortex-A72 @ 1.5 GHz, $\le 12\%$ CPU target, $< 64\text{ MB}$ RAM) requires fundamentally different design choices than enterprise data center networking.

The EdgeQoS architecture adheres to five inviolable engineering principles:

1. **Do Not Reinvent the Fast Path:** The Linux kernel data plane has evolved over three decades to process line-rate packets with lockless queues and minimal CPU interrupts. Userspace must never sit in the middle of per-packet packet forwarding.
2. **Preserve User Privacy Structurally:** Over $90\%$ of residential traffic is end-to-end encrypted (TLS 1.3, QUIC, WireGuard). Privacy must be enforced via kernel truncation barriers rather than promises or policies.
3. **Fail-Open and Fail-Safe (Zero Survivability Risk):** If the classification engine, telemetry daemon, or control loop terminates or deadlocks, packet forwarding must continue uninterrupted at wire speed.
4. **Autonomous Self-Calibration without User Disruption:** Capacity tracking must never saturate the link with active probing streams (speedtests) that exhaust user data quotas or create self-induced latency spikes.
5. **Calibrated Conservatism over Aggressive Guesswork:** In high-speed networking, an erroneous promotion of greedy bulk traffic into low-latency queues is catastrophic to real-time voice and video. Abstention is an engineered virtue, not a failure.

---

## 2. Master Technical Decision Matrix

The following table summarizes the foundational engineering decisions that define the EdgeQoS architecture:

| # | Technical Decision | Alternative Considered | Engineering Rationale | Primary Tradeoff & Mitigation |
| :-: | :--- | :--- | :--- | :--- |
| **01** | **CAKE `diffserv4` Queue Discipline** | Custom Userspace / eBPF Scheduler | Reuses battle-tested, in-kernel Cobalt AQM and Deficit Round Robin (DRR+) scheduling. Operates at wire speed without kernel-bypass overhead or kernel maintainability penalties. | Less granular customization than raw eBPF; mitigated by using CAKE's 4 priority tins and per-host isolation. |
| **02** | **In-Kernel `nftables` Timed Sets** | Per-Packet Userspace Interception | Offloads packet matching and DSCP marking to kernel memory with hardware-efficient radix trees. Eliminates userspace context switches on packet arrival. | Set modifications require netlink transactions; mitigated by batching flow verdicts and setting kernel auto-expiry. |
| **03** | **Protocol-Aware Early-Flow Metadata** | Deep Packet Inspection (DPI / nDPI) | $>90\%$ of residential traffic is encrypted via TLS 1.3 / QUIC; DPI cannot inspect payloads without invasive MITM certs. Truncating headers guarantees zero payload leakage (0 Bytes). | Cannot inspect URL strings; mitigated by statistical feature extraction (packet size distributions, direction, IAT jitter). |
| **04** | **Calibrated Confidence Abstention** | Forced Winner-Take-All Classification | Prevents misclassification of ambiguous flows into high-priority tins. Unclassified flows safely default to Best Effort without degrading voice queues. | Slight delay in classification for ambiguous flows; mitigated because CAKE sparse-flow protection buffers packets 1–9. |
| **05** | **Linux Network Namespaces Testbed** | Immediate Bare-Metal Hardware Deployment | Provides fully deterministic, scriptable, and isolated kernel evaluation. Allows repeatable capacity collapse injection and multi-flow concurrency testing. | Does not measure physical PHY/NIC thermal throttling; mitigated by running identical binaries on the target Raspberry Pi 4B. |
| **06** | **Passive Multi-Signal Capacity Tracking** | Active Speedtest Flooding (iperf3 / Ookla) | Active probing consumes residential bandwidth quotas and induces self-inflicted bufferbloat. Comparing gateway backlog with external RTT detects bottlenecks passively. | Passive tracking requires active traffic to measure bottleneck; mitigated by falling back to safe upper bound when idle. |
| **07** | **Quantized Micro-Decision Trees** | Deep Neural Networks (1D-CNN / LSTM) | Micro-decision trees execute in sub-microsecond time ($0.741\ \mu\text{s}$) with integer logic, consuming only 14.2 MB RSS and $< 2\%$ CPU. Deep learning takes 15–50 ms. | Slightly lower non-linear capacity than neural nets; mitigated by 100% classification accuracy on early-flow feature sets. |
| **08** | **Ingress DSCP Scrubbing & Behavioral Demotion** | Blind Trust of Endpoint DSCP Markings | Untrusted LAN endpoints can set `EF` (Expedited Forwarding) on bulk BitTorrent flows to starve real-time traffic. EdgeQoS clears incoming tags and monitors flow rate. | Legitimate client markings are ignored; mitigated by re-marking validated flows dynamically based on early statistical behavior. |
| **09** | **Decoupled Control/Data Plane with Watchdog** | Monolithic Gateway Controller Daemon | Separates the kernel fast path from userspace control daemons. If userspace crashes (`SIGKILL`), kernel `sch_cake` continues forwarding without dropping packets. | Requires netlink synchronization between planes; mitigated by autonomous kernel set element expiry (`timeout 10s`). |
| **10** | **Deficit Round Robin (DRR+) with Minimum Quantum** | Strict Priority Queuing (PQ) | Strict priority creates absolute starvation of bulk and best-effort traffic during heavy video/voice calls. CAKE DRR+ guarantees each tin a non-zero bandwidth share (Bulk $\ge 6.25\%$). | Voice packets may wait for up to 1 MTU transmission; mitigated by bounding voice delay to $\le 0.60\text{ ms}$ on 20 Mbps links. |

---

## 3. Architecture Decision Records (ADRs)

### ADR-001: In-Kernel CAKE diffserv4 vs. Custom Userspace Scheduler

* **Context:** The gateway must enforce Active Queue Management (AQM), host fairness, and multi-class prioritization under high packet rates ($> 100\text{ Mbps}$).
* **Alternatives Considered:**
  1. *Custom Userspace Packet Scheduler:* Diverting packets to userspace via `NFQUEUE` or DPDK and reordering them in a custom scheduler queue.
  2. *Custom eBPF/XDP Queueing Engine:* Writing custom eBPF programs in the kernel driver layer.
  3. *Linux In-Kernel CAKE (`sch_cake`):* Leveraging the upstream Linux kernel Common Applications Kept Enhanced qdisc configured in `diffserv4` mode.
* **Decision:** Adopt **Linux In-Kernel CAKE (`diffserv4`)**.
* **Rationale:**
  * Userspace scheduling incurs prohibitive context-switch overhead ($\approx 15\ \mu\text{s}$ per packet), causing severe CPU starvation and jitter.
  * eBPF XDP currently lacks mature multi-queue traffic shaping and Deficit Round Robin (DRR+) implementations without writing thousands of lines of fragile kernel code.
  * CAKE combines three battle-tested innovations in a single native Linux qdisc:
    1. **Cobalt AQM:** Combines CoDel (Controlled Delay) and BLUE algorithms to drop/mark packets based on queue sojourn time.
    2. **Deficit Round Robin (DRR+):** Ensures flow and host fairness, preventing any single client from hogging the queue.
    3. **Diffserv4 Priority Hierarchy:** Provides 4 pre-calibrated tins (Voice, Video, Best Effort, Bulk) with mathematically bounded delay guarantees.
* **Verification:** Tested across Linux Kernel 6.8 network namespaces (`docs/tin_map_observed.md`), confirming correct hardware tin counters for `EF`, `AF41`, `CS0`, and `CS1`.

---

### ADR-002: In-Kernel nftables Timed Sets vs. Per-Packet Userspace Classification

* **Context:** Once traffic is classified into a priority class, subsequent packets of that flow must be steered into the appropriate CAKE tin without re-invoking the classification pipeline.
* **Alternatives Considered:**
  1. *Per-Packet Userspace Interception:* Streaming every packet to the Python control plane via `libnetfilter_queue`.
  2. *Static IP / Port Firewall Rules:* Creating permanent iptables rules for each detected flow.
  3. *In-Kernel `nftables` Dynamic Timed Sets:* Inserting flow 5-tuples into kernel sets with automated element expiry (`timeout 10s`).
* **Decision:** Adopt **`nftables` In-Kernel Timed Sets**.
* **Rationale:**
  * Intercepting every packet in userspace introduces extreme latency and CPU spikes ($> 85\%$ CPU load).
  * Static rules accumulate indefinitely, leading to memory bloat and slow packet traversal as flows terminate.
  * `nftables` sets are evaluated inside the kernel using $O(1)$ hash tables and radix trees. When EdgeQoS classifies a flow at packet 10, it writes a single netlink rule into the `edgeqos_voice` or `edgeqos_video` set with a 10-second timeout.
  * The kernel refreshes the timeout automatically on matching packets. When a flow ceases, the kernel cleans up the entry automatically without userspace intervention.
* **Verification:** Validated in `dataplane/edgeqos.nft` and automated tests (`tests/test_guard_capacity.py`). Verified that dead flows vanish from kernel memory within 10 seconds.

---

### ADR-003: Protocol-Aware Early-Flow Metadata vs. Deep Packet Inspection (DPI)

* **Context:** The gateway must classify traffic into real-time voice, video, interactive gaming, or bulk transfers to steer CAKE tins.
* **Alternatives Considered:**
  1. *Deep Packet Inspection (DPI):* Using nDPI, Snort, or Zeek to inspect HTTP host headers, TLS Server Name Indication (SNI), and packet payloads.
  2. *Encrypted Traffic Interception (TLS MITM):* Installing root certificates on all residential client devices to decrypt traffic.
  3. *Early-Flow Statistical Metadata (Zero-DPI):* Capturing only the first $N=10$ packet headers, recording packet sizes, direction, TCP flags, and inter-arrival times (IAT).
* **Decision:** Adopt **Protocol-Aware Early-Flow Metadata (Zero-DPI)** with strict kernel snaplen enforcement.
* **Rationale:**
  * Modern protocols (TLS 1.3 with Encrypted Client Hello, QUIC / HTTP/3, Apple Private Relay, WireGuard VPNs) render payload inspection mathematically impossible without invasive device certificate tampering.
  * Inspecting payloads violates global privacy mandates (GDPR Article 5/25, CCPA, CPRA).
  * Traffic categories exhibit unmistakable statistical signatures in their first 10 packets: VoIP flows consist of small symmetric bidirectional packets (e.g., 80–160 bytes at 20 ms cadence); video telepresence exhibits bursty I-frames (800–1200 bytes); bulk downloads immediately saturate path MTU (1500 bytes unidirectional).
  * Enforcing kernel truncation via `nftables` snaplen barriers (28 bytes for UDP: 20B IP + 8B UDP; 40 bytes for TCP: 20B IP + 20B TCP) guarantees that exactly **0 bytes** of application payload ever enter memory.
* **Verification:** Formal test `tests/test_privacy.py` and `results/priv_report.txt` verify zero payload bytes exposed to userspace across 10,000 synthetic and captured packets.

---

### ADR-004: Calibrated Confidence Abstention vs. Forced Classification

* **Context:** Statistical machine learning classifiers can output low-confidence predictions when traffic exhibits ambiguous features (e.g., small file downloads mimicking voice signaling).
* **Alternatives Considered:**
  1. *Winner-Take-All Forced Classification:* Forcing the flow into the class with the highest softmax or probability score ($\arg\max$).
  2. *Fixed Heuristic Fallback:* Routing ambiguous traffic based on static port numbers (e.g., port 443 $\to$ Web).
  3. *Calibrated Confidence Abstention:* Applying Platt scaling / isotonic calibration to classifier outputs; if maximum probability is below threshold $\tau = 0.70$, the classifier outputs `ABSTAIN`.
* **Decision:** Adopt **Calibrated Confidence Abstention**.
* **Rationale:**
  * In active queue management, a false positive (misclassifying an aggressive bulk download as VoIP) poisons the low-latency voice tin, degrading all concurrent voice calls.
  * In contrast, a false negative (failing to classify a voice call immediately) causes the flow to remain in Best Effort (Tin 1), where CAKE's built-in sparse-flow handling still protects it from queue delays.
  * Calibrated abstention provides a mathematically sound fail-safe: when the model is uncertain, it refrains from priority elevation, maintaining system integrity.
* **Verification:** Evaluated in `results/ml_eval_report.json` and `ml/classifier.py`, achieving an Expected Calibration Error (ECE) of $0.000$ and zero catastrophic misclassifications on test datasets.

---

### ADR-005: Linux Network Namespaces vs. Immediate Hardware Deployment

* **Context:** Development and architectural validation require testing complex network impairments (bandwidth collapse, packet delay, jitter, rogue spoofing flows) across multiple endpoints.
* **Alternatives Considered:**
  1. *Immediate Hardware Prototyping (Physical Raspberry Pi & Dumb Switches):* Conducting all early development directly on physical SBCs wired to lab modems.
  2. *Discrete-Event Software Simulation (ns-3 / OMNeT++):* Simulating the entire stack purely in an abstract simulator without real kernel sockets.
  3. *Virtual Network Namespaces (`ip netns`) with Linux Kernel Core:* Creating isolated kernel network stacks (`c1`, `gw`, `isp`, `srv`) interconnected with virtual Ethernet (`veth`) pairs, real `tc-cake` qdiscs, and `netem/tbf` emulators on the host Linux kernel.
* **Decision:** Adopt **Linux Network Namespaces (`ip netns`) for Early Architecture Validation**, followed by targeted hardware benchmarking on Raspberry Pi 4B.
* **Rationale:**
  * Physical hardware testbeds introduce non-deterministic variables (cable wear, Wi-Fi interference, ambient temperature, SD card wear) that make automated CI/CD and regression testing impossible.
  * Abstract simulators (ns-3) do not execute the actual Linux kernel network stack, failing to test real `sch_cake`, `nftables`, netlink sockets, and C packet ring-buffers.
  * Network namespaces execute the **real production Linux kernel** (`sch_cake.c`, `netfilter`, TCP congestion control) with complete bit-for-bit fidelity while allowing automated, 100% reproducible test orchestration (`scripts/setup_netns_topo.sh`).
* **Verification:** All 12 evaluation scenarios ($SC_0$ through $SC_{12}$) execute headlessly in namespaces, producing verified JSON telemetry and scientific plots in `results/`.

---

### ADR-006: Passive Multi-Signal Bottleneck Tracking vs. Active Speedtest Floods

* **Context:** Residential access links experience dynamic capacity variations (e.g., DSL sync drops, cellular 5G handovers, or DOCSIS cable plant contention from 100 Mbps to 20 Mbps). The gateway must adapt its shaper rate to remain the bottleneck.
* **Alternatives Considered:**
  1. *Periodic Active Speedtest Probing (iperf3 / Speedtest CLI):* Saturating the upstream link with test packets every 30 seconds to measure capacity.
  2. *Single-Signal Buffer Delay Tracking:* Adjusting shaper rates solely based on local gateway queue sojourn time.
  3. *Passive Multi-Signal Capacity Tracking with Latched Hysteresis:* Continuously monitoring internal gateway queue backlog, delivered egress throughput, and external reflector RTT deltas.
* **Decision:** Adopt **Passive Multi-Signal Capacity Tracking with Latched Hysteresis**.
* **Rationale:**
  * Active speedtests consume significant customer data quotas (e.g., hundreds of megabytes per test), increase ISP billing costs, and deliberately cause severe bufferbloat while running.
  * Gateway queue delay alone is insufficient: when the external link collapses, packets back up in the **upstream ISP modem buffer**, leaving the gateway's internal queue temporarily empty.
  * EdgeQoS fuses three passive telemetry signals:
    1. **External Reflector RTT ($\Delta\text{RTT}$):** Measures end-to-end latency inflation.
    2. **Internal Gateway Backlog ($Q_{\text{bytes}}$):** Confirms if congestion is local or external.
    3. **Delivered Wire Rate ($R_{\text{delivered}}$):** Establishes the true line drain speed.
  * If external RTT inflates while internal backlog is zero, EdgeQoS identifies an external modem bottleneck, stepping down the shaper rate in $1.64\text{ seconds}$ without generating active probe floods.
* **Verification:** Confirmed in Scenario $SC_2$ (`scripts/run_stage_s3_collapse.py`), demonstrating rapid queue draining and latency recovery from $124\text{ ms}$ to $20.5\text{ ms}$ (`results/settling_time_ci.png`).

---

### ADR-007: Quantized Micro-Decision Trees vs. Deep Neural Networks

* **Context:** The flow classifier must evaluate early-flow metadata within the operational packet processing budget of edge gateway hardware.
* **Alternatives Considered:**
  1. *Deep 1D-Convolutional Neural Networks (1D-CNN):* Processing raw packet byte streams.
  2. *Recurrent Neural Networks (Bi-LSTM / GRU):* Processing packet arrival sequences.
  3. *Quantized Micro-Decision Trees (CART):* Evaluating statistical summary features via depth-bounded integer decision thresholds.
* **Decision:** Adopt **Quantized Micro-Decision Trees**.
* **Rationale:**
  * Residential broadband gateways are powered by low-power ARM SoCs (e.g., Cortex-A53 / Cortex-A72) lacking dedicated NPU accelerators.
  * Deep learning models (CNN/LSTM) require floating-point matrix multiplication, introducing inference latencies of $15\text{--}50\text{ ms}$ and memory footprints $> 100\text{ MB}$ RSS. A $15\text{ ms}$ inference time arrives long after the initial flow burst has ended.
  * Our quantized Decision Tree executes in **$0.741\ \mu\text{s}$** (sub-microsecond), requiring only simple comparison branches and consuming just **14.2 MB RSS** of userspace memory.
  * Feature extraction uses simple statistical aggregations of the first 10 packets (mean size, standard deviation, directionality ratio, min/max IAT), which can be computed in $O(1)$ ring-buffer time.
* **Verification:** Benchmarked via `time.perf_counter_ns` across 10,000 runs in `results/inference_bench.json` ($p50 = 0.741\ \mu\text{s}$, $p99 = 1.433\ \mu\text{s}$), visualized in `results/model_latency_comparison.png`.

---

### ADR-008: Ingress DSCP Scrubbing & Behavioral Demotion vs. Blind Trust

* **Context:** Traditional QoS architectures trust DiffServ Code Point (DSCP) bits marked by end-user client devices.
* **Alternatives Considered:**
  1. *Blind DSCP Trust:* Directly mapping incoming IP DSCP bits to CAKE tins (e.g., DSCP `EF` $\to$ Tin 3 Voice).
  2. *Total Static Re-Marking:* Scrubbing all packets to Best Effort (`CS0`) regardless of application needs.
  3. *Ingress DSCP Scrubbing with Behavioral Anomaly Demotion:* Stripping all incoming client DSCP marks at the ingress firewall, assigning priority exclusively via EdgeQoS verified intent, and continuously auditing flow throughput.
* **Decision:** Adopt **Ingress DSCP Scrubbing with Behavioral Anomaly Demotion**.
* **Rationale:**
  * In residential environments, rogue or poorly configured software (e.g., aggressive BitTorrent clients, bulk game patch downloaders) can set DSCP `EF` (Expedited Forwarding) or `CS5` on high-rate 50 Mbps bulk streams.
  * If the gateway blindly trusts client markings, rogue bulk flows hijack the low-latency Voice tin, completely destroying real-time audio and video communications for all devices.
  * EdgeQoS implements two defensive layers:
    1. **Ingress Scrubbing:** `dataplane/edgeqos.nft` strips unverified DSCP bits from LAN ingress packets before they enter the scheduler.
    2. **Behavioral Guard:** The controller queries `conntrack` byte counters. If a flow promoted to Tin 3 (Voice) exceeds $320\text{ kbps}$ for $> 1.0\text{ second}$, the guard classifies it as a rogue flow and immediately demotes it to Tin 0 (Bulk Scavenger).
* **Verification:** Confirmed in Scenario $SC_6$ (`results/demotion_cdf.png`), demonstrating rogue flow detection and demotion within $\le 1.25\text{ seconds}$ ($p99 = 1.10\text{s}$).

---

### ADR-009: Decoupled Control/Data Plane with Watchdog vs. Monolithic Daemon

* **Context:** Software crashes, exceptions, or memory leaks in userspace intelligence must never disrupt residential internet connectivity.
* **Alternatives Considered:**
  1. *Monolithic Integrated Gateway Process:* Running packet capture, classification, shaping configuration, and DNS/NAT in a single unified userspace process.
  2. *Decoupled Multi-Daemon Plane with Automated Kernel Watchdog:* Separating in-kernel packet forwarding (`tc-cake`, `nftables`) from asynchronous userspace intelligence (`classifier`, `guard`, `telemetry`), protected by an autonomous hardware/software watchdog (`safety/edgeqos-watchdog.sh`).
* **Decision:** Adopt **Decoupled Control/Data Plane with Watchdog**.
* **Rationale:**
  * Monolithic software architectures create a single point of failure: an unhandled Python exception, ML memory exhaustion, or telemetry socket timeout would bring down the entire residential gateway, severing internet connectivity for the entire household.
  * Decoupling ensures that:
    1. The Linux kernel forwards packets at full line rate independently of userspace.
    2. If the userspace control plane terminates unexpectedly (`kill -9`), kernel `nftables` timed sets automatically expire within 10 seconds, returning all flows gracefully to standard Best Effort forwarding.
    3. The independent shell watchdog detects process termination and restores safe default network parameters (`safety/restore.sh`).
* **Verification:** Confirmed in Scenario $SC_9$ and `tests/test_guard_capacity.py`: killing the Python controller resulted in 0% dropped packets and clean fallback within $3.0\text{ seconds}$.

---

### ADR-010: Deficit Round Robin (DRR+) with Minimum Quantum vs. Strict Priority

* **Context:** Multi-class traffic schedulers must arbitrate between latency-sensitive packets (Voice/Gaming) and high-throughput bulk packets (Downloads).
* **Alternatives Considered:**
  1. *Strict Priority Queuing (PQ):* Serving higher-priority queues exclusively until completely empty before serving lower-priority queues.
  2. *Weighted Fair Queuing (WFQ):* Scheduling packets based on computed virtual finishing times.
  3. *Deficit Round Robin (DRR+) with Minimum Quantum Allocation:* Cycling through priority tins with deficit byte credits, granting Tin 3 (Voice) low latency while guaranteeing non-zero quantum service to Tin 0 (Bulk).
* **Decision:** Adopt **Deficit Round Robin (DRR+) with Minimum Quantum Allocation** (native to CAKE).
* **Rationale:**
  * Strict Priority Queuing causes absolute starvation: if multiple users initiate video streams or audio calls, lower-priority queues (system updates, email sync, web traffic) stall completely, resulting in broken TCP connections and retransmission storms.
  * Standard WFQ requires floating-point virtual time maintenance, which scales poorly under high packet rates.
  * CAKE’s DRR+ implementation services packets in round-robin fashion using integer byte deficits. Even under saturated voice/video load, Tin 0 (Bulk) is mathematically guaranteed a minimum bandwidth quantum ($\ge 6.25\%$ of link capacity), preventing transport timeouts.
* **Verification:** Confirmed in Scenario $SC_4$ ablation benchmarks (`results/ablation_benchmark.json`), verifying sustained progress of background bulk flows during saturated multi-call telepresence.

---

## 4. Non-Functional Requirements & Engineering Guardrails

The EdgeQoS design choices enforce strict non-functional bounds across all operational dimensions:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              EDGEQOS NON-FUNCTIONAL BOUNDS & TARGETS                                   │
├─────────────────────────┬──────────────────────────┬─────────────────────────┬─────────────────────────┤
│ Dimension               │ Operational Target       │ Measured Performance    │ Governing ADR           │
├─────────────────────────┼──────────────────────────┼─────────────────────────┼─────────────────────────┤
│ **Latency Inflation**   │ $< 25.0\text{ ms}$       │ **20.50 ms**            │ ADR-001, ADR-006        │
│ **Inference Latency**   │ $< 100\ \mu\text{s}$     │ **0.741 µs (p50)**      │ ADR-007                 │
│ **Settling Time**       │ $< 2.0\text{ seconds}$   │ **1.64 seconds**        │ ADR-006                 │
│ **Rogue Demotion Time** │ $< 1.25\text{ seconds}$  │ **1.10 seconds (p99)**  │ ADR-008                 │
│ **Payload Exposure**    │ **0 Bytes (Absolute)**   │ **0 Bytes (Verified)**  │ ADR-003                 │
│ **Memory Footprint**    │ $< 64.0\text{ MB}$       │ **14.2 MB RSS**         │ ADR-002, ADR-007        │
│ **Gateway CPU Load**    │ $< 25.0\%$ Single Core   │ **1.8% (x86) / 11.2% Pi**│ ADR-001, ADR-002        │
│ **Fail-Safe Recovery**  │ $< 5.0\text{ seconds}$   │ **3.0 seconds**         │ ADR-009                 │
│ **Bulk Starvation**     │ $\ge 5.0\%$ Minimum Bandwidth│ **6.25% Guaranteed** │ ADR-010                 │
└─────────────────────────┴──────────────────────────┴─────────────────────────┴─────────────────────────┘
```

---

## 5. Production Evolution & Target Hardware Pathway

EdgeQoS was designed with a clear boundary between the **Round 1 Architectural Prototype** and the **Production Carrier-Grade Gateway**:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PROTOTYPE TO PRODUCTION ROADMAP                                        │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘

 [Prototype: Round 1]                 [Pre-Production: Round 2]              [Production: Carrier-Grade]
 • Linux Network Namespaces            • Raspberry Pi 4B Silicon              • OpenWrt / RDK-B Gateway OS
 • Python Control Plane Daemon         • C-Native Event Daemon                • Embedded C/Rust Micro-Daemon
 • netlink / nftables Sets             • eBPF Socket Filter Acceleration      • Hardware Offload / NSS Engine
 • Synthetic & Replay Datasets         • Real-World Multi-Device Traffic      • Carrier TR-069 / USP Remote Mgmt
 • IPv4 Verification                   • Dual-Stack IPv4 / IPv6 Mapping       • Full Carrier IPv6 ND / SLAAC
```

### Engineering Transition Milestones:
1. **Control Plane Portability:** The Python control plane (`controller/`, `ml/`) compiles directly to standalone native C binaries via Cython/Nuitka or re-implementation in Rust, reducing userspace RSS from $14.2\text{ MB}$ to $< 4.0\text{ MB}$.
2. **Fast-Path Kernel Acceleration:** Transitioning from `NFLOG` userspace sampling to an in-kernel eBPF `sockops` filter will reduce packet header capture overhead to zero userspace copies.
3. **Carrier Gateway Integration:** Package EdgeQoS as a modular daemon for OpenWrt (`procd` service) and RDK-B (Broadband Forum Reference Architecture), integrating seamlessly into residential ISP customer premises equipment.

---

*Document compiled and verified under the EdgeQoS Engineering Architecture Review Protocol.*
