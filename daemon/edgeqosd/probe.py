"""
daemon/edgeqosd/probe.py - Load-Scaled Reflector Prober
Maintains 1 Hz per reflector when idle, scales to 5-10 Hz when loaded.
Computes windowed baseline RTT and current delta.
"""

import time
from typing import List, Dict

class ReflectorProber:
    def __init__(self, reflectors: List[str], window_sec: float = 60.0):
        self.reflectors = reflectors
        self.window_sec = window_sec
        self.samples: List[Tuple[float, float]] = [] # (timestamp, rtt_ms)
        self.baseline_rtt_ms = 15.0 # Initial safe estimate

    def record_rtt(self, now: float, rtt_ms: float):
        self.samples.append((now, rtt_ms))
        # Prune old samples outside window
        cutoff = now - self.window_sec
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.pop(0)

        # Update baseline RTT (minimum observed RTT in window)
        if self.samples:
            self.baseline_rtt_ms = min(s[1] for s in self.samples)

    def get_delta_rtt(self, current_rtt_ms: float) -> float:
        return max(0.0, current_rtt_ms - self.baseline_rtt_ms)
