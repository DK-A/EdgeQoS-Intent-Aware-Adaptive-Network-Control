# EdgeQoS: Related Work & Technical Positioning

**Context:** Tata Elxsi TELIPORT Season 4 · Case Study 3  
**Objective:** Ground EdgeQoS in the scientific literature and establish a respectful, factual positioning relative to prior art in Active Queue Management (AQM), traffic shaping, and edge classification.

---

## 1. Prior Art & Documented Capabilities

Modern internet quality of service (QoS) and bufferbloat mitigation rest upon a rich foundation of open-source and standards-track networking technologies:

| Technology | Documented Capabilities & Primary Focus | Canonical References & Sources |
| :--- | :--- | :--- |
| **FQ-CoDel** | Combines Flow Queuing (FQ) with the Controlled Delay (CoDel) Active Queue Management algorithm. Provides per-flow fair queuing, deficit round-robin packet scheduling, and latency-based packet drop to prevent standing queues. Inherent priority for sparse / new flows. | • RFC 8290: *The FlowQueue-CoDel Packet Scheduler and Active Queue Management Algorithm* (Hoeiland-Joergensen et al., 2018)<br>• RFC 8289: *Controlled Delay Active Queue Management* (Nichols & Jacobson, 2018) |
| **Linux CAKE** | Common Applications Kept Enhanced. Next-generation queue discipline combining a high-precision shaper, Cobalt AQM (CoDel + BLUE), Deficit Round Robin (DRR+), per-host isolation, DiffServ multi-tin priority scheduling (`diffserv3`, `diffserv4`, `besteffort`), and automatic packet overhead compensation in a single in-kernel qdisc. | • *Piece of CAKE: A Comprehensive Queue Management Solution for Home Gateways*, T. Høiland-Jørgensen, D. Täht, J. Morton, arXiv:1804.07617 (2018)<br>• Linux Kernel Source: `net/sched/sch_cake.c` |
| **cake-autorate** | Standalone userspace daemon for OpenWrt that dynamically modulates CAKE shaper bandwidth by continuously measuring ping round-trip times (RTT) to internet reflectors, adjusting the shaper rate downward when latency inflation is observed and probing upward when link is stable. | • `cake-autorate` Project: GitHub repository (`lynxthecat/cake-autorate`), OpenWrt Community Forum (2021–2024) |
| **nftables & Netfilter** | Upstream Linux kernel packet classification and filtering framework replacing `iptables`. Features in-kernel dynamic sets, per-element timeout auto-expiry, Netlink event notification (`NFLOG`), and line-rate DSCP/packet mark manipulation via hardware-efficient radix trees. | • Netfilter Documentation & Manpages (`nftables.org`)<br>• P. Waskiewicz, *Netfilter and nftables in modern Linux kernels* |
| **OpenWrt SQM** | Standardized Smart Queue Management (SQM) scripts for OpenWrt embedded routers. Packages `tc-cake` and `fq_codel` with predefined upload/download rate ceilings, DiffServ tier maps, and ingress Intermediate Functional Block (`ifb`) interfaces. | • OpenWrt Project: `luci-app-sqm` and `sqm-scripts` Documentation (OpenWrt.org) |

---

## 2. Technical Positioning: What Prior Art Solves vs. Open Challenges

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              PRIOR ART VS. RESIDENTIAL HOME GATEWAY GAPS                                │
├──────────────────────────┬──────────────────────────────────────────┬──────────────────────────────────┤
│ Technology               │ What It Solves                           │ What Remains Open for Home CPEs  │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ **Static CAKE / SQM**    │ Completely solves bufferbloat **if** the  │ Fails when broadband capacity    │
│                          │ shaper rate matches the line rate.       │ collapses (e.g. 100M -> 20M);    │
│                          │                                          │ standing delay explodes to 124ms.│
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ **cake-autorate**        │ Dynamically tracks changing capacity     │ Uses active ICMP/UDP ping floods │
│                          │ via external reflector latency probes.   │ that consume data quotas; lacks  │
│                          │                                          │ multi-tin traffic intent steering│
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ **Deep Packet Inspection**│ Identifies application protocols by      │ Cryptographically broken by      │
│                          │ parsing HTTP/TLS plain text headers.     │ TLS 1.3 / QUIC; violates GDPR;   │
│                          │                                          │ heavy CPU consumption on SoCs.   │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ **Standard DiffServ**    │ Provides multi-queue priority scheduling │ Untrusted residential LAN hosts  │
│                          │ based on IP packet DSCP bits.            │ can spoof DSCP EF tags on bulk   │
│                          │                                          │ torrents, hijacking voice queues.│
└──────────────────────────┴──────────────────────────────────────────┴──────────────────────────────────┘
```

---

## 3. The EdgeQoS Contribution & Research Hypothesis

> **Honest Positioning:**  
> CAKE and FQ-CoDel already solve the vast majority of residential bufferbloat when the configured shaper rate matches link capacity. Furthermore, latency-based autorate tools have successfully demonstrated the feasibility of dynamic bandwidth tracking. **EdgeQoS does not claim that these foundational building blocks are ineffective or that their individual components are novel inventions.**
>
> Rather, EdgeQoS evaluates an **integrated, privacy-preserving, guard-railed edge architecture** specifically tailored for residential broadband gateways facing encrypted traffic and untrusted endpoints:
> 1. **Zero-DPI Intent Classification:** Classifying encrypted flows within their first $N \le 10$ packets using statistical header distributions rather than invasive payload inspection.
> 2. **Calibrated Confidence Abstention:** Abstaining from priority assignment when model confidence is low, safely defaulting ambiguous flows to Best Effort.
> 3. **Behavioral Anti-Spoofing Guard:** Continuously monitoring promoted flows via `conntrack` counters and demoting misbehaving or spoofed bulk flows within $1.25\text{ seconds}$.
> 4. **Passive Dual-Signal Capacity Tracking:** Fusing gateway queue backlog with external reflector RTT to distinguish between local gateway queuing and upstream modem bottlenecks without saturating the link with active speedtests.
> 5. **Fail-Safe Decoupling:** Decoupling userspace intelligence from kernel forwarding via `nftables` timed sets and watchdog supervision, ensuring zero forwarding degradation if userspace fails.
>
> **The Empirical Hypothesis:**  
> *Does integrating early-flow intent classification, behavioral demotion, and passive capacity tracking into native Linux CAKE provide a measurable reduction in real-time latency and settling time during bandwidth collapse, without adding significant CPU overhead on constrained edge hardware?*  
> Our experiments and open testbed are specifically designed to test this hypothesis.
