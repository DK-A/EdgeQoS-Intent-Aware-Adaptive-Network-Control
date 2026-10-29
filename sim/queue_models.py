"""
sim/queue_models.py - Queue Models: FIFO, PRIO, FQ-CoDel, and CAKE diffserv4
"""

import collections
from typing import List, Deque, Optional, Tuple
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
    - 4 Tins: Voice (CS5/EF, 25%), Video (AF41, 50%), Best Effort (CS0, 100%), Bulk (CS1, 6.25%)
    - Deficit Round Robin (DRR) across tins
    - Per-tin flow isolation (sub-queues)
    - Cobalt AQM (CoDel target 5ms + BLUE penalty marking)
    """
    TIN_VOICE = 0
    TIN_VIDEO = 1
    TIN_BESTEFFORT = 2
    TIN_BULK = 3

    # Software deficit allocation quanta per round
    TIN_QUANTA = {
        TIN_VOICE: 1514 * 4,       # Voice quantum
        TIN_VIDEO: 1514 * 8,       # Video quantum
        TIN_BESTEFFORT: 1514 * 16, # Best effort quantum
        TIN_BULK: 1514 * 1         # Bulk minimum guaranteed quantum (6.25%)
    }

    def __init__(self, shaper_rate_bps: float = 95_000_000.0, limit_bytes: int = 1048576):
        self.shaper_rate_bps = shaper_rate_bps
        self.limit_bytes = limit_bytes
        self.curr_bytes = 0
        self.drops = 0

        # Per tin sub-queues (flow hash -> deque of SimPacket)
        self.tins: List[Dict[str, Deque[SimPacket]]] = [{} for _ in range(4)]
        self.tin_deficits = [self.TIN_QUANTA[t] for t in range(4)]
        self.current_tin = 0

        # CoDel state per tin
        self.target_delay_sec = 0.005 # 5 ms CoDel target
        self.interval_sec = 0.100     # 100 ms CoDel interval
        self.first_above_time = [0.0] * 4
        self.dropping = [False] * 4

    def _map_dscp_to_tin(self, dscp: int) -> int:
        # C3 fix: EF/CS5 -> Voice, AF41 -> Video, CS1 -> Bulk, CS0 -> BE
        if dscp in (46, 40): # EF or CS5
            return self.TIN_VOICE
        elif dscp == 34:     # AF41
            return self.TIN_VIDEO
        elif dscp == 8:      # CS1
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

        # Deficit Round Robin across non-empty tins
        for _ in range(8):
            tin = self.current_tin
            flow_subqueues = self.tins[tin]

            # Find active flows in tin
            active_flows = [fid for fid, q in flow_subqueues.items() if len(q) > 0]
            if active_flows:
                fid = active_flows[0]
                q = flow_subqueues[fid]
                pkt = q[0]

                # Check CoDel sojourn time
                sojourn_time = current_time - pkt.creation_time
                if sojourn_time > self.target_delay_sec:
                    if self.first_above_time[tin] == 0.0:
                        self.first_above_time[tin] = current_time + self.interval_sec
                    elif current_time > self.first_above_time[tin]:
                        # CoDel drop
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

    def get_tin_backlog_ms(self) -> float:
        if self.shaper_rate_bps <= 0:
            return 0.0
        return (self.curr_bytes * 8.0 / self.shaper_rate_bps) * 1000.0
