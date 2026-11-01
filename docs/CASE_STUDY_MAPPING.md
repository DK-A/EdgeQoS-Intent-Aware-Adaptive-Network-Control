# EdgeQoS: Case Study Requirement Mapping & Evidence Ledger

**Challenge:** Tata Elxsi TELIPORT Season 4 · Case Study 3  
**Title:** Adaptive QoS Engine for Mixed Home Broadband Traffic  
**Status Audit Rule:** Evidence-gated status. A component is marked ✅ only with direct code and verifiable test logs. Gaps are explicitly marked 📝 Planned or 🔧 In Progress.

---

## 1. Status Label Taxonomy

To maintain strict scientific honesty and prevent over-claiming, all components in this ledger are assigned exactly one of four statuses:
* **✅ Implemented & Tested:** Code complete, verified with repeatable automated test suite, logs, and artifacts.
* **🟡 Implemented, Partially Tested:** Code complete, tested in simulation or isolated unit tests; full end-to-end integration underway.
* **🔧 In Progress:** Active development; functional baseline established, full test automation pending.
* **📝 Planned:** Architected on technical roadmap; not yet implemented or measured.

---

## 2. Master Case Study 3 Requirements Mapping

| # | Case Study Requirement | EdgeQoS Technical Approach | Verifiable Code & Evidence Artifacts | Status |
| :-: | :--- | :--- | :--- | :---: |
| **01** | **Classify traffic categories without reading private payloads** | Protocol-aware early-flow metadata classification (packet size distributions, direction, inter-arrival time, TCP flags) at packet $N \le 10$. Ingress snaplen header truncation via `nftables`. | • `ml/classifier.py`<br>• `dataplane/edgeqos.nft`<br>• `tests/test_privacy.py`<br>• `results/priv_report.txt` | **🟡 Implemented, Partially Tested** *(Tested on synthetic generator; live traffic drift testing pending)* |
| **02** | **Estimate link capacity dynamically** | Passive dual-signal capacity tracking. Fuses external reflector RTT inflation ($\Delta\text{RTT}$) with gateway queue backlog ($Q_{\text{bytes}}$) and wire drain rate to detect bottleneck collapse without speedtest floods. | • `controller/guard.py`<br>• `scripts/run_stage_s3_collapse.py`<br>• `results/netns_collapse_result.json`<br>• `results/settling_time_ci.png` | **🟡 Implemented, Partially Tested** *(Single upload step-down verified in netns; multi-step fluctuation in progress)* |
| **03** | **Apply queueing and shaping** | Linux in-kernel CAKE (`sch_cake`) configured in `diffserv4` mode with Deficit Round Robin (DRR+) scheduling. DSCP marking driven by `nftables` kernel timed sets. | • `dataplane/edgeqos.nft`<br>• `scripts/test_tin_mapping.py`<br>• `docs/tin_map_observed.md`<br>• `results/tin_steering_distribution.png` | **✅ Implemented & Tested** |
| **04** | **Verify whether policy improved user experience** | Closed-loop latency and jitter telemetry before and after shaper actions; automated baseline comparison ($B_0$ FIFO vs. $B_4$ Stale CAKE vs. $S_3$ EdgeQoS). Per-flow QoE score evaluation on roadmap. | • `sim/benchmark.py`<br>• `scripts/run_stage_s3_collapse.py`<br>• `results/latency_comparison_bar.png`<br>• *(Per-flow subjective QoE verification)* | **🟡 Implemented, Partially Tested** *(Macro latency ✅, Per-flow QoE 📝)* |
| **05** | **Temporary user intent (e.g., prioritize a call)** | Time-bounded `nftables` set elements (`lease_rt`) mapping client IP or 5-tuple with automated kernel timeout. Implemented via CLI command; REST/UI integration planned. | • `dataplane/edgeqos.nft` (lines 30-34, 55-56)<br>• `controller/lease.py`<br>• *(Web GUI Intent Trigger: Planned)* | **🔧 In Progress** *(CLI prototype functional; REST API & Web GUI planned)* |
| **06** | **Independently testable modules with explicit contracts** | Fully modular architecture with defined inputs, outputs, state machines, failure transitions, and success conditions documented in `docs/MODULES.md`. | • `docs/MODULES.md`<br>• `tests/test_classifier.py`<br>• `tests/test_guard_capacity.py`<br>• `tests/test_privacy.py` | **✅ Implemented & Tested** |
| **07** | **Compare AI with deterministic baseline** | Evaluation comparing TinyML Decision Tree against deterministic heuristic rules across identical held-out test sessions (n=2,400). TinyML achieves 99.9% F1 vs Rules 66.7% F1. | • `ml/compare_baseline.py`<br>• `results/ml_vs_rule_comparison.json`<br>• `results/ml_vs_rule_baseline.png` | **🟡 Implemented, Partially Tested** *(Evaluated on held-out synthetic sessions; live traffic benchmark in progress)* |
| **08** | **Do not decrypt traffic** | Protocol-aware truncation enforcing 28B snaplen for UDP and 40B for TCP. 0 application payload bytes ever reach userspace or inference. | • `dataplane/edgeqos.nft`<br>• `tests/test_privacy.py`<br>• `results/priv_report.txt` | **✅ Implemented & Tested** |
| **09** | **Linux tc or open enforcement** | Native upstream Linux kernel `tc-cake` and `nftables`. Zero proprietary kernel modules or closed-source drivers. | • `dataplane/edgeqos.nft`<br>• `scripts/setup_netns_topo.sh` | **✅ Implemented & Tested** |
| **10** | **IPv4 and, where available, IPv6** | Prototype fully supports IPv4. IPv6 header parser (40B fixed header) and flow label classification defined on roadmap. | • Prototype: IPv4 (`dataplane/edgeqos.nft`)<br>• Roadmap: IPv6 (`docs/ROADMAP.md`) | **IPv4: ✅**<br>**IPv6: 📝 Planned** |
| **11** | **Policy rollback & starvation prevention** | Kernel set element auto-expiry (10s/60s), independent watchdog script restoring clean state on daemon death, and CAKE DRR+ minimum quantum (Bulk $\ge 6.25\%$). | • `safety/restore.sh`<br>• `safety/edgeqos-watchdog.sh`<br>• `results/ablation_benchmark.json` | **🟡 Implemented, Partially Tested** *(Kernel timeouts & watchdog verified; starvation stress-test pending)* |
| **12** | **Classifiers expose confidence and allow correction** | Calibrated class probabilities with isotonic scaling. Abstains (`ABSTAIN`) if confidence $< 0.70$. Behavioral guard monitors byte counters and demotes misclassified flows within $1.25\text{s}$. | • `ml/classifier.py`<br>• `controller/guard.py`<br>• `results/demotion_cdf.png`<br>• `results/ml_eval_report.json` | **🟡 Implemented, Partially Tested** *(Calibrated confidence & demotion unit tested; high-churn live deployment ongoing)* |
| **13** | **Document third-party licenses** | Comprehensive inventory of all third-party software, libraries, and kernel components with upstream licensing terms in `THIRD_PARTY_LICENSES.md`. | • `THIRD_PARTY_LICENSES.md`<br>• `LICENSE` (MIT) | **✅ Implemented & Tested** |
| **14** | **Generated data & impairment settings included** | Testbed setup scripts include repeatable `tc qdisc netem` and `tbf` configurations for delay, bandwidth throttling, and packet drops. | • `scripts/setup_netns_topo.sh`<br>• `scripts/run_stage_s3_collapse.py` | **✅ Implemented & Tested** |
| **15** | **Label emulation as emulation** | All experimental results carry explicit provenance tags: `[SIM]` (Discrete simulator), `[NETNS]` (Linux namespaces with emulated bottleneck), or `[PI]` (Hardware). | • `docs/result_provenance.md`<br>• `README.md` | **✅ Implemented & Tested** |
| **16** | **No secrets in source control** | Zero API keys, private passwords, or personal credentials committed. Checked via automated secret scanning rules. | • `.gitignore`<br>• Clean repository commit log | **✅ Implemented & Tested** |
| **17** | **Bounded, observable, reversible remediation** | Controller rate adjustments clamped to $[10\text{ Mbps}, 100\text{ Mbps}]$ with step limits ($\le 15\text{ Mbps/s}$). Asynchronous decision logs written to CSV/JSON. | • `controller/guard.py`<br>• `results/performance_evaluation.json` | **✅ Implemented & Tested** |

