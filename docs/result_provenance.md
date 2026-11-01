# EdgeQoS: Result Provenance Matrix (Stage S0)
*Traces every reported figure, metric, and artifact to its exact generating script, raw data file, and scientific label.*

---

## 1. Provenance Legend
* **`[SIM]`**: Discrete-Event Simulation Model (pure Python event-driven queue simulator in `sim/`). Model illustration only.
* **`[NETNS]`**: Real Linux Kernel running inside Network Namespaces (`c1 -> gw -> isp -> srv`) on PC testbed. Headline-eligible.
* **`[PI]`**: Physical Raspberry Pi 4B hardware testbed with dual physical Gigabit Ethernet cables. Headline-eligible.

---

## 2. Comprehensive Metric & Artifact Traceability Table

| Artifact / Metric | Label | Generating Script | Raw Output Path | Purpose / Description |
| :--- | :---: | :--- | :--- | :--- |
| **`b0_vs_theory.png`** | `[SIM]` | `analysis/plots.py` | `results/b0_vs_theory.png` | DropTail bufferbloat vs theoretical queuing math ($T = \text{BUF}/C$) across buffer sizes |
| **`demotion_cdf.png`** | `[SIM]` | `analysis/plots.py` | `results/demotion_cdf.png` | CDF of behavioral rate guard demotion latency (1.00s empirical vs 1.25s theoretical bound) |
| **`settling_time_ci.png`** | `[SIM]` | `analysis/plots.py` | `results/settling_time_ci.png` | Capacity collapse settling time comparison across baselines with 95% bootstrap CIs |
| **`performance_evaluation.json`** | `[SIM]` | `analysis/aggregate.py` | `results/performance_evaluation.json` | Aggregated p50, p95, p99, and jitter for SC1 (100M steady) and SC2 (collapse) |
| **`ablation_benchmark.json`** | `[SIM]` | `sim/benchmark.py` | `results/ablation_benchmark.json` | Raw per-packet traces for B0, B1, B3, B4, S2, S3 across SC1, SC2, SC6 |
| **`inference_bench.json`** | `[NETNS]` / Host | `tests/test_classifier.py` | `results/inference_bench.json` | Empirical 10,000-run microbenchmark of CART decision tree: p50=0.741 µs, p99=1.513 µs |
| **`priv_report.txt`** | `[NETNS]` / Host | `tests/test_privacy.py` | `results/priv_report.txt` | In-kernel snaplen privacy test report verifying 0 bytes of secret payload |
| **`ml_eval_report.json`** | `[NETNS]` / Pre-reg | `ml/evaluate.py` | `results/ml_eval_report.json` | Held-out test session metrics (Macro F1=0.9702, FPR=0.39%), Platt calibration (ECE=0.017), and real-app generalisation gap |
| **`tree_model.json`** | Model Artifact | `ml/train.py` | `ml/models/tree_model.json` | Standalone 1.7 KB pure JSON decision tree array used for inference |

---

## 3. Exclusion and Headline Policy
* **Current Headline Numbers:** All macro-latency and settling figures currently reported in high-level summaries are labeled `[SIM]`.
* **Gate Rule (R2):** Once Stage S2–S6 network namespace tests complete, headline figures will be updated and replaced strictly with `[NETNS]` measured data.
