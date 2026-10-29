# EdgeQoS: Claim Ledger & Verification Status
**Tata Elxsi TELIPORT Season 4 · Problem Statement 3**  
**Audit Rule:** Every claim in the report, poster, or presentation MUST be backed by an empirical artifact in `results/` or explicit calculation. Unverified claims remain strictly marked as `[PENDING]` or `[TARGET]`.

| Claim (Report / Poster) | Evidence Required | Experiment / Scenario | Artifact Path | Status |
| :--- | :--- | :--- | :--- | :---: |
| Bufferbloat magnitude = BUF / rate | Measured B0 delay vs theory | SC0 / SC1 | `results/b0_vs_theory.png` | [PENDING] |
| CAKE diffserv4 tin mapping as stated | Observed tin counters for EF/AF41/CS1/CS0 | Spike S1 | `docs/tin_map_observed.md` | [PENDING] |
| Payload never exposed to userspace | 40B snaplen + L4 parser truncation | Test T-PRIV | `results/priv_report.txt` | [PENDING] |
| Capacity collapse detected without throughput cue | S3 beats B4 and B5 settling time | SC2 / SC3 | `results/settling_time_ci.png`| [PENDING] |
| Zero false rate reductions on idle link | Count <= 1 per 10 minutes | SC3a / SC3b | `results/false_reductions.json`| [PENDING] |
| Early classifier classifies encrypted flows at N<=10 | Macro-F1 >= 0.90, ECE <= 0.08, LOAO | ML evaluation | `results/ml_eval_report.json` | [PENDING] |
| Machine learning adds value over static rules | F1(ML) > F1(Rules), lower jitter | SC4 / SC5 | `results/ml_vs_rules.png` | [PENDING] |
| Misclassified bulk demoted within T_demote | Measured T_demote <= 1.5s - 3.0s | SC6 | `results/demotion_cdf.png` | [PENDING] |
| Structural non-starvation of background flows | Min 1-s goodput >= 500 kbps, 0 RSTs | SC1 / SC4 | `results/non_starvation.json` | [PENDING] |
| Multi-tiered fail-safe rollback (kill -9) | Traffic continues, sets flush <= 3s | SC9 | `results/failsafe_log.txt` | [PENDING] |
| Edge resource budget on Raspberry Pi 4B | Marginal CPU <= 12%, RSS <= 75 MB | Section 11 / SC10 | `results/resource_profile.png`| [TARGET] |
| Anti-spoofing clears host-supplied DSCP | Host EF packets placed in Best Effort | SC12 | `results/spoof_test.txt` | [PENDING] |
