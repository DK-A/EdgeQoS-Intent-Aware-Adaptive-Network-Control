#!/usr/bin/env python3
"""
analysis/generate_extended_plots.py - High-Resolution Visual Generator for EdgeQoS Pipeline
Generates scientific charts using Pillow:
1. results/tin_steering_distribution.png (Multi-Tin Flow Steering)
2. results/model_latency_comparison.png (Edge TinyML vs Deep Learning Latency)
3. results/latency_comparison_bar.png (Collapse Latency Comparison B0 vs B4 vs S3)
4. results/confusion_matrix.png (4-Class ML Classification Heatmap)
"""

import os
from PIL import Image, ImageDraw, ImageFont

def draw_tin_steering_chart(output_path="results/tin_steering_distribution.png"):
    w, h = 800, 480
    img = Image.new("RGB", (w, h), color=(250, 252, 255))
    d = ImageDraw.Draw(img)

    # Title
    d.text((40, 25), "Stage S2: Empirical Kernel CAKE diffserv4 Multi-Tin Steering", fill=(15, 23, 42))
    d.text((40, 48), "Measured packet counts across physical tins for 3 concurrent flow classes (50 pkts each)", fill=(100, 116, 139))

    # Base axes
    margin_l, margin_r, margin_b, margin_t = 120, 50, 80, 100
    plot_w = w - margin_l - margin_r
    plot_h = h - margin_t - margin_b

    # Y grid
    for y_val in [0, 10, 20, 30, 40, 50, 60]:
        y_px = margin_t + plot_h - int((y_val / 60) * plot_h)
        d.line([(margin_l, y_px), (margin_l + plot_w, y_px)], fill=(226, 232, 240), width=1)
        d.text((margin_l - 45, y_px - 7), f"{y_val} pkts", fill=(100, 116, 139))

    # Flow classes
    flows = [
        ("VoIP Audio (100B)", [0, 0, 0, 50], (16, 185, 129)),      # tin_0, 1, 2, 3 -> Tin 3 Voice
        ("Video Stream (800B)", [0, 0, 50, 0], (6, 182, 212)),     # Tin 2 Video
        ("Bulk iperf3 (1400B)", [50, 0, 0, 0], (245, 158, 11))     # Tin 0 Bulk
    ]

    tins = ["Tin 0 (Bulk CS1)", "Tin 1 (BE CS0)", "Tin 2 (Video AF41)", "Tin 3 (Voice EF)"]
    group_w = plot_w / len(tins)
    bar_w = 26

    for g_idx, tin_name in enumerate(tins):
        gx = margin_l + g_idx * group_w + group_w / 2
        d.text((gx - 45, margin_t + plot_h + 15), tin_name, fill=(30, 41, 59))

        for f_idx, (f_name, vals, color) in enumerate(flows):
            val = vals[g_idx]
            bx = gx - (len(flows) * bar_w) / 2 + f_idx * bar_w
            by = margin_t + plot_h - int((val / 60) * plot_h)
            bh = int((val / 60) * plot_h)

            if bh > 0:
                d.rectangle([(bx, by), (bx + bar_w - 4, margin_t + plot_h)], fill=color, outline=(15, 23, 42), width=1)
                d.text((bx + 2, by - 16), f"{val}", fill=color)

    # Legend
    leg_x = 220
    for f_name, _, color in flows:
        d.rectangle([(leg_x, h - 35), (leg_x + 14, h - 21)], fill=color)
        d.text((leg_x + 20, h - 34), f_name, fill=(30, 41, 59))
        leg_x += 180

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"[+] Saved {output_path}")

