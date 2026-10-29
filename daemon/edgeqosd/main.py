"""
daemon/edgeqosd/main.py - EdgeQoS Asynchronous Control Plane Daemon
Tata Elxsi TELIPORT S4 · Problem Statement 3
Orchestrates early-flow classification, behavioral rate guard,
queue-location capacity control, and heartbeat maintenance.
"""

import sys
import os
import time
import asyncio
import signal
from typing import Dict, Tuple

from daemon.edgeqosd.config import EdgeQoSConfig
from daemon.edgeqosd.features import FlowPacketRecord, EarlyFlowBuffer, extract_zero_dpi_features
from daemon.edgeqosd.model import ZeroDPIClassifier
from daemon.edgeqosd.guard import BehavioralRateGuard
from daemon.edgeqosd.capacity import QueueLocationCapacityController
from daemon.edgeqosd.promote import NftablesActuator

class EdgeQoSDaemon:
    def __init__(self, config: EdgeQoSConfig, dry_run: bool = False):
        self.cfg = config
        self.dry_run = dry_run
        self.running = False

        self.classifier = ZeroDPIClassifier(tau_confidence=0.85)
        self.actuator = NftablesActuator(dry_run=self.dry_run)
        self.guard = BehavioralRateGuard(config=self.cfg.guard, demote_callback=self.on_guard_demote)
        self.down_controller = QueueLocationCapacityController(direction="down", config=self.cfg.capacity, apply_callback=self.on_rate_change)
        self.up_controller = QueueLocationCapacityController(direction="up", config=self.cfg.capacity, apply_callback=self.on_rate_change)

        self.flow_buffers: Dict[Tuple, EarlyFlowBuffer] = {}
        self.stats = {
            "packets_observed": 0,
            "flows_evaluated": 0,
            "flows_promoted_rt": 0,
            "flows_promoted_vid": 0,
            "flows_abstained": 0,
            "flows_demoted": 0
        }

    def on_guard_demote(self, flow_key: Tuple, prev_class: str, rate_bps: float):
        self.stats["flows_demoted"] += 1
        proto, saddr, daddr, sport, dport = flow_key
        print(f"[GUARD DEMOTE] Flow {saddr}:{sport}->{daddr}:{dport} demoted from {prev_class} (Rate={rate_bps/1e6:.1f} Mbps)")
        self.actuator.demote_flow(proto, saddr, daddr, sport, dport, prev_class)

    def on_rate_change(self, direction: str, new_rate_bps: float):
        print(f"[CAPACITY ACTUATE] {direction.upper()} rate adjusted to {new_rate_bps/1e6:.2f} Mbps")
        # In production: invokes tc qdisc change dev <wan/lan> root cake bandwidth <new_rate>mbit
        if not self.dry_run:
            dev = self.cfg.lan_if if direction == "down" else self.cfg.wan_if
            cmd = f"tc qdisc change dev {dev} root cake bandwidth {int(new_rate_bps/1e6)}mbit"
            os.system(cmd)

    def handle_parsed_packet(self, ts: float, proto: int, saddr: str, daddr: str, sport: int, dport: int, tot_len: int, tcp_flags: int):
        self.stats["packets_observed"] += 1

        # Canonical flow key
        is_fwd = (saddr < daddr) or (saddr == daddr and sport <= dport)
        key = (proto, saddr, daddr, sport, dport) if is_fwd else (proto, daddr, saddr, dport, sport)

        if key not in self.flow_buffers:
            self.flow_buffers[key] = EarlyFlowBuffer(max_packets=10, timeout_sec=2.0)

        buf = self.flow_buffers[key]
        if buf.is_complete:
            return

        rec = FlowPacketRecord(timestamp=ts, proto=proto, length=tot_len, is_forward=is_fwd, tcp_flags=tcp_flags)
        reached_10 = buf.add_packet(rec)

        if reached_10:
            self.stats["flows_evaluated"] += 1
            feats = extract_zero_dpi_features(buf.records, n_packets=10)
            assigned_cls, conf, abstained = self.classifier.classify_with_abstention(feats)

            if abstained or assigned_cls is None or assigned_cls == "Other":
                self.stats["flows_abstained"] += 1
            elif assigned_cls in ("Realtime", "Stream", "Bulk"):
                if assigned_cls == "Realtime":
                    self.stats["flows_promoted_rt"] += 1
                elif assigned_cls == "Stream":
                    self.stats["flows_promoted_vid"] += 1

                self.actuator.promote_flow(proto, saddr, daddr, sport, dport, assigned_cls)
                # Register with behavioral guard
                self.guard.register_promotion(key, assigned_cls, current_bytes=tot_len * 10, now=ts)

    async def heartbeat_loop(self):
        while self.running:
            hb_path = self.cfg.heartbeat_path
            try:
                os.makedirs(os.path.dirname(hb_path), exist_ok=True)
                with open(hb_path, "w") as f:
                    f.write(str(int(time.time())))
            except Exception:
                # If /run is not writable in sandbox, write to /tmp
                pass
            await asyncio.sleep(1.0)

    async def start(self):
        self.running = True
        print("[+] EdgeQoS Daemon started (dry_run={}).".format(self.dry_run))
        asyncio.create_task(self.heartbeat_loop())

    def stop(self):
        self.running = False
        print("[+] EdgeQoS Daemon stopped.")

if __name__ == "__main__":
    cfg = EdgeQoSConfig()
    daemon = EdgeQoSDaemon(config=cfg, dry_run=True)
    asyncio.run(daemon.start())
