"""
daemon/edgeqosd/promote.py - nftables Dynamic Set Actuator
Executes atomic set mutations (add/delete element with hardware TTL).
"""

import subprocess
import os

CLASS_TO_SET = {
    "Realtime": "promo_rt",
    "Stream": "promo_vid",
    "Bulk": "promo_blk"
}

def format_5tuple(proto_str: str, saddr: str, daddr: str, sport: int, dport: int) -> str:
    # Concatenated format: ip saddr . ip daddr . meta l4proto . th sport . th dport
    return f"{saddr} . {daddr} . {proto_str} . {sport} . {dport}"

class NftablesActuator:
    def __init__(self, table: str = "inet edgeqos", timeout_sec: int = 60, dry_run: bool = False):
        self.table = table
        self.timeout_sec = timeout_sec
        self.dry_run = dry_run

    def promote_flow(self, proto: int, saddr: str, daddr: str, sport: int, dport: int, assigned_class: str) -> bool:
        set_name = CLASS_TO_SET.get(assigned_class)
        if not set_name:
            return False

        proto_str = "tcp" if proto == 6 else "udp"
        # Insert both forward and reverse directions
        fwd = format_5tuple(proto_str, saddr, daddr, sport, dport)
        rev = format_5tuple(proto_str, daddr, saddr, dport, sport)

        cmd = (
            f"nft -f - <<EOF\n"
            f"add element {self.table} {set_name} {{ {fwd} timeout {self.timeout_sec}s }}\n"
            f"add element {self.table} {set_name} {{ {rev} timeout {self.timeout_sec}s }}\n"
            f"EOF\n"
        )
        if self.dry_run:
            return True
        try:
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def demote_flow(self, proto: int, saddr: str, daddr: str, sport: int, dport: int, previous_class: str) -> bool:
        set_name = CLASS_TO_SET.get(previous_class)
        if not set_name:
            return False

        proto_str = "tcp" if proto == 6 else "udp"
        fwd = format_5tuple(proto_str, saddr, daddr, sport, dport)
        rev = format_5tuple(proto_str, daddr, saddr, dport, sport)

        cmd = (
            f"nft -f - <<EOF\n"
            f"delete element {self.table} {set_name} {{ {fwd} }}\n"
            f"delete element {self.table} {set_name} {{ {rev} }}\n"
            f"EOF\n"
        )
        if self.dry_run:
            return True
        try:
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
