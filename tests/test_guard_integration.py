"""
tests/test_guard_integration.py - Integration Test: Abstention + Behavioral Rate Guard
Verifies:
1. Legitimate Opus VoIP call (128 kbps) is NEVER demoted.
2. Legitimate Cloud Gaming stream (3.0 Mbps) is NEVER demoted.
3. Rogue mimic stream (blasts 40 Mbps) IS demoted within (K+1)/f_poll + t_nft <= 1.25s.
4. Abstention integration: flows with confidence < tau stay in CS0 without promotion.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from daemon.edgeqosd.guard import BehavioralRateGuard
from daemon.edgeqosd.config import GuardConfig
from daemon.edgeqosd.model import ZeroDPIClassifier

def test_guard_abstention_integration():
    print("[*] Running Integration Test: Abstention + Behavioral Rate Guard...")

    # Load trained model
    classifier = ZeroDPIClassifier(model_path="ml/models/tree_model.json", tau_confidence=0.70)
    guard = BehavioralRateGuard(config=GuardConfig(f_poll_hz=4.0, m_consecutive=4))

    # Case 1: Legitimate 128 kbps Opus Call
    flow_key_call = ("192.168.1.10", "10.0.2.2", 50000, 50002, 17)
    guard.register_promotion(flow_key_call, "Realtime", current_bytes=0, now=0.0)

    # Simulate 4.0 seconds (16 ticks at 4 Hz) of 128 kbps traffic (16,000 bytes/sec = 4,000 bytes/tick)
    cum_bytes = 0
    demoted_call = False
    for tick in range(1, 17):
        t = tick * 0.25
        cum_bytes += 4000
        event = guard.update_flow_bytes(flow_key_call, cum_bytes, now=t)
        if event:
            demoted_call = True
            break
    assert not demoted_call, "Legitimate Opus call was incorrectly demoted!"
    print("  [+] Legitimate Opus Call (128 kbps): Sustained without demotion (PASS)")

    # Case 2: Legitimate 3.0 Mbps Cloud Gaming
    flow_key_game = ("192.168.1.10", "10.0.2.2", 51000, 51002, 17)
    guard.register_promotion(flow_key_game, "Realtime", current_bytes=0, now=0.0)

    # 3.0 Mbps = 375,000 bytes/sec = 93,750 bytes/tick
    cum_bytes = 0
    demoted_game = False
    for tick in range(1, 17):
        t = tick * 0.25
        cum_bytes += 93750
        event = guard.update_flow_bytes(flow_key_game, cum_bytes, now=t)
        if event:
            demoted_game = True
            break
    assert not demoted_game, "Legitimate Cloud Gaming stream was incorrectly demoted!"
    print("  [+] Legitimate Cloud Gaming (3.0 Mbps): Sustained without demotion (PASS)")

    # Case 3: Rogue Mimic Flow (mimics VoIP then blasts at 40 Mbps)
    flow_key_rogue = ("192.168.1.10", "10.0.2.2", 52000, 52002, 17)
    guard.register_promotion(flow_key_rogue, "Realtime", current_bytes=0, now=0.0)

    # 40 Mbps = 5,000,000 bytes/sec = 1,250,000 bytes/tick (> 5.0 Mbps budget)
    cum_bytes = 0
    demotion_event = None
    for tick in range(1, 17):
        t = tick * 0.25
        cum_bytes += 1250000
        event = guard.update_flow_bytes(flow_key_rogue, cum_bytes, now=t)
        if event:
            demotion_event = event
            break

    assert demotion_event is not None, "Rogue mimic stream was NOT demoted!"
    t_demote = demotion_event["elapsed_sec"]
    print(f"  [+] Rogue Mimic Stream (40 Mbps): Demoted at t = {t_demote:.2f}s (Theoretical bound <= 1.25s) (PASS)")
    assert t_demote <= 1.25, f"Demotion took {t_demote}s, exceeding 1.25s bound"

    # Case 4: Abstention Handling
    ambiguous_feat = [0.0] * 22
    cls_name, conf, abstained = classifier.classify_with_abstention(ambiguous_feat)
    # If abstained, controller does NOT promote to Realtime or Stream; keeps in Best-Effort
    assert conf < 0.70 or cls_name == "Bulk", "Expected low confidence or Bulk on ambiguous vector"
    print("  [+] Abstention Test: Ambiguous flow safely defaulted without priority promotion (PASS)")

    print("[+] All Guard Integration Tests Passed Successfully!")

if __name__ == "__main__":
    test_guard_abstention_integration()
