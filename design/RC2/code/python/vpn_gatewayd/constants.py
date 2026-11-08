from __future__ import annotations

import logging
from pathlib import Path



# ---------------------------------------------------------------------------
# Architecture: RC2.4.1
# Implementation: RC2.5.1
# ---------------------------------------------------------------------------

VERSION = "RC2.5.1"

DEFAULT_CONFIG_PATH = Path("/etc/vpn-gateway/vpn-gateway.toml")
DEFAULT_LOCK_PATH = Path("/run/vpn-gateway/vpn-gatewayd.lock")

DEFAULT_RECONCILE_INTERVAL = 10.0
MIN_RECONCILE_INTERVAL = 1.0
MAX_RECONCILE_INTERVAL = 60.0
DEFAULT_FAILURE_REMINDER_INTERVAL = 300.0

BLACKHOLE_ROUTE_PROTO = 201
KERNEL_ROUTE_PROTO = 2
VPN_ROUTE_PROTO = 202
BLACKHOLE_METRIC = 65536
PEER_METRIC_STEP = 10
MAX_ROUTE_METRIC = (1 << 32) - 1

VPNG_CHAIN_PREFIX = "VPNG-"
IP_FORWARD_PATH = Path("/proc/sys/net/ipv4/ip_forward")

LOG = logging.getLogger("vpn-gatewayd")