---

## 3. Case Study Scenario Coverage

| Scenario | Objective | EdgeQoS Mitigation | Status | Evidence Artifact |
| :--- | :--- | :--- | :---: | :--- |
| **Scenario 1: ISO Download during Video Call** | Preserve video telepresence latency while saturating link with bulk TCP download. | TinyML promotes call packets to Tin 2 (`AF41`); bulk stays in Tin 0 (`CS1`). CAKE DRR+ isolates flows, preserving $< 21\text{ ms}$ call latency. | **✅ Tested** | `results/tin_steering_distribution.png`<br>`results/latency_comparison_bar.png` |
| **Scenario 2: WAN Capacity Collapse (100M $\to$ 20M)** | Prevent $124\text{ ms}$ modem bufferbloat when access link collapses under full load. | Dual-signal capacity tracker detects external queuing, throttles gateway shaper to 18 Mbps, and drains modem queue in $1.64\text{s}$. | **✅ Tested** | `results/netns_collapse_result.json`<br>`results/settling_time_ci.png` |
| **Scenario 3: Three 4K TVs + Cloud Gaming** | Prevent bursty ABR streaming chunks from inducing jitter spikes on interactive gaming flows. | Gaming flows steered to Tin 3 (`EF`) / Tin 2 (`AF41`); streaming buffered into Best Effort (`CS0`). Bound Voice/Gaming tier sojourn. | **📝 Planned** | Test automation script in design (`scripts/run_scenario_3tvs_game.py`) |

---

## 4. Expected Deliverables & Current State

| Deliverable | Expected Artifact | Current Delivery State |
| :--- | :--- | :--- |
| **Traffic Classifier & Capacity Estimator** | Standalone Python/C modules | ✅ Delivered (`ml/classifier.py`, `controller/guard.py`) |
| **Dynamic QoS Policy Enforcement** | Linux `tc-cake` + `nftables` ruleset | ✅ Delivered (`dataplane/edgeqos.nft`, `scripts/setup_netns_topo.sh`) |
| **Operations Dashboard** | Dark-mode NOC console with live waveform & SVG topology | ✅ Delivered prototype (`demo/edgeqos_dashboard.html`, `demo/serve_dashboard.py`) |
| **Automated Baseline Experiments** | One-command reproduction scripts comparing $B_0, B_4, S_3$ | ✅ Delivered (`scripts/run_stage_s3_collapse.py`, `results/netns_collapse_result.json`) |
| **Temporary User Intent API** | CLI/REST endpoint for user-directed QoS passes | 🟡 CLI functional (`controller/lease.py`); REST daemon in progress |
| **Layered Architecture Diagram** | Diagram detailing Device, Edge, Network, Data, UI layers | ✅ Delivered (Included in `README.md` and `docs/CASE_STUDY_MAPPING.md`) |
| **Hardware Validation (Raspberry Pi 4B)** | Benchmarks run on physical ARM Cortex-A72 hardware | 📝 Roadmap Phase 4 (BOM specified; netns execution verified) |
