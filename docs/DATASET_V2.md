# Dataset v2 Datasheet (EdgeQoS Real-Stack Network Dataset)

**Provenance:** `[NETNS]` / Real Linux Kernel Sockets (`AF_INET` TCP/UDP)  
**Generation Date:** November 1, 2026 · **Status:** Validated  
**Supersedes:** `results/archive_v1_synthetic/`  

---

## 1. Motivation & Overview
Dataset v2 was generated through the live Linux kernel networking stack to address the synthetic distribution separability identified in v1. Flows are produced using actual kernel socket operations (`AF_INET`, `SOCK_STREAM` for TCP, `SOCK_DGRAM` for UDP), capturing authentic transport framing, kernel segmentation, inter-arrival time variation, and condition shifts.

---

## 2. Dataset Composition

* **Total Flows:** 2400
* **Total Sessions:** 480 (120 sessions per class)
* **Flows per Session:** 5
* **Feature Dimensionality:** 22 Zero-DPI features (10 signed packet lengths, 9 log10 IATs, 1 protocol flag, 1 directionality ratio, 1 mean forward length).
* **Payload Retention:** **0 Bytes (100% Zero-DPI)**. No payload data is retained or processed.

### Class Breakdown

| Class ID | Class Name | Applications Emulated | Transport Protocols | Condition Variants |
| :---: | :--- | :--- | :---: | :--- |
| **0** | **Realtime** | Opus Audio (VBR 60–240B, 20ms pacing), Cloud Gaming (250–950B), FPS game ticks | UDP (17) | Low load, High competing load (jitter injection) |
| **1** | **Stream** | DASH/HLS chunk download over HTTP, segment chunk bursts | TCP (6) | Low load, High competing load |
| **2** | **Bulk** | Saturated TCP CUBIC download, upload transfers, multi-stream | TCP (6) | Low load, High competing load |
| **3** | **Other** | DNS queries (UDP 53), REST API calls (JSON payloads), web page loads | UDP (17), TCP (6) | Low load, High competing load |

---

## 3. Recording Conditions & Shift

* **Low-Load Condition (~70% of sessions):** Baseline link transmission with nominal packet timing.
* **High-Competing-Load Condition (~30% of sessions):** Cross-traffic congestion inducing inter-arrival delay inflation, jitter (sigma = 3-8ms), and buffer variance. Used for evaluating out-of-distribution condition shift.

---

## 4. Ethical Collection & Privacy Assurance

* All sessions are generated through isolated Linux socket environments or local network tests.
* No personal, subscriber, or private data was collected.
* IP addresses and 5-tuples are anonymized into session identifiers.
