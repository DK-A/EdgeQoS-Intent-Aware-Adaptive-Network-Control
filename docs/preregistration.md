# EdgeQoS: Pre-Registration Document
**Tata Elxsi TELIPORT Season 4 · Problem Statement 3**  
**Pre-Registration Date:** 29 October 2026 · **Status:** Committed Prior to Final Runs  

## 1. Pre-Registered Hypotheses & Success Criteria

| Hypothesis ID | Statement | Primary Metric | Baseline Comparison | Success Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **H1** | Latency suppression under bulk saturation | Delta p99 RTT over unloaded baseline | S3 vs. B0, B3 | Delta p99 <= 15 ms; non-inferior to B3 within margin delta = 3.0 ms |
| **H2** | Faster settling time after link capacity collapse (100 -> 20 Mbps) | Settling time T_settle (s) to p95 RTT <= baseline + 10 ms | S3 vs. B4, B5 | T_settle(S3) < T_settle(B4) with non-overlapping bootstrap 95% CIs. Stretch: <= 2.0 s |
| **H2c** | Zero false reductions on healthy/idle link | Count of shaper rate decreases when link is healthy/idle | S3 (SC3a/b) | False reductions <= 1 per 10-minute run |
| **H3** | Structural non-starvation of background flows | Minimum 1.0 s bulk goodput | S3, S4 (SC1, SC4) | Goodput >= 500 kbps in all 1.0s windows; 0 TCP RSTs via nstat |
| **H4** | Bounded harm of misclassified / rogue streams | Demotion latency T_demote | S3 vs. S2 (SC6) | T_demote <= (m+1)/f_poll + t_nft (<= 1.5s - 3.0s) |
| **H5** | Machine learning justification vs. port rules | Macro-F1 on encrypted traffic & p99 jitter | S3 vs. S1 (SC4, SC5) | F1(ML) > F1(Rules) + 0.15; p99 jitter lower in multi-flow collapse |
| **H6** | Edge hardware feasibility budget | Marginal CPU (S3 - B3) and RSS | S3 on Raspberry Pi 4B | Marginal CPU <= 12%; RSS <= 75 MB; per-flow decision <= 100 us |
| **H7** | Multi-tiered fail-safe rollback | Continuity of forwarding & state cleanup | S3 (SC9 kill -9) | Zero packet drops in fast-path; sets flushed <= 3s by watchdog |
| **H8** | DSCP spoof-resistance | Queue assignment of host-marked packets | S3 (SC12) | Self-marked EF packets assigned to Best-Effort (CS0) |

## 2. Metric Formulations

* **Unloaded Baseline RTT ($RTT_{\text{base}}$):** Median RTT of 50 pps probe during 30s silent window prior to traffic generation.
* **Delta Percentile Latency ($\Delta p99$):** $p99(RTT_{\text{load}}) - RTT_{\text{base}}$.
* **IPDV Jitter ($J$):** Mean absolute difference between consecutive probe packets:
  $$J = \frac{1}{M-1} \sum_{i=1}^{M-1} |RTT_{i+1} - RTT_i|$$
* **Settling Time ($T_{\text{settle}}$):** Time from capacity drop event ($t_0$) until 1.0s sliding window p95 RTT remains below $RTT_{\text{base}} + 10\text{ ms}$ for 5 consecutive seconds.
* **Demotion Latency ($T_{\text{demote}}$):** Time elapsed from the exact moment a rogue flow exceeds its rate budget until its 5-tuple element is deleted from the nftables priority set.

## 3. Run Exclusion & Invalidation Rules

A run is strictly invalid and excluded from analysis if:
1. **Thermal Throttling:** On Raspberry Pi 4B, `vcgencmd get_throttled` returns non-zero during any second of the run.
2. **Harness Error:** An endpoint generator exits prematurely or fails to start.
3. **Netlink Buffer Overflow:** The NFLOG socket reports `ENOBUFS` due to unexpected system stall.
*Every excluded run must be logged with timestamp and reason in an appendix.*

## 4. Statistical Methodology

* **Sample Size:** $R = 15$ runs per configuration-scenario pair for primary matrix; $R = 5$ for preliminary baselines.
* **Confidence Intervals:** 10,000 bootstrap resamples for median and 95% confidence intervals.
* **Hypothesis Testing:** Mann-Whitney U test with Holm-Bonferroni correction for multiple comparisons; Cliff's delta for non-parametric effect size.
