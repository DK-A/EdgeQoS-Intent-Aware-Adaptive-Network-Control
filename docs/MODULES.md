# EdgeQoS: Modular Component Contracts & State Machine Specification

**Project:** EdgeQoS — Intent-Aware Active Queue Management  
**Compliance:** Tata Elxsi TELIPORT Season 4 · Case Study 3 ("Independently Testable Modules")  
**Scope:** Formal definition of inputs, outputs, state transitions, failure modes, and acceptance criteria for every system module.

---

## 1. Modular System Decomposition

EdgeQoS is decomposed into six independently testable modules across the data plane, control plane, and safety supervision layer:

```
                      ┌───────────────────────────────────────────────┐
                      │              Incoming LAN Packets             │
                      └──────────────────────┬────────────────────────┘
                                             │
                                             ▼
                                  ┌────────────────────┐
                                  │   Module 1: CAPTURE│
                                  │   (nft + reader)   │
                                  └──────────┬─────────┘
                                             │ Header Records (N <= 10)
                                             ▼
                                  ┌────────────────────┐
                                  │ Module 2: CLASSIFY │
                                  │ (TinyML + Abstain) │
                                  └──────────┬─────────┘
                                             │ Class Verdict (Voice / Video / Bulk / Abstain)
                                             ▼
                                  ┌────────────────────┐
       ┌─────────────────────────►│  Module 4: ACTUATE │
       │                          │ (nft Timed Sets)   │
       │                          └──────────┬─────────┘
       │                                     │
       │ conntrack byte counts               ▼
┌──────┴─────────────┐            ┌────────────────────┐            ┌────────────────────┐
│   Module 3: GUARD  │            │  Module 5: TRACKER │            │ Module 6: WATCHDOG │
│(Behavioral Demote) │            │ (Capacity Tracker) │            │  (Safety Restore)  │
└────────────────────┘            └──────────┬─────────┘            └──────────┬─────────┘
                                             │ tc cake bandwidth               │ Heartbeat & Safe State
                                             ▼                                 ▼
                                  ┌────────────────────┐            ┌────────────────────┐
                                  │  Kernel Data Plane │◄───────────┤   Fail-Safe Reset  │
                                  │  (sch_cake diffserv│            │   (safety/restore) │
                                  └────────────────────┘            └────────────────────┘
```

---

## 2. Module Contract Specifications

### Module 1: Packet Capture & Truncation (`dataplane/edgeqos.nft` & `reader/reader.c`)
* **Purpose:** Inspects early-flow packet headers at line rate while enforcing the Zero-DPI privacy barrier.
* **Inputs:** Raw ingress IP packets routed across the gateway bridge.
* **Outputs:** Fixed-length binary header records: 5-tuple (src IP, dst IP, src port, dst port, proto), packet length, TCP flags, timestamp.
* **States & Transitions:**
  * `IDLE`: No packet matching flow table.
  * `SAMPLING`: Packet counter $N \le 10$ for flow. Copying header via `NFLOG` with protocol snaplen (28B UDP / 40B TCP).
  * `BYPASS`: Packet counter $N > 10$. Logging disabled by kernel `ct packets > 10`; packets forwarded without CPU interrupt.
* **Failure Handling:** If the userspace reader daemon crashes or exits, `NFLOG` packets are dropped silently by the kernel ring-buffer with zero packet loss or forwarding delay on the data path.
* **Success Condition:** Exactly 0 payload bytes copied to userspace (`tests/test_privacy.py` PASS).
* **Implementation Status:** **✅ Implemented & Tested** (`reader/reader.c`, `dataplane/edgeqos.nft`).

---

### Module 2: Early-Flow Classifier & Calibrator (`ml/classifier.py`)
* **Purpose:** Predicts application traffic intent (Voice, Video, Bulk, Web) from early-flow statistical summary features.
* **Inputs:** Array of first $N \le 10$ packet sizes, directionality flags, and inter-arrival times (IAT).
* **Outputs:** Tuple: `(Predicted_Class, Calibrated_Confidence, Action)`. Action is `PROMOTE` or `ABSTAIN`.
* **States & Transitions:**
  * `ACCUMULATING`: Flow has observed $< 10$ packets; awaiting feature vector completion.
  * `EVALUATING`: Flow reaches packet 10; CART Decision Tree evaluates integer threshold branches ($0.741\ \mu\text{s}$).
  * `DECIDED`: If $\max(P) \ge 0.70$, output predicted class.
  * `ABSTAINED`: If $\max(P) < 0.70$, output `ABSTAIN`; assign default Best Effort (`CS0`).
* **Failure Handling:** On missing or corrupted feature records, catches exception and safely outputs `(BEST_EFFORT, 0.0, ABSTAIN)`.
* **Success Condition:** Macro F1 $\ge 0.95$ on held-out test sessions, ECE $\le 0.05$, per-flow inference time $< 10\ \mu\text{s}$.
* **Implementation Status:** **✅ Implemented & Tested** (`ml/classifier.py`, `tests/test_classifier.py`).

---

### Module 3: Behavioral Rate Guard (`controller/guard.py`)
* **Purpose:** Continuously audits promoted flows to detect misclassifications or DSCP spoofing attacks.
* **Inputs:** Netfilter `conntrack` byte and packet counters queried every $250\text{ ms}$.
* **Outputs:** Demotion command: `nft delete element inet edgeqos promo_rt { 5-tuple } && nft add element inet edgeqos promo_blk { 5-tuple }`.
* **States & Transitions:**
  * `MONITORING`: Flow in `promo_rt` (Voice) has rolling throughput $\le 320\text{ kbps}$.
  * `SUSPECT`: Flow exceeds $320\text{ kbps}$ for $> 500\text{ ms}$.
  * `DEMOTED`: Flow exceeds threshold for $> 1.0\text{ second}$. Immediately moved to `promo_blk` (Tin 0).
