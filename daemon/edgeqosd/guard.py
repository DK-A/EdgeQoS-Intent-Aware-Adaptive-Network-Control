"""
daemon/edgeqosd/guard.py - Behavioral Rate Budget Guard
Tata Elxsi TELIPORT S4 · Problem Statement 3
Guards priority tins against misclassified, greedy, or adversarial flows.
Demotes flows exceeding class budget within T_demote,max = (m+1)/f_poll + t_nft.
"""

import time
from typing import Dict, Tuple, Optional, Callable
from daemon.edgeqosd.config import GuardConfig

class PromotedFlow:
    __slots__ = ("key", "assigned_class", "promoted_at", "last_bytes", "last_time", "over_budget_count")
    def __init__(self, key: Tuple, assigned_class: str, initial_bytes: int, initial_time: float):
        self.key = key
        self.assigned_class = assigned_class
        self.promoted_at = initial_time
        self.last_bytes = initial_bytes
        self.last_time = initial_time
        self.over_budget_count = 0

class BehavioralRateGuard:
    def __init__(self, config: Optional[GuardConfig] = None, demote_callback: Optional[Callable] = None):
        self.cfg = config or GuardConfig()
        self.demote_callback = demote_callback
        self.promoted_flows: Dict[Tuple, PromotedFlow] = {}
        self.demoted_flows: Dict[Tuple, float] = {} # Key -> Demotion timestamp (cooldown)
        self.demotion_events = []

    def register_promotion(self, flow_key: Tuple, assigned_class: str, current_bytes: int, now: Optional[float] = None):
        t = now if now is not None else time.time()
        # If flow was previously demoted within 60s, do not re-promote
        if flow_key in self.demoted_flows and (t - self.demoted_flows[flow_key]) < 60.0:
            return False
        self.promoted_flows[flow_key] = PromotedFlow(flow_key, assigned_class, current_bytes, t)
        return True

    def update_flow_bytes(self, flow_key: Tuple, current_bytes: int, now: Optional[float] = None) -> Optional[Dict]:
        """
        Processes a single flow rate sample.
        Returns demotion event dict if flow was demoted, else None.
        """
        if flow_key not in self.promoted_flows:
            return None

        t = now if now is not None else time.time()
        flow = self.promoted_flows[flow_key]
        dt = t - flow.last_time
        if dt <= 0.0:
            return None

        d_bytes = max(0, current_bytes - flow.last_bytes)
        current_rate_bps = (d_bytes * 8.0) / dt
        flow.last_bytes = current_bytes
        flow.last_time = t

        budget = self.cfg.budget_bps.get(flow.assigned_class, 5_000_000.0)

        if current_rate_bps > budget:
            flow.over_budget_count += 1
            if flow.over_budget_count >= self.cfg.m_consecutive:
                # Trigger Demotion
                elapsed_since_promotion = t - flow.promoted_at
                event = {
                    "key": flow_key,
                    "demoted_class": flow.assigned_class,
                    "sustained_rate_bps": current_rate_bps,
                    "budget_bps": budget,
                    "over_budget_samples": flow.over_budget_count,
                    "elapsed_sec": elapsed_since_promotion,
                    "timestamp": t
                }
                del self.promoted_flows[flow_key]
                self.demoted_flows[flow_key] = t
                self.demotion_events.append(event)
                if self.demote_callback:
                    self.demote_callback(flow_key, flow.assigned_class, current_rate_bps)
                return event
        else:
            flow.over_budget_count = 0

        return None
