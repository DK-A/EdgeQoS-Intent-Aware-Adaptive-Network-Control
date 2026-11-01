# EdgeQoS ML Evaluation Protocol (ml-v2)

**Pre-Registered Evaluation Standard**  
**Author:** EdgeQoS Team · Tata Elxsi TELIPORT S4 (Problem Statement 3)  
**Date:** November 1, 2026 · **Status:** Active / Pre-Registered  

---

## 1. Scope & Objective

This document pre-registers the evaluation protocol for the early-flow Zero-DPI classifier before conducting any evaluation on test partitions. Pre-registration ensures:
1. **Zero Data Leakage:** Hyperparameter tuning occurs strictly on train splits; calibration and threshold selection occur strictly on validation splits; the test partition is opened **exactly once**.
2. **Safety-Oriented Evaluation:** Primary evaluation metrics focus on system safety (avoiding false promotions that pollute priority queues) rather than raw classification accuracy alone.
3. **No Target Metric Shaping:** Experimental results are reported as empirically measured, regardless of whether numbers are high or low.

---

## 2. Class Definitions & Queue Mapping

| Class ID | Class Name | Underlying Traffic Types | CAKE Queue / DSCP Target | Priority Tier |
| :---: | :--- | :--- | :---: | :---: |
| **0** | **Realtime** | VoIP (Opus / G.711 RTP), Cloud Gaming ticks, low-latency audio | Voice (`CS5` / `EF`) | **High Priority** |
| **1** | **Stream** | Adaptive Video (DASH / HLS over TLS), QUIC chunk bursts | Video (`AF41`) | **High Priority** |
| **2** | **Bulk** | TCP large file transfers (CUBIC/BBR), background updates | Bulk (`CS1`) | **Low Priority** |
| **3** | **Other** | DNS, web browsing, REST API calls, transient flows | Best-Effort (`CS0`) | **Default Tier** |
| **-** | **Abstain** | Any flow with prediction confidence $< \tau$ | Best-Effort (`CS0`) | **Default Tier** |

> **Safety Rule:** Both `Other` and `Abstain` flows are steered to the unpromoted Best-Effort tier (`CS0`). They never enter the high-priority Voice or Video tins.

---

## 3. Data Partitioning & Session Isolation

* **Unit of Partition:** **Session ID** (and network recording condition). All flows originating from or targeting a specific session instance belong entirely to one partition.
* **Partition Split Ratio:**
  * **Train Set (60% of sessions):** Used for decision tree feature split optimization and leaf pruning.
  * **Validation Set (20% of sessions):** Used for Platt scaling calibration fitting, leaf-support gating, and selection of the confidence abstention threshold $\tau$.
  * **Test Set (20% of sessions):** Kept untouched until final evaluation. Evaluated once.
* **Cross-Validation:** 5-Fold `GroupKFold` on the training partition to ensure stability across sessions.

---

## 4. Confidence Abstention ($\tau$) Selection Rule

The confidence abstention threshold $\tau \in [0.50, 0.95]$ is selected strictly on the **Validation Set** using an a priori safety criterion:

$$\tau^* = \min \{ \tau \mid \text{Validation False-Promotion Rate}(\tau) \le 5.0\% \}$$

Where **False-Promotion Rate (FPR)** is defined as:
$$\text{FPR} = \frac{\text{Count of (Bulk or Other flows promoted to Realtime or Stream)}}{\text{Total Non-Priority Flows (Bulk + Other)}} \times 100\%$$

* **Rationale:** In edge QoS, misclassifying a Bulk file download as Voice causes bufferbloat in the Voice tin, destroying call quality for all users. Misclassifying Voice as Best-Effort is harmless because CAKE's FQ-CoDel fair queuing still isolates sparse voice flows. Therefore, false promotion is $\ge 10\times$ more damaging than false demotion.

---

## 5. Metrics to Report

1. **Safety Metrics (Primary):**
   * **False-Promotion Rate (%):** Proportion of Bulk/Other flows improperly steered to Voice/Video.
   * **False-Demotion Rate (%):** Proportion of Realtime/Stream flows steered to Bulk.
   * **Risk-Coverage Curve:** Selective accuracy as a function of coverage (fraction of non-abstained flows).
   * **Abstention Rate (%):** Percentage of total flows where the classifier abstains.
2. **Classification Metrics:**
   * **Macro F1-Score** (calculated with abstentions explicitly counted as errors, and reported both ways).
   * **Per-Class Precision, Recall, and F1** for Realtime, Stream, Bulk, and Other.
   * **Confusion Matrix** (4×4 classification + 1 column for Abstain).
3. **Calibration Quality:**
   * **Expected Calibration Error (ECE):** 10-bin reliability comparison of predicted confidence vs. empirical accuracy.
   * **Reliability Plot data.**
4. **Disaggregated Decision Latency:**
   * $t_{\text{feat}}$: Zero-DPI feature vector extraction time ($\mu\text{s}$).
   * $t_{\text{infer}}$: Model tree traversal time ($\mu\text{s}$).
   * $t_{\text{decision}}$: Total flow decision time ($t_{\text{feat}} + t_{\text{infer}}$) ($\mu\text{s}$).
   * $t_{\text{policy}}$: nftables set element insertion / timeout update time ($\mu\text{s}$).
5. **Robustness & Generalization:**
   * **Packet Window Ablation:** Performance evaluated at $N \in \{3, 5, 8, 10\}$.
   * **Condition-Shift Drop:** Degradation from low-load baseline to high-competing-load environment.
   * **Open-Set / OOD Promotion Rate:** Promotion rate on held-out application types.
   * **Real-Application Set Performance:** Evaluated on the dedicated `[REAL]` test set.
6. **Statistical Confidence:**
   * All metrics reported with 95% Confidence Intervals computed via **session-level bootstrap** (1,000 resamples over session IDs).

---

## 6. Exclusion & Failure Rules

* Flows with fewer than 3 packets within the 2.0-second observation window are deemed incomplete and default to `CS0` (excluded from early-flow classification evaluation).
* Any run where the background impairment emulator fails to apply programmed `netem` parameters is discarded and flagged in the test log.
* The test set is evaluated exactly once after locking model weights and $\tau^*$. No post-hoc tuning on test data is permitted.