* **Failure Handling:** If `conntrack` counters are inaccessible, demotion halts; kernel timed set automatically expires flow after $60\text{s}$.
* **Success Condition:** Measured rogue flow demotion latency $\le 1.25\text{ seconds}$ (`results/demotion_cdf.png`).
* **Implementation Status:** **✅ Implemented & Tested** (`controller/guard.py`, `tests/test_guard_capacity.py`).

---

### Module 4: Policy Actuator (`dataplane/edgeqos.nft` & `controller/lease.py`)
* **Purpose:** Applies traffic steering and QoS tags directly inside the Linux network stack.
* **Inputs:** Promotion verdicts from Classifier or Intent Leases from CLI/API.
* **Outputs:** Populated in-kernel `nftables` timed set elements (`promo_rt`, `promo_vid`, `promo_blk`, `lease_rt`).
* **States & Transitions:**
  * `ACTIVE`: Set element present in kernel; matching packets marked with DSCP `EF`, `AF41`, or `CS1`.
  * `REFRESHED`: In-flight packets reset kernel element timeout timer.
  * `EXPIRED`: No packets for $60\text{s}$ (or lease expiration); kernel deletes element automatically.
* **Failure Handling:** If actuator script crashes, kernel maintains existing timeouts; stale entries flush automatically.
* **Success Condition:** CAKE hardware tin counters match predicted flow counts (`scripts/test_tin_mapping.py` PASS).
* **Implementation Status:** **✅ Implemented & Tested** (`dataplane/edgeqos.nft`, `scripts/test_tin_mapping.py`).

---

### Module 5: Dynamic Capacity Tracker (`controller/guard.py`)
* **Purpose:** Dynamically tracks upstream bottleneck capacity and updates the CAKE shaper bandwidth.
* **Inputs:** Local gateway queue backlog ($Q_{\text{bytes}}$), delivered wire throughput ($R_{\text{wire}}$), and external reflector RTT ($\Delta\text{RTT}$).
* **Outputs:** Netlink command: `tc qdisc change dev <wan> root cake bandwidth <R_new>`.
* **States & Transitions:**
  * `STEADY`: External RTT stable ($\Delta\text{RTT} \le 5\text{ ms}$); shaper holds configured ceiling.
  * `CONGESTED`: External RTT spikes ($\Delta\text{RTT} > 15\text{ ms}$) while local backlog is zero. Step down shaper rate.
  * `SETTLING`: Rate adjusted; latch hysteresis for $1.5\text{ seconds}$ to allow queue draining without oscillation.
  * `RECOVERING`: External RTT returns to baseline; probe shaper rate upward gradually ($+2\text{ Mbps/s}$).
* **Failure Handling:** If external telemetry fails (e.g. reflector unreachable), freezes rate at current stable level or safe default (90% link rate). Never clamps below $10\text{ Mbps}$.
* **Success Condition:** Capacity collapse settling time $T_{\text{settle}} \le 2.0\text{ seconds}$ with zero hunting oscillations.
* **Implementation Status:** **✅ Implemented & Tested** (`controller/guard.py`, `scripts/run_stage_s3_collapse.py`).

---

### Module 6: Safety Supervisor & Watchdog (`safety/edgeqos-watchdog.sh` & `safety/restore.sh`)
* **Purpose:** Guarantees gateway fail-safe survivability and system recovery.
* **Inputs:** Process heartbeat (`pidof python3`), system memory usage, and interface forwarding state.
* **Outputs:** Rollback script execution: resets `nftables` tables and restores CAKE to unshaped baseline.
* **States & Transitions:**
  * `HEALTHY`: Userspace daemons responding to heartbeat.
  * `DEGRADED`: Telemetry lag detected; restarts control daemon.
  * `CRITICAL / CRASH`: Daemon dead (`SIGKILL` / crash); triggers `safety/restore.sh` within $3.0\text{ seconds}$.
* **Failure Handling:** Pure shell script with no external library dependencies; guaranteed execution under high system stress.
* **Success Condition:** Packet forwarding continues with 0 dropped packets during daemon crash (`tests/test_guard_capacity.py`).
* **Implementation Status:** **✅ Implemented & Tested** (`safety/restore.sh`, `safety/edgeqos-watchdog.sh`).

---

## 3. Summary of Module Validation Matrix

| Module | Unit Test | Integration Test | Empirical Evidence File |
| :--- | :--- | :--- | :--- |
| **1. Capture** | `tests/test_privacy.py` | `scripts/run_stage_s2_trace.py` | `results/priv_report.txt` |
| **2. Classifier** | `tests/test_classifier.py` | `ml/train.py` | `results/inference_bench.json`, `results/confusion_matrix.png` |
| **3. Guard** | `tests/test_guard_capacity.py` | `scripts/run_stage_s3_collapse.py` | `results/demotion_cdf.png` |
| **4. Actuator** | `scripts/test_tin_mapping.py` | `scripts/run_stage_s2_trace.py` | `results/tin_steering_distribution.png` |
| **5. Capacity Tracker** | `tests/test_guard_capacity.py` | `scripts/run_stage_s3_collapse.py` | `results/settling_time_ci.png`, `results/netns_collapse_result.json` |
| **6. Watchdog** | `safety/edgeqos-watchdog.sh` | Scenario $SC_9$ (Fault Injection) | `EdgeQoS_Technical_Report.md` §9 |
