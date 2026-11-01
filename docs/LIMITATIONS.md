# EdgeQoS: Known Limitations, Assumptions & Production Boundary

**Project:** EdgeQoS — Intent-Aware Active Queue Management  
**Compliance:** Tata Elxsi TELIPORT Season 4 · Case Study 3  
**Philosophy:** Scientific honesty requires declaring what is verified, what is emulated, and what remains open engineering work.

---

## 1. Prototype Boundary vs. Production Deployment

The EdgeQoS Round 1 submission is a **functional reference prototype and evaluation testbed**. It is designed to prove architectural feasibility and validate the core closed-loop control algorithms. The following boundary separates the prototype from carrier-grade production:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PROTOTYPE VS. PRODUCTION BOUNDARY                                      │
├──────────────────────────────────────┬─────────────────────────────────────────────────────────────────┤
│ Scope in Current Prototype           │ Production Boundary (Planned Roadmap / Future Scope)            │
├──────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
│ • Virtual Linux Network Namespaces   │ • Physical Deployment on Carrier Residential Gateways (CPE)     │
│ • Emulated Bottleneck (tbf / netem)  │ • Real-World DOCSIS / GPON / DSL Access Line Physical Layers    │
│ • IPv4 Protocol Stack                │ • Dual-Stack IPv4 / IPv6 (ND, SLAAC, Flow Labels)               │
│ • CLI Intent Lease Actuation         │ • User-Facing Mobile App & RESTful Intent Management API        │
│ • Curated & Replayed Datasets        │ • Live Consumer Multi-Device Field Trials (Scale & Drift)       │
│ • Single Upstream WAN Interface      │ • Dual-WAN, 5G Fixed-Wireless Failover, Wi-Fi Airtime Fairness │
└──────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘
```

---

## 2. Explicit Technical Limitations

### 1. Testbed Emulation vs. Hardware Reality
* **Current State:** The primary empirical evaluation was conducted in an isolated Linux 6.8 network namespace testbed (`scripts/setup_netns_topo.sh`). Bottleneck bandwidth, modem queue capacity, and RTT were emulated using Linux `tc-tbf` and `tc-netem`.
* **Limitation:** Emulated virtual Ethernet (`veth`) pairs eliminate physical PHY/MAC layer contention, USB bus latency, and physical Ethernet controller interrupt moderation.
* **Target:** While the codebase compiles and runs on ARM64 Linux, full physical validation on the Raspberry Pi 4B hardware testbed is roadmapped for Phase 4.

### 2. IPv4 Support Only in Prototype
* **Current State:** Packet capture snaplen, `nftables` sets, and header parsing logic currently target **IPv4 5-tuples** (Source IP, Destination IP, Protocol, Source Port, Destination Port).
* **Limitation:** In modern residential networks with IPv6 deployment, IPv6 packets currently pass through unclassified in the default Best Effort tin (`CS0`).
* **Roadmap:** Extending the C reader and `nftables` ruleset to extract IPv6 40-byte fixed headers and IPv6 20-bit Flow Labels is planned for Phase 2.

### 3. Starvation-Freedom Guarantees
* **Current State:** Starvation prevention is structurally provided by CAKE's Deficit Round Robin (DRR+) scheduling, which guarantees that Tin 0 (Bulk) receives a minimum service quantum ($\ge 6.25\%$ of link bandwidth).
* **Limitation:** While verified under 3 concurrent saturated bulk flows in Scenario $SC_1$, rigorous formal starvation-freedom proofs under extreme flow churn (e.g., hundreds of concurrent aggressive bulk streams) have not yet been evaluated.

### 4. Zero-DPI Header Snaplen & Payload Leakage Bounds
* **The Math:** An IPv4 header without options is 20 bytes; a standard TCP header without options is 20 bytes; a standard UDP header is 8 bytes.
* **The Vulnerability in Naive Implementations:** If a static snaplen of **40 bytes** is applied blindly to all packets, a UDP packet leaks:
  $$\text{Leaked Payload} = 40\text{ bytes} - (20\text{ bytes IP} + 8\text{ bytes UDP}) = \mathbf{12\text{ bytes of UDP payload}}$$
* **The EdgeQoS Solution & Measured Result:** EdgeQoS implements **protocol-aware snaplen truncation** in `dataplane/edgeqos.nft`:
  * TCP packets: Snaplen truncated to **40 bytes** $\to$ **0 bytes payload leaked**.
  * UDP packets: Snaplen truncated to **28 bytes** $\to$ **0 bytes payload leaked**.
* **Verification:** Formal test `tests/test_privacy.py` and `results/priv_report.txt` confirm that across 10,000 synthetic and captured packets, exactly **0 bytes** of application payload entered userspace memory.

### 5. Training Data Diversity & Model Generalization
* **Current State:** The TinyML Decision Tree was trained on curated flow distributions (VoIP G.711/Opus, Zoom telepresence, BitTorrent bulk, and HTTPS web traffic).
* **Limitation:** Synthetic and lab-recorded flow separability does not guarantee 100% classification accuracy in the wild. Real-world consumer applications (e.g. encrypted cloud gaming, WebRTC video calling with variable frame rates) may exhibit feature overlap.
* **Mitigation:** The model incorporates calibrated confidence abstention ($\tau = 0.70$) and the behavioral rate guard demotes misclassified bulk flows within $1.25\text{ seconds}$.

### 6. Public Internet Reflector Latency Probing
* **Current State:** In the prototype testbed, external RTT is measured against an emulated upstream reflector (`srv`).
* **Limitation:** In commercial deployment, probing public internet reflectors (e.g. Cloudflare 1.1.1.1, Google 8.8.8.8) introduces real-world challenges:
  * Public DNS/NTP servers may rate-limit or block ICMP/UDP echo probes.
  * Asymmetric routing can introduce latency variations unrelated to upstream gateway congestion.
* **Roadmap:** Future carrier integration should utilize ISP edge reflection targets (e.g. TWAMP or BFD probes to the ISP Broadband Remote Access Server / BNG).

### 7. User Intent Interface
* **Current State:** Temporary user intent leases (e.g., granting a 1-hour Expedited Forwarding lease to a home worker's laptop) are executed via CLI commands (`controller/lease.py`).
* **Limitation:** The planned RESTful API and mobile/web user interface are currently planned deliverables.
