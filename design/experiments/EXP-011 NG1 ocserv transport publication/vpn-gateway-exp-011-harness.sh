#!/usr/bin/env bash
set -euo pipefail

SRC_CONF="${1:-/etc/ocserv/ocserv.conf}"

NS="vg-exp011"
HOST_IF="exp11h"
ROU_IF="host0"
HOST_ADDR="192.0.2.1"
ROU_ADDR="192.0.2.2"
PREFIX="30"
PORT="45443"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELAY="$SCRIPT_DIR/vpn-gateway-exp-011-oc-relay.py"

OUTDIR="vpn-gateway-exp-011-$(date -u +%Y%m%d-%H%M%SZ)"
mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"

TMP_CONF="$OUTDIR/ocserv-exp011.conf"
OCSERV_LOG="$OUTDIR/ocserv.log"
RELAY_LOG="$OUTDIR/relay.log"

relay_pid=""
ocserv_pid=""

cleanup() {
    set +e
    [[ -n "$relay_pid" ]] && kill "$relay_pid" 2>/dev/null
    [[ -n "$ocserv_pid" ]] && kill "$ocserv_pid" 2>/dev/null
    [[ -n "$relay_pid" ]] && wait "$relay_pid" 2>/dev/null
    [[ -n "$ocserv_pid" ]] && wait "$ocserv_pid" 2>/dev/null
    ip netns del "$NS" 2>/dev/null
    ip link del "$HOST_IF" 2>/dev/null
}
trap cleanup EXIT INT TERM

require() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "missing required command: $1" >&2
        exit 2
    }
}

require ip
require python3
require ocserv
require ss

if [[ "$(id -u)" -ne 0 ]]; then
    echo "EXP-011 requires root" >&2
    exit 2
fi

if [[ ! -r "$SRC_CONF" ]]; then
    echo "cannot read source config: $SRC_CONF" >&2
    exit 2
fi

if [[ ! -x "$RELAY" ]]; then
    chmod 700 "$RELAY"
fi

if ss -H -ltn "sport = :$PORT" | grep -q .; then
    echo "TCP $PORT is already in use in main namespace" >&2
    exit 2
fi
if ss -H -lun "sport = :$PORT" | grep -q .; then
    echo "UDP $PORT is already in use in main namespace" >&2
    exit 2
fi

if ip netns list | awk '{print $1}' | grep -Fxq "$NS"; then
    echo "refusing to reuse existing netns: $NS" >&2
    exit 2
fi
if ip link show "$HOST_IF" >/dev/null 2>&1; then
    echo "refusing to reuse existing interface: $HOST_IF" >&2
    exit 2
fi

python3 - "$SRC_CONF" "$TMP_CONF" "$ROU_ADDR" "$PORT" <<'PY'
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
listen = sys.argv[3]
port = sys.argv[4]

replacements = {
    "tcp-port": port,
    "udp-port": port,
    "listen-host": listen,
    "udp-listen-host": listen,
    "socket-file": "/run/ocserv-exp011.sock",
    "occtl-socket-file": "/run/occtl-exp011.sock",
    "pid-file": "/run/ocserv-exp011.pid",
}

seen = set()
out = []
for raw in src.read_text().splitlines():
    line = raw
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        out.append(line)
        continue

    m = re.match(r"^\s*([A-Za-z0-9_-]+)\s*=", line)
    if m and m.group(1) in replacements:
        key = m.group(1)
        if key in seen:
            out.append("# EXP-011 disabled duplicate: " + line)
        else:
            out.append(f"{key} = {replacements[key]}")
            seen.add(key)
    else:
        out.append(line)

for key, value in replacements.items():
    if key not in seen:
        out.append(f"{key} = {value}")

dst.write_text("\n".join(out) + "\n")
PY

ip netns add "$NS"
ip link add "$HOST_IF" type veth peer name "$ROU_IF"
ip link set "$ROU_IF" netns "$NS"

ip addr add "$HOST_ADDR/$PREFIX" dev "$HOST_IF"
ip link set "$HOST_IF" up

ip -n "$NS" link set lo up
ip -n "$NS" addr add "$ROU_ADDR/$PREFIX" dev "$ROU_IF"
ip -n "$NS" link set "$ROU_IF" up

ip netns exec "$NS" ocserv -f -c "$TMP_CONF" >"$OCSERV_LOG" 2>&1 &
ocserv_pid=$!

sleep 1
if ! kill -0 "$ocserv_pid" 2>/dev/null; then
    echo "temporary ocserv exited; log follows:" >&2
    cat "$OCSERV_LOG" >&2
    exit 1
fi

python3 "$RELAY"     --listen-address 0.0.0.0     --internal-source-address "$HOST_ADDR"     --target-address "$ROU_ADDR"     --port "$PORT"     >"$RELAY_LOG" 2>&1 &
relay_pid=$!

sleep 0.5
if ! kill -0 "$relay_pid" 2>/dev/null; then
    echo "relay exited; log follows:" >&2
    cat "$RELAY_LOG" >&2
    exit 1
fi

{
    echo "EXP-011 READY"
    echo
    echo "main namespace:"
    ip -br addr show "$HOST_IF"
    echo
    echo "ROU namespace:"
    ip -n "$NS" -br addr show
    echo
    echo "ROU listeners:"
    ip netns exec "$NS" ss -ltnup | grep ":$PORT" || true
    echo
    echo "published listeners:"
    ss -ltnup | grep ":$PORT" || true
    echo
    echo "temporary config: $TMP_CONF"
    echo "ocserv log:       $OCSERV_LOG"
    echo "relay log:        $RELAY_LOG"
    echo
    echo "Connect remote OpenConnect client to:"
    echo "    https://<this-host-name-or-ip>:$PORT/"
    echo
    echo "After the client reports TLS/CSTP and DTLS connected, inspect:"
    echo "    tail -n 100 '$RELAY_LOG'"
    echo "    tail -n 100 '$OCSERV_LOG'"
    echo "    ip -n '$NS' -br link"
    echo "    ip -n '$NS' -br addr"
    echo
    echo "Press Ctrl-C after collecting the result."
} | tee "$OUTDIR/ready.txt"

while kill -0 "$ocserv_pid" 2>/dev/null && kill -0 "$relay_pid" 2>/dev/null; do
    sleep 1
done

echo "ocserv or relay exited unexpectedly" >&2
exit 1
