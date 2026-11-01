#!/usr/bin/env python3
"""
scripts/intent_ctl.py - User-Facing CLI for EdgeQoS Intent Leases
Convenience wrapper for granting, checking, and revoking temporary QoS passes.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from daemon.edgeqosd.lease import main

if __name__ == "__main__":
    main()
