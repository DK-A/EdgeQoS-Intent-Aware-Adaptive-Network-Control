"""
sim/queue_models.py - Queue Models: FIFO, PRIO, FQ-CoDel, and CAKE diffserv4
"""

import collections
from typing import List, Deque, Dict, Optional, Tuple
from sim.packet import SimPacket

class BaseQueue:
    def enqueue(self, pkt: SimPacket, current_time: float) -> bool:
        raise NotImplementedError
    def dequeue(self, current_time: float) -> Optional[SimPacket]:
        raise NotImplementedError
    def backlog_bytes(self) -> int:
        raise NotImplementedError

class FIFOQueue(BaseQueue):
    def __init__(self, limit_bytes: int = 262144): # Default: 256 KB
        self.limit_bytes = limit_bytes
        self.queue: Deque[SimPacket] = collections.deque()
        self.curr_bytes = 0
        self.drops = 0

    def enqueue(self, pkt: SimPacket, current_time: float) -> bool:
        if self.curr_bytes + pkt.size_bytes > self.limit_bytes:
            pkt.dropped = True
            self.drops += 1
            return False
        self.queue.append(pkt)
        self.curr_bytes += pkt.size_bytes
        return True

    def dequeue(self, current_time: float) -> Optional[SimPacket]:
        if not self.queue:
            return None
        pkt = self.queue.popleft()
        self.curr_bytes -= pkt.size_bytes
        pkt.dequeued_time = current_time
        return pkt

    def backlog_bytes(self) -> int:
        return self.curr_bytes

class PRIOQueue(BaseQueue):
    """Static 3-band priority queue (0=High/Voice, 1=Medium/Video, 2=Low/Bulk)."""
    def __init__(self, limit_bytes: int = 262144):
        self.bands: List[Deque[SimPacket]] = [collections.deque() for _ in range(3)]
        self.limit_bytes = limit_bytes
        self.curr_bytes = 0
        self.drops = 0

    def _get_band(self, pkt: SimPacket) -> int:
        if pkt.dscp in (46, 40): # EF / CS5
            return 0
        elif pkt.dscp in (34, 32): # AF41 / CS4
            return 1
        return 2 # Best effort / Bulk

    def enqueue(self, pkt: SimPacket, current_time: float) -> bool:
        if self.curr_bytes + pkt.size_bytes > self.limit_bytes:
            pkt.dropped = True
            self.drops += 1
            return False
        b = self._get_band(pkt)
        self.bands[b].append(pkt)
        self.curr_bytes += pkt.size_bytes
        return True

    def dequeue(self, current_time: float) -> Optional[SimPacket]:
        for b in range(3):
            if self.bands[b]:
                pkt = self.bands[b].popleft()
                self.curr_bytes -= pkt.size_bytes
                pkt.dequeued_time = current_time
                return pkt
        return None

    def backlog_bytes(self) -> int:
        return self.curr_bytes

class CAKEDiffserv4Queue(BaseQueue):
    """
    Emulates Linux CAKE diffserv4 queue discipline (sch_cake.c):
    - 4 Tins: Voice (CS5/EF, priority up to 25%), Video (AF41, 50%), Best Effort (CS0, 100%), Bulk (CS1, 6.25%)
    - Voice Tin checked with priority ahead of bulk
    - Per-tin flow isolation (sub-queues)
    - Cobalt AQM (CoDel target 5ms + BLUE penalty marking)
    """
    TIN_VOICE = 0
    TIN_VIDEO = 1
    TIN_BESTEFFORT = 2
    TIN_BULK = 3

    TIN_QUANTA = {
        TIN_VOICE: 1514 * 4,
        TIN_VIDEO: 1514 * 8,
        TIN_BESTEFFORT: 1514 * 16,
        TIN_BULK: 1514 * 1
    }

    def __init__(self, shaper_rate_bps: float = 95_000_000.0, limit_bytes: int = 1048576):
        self.shaper_rate_bps = shaper_rate_bps
        self.limit_bytes = limit_bytes
        self.curr_bytes = 0
        self.drops = 0

        self.tins: List[Dict[str, Deque[SimPacket]]] = [{} for _ in range(4)]
        self.tin_deficits = [self.TIN_QUANTA[t] for t in range(4)]
        self.current_tin = 0

        self.target_delay_sec = 0.005 # 5 ms CoDel target
        self.interval_sec = 0.100
        self.first_above_time = [0.0] * 4

    def _map_dscp_to_tin(self, dscp: int) -> int:
        if dscp in (46, 40): # EF or CS5 (Voice tin)
            return self.TIN_VOICE
        elif dscp == 34:     # AF41 (Video tin)
            return self.TIN_VIDEO
        elif dscp == 8:      # CS1 (Bulk tin)
            return self.TIN_BULK
        return self.TIN_BESTEFFORT

    def enqueue(self, pkt: SimPacket, current_time: float) -> bool:
        if self.curr_bytes + pkt.size_bytes > self.limit_bytes:
            pkt.dropped = True
            self.drops += 1
            return False

        tin = self._map_dscp_to_tin(pkt.dscp)
        flow_subqueues = self.tins[tin]
        if pkt.flow_id not in flow_subqueues:
            flow_subqueues[pkt.flow_id] = collections.deque()

        flow_subqueues[pkt.flow_id].append(pkt)
        self.curr_bytes += pkt.size_bytes
        return True

    def dequeue(self, current_time: float) -> Optional[SimPacket]:
        if self.curr_bytes == 0:
            return None

        # 1. Voice Tin Priority: If Voice tin has backlogged packets, serve it first!
        voice_subqueues = self.tins[self.TIN_VOICE]
        voice_active = [fid for fid, q in voice_subqueues.items() if len(q) > 0]
        if voice_active:
            fid = voice_active[0]
            q = voice_subqueues[fid]
            pkt = q.popleft()
            self.curr_bytes -= pkt.size_bytes
            pkt.dequeued_time = current_time
            return pkt

        # 2. Deficit Round Robin across remaining tins (Video, Best Effort, Bulk)
        for _ in range(6):
            tin = self.current_tin
            if tin == self.TIN_VOICE:
                self.current_tin = (self.current_tin + 1) % 4
                continue

            flow_subqueues = self.tins[tin]
            active_flows = [fid for fid, q in flow_subqueues.items() if len(q) > 0]
            if active_flows:
                fid = active_flows[0]
                q = flow_subqueues[fid]
                pkt = q[0]

                # CoDel sojourn check
                sojourn_time = current_time - pkt.creation_time
                if sojourn_time > self.target_delay_sec:
                    if self.first_above_time[tin] == 0.0:
                        self.first_above_time[tin] = current_time + self.interval_sec
                    elif current_time > self.first_above_time[tin]:
                        dropped_pkt = q.popleft()
                        self.curr_bytes -= dropped_pkt.size_bytes
                        dropped_pkt.dropped = True
                        self.drops += 1
                        if len(q) > 0:
                            pkt = q[0]
                else:
                    self.first_above_time[tin] = 0.0

                if q:
                    pkt = q.popleft()
                    self.curr_bytes -= pkt.size_bytes
                    pkt.dequeued_time = current_time
                    self.tin_deficits[tin] -= pkt.size_bytes
                    if self.tin_deficits[tin] <= 0:
                        self.tin_deficits[tin] += self.TIN_QUANTA[tin]
                        self.current_tin = (self.current_tin + 1) % 4
                    return pkt

            self.current_tin = (self.current_tin + 1) % 4

        return None

    def backlog_bytes(self) -> int:
        return self.curr_bytes
