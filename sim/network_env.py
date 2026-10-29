"""
sim/network_env.py - Discrete-Event Bottleneck & Dual-Queue Network Simulator
Simulates Gateway Queue -> Bottleneck Link -> Upstream Modem Buffer -> Server.
"""

import heapq
import collections
from typing import List, Dict, Any, Optional, Tuple
from sim.packet import SimPacket
from sim.queue_models import BaseQueue, FIFOQueue, CAKEDiffserv4Queue, PRIOQueue
from daemon.edgeqosd.guard import BehavioralRateGuard
from daemon.edgeqosd.capacity import QueueLocationCapacityController
from daemon.edgeqosd.model import ZeroDPIClassifier
from daemon.edgeqosd.config import GuardConfig, CapacityConfig

class NetworkSimulator:
    def __init__(self,
                 gateway_queue: BaseQueue,
                 modem_buffer_bytes: int = 262144, # Default 256 KB
                 base_propagation_delay_sec: float = 0.010, # 10 ms one-way
                 initial_link_rate_bps: float = 100_000_000.0, # 100 Mbps
                 enable_edgeqos_control: bool = False,
                 enable_guard: bool = True):
        self.gw_q = gateway_queue
        self.modem_q = FIFOQueue(limit_bytes=modem_buffer_bytes)
        self.base_prop_delay = base_propagation_delay_sec
        self.link_rate_bps = initial_link_rate_bps
        self.enable_edgeqos = enable_edgeqos_control
        self.enable_guard = enable_guard

        # EdgeQoS control components
        self.classifier = ZeroDPIClassifier(tau_confidence=0.85)
        self.guard = BehavioralRateGuard(config=GuardConfig(f_poll_hz=4.0, m_consecutive=4))
        self.capacity_ctrl = QueueLocationCapacityController(direction="down", config=CapacityConfig(dt_sec=0.20, K_confirm=3, beta_down=0.90))

        # Flow tracking
        self.flow_pkts = collections.defaultdict(list)
        self.flow_dscp_map = {}
        self.flow_byte_counters = collections.defaultdict(int)

        self.current_time = 0.0
        self.completed_packets: List[SimPacket] = []
        self.seq = 0

    def set_bottleneck_rate(self, new_rate_bps: float):
        self.link_rate_bps = new_rate_bps

    def run(self, input_packets: List[SimPacket],
            capacity_step_time: Optional[float] = None,
            capacity_step_rate: Optional[float] = None) -> Dict[str, Any]:
        """
        Runs discrete-event simulation over packet list.
        """
        events = [] # (time, ev_type, seq, data)
        self.seq = 0

        def push_ev(t, ev_type, data):
            self.seq += 1
            heapq.heappush(events, (t, ev_type, self.seq, data))

        for p in input_packets:
            push_ev(p.creation_time, 0, p)

        if capacity_step_time and capacity_step_rate:
            push_ev(capacity_step_time, 99, capacity_step_rate)

        max_sim_time = max(p.creation_time for p in input_packets) + 2.0
        t_ctrl = 0.0
        while t_ctrl < max_sim_time:
            push_ev(t_ctrl, 4, None)
            t_ctrl += 0.05

        gw_busy_until = 0.0
        modem_busy_until = 0.0

        while events:
            now, ev_type, _, data = heapq.heappop(events)
            self.current_time = now

            if ev_type == 99:
                self.link_rate_bps = data
                continue

            elif ev_type == 4:
                # Periodic control tick
                if self.enable_edgeqos:
                    # Guard tick (every 250ms)
                    if int(round(now * 100)) % 25 == 0 and self.enable_guard:
                        for fid, b in list(self.flow_byte_counters.items()):
                            ev = self.guard.update_flow_bytes(fid, b, now=now)
                            if ev is not None:
                                self.flow_dscp_map[fid] = 8 # Demote to Bulk (CS1)

                    # Capacity controller tick (every 200ms)
                    if int(round(now * 100)) % 20 == 0:
                        # Report Table III: Internal Delay is measured on the Latency-Sensitive (Voice) tin
                        if isinstance(self.gw_q, CAKEDiffserv4Queue):
                            voice_bytes = sum(sum(p.size_bytes for p in q) for q in self.gw_q.tins[CAKEDiffserv4Queue.TIN_VOICE].values())
                            int_delay = (voice_bytes * 8.0 / max(1.0, self.link_rate_bps)) * 1000.0
                        else:
                            int_delay = (self.gw_q.backlog_bytes() * 8.0 / max(1.0, self.link_rate_bps)) * 1000.0
                        recent_rtts = [p.rtt_ms for p in self.completed_packets[-20:] if p.traffic_class == "Realtime"]
                        base_rtt = 2.0 * self.base_prop_delay * 1000.0
                        current_ext_delta = max(0.0, (sum(recent_rtts) / len(recent_rtts)) - base_rtt) if recent_rtts else 0.0

                        # Offered rate is traffic arriving from LAN into gateway
                        offered_bps = (sum(self.flow_byte_counters.values()) * 8.0 / max(1.0, now))
                        delivered_rate = self.link_rate_bps if current_ext_delta > 15 else 100e6
                        res = self.capacity_ctrl.step(
                            now=now,
                            int_delay_ms=int_delay,
                            ext_delay_delta_ms=current_ext_delta,
                            offered_rate_bps=offered_bps,
                            rx_delivered_bps=delivered_rate,
                            active_flows=max(1, len(self.flow_byte_counters))
                        )
                        if isinstance(self.gw_q, CAKEDiffserv4Queue):
                            self.gw_q.shaper_rate_bps = res["rate_bps"]
                continue

            elif ev_type == 0:
                pkt: SimPacket = data
                fid = pkt.flow_id

                if self.enable_edgeqos:
                    if fid not in self.flow_dscp_map:
                        self.flow_pkts[fid].append(pkt)
                        if len(self.flow_pkts[fid]) == 10:
                            if pkt.traffic_class == "Realtime":
                                self.flow_dscp_map[fid] = 46 # EF (Voice tin)
                                if self.enable_guard:
                                    self.guard.register_promotion(fid, "Realtime", current_bytes=sum(p.size_bytes for p in self.flow_pkts[fid]), now=now)
                            elif pkt.traffic_class == "Stream":
                                self.flow_dscp_map[fid] = 34 # AF41 (Video tin)
                            else:
                                self.flow_dscp_map[fid] = 0  # CS0 (BE)
                    pkt.dscp = self.flow_dscp_map.get(fid, 0)
                else:
                    pkt.dscp = 0

                self.flow_byte_counters[fid] += pkt.size_bytes

                accepted = self.gw_q.enqueue(pkt, now)
                if accepted and now >= gw_busy_until:
                    push_ev(now, 1, None)

            elif ev_type == 1:
                pkt = self.gw_q.dequeue(now)
                if pkt:
                    tx_rate = getattr(self.gw_q, "shaper_rate_bps", self.link_rate_bps)
                    tx_time = (pkt.size_bytes * 8.0) / tx_rate
                    gw_busy_until = now + tx_time

                    modem_arr_time = now + tx_time + self.base_prop_delay
                    push_ev(modem_arr_time, 2, pkt)

                    if self.gw_q.backlog_bytes() > 0:
                        push_ev(gw_busy_until, 1, None)

            elif ev_type == 2:
                pkt: SimPacket = data
                accepted = self.modem_q.enqueue(pkt, now)
                if accepted and now >= modem_busy_until:
                    push_ev(now, 3, None)

            elif ev_type == 3:
                pkt = self.modem_q.dequeue(now)
                if pkt:
                    tx_time = (pkt.size_bytes * 8.0) / self.link_rate_bps
                    modem_busy_until = now + tx_time

                    delivered_time = now + tx_time + self.base_prop_delay
                    pkt.received_time = delivered_time
                    self.completed_packets.append(pkt)

                    if self.modem_q.backlog_bytes() > 0:
                        push_ev(modem_busy_until, 3, None)

        return {
            "total_packets": len(input_packets),
            "completed": len(self.completed_packets),
            "dropped_gw": self.gw_q.drops,
            "dropped_modem": self.modem_q.drops,
            "packets": self.completed_packets
        }
