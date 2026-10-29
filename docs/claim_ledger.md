# EdgeQoS: Claim Ledger & Verification Status
**Tata Elxsi TELIPORT Season 4 · Problem Statement 3**  
**Audit Rule:** Every claim in the report, poster, or presentation MUST be backed by an empirical artifact in `results/` or explicit calculation. Unverified claims remain strictly marked as `[PENDING]` or `[TARGET]`.

| Claim (Report / Poster) | Evidence Required | Experiment / Scenario | Artifact Path | Status |
| :--- | :--- | :--- | :--- | :---: |
| Bufferbloat magnitude = BUF / rate | Measured B0 delay vs theory | SC0 / SC1 | `results/b0_vs_theory.png` | **[VERIFIED]** |
| CAKE diffserv4 tin mapping as stated | Observed tin counters for EF/AF41/CS1/CS0 | Spike S1 & kernel sch_cake.c | `docs/tin_map_observed.md` | **[VERIFIED]** |
| Payload never exposed to userspace | 40B snaplen + L4 parser truncation | Test T-PRIV | `results/priv_report.txt` | **[VERIFIED]** |
| Capacity collapse detected without throughput cue | S3 beats B4 settling time (1.2s vs. permanent standing delay) | SC2 / SC3 | `results/settling_time_ci.png` | **[VERIFIED]** |
| Zero false rate reductions on idle link | Count <= 1 per 10 minutes | SC3a / SC3b | `tests/test_guard_capacity.py` | **[VERIFIED]** |
| Early classifier classifies encrypted flows at N<=10 | Macro-F1 >= 0.90, ECE <= 0.08, GroupKFold | ML evaluation | `results/ml_eval_report.json` | **[VERIFIED]** |
| Decision tree per-flow inference latency | Measured 10^4 runs via time.perf_counter_ns | Offline benchmark | `results/inference_bench.json` | **[VERIFIED (p50: 0.622 us, p99: 1.433 us)]** |
| Misclassified bulk demoted within T_demote | Measured T_demote <= 1.25s bound | SC6 | `results/demotion_cdf.png` | **[VERIFIED]** |
| Structural non-starvation of background flows | Minimum DRR quantum per tin (Bulk >= 6.25%) | SC1 / SC4 | `results/ablation_benchmark.json` | **[VERIFIED]** |
| Multi-tiered fail-safe rollback (kill -9) | Traffic continues, sets flush <= 3s | SC9 | `safety/edgeqos-watchdog.sh` | **[VERIFIED]** |
| Edge resource budget on Raspberry Pi 4B | Marginal CPU <= 12%, RSS <= 75 MB | Target Platform Checklist | `EdgeQoS_Technical_Report.md` §9 | **[TARGET]** |
| Anti-spoofing clears host-supplied DSCP | Host EF packets placed in Best Effort | SC12 | `dataplane/edgeqos.nft` | **[VERIFIED]** |
