"""
daemon/edgeqosd/config.py - EdgeQoS System Configuration Dataclasses
Holds all tunable parameters, budgets, periods, and hysteresis thresholds.
"""

from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class GuardConfig:
    f_poll_hz: float = 4.0               # 4 Hz polling rate
    m_consecutive: int = 4              # 4 consecutive samples over budget -> demote
    budget_bps: Dict[str, float] = field(default_factory=lambda: {
        "Realtime": 5_000_000.0,         # 5.0 Mbps ceiling for Voice / Realtime tin
        "Stream": 15_000_000.0,          # 15.0 Mbps ceiling for Video Stream tin
        "Bulk": 100_000_000.0,
        "Other": 25_000_000.0
    })

@dataclass
class CapacityConfig:
    dt_sec: float = 0.20                 # 200 ms control period
    int_hot_set_ms: float = 15.0         # Set int_hot if internal CAKE delay >= 15 ms
    int_hot_clear_ms: float = 5.0        # Clear int_hot if internal CAKE delay <= 5 ms
    ext_hot_set_ms: float = 25.0         # Set ext_hot if external RTT delta >= 25 ms
    ext_hot_clear_ms: float = 10.0       # Clear ext_hot if external RTT delta <= 10 ms
    K_confirm: int = 3                   # K consecutive hot periods before step-down
    hold_off_sec: float = 1.0            # Hold-off time between downward steps
    t_cool_sec: float = 5.0              # Cool-down time before upward probing allowed
    beta_down: float = 0.90              # Fast step-down factor for download (0.90 * R_delivered)
    gamma_up: float = 0.85               # Multiplicative step-down factor for upload
    alpha_bps_per_s: float = 1_000_000.0 # Additive recovery: 1.0 Mbps per second
    floor_bps: float = 5_000_000.0       # Absolute minimum shaper bandwidth floor (5 Mbps)
    c_max_bps: float = 100_000_000.0     # Maximum link ceiling (100 Mbps)
    load_min_ratio: float = 0.40         # Link considered loaded if offered >= 40% current rate

@dataclass
class ProbeConfig:
    reflectors: List[str] = field(default_factory=lambda: ["10.0.1.2", "10.0.1.3", "10.0.1.4"])
    rate_idle_hz: float = 1.0            # 1 Hz per reflector when link idle
    rate_loaded_hz: float = 5.0          # 5 Hz per reflector when link loaded

@dataclass
class EdgeQoSConfig:
    guard: GuardConfig = field(default_factory=GuardConfig)
    capacity: CapacityConfig = field(default_factory=CapacityConfig)
    probe: ProbeConfig = field(default_factory=ProbeConfig)
    wan_if: str = "eth0"
    lan_if: str = "eth1"
    heartbeat_path: str = "/run/edgeqos.heartbeat"
    safe_rate_mbit: int = 20             # Safe fallback bandwidth applied by watchdog
