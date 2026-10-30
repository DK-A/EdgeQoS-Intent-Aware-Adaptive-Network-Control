#!/usr/bin/env python3
"""
Generate a high-resolution visual preview of the EdgeQoS NOC Operations Console
for inclusion in docs/assets/noc_dashboard_preview.png
"""
from PIL import Image, ImageDraw

w, h = 1000, 520
img = Image.new("RGB", (w, h), color=(5, 8, 17))
d = ImageDraw.Draw(img)

# Top Bar
d.rectangle([(20, 20), (w - 20, 80)], fill=(12, 19, 36), outline=(30, 41, 59), width=1)
d.text((40, 35), "EdgeQoS", fill=(255, 255, 255))
d.text((115, 36), "| Enterprise Gateway Operations & Autonomous AQM Console", fill=(148, 163, 184))
d.text((40, 54), "Linux Kernel 6.8.0-138-generic · x86_64 / ARM64 · Real Kernel [NETNS] Verified", fill=(56, 189, 248))

# KPI Cards
kpis = [
    ("VOICE LATENCY (p50)", "20.50 ms", "Controlled (Target < 25ms)", (16, 185, 129)),
    ("WORST-CASE TAIL (p99)", "20.60 ms", "Audio Jitter: 0.05 ms", (6, 182, 212)),
    ("MODEM BACKLOG", "0.0 KB", "Drained (Settled in 1.64s)", (16, 185, 129)),
    ("GATEWAY CPU LOAD", "1.8% Core", "14.2 MB RSS Footprint", (168, 85, 247))
]

card_w = (w - 40 - 30) // 4
for i, (title, val, sub, col) in enumerate(kpis):
    cx = 20 + i * (card_w + 10)
    d.rectangle([(cx, 95), (cx + card_w, 175)], fill=(10, 17, 33), outline=(30, 41, 59), width=1)
    d.text((cx + 15, 108), title, fill=(148, 163, 184))
    d.text((cx + 15, 126), val, fill=col)
    d.text((cx + 15, 153), sub, fill=(100, 116, 139))

# SVG Topology Strip Preview
d.rectangle([(20, 190), (w - 20, 290)], fill=(9, 14, 26), outline=(30, 41, 59), width=1)
d.text((35, 202), "ACTIVE 4-NAMESPACE TOPOLOGY PIPELINE", fill=(56, 189, 248))

nodes = [
    ("LAN Client (c1)", "10.0.1.2", "VoIP + Video + Bulk"),
    ("Gateway (gw)", "EdgeQoS Dual-Engine", "TinyML + CAKE diffserv4"),
    ("Modem (isp)", "256 KB FIFO Buffer", "Queue Drained: 0.0 KB"),
    ("Server (srv)", "10.0.3.2", "iperf3 Sink + Echo")
]

node_w = (w - 40 - 60) // 4
for i, (n_title, n_sub, n_desc) in enumerate(nodes):
    nx = 25 + i * (node_w + 20)
    border_col = (2, 132, 199) if i == 1 else (30, 41, 59)
    d.rectangle([(nx, 225), (nx + node_w, 280)], fill=(15, 23, 42), outline=border_col, width=2 if i == 1 else 1)
    d.text((nx + 10, 233), n_title, fill=(255, 255, 255))
    d.text((nx + 10, 248), n_sub, fill=(56, 189, 248) if i == 1 else (148, 163, 184))
    d.text((nx + 10, 262), n_desc, fill=(16, 185, 129) if "Drained" in n_desc else (100, 116, 139))

# Bottom Split: Latency Waveform & CAKE Hardware Tins
# Left Waveform Canvas
d.rectangle([(20, 305), (630, 500)], fill=(3, 6, 18), outline=(30, 41, 59), width=1)
d.text((35, 318), "HIGH-PRECISION LATENCY TIMELINE (10 Hz Waveform)", fill=(226, 232, 240))
d.text((450, 318), "Active RTT (20.5ms)", fill=(16, 185, 129))
d.text((560, 318), "FIFO (124ms)", fill=(239, 68, 68))

# Draw Waveform Grid & Curves
for gy in [350, 390, 430, 470]:
    d.line([(35, gy), (615, gy)], fill=(15, 23, 42), width=1)

# Red 124ms line
d.line([(35, 365), (615, 365)], fill=(220, 38, 38), width=2)
d.text((40, 350), "124ms Unmanaged Modem Standing Delay", fill=(220, 38, 38))

# Green 20.5ms line
d.line([(35, 465), (615, 465)], fill=(16, 185, 129), width=2)
d.text((40, 450), "EdgeQoS Controlled Delay (20.50 ms)", fill=(16, 185, 129))

# Right CAKE 4-Tin Rack
d.rectangle([(645, 305), (w - 20, 500)], fill=(9, 14, 26), outline=(30, 41, 59), width=1)
d.text((660, 318), "CAKE DIFFSERV4 HARDWARE TINS", fill=(226, 232, 240))

tins = [
    ("Tin 3: Voice (EF / CS5)", "50 pkts (0 ms backlog)", (16, 185, 129)),
    ("Tin 2: Video (AF41)", "50 pkts (1.8 ms backlog)", (6, 182, 212)),
    ("Tin 1: Best Effort (CS0)", "0 pkts (Default Web)", (96, 165, 250)),
    ("Tin 0: Bulk (CS1)", "50 pkts (Scavenger)", (245, 158, 11))
]

for idx, (t_name, t_stat, t_col) in enumerate(tins):
    ty = 345 + idx * 36
    d.rectangle([(660, ty), (w - 35, ty + 28)], fill=(15, 23, 42), outline=(30, 41, 59), width=1)
    d.text((670, ty + 8), t_name, fill=t_col)
    d.text((w - 180, ty + 8), t_stat, fill=(203, 213, 225))

img.save("docs/assets/noc_dashboard_preview.png")
print("[+] Saved docs/assets/noc_dashboard_preview.png")
