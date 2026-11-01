"""
tests/test_classifier.py - Unit Tests & Latency Benchmark for ZeroDPIClassifier
"""

import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from daemon.edgeqosd.model import ZeroDPIClassifier

def test_classifier():
    classifier = ZeroDPIClassifier(model_path="ml/models/tree_model.json", tau_confidence=0.85)

    # 1. VoIP vector: small positive and negative lengths, ~20ms IAT (log10(20000) ~ 4.3), UDP=1.0
    voip_feat = [120.0, -120.0, 120.0, -120.0, 120.0, -120.0, 120.0, -120.0, 120.0, -120.0,
                 4.3, 4.3, 4.3, 4.3, 4.3, 4.3, 4.3, 4.3, 4.3,
                 1.0, 0.5, 120.0]

    cls, conf, abstained = classifier.classify_with_abstention(voip_feat)
    print(f"VoIP test classification: class={cls}, conf={conf:.4f}, abstained={abstained}")
    assert cls == "Realtime", f"Expected Realtime, got {cls}"
    assert not abstained, "VoIP flow should not abstain"

    # 2. Bulk download vector: large negative lengths (-1500B), tiny ACKs (54B), TCP=0.0
    bulk_feat = [60.0, -60.0, 54.0, -1500.0, -1500.0, 54.0, -1500.0, -1500.0, 54.0, -1500.0,
                 4.1, 3.0, 3.5, 2.8, 2.5, 2.9, 2.4, 2.6, 2.4,
                 0.0, 0.3, 56.0]

    cls, conf, abstained = classifier.classify_with_abstention(bulk_feat)
    print(f"Bulk test classification: class={cls}, conf={conf:.4f}, abstained={abstained}")
    assert cls == "Bulk", f"Expected Bulk, got {cls}"
    assert not abstained, "Bulk flow should not abstain"

    # 3. Ambiguous vector with tau threshold
    ambiguous_feat = [0.0] * 22
    cls, conf, abstained = classifier.classify_with_abstention(ambiguous_feat)
    print(f"Ambiguous test classification: class={cls}, conf={conf:.4f}, abstained={abstained}")

    # 4. Latency Benchmark over 10,000 iterations (Section 7.3 requirement)
    bench = classifier.benchmark_latency(voip_feat, n_iterations=10000)
    print(f"[+] Measured Tree Inference Latency (10^4 iterations):")
    print(f"    p50: {bench['p50_us']:.3f} us")
    print(f"    p95: {bench['p95_us']:.3f} us")
    print(f"    p99: {bench['p99_us']:.3f} us")

    os.makedirs("results", exist_ok=True)
    with open("results/inference_bench.json", "w") as f:
        json.dump(bench, f, indent=2)
    print("[+] Wrote results/inference_bench.json")

if __name__ == "__main__":
    test_classifier()
