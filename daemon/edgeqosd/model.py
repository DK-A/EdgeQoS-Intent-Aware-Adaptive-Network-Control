"""
daemon/edgeqosd/model.py - Lightweight Runtime Tree Inference & Abstention
Tata Elxsi TELIPORT S4 · Problem Statement 3
Pure-Python tree traversal over exported JSON arrays.
Zero external dependencies. Operates in < 15 microseconds per flow.
"""

import json
import time
from typing import List, Dict, Any, Tuple, Optional

class ZeroDPIClassifier:
    def __init__(self, model_path: str = "ml/models/tree_model.json", tau_confidence: float = 0.85):
        with open(model_path, "r") as f:
            self.model = json.load(f)
        self.left = self.model["left"]
        self.right = self.model["right"]
        self.feat = self.model["feat"]
        self.thr = self.model["thr"]
        self.value = self.model["value"]
        self.classes = self.model["classes"]
        self.tau_confidence = tau_confidence

    def predict_proba(self, x: List[float]) -> List[float]:
        """Evaluates tree in O(depth) steps (depth <= 6)."""
        n = 0
        while self.left[n] != -1:
            f = self.feat[n]
            t = self.thr[n]
            n = self.left[n] if x[f] <= t else self.right[n]
        v = self.value[n]
        s = sum(v)
        if s <= 0:
            return [0.25, 0.25, 0.25, 0.25]
        return [c / s for c in v]

    def classify_with_abstention(self, x: List[float]) -> Tuple[Optional[str], float, bool]:
        """
        Returns: (predicted_class_or_None, confidence, did_abstain)
        If confidence < tau_confidence (default 0.85), abstains (returns None, conf, True).
        """
        probs = self.predict_proba(x)
        top_idx = max(range(len(probs)), key=lambda i: probs[i])
        confidence = probs[top_idx]

        if confidence < self.tau_confidence:
            return None, confidence, True # Abstain -> keep in default Best-Effort (CS0)

        return self.classes[top_idx], confidence, False

    def benchmark_latency(self, x: List[float], n_iterations: int = 10000) -> Dict[str, float]:
        """Measures empirical per-call decision latency in microseconds."""
        latencies_ns = []
        for _ in range(n_iterations):
            t0 = time.perf_counter_ns()
            _ = self.predict_proba(x)
            t1 = time.perf_counter_ns()
            latencies_ns.append(t1 - t0)

        latencies_ns.sort()
        p50_us = latencies_ns[int(0.50 * n_iterations)] / 1000.0
        p95_us = latencies_ns[int(0.95 * n_iterations)] / 1000.0
        p99_us = latencies_ns[int(0.99 * n_iterations)] / 1000.0
        return {
            "p50_us": p50_us,
            "p95_us": p95_us,
            "p99_us": p99_us,
            "n_iterations": n_iterations
        }