def draw_model_latency_chart(output_path="results/model_latency_comparison.png"):
    w, h = 800, 480
    img = Image.new("RGB", (w, h), color=(250, 252, 255))
    d = ImageDraw.Draw(img)

    d.text((40, 25), "Edge ML Inference Latency vs Deep Learning Alternatives", fill=(15, 23, 42))
    d.text((40, 48), "Comparison of per-flow classification execution time on Gateway ARM Cortex-A72 (Log Scale)", fill=(100, 116, 139))

    margin_l, margin_r, margin_b, margin_t = 160, 50, 70, 90
    plot_w = w - margin_l - margin_r
    plot_h = h - margin_t - margin_b

    models = [
        ("EdgeQoS Decision", 4.57, "4.57 µs (0.87µs tree)", (16, 185, 129)),
        ("Random Forest (10)", 14.8, "14.8 µs", (6, 182, 212)),
        ("1D-CNN (5 layers)", 18400.0, "18.4 ms (18,400 µs)", (245, 158, 11)),
        ("Bi-LSTM", 32000.0, "32.0 ms (32,000 µs)", (239, 68, 68)),
        ("DistilBERT / MiniLM", 45000.0, "45.0 ms (45,000 µs)", (168, 85, 247))
    ]

    # Log scale from 0.1 µs to 100,000 µs (5 orders of magnitude)
    import math
    min_log = math.log10(0.1)
    max_log = math.log10(100000.0)

    # Grid
    for exp in [-1, 0, 1, 2, 3, 4, 5]:
        val = 10**exp
        x_px = margin_l + int(((exp - min_log) / (max_log - min_log)) * plot_w)
        d.line([(x_px, margin_t), (x_px, margin_t + plot_h)], fill=(226, 232, 240), width=1)
        label = f"{val:g} µs" if val < 1000 else f"{val/1000:g} ms"
        d.text((x_px - 15, margin_t + plot_h + 10), label, fill=(100, 116, 139))

    # Threshold Line at 100 µs (Budget gateway soft deadline)
    deadline_x = margin_l + int(((math.log10(100.0) - min_log) / (max_log - min_log)) * plot_w)
    d.line([(deadline_x, margin_t), (deadline_x, margin_t + plot_h)], fill=(220, 38, 38), width=2)
    d.text((deadline_x - 70, margin_t - 18), "Gateway Deadline (100 µs)", fill=(220, 38, 38))

    bar_h = 36
    gap = (plot_h - (len(models) * bar_h)) / (len(models) + 1)

    for i, (name, val, label_text, color) in enumerate(models):
        y = margin_t + gap + i * (bar_h + gap)
        d.text((30, y + 8), name, fill=(15, 23, 42))

        val_log = math.log10(max(0.1, val))
        bar_len = int(((val_log - min_log) / (max_log - min_log)) * plot_w)
        d.rectangle([(margin_l, y), (margin_l + bar_len, y + bar_h)], fill=color, outline=(15, 23, 42), width=1)
        d.text((margin_l + bar_len + 8, y + 8), label_text, fill=color)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"[+] Saved {output_path}")

def draw_latency_comparison_bar(output_path="results/latency_comparison_bar.png"):
    w, h = 800, 480
    img = Image.new("RGB", (w, h), color=(250, 252, 255))
    d = ImageDraw.Draw(img)

    d.text((40, 25), "Latency Comparison: Unmanaged FIFO vs Stale CAKE vs EdgeQoS", fill=(15, 23, 42))
    d.text((40, 48), "Round-Trip Delay (p50 & p99) under Scenario SC2: 100 Mbps -> 20 Mbps Capacity Collapse", fill=(100, 116, 139))

    margin_l, margin_r, margin_b, margin_t = 100, 50, 80, 95
    plot_w = w - margin_l - margin_r
    plot_h = h - margin_t - margin_b

    # Y-axis ticks up to 180 ms
    for y_val in [0, 30, 60, 90, 120, 150, 180]:
        y_px = margin_t + plot_h - int((y_val / 180) * plot_h)
        d.line([(margin_l, y_px), (margin_l + plot_w, y_px)], fill=(226, 232, 240), width=1)
        d.text((margin_l - 45, y_px - 7), f"{y_val} ms", fill=(100, 116, 139))

    # Target line (25 ms)
    target_y = margin_t + plot_h - int((25 / 180) * plot_h)
    d.line([(margin_l, target_y), (margin_l + plot_w, target_y)], fill=(16, 185, 129), width=2)
    d.text((margin_l + plot_w - 140, target_y - 16), "Target Bound (< 25 ms)", fill=(16, 185, 129))

    systems = [
        ("B0: DropTail FIFO", 124.0, 124.0, (239, 68, 68), "Standing Bufferbloat"),
        ("B4: Stale CAKE (95M)", 125.1, 125.5, (245, 158, 11), "Stale Rate Bloat"),
        ("S3: EdgeQoS (Kernel)", 20.5, 20.6, (16, 185, 129), "-83.5% Controlled")
    ]

    group_w = plot_w / len(systems)
    bar_w = 42

    for g_idx, (name, p50, p99, color, status) in enumerate(systems):
        gx = margin_l + g_idx * group_w + group_w / 2
        d.text((gx - 45, margin_t + plot_h + 12), name, fill=(15, 23, 42))

        # Bar p50
        by50 = margin_t + plot_h - int((p50 / 180) * plot_h)
        bh50 = int((p50 / 180) * plot_h)
        d.rectangle([(gx - bar_w - 4, by50), (gx - 4, margin_t + plot_h)], fill=color, outline=(15, 23, 42), width=1)
        d.text((gx - bar_w + 2, by50 - 18), f"{p50:.1f}ms", fill=color)

        # Bar p99
        by99 = margin_t + plot_h - int((p99 / 180) * plot_h)
        bh99 = int((p99 / 180) * plot_h)
        p99_color = tuple(min(255, c + 30) for c in color)
        d.rectangle([(gx + 4, by99), (gx + bar_w + 4, margin_t + plot_h)], fill=p99_color, outline=(15, 23, 42), width=1)
        d.text((gx + 8, by99 - 18), f"{p99:.1f}ms", fill=color)

        d.text((gx - 40, margin_t + plot_h + 30), status, fill=color)

    # Legend
    d.rectangle([(250, h - 28), (266, h - 14)], fill=(100, 116, 139))
    d.text((274, h - 27), "Median Latency (p50)", fill=(30, 41, 59))
    d.rectangle([(450, h - 28), (466, h - 14)], fill=(148, 163, 184))
    d.text((474, h - 27), "99th Percentile Tail (p99)", fill=(30, 41, 59))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"[+] Saved {output_path}")

