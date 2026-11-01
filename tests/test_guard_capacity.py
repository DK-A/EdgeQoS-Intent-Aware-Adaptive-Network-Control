"""
tests/test_guard_capacity.py - Unit tests for Guard and Capacity Controller
"""

import time
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from daemon.edgeqosd.guard import BehavioralRateGuard
from daemon.edgeqosd.capacity import QueueLocationCapacityController
from daemon.edgeqosd.config import GuardConfig, CapacityConfig

def test_behavioral_guard_demotion():
    print("[*] Testing BehavioralRateGuard demotion...")
    demoted_records = []
    def on_demote(key, cls, rate):
        demoted_records.append((key, cls, rate))

    cfg = GuardConfig(f_poll_hz=4.0, m_consecutive=4) # 4 Hz, 4 consecutive ticks
    guard = BehavioralRateGuard(config=cfg, demote_callback=on_demote)

    flow_key = ("tcp", "192.168.50.10", "10.0.1.2", 45000, 443)
    t = 100.0

    # Register as Realtime (budget 5.0 Mbps)
    guard.register_promotion(flow_key, "Realtime", current_bytes=1000, now=t)

    # Simulate 50 Mbps rogue flow (6,250,000 bytes/sec -> 1,562,500 bytes per 0.25s)
    bytes_curr = 1000
    demoted = False
    for i in range(1, 10):
        t += 0.25 # 4 Hz tick
        bytes_curr += int(50_000_000 / 8 * 0.25)
        ev = guard.update_flow_bytes(flow_key, bytes_curr, now=t)
        if ev is not None:
            demoted = True
            print(f"    Demoted at tick {i}: rate={ev['sustained_rate_bps']/1e6:.1f} Mbps, elapsed={ev['elapsed_sec']:.2f}s")
            assert ev["sustained_rate_bps"] > 5_000_000
            # Bound: T_demote <= (m+1)/f_poll = (4+1)/4 = 1.25s
            assert ev["elapsed_sec"] <= 1.5, f"Demotion took {ev['elapsed_sec']}s, expected <= 1.5s"
            break

    assert demoted, "Rogue flow was not demoted by guard!"
    print("[+] BehavioralRateGuard verified successfully.")

def test_capacity_controller_collapse_detection():
    print("[*] Testing QueueLocationCapacityController collapse detection...")
    cfg = CapacityConfig(dt_sec=0.20, K_confirm=3, beta_down=0.90)
    ctrl = QueueLocationCapacityController(direction="down", config=cfg)

    # State 1: Healthy & Idle (no reduction)
    res = ctrl.step(now=10.0, int_delay_ms=2.0, ext_delay_delta_ms=3.0,
                    offered_rate_bps=1_000_000.0, rx_delivered_bps=1_000_000.0, active_flows=1)
    assert res["action"] == "HOLD"
    assert res["rate_mbps"] == 100.0

    # State 2: 100M -> 20M collapse under load
    # External delay inflates to 50ms, internal delay is 1ms (standing buffer is upstream!)
    # Delivered rate drops to 20 Mbps
    step_down_triggered = False
    for i in range(1, 6):
        t = 10.0 + i * 0.20
        res = ctrl.step(now=t, int_delay_ms=1.5, ext_delay_delta_ms=50.0,
                        offered_rate_bps=70_000_000.0, rx_delivered_bps=20_000_000.0, active_flows=4)
        if res["action"] == "FAST_STEP_DOWN":
            step_down_triggered = True
            expected_target = 0.90 * 20.0 # 18 Mbps
            print(f"    Fast step-down actuated at step {i} (t={t:.2f}): rate={res['rate_mbps']:.1f} Mbps")
            assert abs(res["rate_mbps"] - expected_target) < 0.1, f"Expected {expected_target} Mbps, got {res['rate_mbps']}"
            break

    assert step_down_triggered, "Capacity controller failed to detect capacity collapse!"
    print("[+] QueueLocationCapacityController verified successfully.")

if __name__ == "__main__":
    test_behavioral_guard_demotion()
    test_capacity_controller_collapse_detection()
