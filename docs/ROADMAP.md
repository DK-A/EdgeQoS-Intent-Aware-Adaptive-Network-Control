# EdgeQoS: Engineering Roadmap & Milestones

**Project:** EdgeQoS — Intent-Aware Active Queue Management  
**Compliance:** Tata Elxsi TELIPORT Season 4 · Case Study 3  
**Planning Principle:** Clear delineation between current prototype milestones, pre-production integration, and production hardware validation.

---

## 🗺️ Multi-Phase Development Roadmap

The engineering roadmap is structured into four sequential phases:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     FOUR-PHASE ENGINEERING ROADMAP                                     │
├─────────────────────┬─────────────────────┬───────────────────────────┬────────────────────────────────┤
│ Phase 1: Foundation │ Phase 2: Integration│ Phase 3: Comparative Eval │ Phase 4: Hardware Validation   │
│ [STATUS: COMPLETED] │ [STATUS: IN PROGRESS│ [STATUS: PLANNED]         │ [STATUS: PLANNED]              │
├─────────────────────┼─────────────────────┼───────────────────────────┼────────────────────────────────┤
│ • 4-Netns Testbed   │ • Closed Control    │ • SOTA Comparative Bench  │ • Raspberry Pi 4B Deployment   │
│ • CAKE diffserv4    │   Loop Pipeline     │   (OpenWrt SQM, Autorate) │ • Physical Dual-GbE Interfaces │
│ • Zero-DPI Snaplen  │ • Behavioral Guard  │ • Multi-Run Matrix (n>=10)│ • Hardware CPU/Thermal Profile │
│ • TinyML Decision   │   Demotion (SC6)    │ • Scenario 3 Evaluation   │ • Sustained Churn Stress Test  │
│   Tree Classifier   │ • CLI Intent Leases │ • Fairness & Starvation   │ • OpenWrt Package (.ipk)       │
│ • Proof of Privacy  │ • IPv6 Architecture │ • RESTful Intent API      │ • Carrier Field Trial Readiness│
└─────────────────────┴─────────────────────┴───────────────────────────┴────────────────────────────────┘
```

---

## Phase 1: Foundation & Feasibility
* **Objective:** Prove the core networking and classification building blocks on a real Linux kernel.
* **Key Deliverables:**
  * [x] **Virtual 4-Namespace Testbed (`c1`, `gw`, `isp`, `srv`):** Automated setup and teardown scripts with `tc-cake`, `tbf`, and `netem` (`scripts/setup_netns_topo.sh`).
  * [x] **CAKE Multi-Tin Mapping Verification:** Empirically verified DSCP-to-tin steering (`EF` $\to$ Tin 3, `AF41` $\to$ Tin 2, `CS0` $\to$ Tin 1, `CS1` $\to$ Tin 0) in `scripts/test_tin_mapping.py` and `docs/tin_map_observed.md`.
  * [x] **In-Kernel Protocol-Aware Zero-DPI Capture:** Enforced 28B snaplen for UDP and 40B for TCP in `dataplane/edgeqos.nft`. Verified 0 bytes payload leak in `tests/test_privacy.py`.
  * [x] **Sub-Microsecond TinyML Classifier:** Quantized Decision Tree model achieving $0.741\ \mu\text{s}$ inference, $100\%$ accuracy on test dataset, and calibrated confidence abstention (`ml/classifier.py`).
* **Status:** **✅ COMPLETED**

---

## Phase 2: Core Module Integration
* **Objective:** Close the end-to-end feedback loop between classification, dynamic rate tracking, and kernel enforcement.
* **Key Deliverables:**
  * [x] **Integrated Capacity Tracking Controller:** Passive queue-RTT latency fusion controller with latched hysteresis (`controller/guard.py`).
  * [x] **Capacity Collapse Draining Test ($SC_2$):** Demonstrating real-time recovery from $124\text{ ms}$ bufferbloat to $20.5\text{ ms}$ bounded delay in $1.64\text{s}$ (`results/netns_collapse_result.json`).
  * [x] **Behavioral Rate Guard Demotion ($SC_6$):** Detection and demotion of rogue bulk flows masquerading as voice within $\le 1.25\text{s}$ (`results/demotion_cdf.png`).
  * [x] **Temporary Intent Leases (CLI):** Time-bounded priority reservation via `nftables` sets (`controller/lease.py`).
  * [ ] **IPv6 Dual-Stack Support:** Extend C packet reader and `nftables` rules to parse IPv6 fixed 40-byte headers and 20-bit Flow Labels.
  * [ ] **RESTful Intent API:** Expose HTTP endpoints (`POST /api/v1/intent`) for mobile app / web integration.
* **Status:** **🔧 IN PROGRESS**

---

## Phase 3: Comprehensive Comparative Evaluation
* **Objective:** Rigorously benchmark EdgeQoS against state-of-the-art baselines across repeated runs with statistical confidence intervals.
* **Key Deliverables:**
  * [ ] **Multi-Run Experimental Sweeps ($n \ge 10$):** Execute 10 runs per scenario cell; report median, $p95$, $p99$, and interquartile spread (IQR).
  * [ ] **Fair Baseline Sweep:** Compare EdgeQoS against tuned static CAKE (90%, 95%, 98% line rate) and existing `cake-autorate` under identical collapse conditions.
  * [ ] **Scenario 3 Execution:** Saturated three 4K streaming TVs concurrently with competitive cloud gaming.
  * [ ] **Starvation & Fairness Stress Testing:** Saturated multi-flow stress test measuring Jain's Fairness Index across background bulk downloads during prolonged telepresence calls.
* **Status:** **📝 PLANNED**

---

## Phase 4: Embedded Hardware Validation (Raspberry Pi 4B)
* **Objective:** Transition from virtual network namespaces to physical silicon deployment on the target CPE hardware.
* **Key Deliverables:**
  * [ ] **Physical Testbed Benchmarking:** Deploy EdgeQoS on Raspberry Pi 4 Model B (Quad-Core Cortex-A72 @ 1.5 GHz, dual-NIC setup: on-board GbE LAN + USB 3.0 RTL8153 GbE WAN).
  * [ ] **Resource Profiling under Sustained Line Rate:** Measure CPU utilization (target $< 12\%$ single core), RAM footprint (target $< 25\text{ MB}$ RSS), and thermal equilibrium under full 100 Mbps load.
  * [ ] **Flow Churn & Scale Testing:** Benchmark classifier and `nftables` radix tree performance under 1,000 active concurrent flows.
  * [ ] **OpenWrt Packaging:** Create standalone `.ipk` package and UCI configuration scripts for native deployment on carrier OpenWrt / RDK-B residential gateways.
* **Status:** **📝 PLANNED**