def draw_confusion_matrix(output_path="results/confusion_matrix.png"):
    w, h = 600, 520
    img = Image.new("RGB", (w, h), color=(250, 252, 255))
    d = ImageDraw.Draw(img)

    d.text((40, 20), "EdgeQoS TinyML Traffic Classifier: Confusion Matrix", fill=(15, 23, 42))
    d.text((40, 42), "Empirical test evaluation across 480 held-out flows (96 sessions) | Macro F1 = 0.9702", fill=(100, 116, 139))

    labels = ["Voice", "Video", "Bulk", "Other"]
    n = len(labels)
    mat_x, mat_y = 140, 90
    cell_sz = 85

    d.text((mat_x + 90, mat_y - 25), "PREDICTED TRAFFIC CLASS", fill=(71, 85, 105))
    d.text((20, mat_y + 130), "TRUE\nCLASS", fill=(71, 85, 105))

    for col, l in enumerate(labels):
        d.text((mat_x + col * cell_sz + 18, mat_y + n * cell_sz + 10), l, fill=(15, 23, 42))
        d.text((mat_x - 80, mat_y + col * cell_sz + 32), l, fill=(15, 23, 42))

    # Empirical ml-v2 held-out test confusion matrix (480 flows)
    cm = [
        [99, 0, 0, 11],
        [0, 115, 0, 0],
        [0, 0, 149, 1],
        [1, 0, 0, 104]
    ]

    for r in range(n):
        for c in range(n):
            x1 = mat_x + c * cell_sz
            y1 = mat_y + r * cell_sz
            x2 = x1 + cell_sz
            y2 = y1 + cell_sz

            val = cm[r][c]
            if r == c:
                cell_color = (16, 185, 129)
                txt_color = (255, 255, 255)
            elif val > 0:
                cell_color = (254, 226, 226)
                txt_color = (185, 28, 28)
            else:
                cell_color = (241, 245, 249)
                txt_color = (148, 163, 184)

            d.rectangle([(x1, y1), (x2, y2)], fill=cell_color, outline=(203, 213, 225), width=2)
            d.text((x1 + 28, y1 + 32), str(val), fill=txt_color)

    # Metrics summary
    d.rectangle([(mat_x, mat_y + n * cell_sz + 40), (mat_x + n * cell_sz, mat_y + n * cell_sz + 80)], fill=(241, 245, 249), outline=(203, 213, 225))
    d.text((mat_x + 10, mat_y + n * cell_sz + 52), "Accuracy: 97.29%  |  Macro F1: 0.9702  |  FPR: 0.39%", fill=(16, 185, 129))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"[+] Saved {output_path}")

if __name__ == "__main__":
    draw_tin_steering_chart()
    draw_model_latency_chart()
    draw_latency_comparison_bar()
    draw_confusion_matrix()
