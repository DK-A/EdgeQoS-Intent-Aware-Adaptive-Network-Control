"""
tests/test_classifier.py - Unit Tests & Latency Benchmark for ZeroDPIClassifier (ml-v2)
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from daemon.edgeqosd.model import ZeroDPIClassifier

def test_classifier():
    classifier = ZeroDPIClassifier(model_path="ml/models/tree_model.json", tau_confidence=0.70)

    # Load representative samples from dataset_v2
    with open("ml/data/dataset_v2.json", "r") as f:
        data = json.load(f)

    realtime_sample = next(d["features"] for d in data if d["class_name"] == "Realtime")
    bulk_sample = next(d["features"] for d in data if d["class_name"] == "Bulk")

    # 1. Realtime classification
    cls, conf, abstained = classifier.classify_with_abstention(realtime_sample)
    print(f"VoIP test classification: class={cls}, conf={conf:.4f}, abstained={abstained}")
    assert cls == "Realtime", f"Expected Realtime, got {cls}"
    assert not abstained, "Realtime flow should not abstain"

    # 2. Bulk download classification
    cls, conf, abstained = classifier.classify_with_abstention(bulk_sample)
    print(f"Bulk test classification: class={cls}, conf={conf:.4f}, abstained={abstained}")
    assert cls == "Bulk", f"Expected Bulk, got {cls}"
    assert not abstained, "Bulk flow should not abstain"

    # 3. Ambiguous vector with tau threshold
    ambiguous_feat = [0.0] * 22
    cls, conf, abstained = classifier.classify_with_abstention(ambiguous_feat)
    print(f"Ambiguous test classification: class={cls}, conf={conf:.4f}, abstained={abstained}")

    # 4. Latency Benchmark over 10,000 iterations (Section 7.3 requirement)
    bench = classifier.benchmark_latency(realtime_sample, n_iterations=10000)
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
