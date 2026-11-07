#!/usr/bin/env bash
set -Eeuo pipefail

export LC_ALL=C
export LANG=C

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "ERROR: run as root (sudo)." >&2
    exit 2
fi

for cmd in ip python3; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: required command not found: $cmd" >&2
        exit 2
    }
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="${SCRIPT_DIR}/../../code/vpn-gatewayd-rc2.wip.py"
NS="vpng-exp002a-$$"

cleanup() {
    ip netns del "$NS" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

ip netns add "$NS"
ip -n "$NS" link set lo up

ip -n "$NS" link add empty0 type dummy
ip -n "$NS" link set empty0 up

ip -n "$NS" link add p2p0 type dummy
ip -n "$NS" link set p2p0 up
ip -n "$NS" addr add 172.20.140.1 peer 172.20.140.2/32 dev p2p0

ip netns exec "$NS" python3 - "$DAEMON" <<'PY'
from __future__ import annotations

import importlib.util
import sys
from ipaddress import IPv4Address
from pathlib import Path

module_path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("vpn_gatewayd_exp002a", module_path)
assert spec is not None and spec.loader is not None
vpng = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vpng
spec.loader.exec_module(vpng)

adapter = vpng.SubprocessKernelInterface()
snapshot = adapter.list_interface_ipv4()

expected_empty = frozenset()
expected_p2p = frozenset({IPv4Address("172.20.140.1")})

print("empty0 =", snapshot.get("empty0", "<missing>"))
print("p2p0   =", snapshot.get("p2p0", "<missing>"))

if snapshot.get("empty0") != expected_empty:
    raise SystemExit("FAIL: empty0 is missing or not an empty IPv4 set")
if snapshot.get("p2p0") != expected_p2p:
    raise SystemExit("FAIL: p2p0 local IPv4 set does not match")

print("EXP-002A OVERALL=PASS")
PY
