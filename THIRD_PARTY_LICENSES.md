# EdgeQoS: Third-Party Licenses & Open Source Attributions

**Project:** EdgeQoS — Intent-Aware Active Queue Management  
**Compliance:** Tata Elxsi TELIPORT Season 4 · Case Study 3  
**License:** EdgeQoS source code is released under the **MIT License** (see [LICENSE](LICENSE)).

This document provides attributions and licensing details for third-party open-source software, kernel subsystems, and libraries utilized or referenced by the EdgeQoS project.

---

## 1. Operating System & Linux Kernel Subsystems

| Component | Upstream Project & Copyright | License | Usage in EdgeQoS |
| :--- | :--- | :--- | :--- |
| **Linux Kernel Network Stack** | The Linux Kernel Authors (`kernel.org`) | **GPL-2.0-only** | Virtual network namespaces (`ip netns`), socket buffers (`sk_buff`), TCP/IP networking stack |
| **sch_cake (CAKE qdisc)** | T. Høiland-Jørgensen, D. Täht, J. Morton | **GPL-2.0-only / Dual BSD** | In-kernel packet scheduling, Cobalt AQM, Deficit Round Robin (DRR+), and multi-tin prioritization (`diffserv4`) |
| **Netfilter & nftables** | Netfilter Core Team (`netfilter.org`) | **GPL-2.0-or-later** | In-kernel packet filtering, timed 5-tuple sets (`promo_rt`), and protocol snaplen truncation |
| **iproute2 (tc / ip)** | Stephen Hemminger, Alexey Kuznetsov et al. | **GPL-2.0-only** | CLI tools for traffic control (`tc`) and network namespace management |
| **libnetfilter_log** | Netfilter Project | **GPL-2.0-or-later** | Userspace packet header logging interface via Netlink ring-buffers (`reader/reader.c`) |

---

## 2. Python Libraries & Runtime Dependencies

| Library | Author / Maintainers | License | Usage in EdgeQoS |
| :--- | :--- | :--- | :--- |
| **Python Standard Library** | Python Software Foundation (`python.org`) | **PSF License** | Core runtime for control plane, telemetry, and test harnesses |
| **scikit-learn** | scikit-learn developers (`scikit-learn.org`) | **BSD-3-Clause** | Offline training, GroupKFold validation, and decision tree quantization (`ml/train.py`) |
| **numpy** | NumPy Developers (`numpy.org`) | **BSD-3-Clause** | Numerical array manipulation and feature vector serialization |
| **Pillow (PIL Fork)** | Jeffrey A. Clark (Alex) and contributors | **HPND License** | Zero-dependency generation of standalone scientific results plots (`analysis/plots.py`) |

---

## 3. Network Emulation & Benchmarking Tools

| Tool | Upstream Project | License | Usage in EdgeQoS |
| :--- | :--- | :--- | :--- |
| **iperf3** | ESnet / Lawrence Berkeley National Laboratory | **BSD-3-Clause** | Generation of controlled TCP bulk streams and UDP telepresence flows in testbed |
| **tc-netem & tc-tbf** | Stephen Hemminger, Linux Foundation | **GPL-2.0-only** | In-kernel emulation of link propagation delay, packet loss, and bottleneck rate collapse |

---

## 4. Compliance & Licensing Invariants

1. **Kernel Border Invariant:** EdgeQoS interacts with Linux kernel subsystems (`tc`, `nftables`, `netlink`) exclusively through standard userspace syscalls and netlink socket boundaries. It contains no proprietary kernel-space modifications.
2. **Clean Separation:** The userspace control plane daemons are distributed under the permissive MIT license and do not statically link against GPL-only userspace libraries.
