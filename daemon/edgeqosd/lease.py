#!/usr/bin/env python3
"""
daemon/edgeqosd/lease.py - Intent-Aware Dynamic Lease Actuator & CLI
Enables explicit user/application QoS intent grants (e.g. "Prioritize Work Call for 1 Hour").
Actuates in-kernel time-bounded nftables set elements (@lease_rt) with automatic kernel TTL expiry
and manual administrative rollback.
"""

import os
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime, timezone

PROFILES = {
    "work-call": {
        "dscp": "ef",
        "tin": "Tin 3 (Voice/Interactive)",
        "default_duration_sec": 3600,
        "description": "Expedited Forwarding for Zoom, Teams, Webex audio/video telepresence"
    },
    "cloud-gaming": {
        "dscp": "ef",
        "tin": "Tin 3 (Voice/Interactive)",
        "default_duration_sec": 7200,
        "description": "Ultra-low jitter prioritization for GeForce NOW, Xbox Cloud Gaming"
    },
    "streaming-pass": {
        "dscp": "af41",
        "tin": "Tin 2 (Video Streaming)",
        "default_duration_sec": 7200,
        "description": "Assured Forwarding for uninterrupted 4K HDR media playback"
    }
}

STATE_FILE = "/tmp/edgeqos_active_leases.json"

class IntentLeaseManager:
    def __init__(self, table: str = "inet edgeqos", set_name: str = "lease_rt", state_file: str = STATE_FILE):
        self.table = table
        self.set_name = set_name
        self.state_file = state_file

    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_state(self, state: dict):
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def grant_lease(self, ip: str, profile: str = "work-call", duration_sec: int = None, reason: str = "") -> dict:
        if profile not in PROFILES:
            raise ValueError(f"Unknown intent profile: {profile}. Valid options: {list(PROFILES.keys())}")

        prof_meta = PROFILES[profile]
        dur = duration_sec if duration_sec is not None and duration_sec > 0 else prof_meta["default_duration_sec"]
        now = time.time()
        expires_at = now + dur

        # 1. In-kernel nftables actuation
        nft_cmd = f"nft add element {self.table} {self.set_name} {{ {ip} timeout {dur}s }}"
        kernel_applied = False
        try:
            res = subprocess.run(nft_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            kernel_applied = (res.returncode == 0)
        except Exception:
            kernel_applied = False

        lease_record = {
            "ip": ip,
            "profile": profile,
            "dscp_target": prof_meta["dscp"],
            "tin": prof_meta["tin"],
            "duration_sec": dur,
            "granted_at": now,
            "granted_at_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "expires_at": expires_at,
            "expires_at_iso": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            "reason": reason or f"User intent: {profile}",
            "kernel_applied": kernel_applied,
            "status": "ACTIVE"
        }

        state = self._load_state()
        state[ip] = lease_record
        self._save_state(state)
        return lease_record

    def revoke_lease(self, ip: str) -> bool:
        state = self._load_state()
        if ip not in state:
            return False

        # 1. In-kernel deletion
        nft_cmd = f"nft delete element {self.table} {self.set_name} {{ {ip} }}"
        try:
            subprocess.run(nft_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        del state[ip]
        self._save_state(state)
        return True

    def list_leases(self) -> list:
        state = self._load_state()
        now = time.time()
        active = []
        changed = False

        for ip, record in list(state.items()):
            remaining = record["expires_at"] - now
            if remaining <= 0:
                # Expired by timeout
                del state[ip]
                changed = True
            else:
                record["remaining_sec"] = int(remaining)
                active.append(record)

        if changed:
            self._save_state(state)
        return active

def main():
    parser = argparse.ArgumentParser(description="EdgeQoS Intent Lease Controller")
    subparsers = parser.add_subparsers(dest="command")

    # grant
    p_grant = subparsers.add_parser("grant", help="Grant a temporary high-priority intent lease to an IP")
    p_grant.add_argument("--ip", required=True, help="Target LAN Client IPv4 address (e.g. 192.168.1.100)")
    p_grant.add_argument("--profile", default="work-call", choices=list(PROFILES.keys()), help="Intent Profile")
    p_grant.add_argument("--duration", type=int, default=None, help="Lease duration in seconds (defaults to profile preset)")
    p_grant.add_argument("--reason", default="", help="Human-readable reason for audit logging")

    # list
    subparsers.add_parser("list", help="List all currently active intent leases and remaining TTL")

    # revoke
    p_revoke = subparsers.add_parser("revoke", help="Immediately revoke an intent lease and roll back to Best Effort")
    p_revoke.add_argument("--ip", required=True, help="Target IP address to revoke")

    args = parser.parse_args()
    mgr = IntentLeaseManager()

    if args.command == "grant":
        res = mgr.grant_lease(args.ip, args.profile, args.duration, args.reason)
        print(f"[+] Intent Lease Granted Successfully:")
        print(f"    Target IP:     {res['ip']}")
        print(f"    Profile:       {res['profile']} -> {res['dscp_target'].upper()} ({res['tin']})")
        print(f"    Duration:      {res['duration_sec']} seconds ({res['duration_sec']/60:.1f} minutes)")
        print(f"    Expires At:    {res['expires_at_iso']}")
        print(f"    Reason:        {res['reason']}")
        print(f"    Kernel Hook:   {'nftables set @lease_rt updated' if res['kernel_applied'] else 'Recorded (Kernel mock/dry-run)'}")

    elif args.command == "list":
        active = mgr.list_leases()
        print(f"[*] Active EdgeQoS Intent Leases: {len(active)}")
        if not active:
            print("    No active user intent leases. All traffic managed under standard TinyML + CAKE policy.")
        else:
            for rec in active:
                print(f"    • IP: {rec['ip']:<15} | Profile: {rec['profile']:<14} | DSCP: {rec['dscp_target'].upper():<4} | Remaining: {rec['remaining_sec']:>5}s | Reason: {rec['reason']}")

    elif args.command == "revoke":
        ok = mgr.revoke_lease(args.ip)
        if ok:
            print(f"[+] Successfully revoked lease for {args.ip}. Flow rolled back to Best Effort (CS0).")
        else:
            print(f"[-] No active lease found for {args.ip}.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
