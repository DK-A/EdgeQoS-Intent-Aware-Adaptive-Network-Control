# EdgeQoS: Report & Poster Corrections Log (C1–C16)
**Tata Elxsi TELIPORT Season 4 · Problem Statement 3**  
**Audit Date:** 29 October 2026 · **Status:** Fully Resolved  

| Ref | Location | Original Issue | Evidence & Correction Applied |
| :-: | :--- | :--- | :--- |
| **C1** | §1.1 | "256 KB at 100 Mbps gives >200 ms; at 20 Mbps >1000 ms" is off by ~10x. | `[CALC]` 256 KB = 2,097,152 bits. At 100 Mbps: 2,097,152 / 100e6 = 20.97 ms (~21 ms). At 20 Mbps: 2,097,152 / 20e6 = 104.85 ms (~105 ms). To reach >200 ms standing delay at 100 Mbps requires buffer BUF >= 2.5 MB. Modem buffer BUF is now an explicit sweep parameter: {64KB, 256KB, 1MB, 2.5MB}. |
| **C2** | §3.1, §4.2, Abstract | "Payload stripped by 128 B snaplen". | `[CALC]` 128 - (20 IP + 8 UDP) = 100 B payload captured. Snaplen set to exact minimum covering fields used (40 B for IPv4 + TCP flags). Reader explicitly discards any bytes beyond L4 header. Added test T-PRIV. |
| **C3** | §3.2 | Report stated "Video = CS4". | `[LIT]` In Linux CAKE diffserv4 (sch_cake.c), CS4/CS5 map to Voice tin; Stream is AF4x/AF3x/CS3/AF2x. Corrected: EF/CS5 -> Voice, AF41 -> Video/Stream, CS1 -> Bulk. Verified via tin counter test S1. |
| **C4** | §3, §6.2 | Stated "hardware bandwidth caps per tin". | `[LIT]` CAKE tin percentages are software deficit thresholds (Voice 25%, Video 50%, BE 100%, Bulk 6.25%). Reworded to software thresholds and proven empirically via H3. |
| **C5** | §8 H1 | Target "p99 RTT <= 20 ms" without baseline. | `[DESIGN]` Targets defined as Delta over unloaded baseline RTT (Delta-p99). |
| **C6** | §5.1, H2 | 1 Hz probe vs 2.0s recovery time claim. | `[CALC]` 1 Hz probe with K>=3 needs >=3s. Adjusted probe rate to 1 Hz idle and 5-10 Hz when loaded. Defined recovery as settling time. |
| **C7** | §4.4, H4 | Abstract claimed "< 2.0s" demotion with 1 Hz polling and m=2. | `[CALC]` Worst-case: T_demote,max = (m+1)/f_poll + t_nft. With f=4 Hz, m=4 -> T <= 1.25s + t_nft. Stated formula and measured t_nft. |
| **C8** | §4.4 | "Voice/video rarely exceeds 3 Mbps; budget 5 Mbps" unsupported. | `[DESIGN]` Budgets set from measured trace p99 x safety margin. |
| **C9** | §5.2 | R_delivered undefined for upload. | `[DESIGN]` Download: smoothed WAN RX rate. Upload: multiplicative step-down until external delay clears. |
| **C10** | Table III | Threshold gaps undefined (5-15 ms internal, 10-25 ms external). | `[DESIGN]` Added hysteresis latches (int_hot set >=15ms, clear <=5ms; ext_hot set >=25ms, clear <=10ms). |
| **C11** | Table VI | ~45 us, <12% CPU, <75 MB presented as facts. | `[MEASURE]` Relabeled as TARGETS until backed by measured runs in results/. Marginal cost (S3 - B3) reported. |
| **C12** | Jury Ans 5 | Unmeasured "jitter < 1 ms" claim. | `[MEASURE]` Replaced with measured IPDV-style jitter. |
| **C13** | §12 Refs | Reference [2] authors/venue garbled. | `[LIT]` Corrected to: T. Høiland-Jørgensen, D. Täht, and J. Morton, Piece of CAKE, arXiv:1804.07617, submitted to IEEE LANMAN 2018. All references verified. |
| **C14** | Poster | Unsourced figures and illustrative target bars. | `[DESIGN]` Labeled as illustrative targets, not measured results. |
| **C15** | §8, Table V | Default qdisc assumption for B0. | `[DESIGN]` Explicitly set B0 with tc qdisc replace ... pfifo limit 10000 and verify. |
| **C16** | §3.1 | Untrusted host DSCP. | `[DESIGN]` Enforced first rule in forward chain: ip dscp set cs0. |
