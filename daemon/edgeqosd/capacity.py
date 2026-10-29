"""
daemon/edgeqosd/capacity.py - Queue-Location Dynamic Capacity Controller
Tata Elxsi TELIPORT S4 · Problem Statement 3
Distinguishes internal queueing from upstream ISP modem bufferbloat using
dual-delay telemetry with hysteresis latches.
"""

from typing import Dict, Any, Optional, Callable
from daemon.edgeqosd.config import CapacityConfig

class HysteresisLatch:
    def __init__(self, set_threshold: float, clear_threshold: float):
        self.set_thr = set_threshold
        self.clear_thr = clear_threshold
        self.state = False

    def update(self, val: float) -> bool:
        if not self.state and val >= self.set_thr:
            self.state = True
        elif self.state and val <= self.clear_thr:
            self.state = False
        return self.state

class QueueLocationCapacityController:
    def __init__(self, direction: str = "down", config: Optional[CapacityConfig] = None, apply_callback: Optional[Callable] = None):
        self.direction = direction # "down" or "up"
        self.cfg = config or CapacityConfig()
        self.apply_callback = apply_callback

        self.current_rate_bps = self.cfg.c_max_bps
        self.int_latch = HysteresisLatch(self.cfg.int_hot_set_ms, self.cfg.int_hot_clear_ms)
        self.ext_latch = HysteresisLatch(self.cfg.ext_hot_set_ms, self.cfg.ext_hot_clear_ms)

        self.hot_counter = 0
        self.t_last_decrease = 0.0
        self.c_fail = self.cfg.c_max_bps
        self.rate_history = []

    def step(self, now: float, int_delay_ms: float, ext_delay_delta_ms: float,
             offered_rate_bps: float, rx_delivered_bps: float, active_flows: int) -> Dict[str, Any]:
        """
        Executes one control step every dt seconds (e.g. 200 ms).
        """
        int_hot = self.int_latch.update(int_delay_ms)
        ext_hot = self.ext_latch.update(ext_delay_delta_ms)

        is_loaded = (offered_rate_bps >= (self.cfg.load_min_ratio * self.current_rate_bps)) and (active_flows > 0)
        action = "HOLD"
        new_rate = self.current_rate_bps

        if ext_hot and is_loaded:
            self.hot_counter += 1
        else:
            self.hot_counter = 0

        # Downward Fast-Path Step-Down (Capacity Collapse Detection)
        if self.hot_counter >= self.cfg.K_confirm and (now - self.t_last_decrease >= self.cfg.hold_off_sec):
            if self.direction == "down" and (not int_hot) and rx_delivered_bps > 0:
                # Downlink fast-path: set to beta * delivered RX rate
                target = max(self.cfg.floor_bps, self.cfg.beta_down * rx_delivered_bps)
                new_rate = min(target, self.current_rate_bps)
                action = "FAST_STEP_DOWN"
            else:
                # Multiplicative decrease
                target = max(self.cfg.floor_bps, self.cfg.gamma_up * self.current_rate_bps)
                new_rate = min(target, self.current_rate_bps)
                action = "MULT_STEP_DOWN"

            self.t_last_decrease = now
            self.c_fail = self.current_rate_bps
            self.current_rate_bps = new_rate
            if self.apply_callback:
                self.apply_callback(self.direction, self.current_rate_bps)

        # Upward Additive Probing (Safe recovery after cooldown)
        elif (not ext_hot) and (now - self.t_last_decrease >= self.cfg.t_cool_sec):
            # Probe upward only if near shaper limit or local queues moderately utilized
            if offered_rate_bps >= 0.85 * self.current_rate_bps or int_hot:
                inc = self.cfg.alpha_bps_per_s * self.cfg.dt_sec
                new_rate = min(self.cfg.c_max_bps, self.current_rate_bps + inc)
                if new_rate != self.current_rate_bps:
                    action = "ADDITIVE_INCREASE"
                    self.current_rate_bps = new_rate
                    if self.apply_callback:
                        self.apply_callback(self.direction, self.current_rate_bps)

        record = {
            "timestamp": now,
            "direction": self.direction,
            "rate_bps": self.current_rate_bps,
            "rate_mbps": self.current_rate_bps / 1e6,
            "action": action,
            "int_hot": int_hot,
            "ext_hot": ext_hot,
            "is_loaded": is_loaded,
            "int_delay_ms": int_delay_ms,
            "ext_delay_delta_ms": ext_delay_delta_ms
        }
        self.rate_history.append(record)
        return record
