#!/usr/bin/env bash
set -euo pipefail

# EXP-010 — NG1 ROU transport publication through a network namespace.
#
# This script does not require WireGuard. It proves the generic transport chain:
#
#   host client
#     -> published UDP socket
#     -> host-side ROU relay
#     -> veth
#     -> listener in ROU netns
#     -> dependent payload emitted back through veth
#     -> host sink
#
# The listener also returns ACK:<input> through the relay to the original client.

NS="vg-exp010"
HOST_IF="exp10h"
ROU_IF="host0"
HOST_ADDR="192.0.2.1"
ROU_ADDR="192.0.2.2"
PREFIX="30"

PUBLISH_ADDR="127.0.0.1"
PUBLISH_PORT="15678"
INTERNAL_PORT="17890"
SINK_PORT="19900"
MESSAGE="exp010-$(date +%s)-$$"

OUTDIR="vpn-gateway-exp-010-$(date -u +%Y%m%d-%H%M%SZ)"
mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"

HELPER="$OUTDIR/exp010_helper.py"
RESULT="$OUTDIR/result.txt"

relay_pid=""
sink_pid=""
internal_pid=""

cleanup() {
    set +e
    [[ -n "$relay_pid" ]] && kill "$relay_pid" 2>/dev/null
    [[ -n "$sink_pid" ]] && kill "$sink_pid" 2>/dev/null
    [[ -n "$internal_pid" ]] && kill "$internal_pid" 2>/dev/null
    wait "$relay_pid" "$sink_pid" "$internal_pid" 2>/dev/null
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

if [[ "$(id -u)" -ne 0 ]]; then
    echo "EXP-010 requires root for network namespace/veth creation" >&2
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

cat >"$HELPER" <<'PY'
#!/usr/bin/env python3
import argparse
import socket
import sys
import time


def udp_socket(bind=None, timeout=5.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    if bind is not None:
        s.bind(bind)
    return s


def mode_sink(args):
    s = udp_socket((args.bind, args.port), args.timeout)
    data, peer = s.recvfrom(65535)
    text = data.decode("utf-8", "strict")
    print(f"SINK peer={peer[0]}:{peer[1]} payload={text}", flush=True)
    expected = "PAYLOAD:" + args.message
    if text != expected:
        print(f"SINK_FAIL expected={expected!r} actual={text!r}", file=sys.stderr)
        return 1
    print("SINK_PASS", flush=True)
    return 0


def mode_internal(args):
    listener = udp_socket((args.bind, args.port), args.timeout)
    data, peer = listener.recvfrom(65535)
    text = data.decode("utf-8", "strict")
    print(f"INTERNAL_RX peer={peer[0]}:{peer[1]} payload={text}", flush=True)
    if text != args.message:
        print(f"INTERNAL_FAIL expected={args.message!r} actual={text!r}", file=sys.stderr)
        return 1

    out = udp_socket(timeout=args.timeout)
    generated = ("PAYLOAD:" + text).encode()
    out.sendto(generated, (args.sink_addr, args.sink_port))
    out.close()
    print(f"INTERNAL_TX sink={args.sink_addr}:{args.sink_port} payload={generated.decode()}", flush=True)

    reply = ("ACK:" + text).encode()
    listener.sendto(reply, peer)
    print(f"INTERNAL_ACK peer={peer[0]}:{peer[1]} payload={reply.decode()}", flush=True)
    print("INTERNAL_PASS", flush=True)
    return 0


def mode_relay(args):
    external = udp_socket((args.publish_addr, args.publish_port), args.timeout)
    internal = udp_socket((args.internal_bind, 0), args.timeout)

    data, client = external.recvfrom(65535)
    text = data.decode("utf-8", "strict")
    print(f"RELAY_RX client={client[0]}:{client[1]} payload={text}", flush=True)

    internal.sendto(data, (args.internal_addr, args.internal_port))
    print(
        f"RELAY_FWD target={args.internal_addr}:{args.internal_port} "
        f"source={internal.getsockname()[0]}:{internal.getsockname()[1]}",
        flush=True,
    )

    reply, peer = internal.recvfrom(65535)
    reply_text = reply.decode("utf-8", "strict")
    print(f"RELAY_RETURN peer={peer[0]}:{peer[1]} payload={reply_text}", flush=True)

    external.sendto(reply, client)
    print(f"RELAY_TX client={client[0]}:{client[1]} payload={reply_text}", flush=True)
    print("RELAY_PASS", flush=True)
    return 0


def mode_client(args):
    s = udp_socket(timeout=args.timeout)
    payload = args.message.encode()
    s.sendto(payload, (args.publish_addr, args.publish_port))
    print(
        f"CLIENT_TX target={args.publish_addr}:{args.publish_port} payload={args.message}",
        flush=True,
    )
    reply, peer = s.recvfrom(65535)
    text = reply.decode("utf-8", "strict")
    print(f"CLIENT_RX peer={peer[0]}:{peer[1]} payload={text}", flush=True)
    expected = "ACK:" + args.message
    if text != expected:
        print(f"CLIENT_FAIL expected={expected!r} actual={text!r}", file=sys.stderr)
        return 1
    print("CLIENT_PASS", flush=True)
    return 0


def parser():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("sink", "internal", "relay", "client"))
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument("--message", required=True)

    p.add_argument("--bind")
    p.add_argument("--port", type=int)
    p.add_argument("--sink-addr")
    p.add_argument("--sink-port", type=int)

    p.add_argument("--publish-addr")
    p.add_argument("--publish-port", type=int)
    p.add_argument("--internal-bind")
    p.add_argument("--internal-addr")
    p.add_argument("--internal-port", type=int)
    return p


def main():
    args = parser().parse_args()
    fn = {
        "sink": mode_sink,
        "internal": mode_internal,
        "relay": mode_relay,
        "client": mode_client,
    }[args.mode]
    return fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
PY
chmod 700 "$HELPER"

{
    echo "EXP-010 NG1 ROU transport publication namespace relay"
    echo "timestamp=$(date -u +%FT%TZ)"
    echo "kernel=$(uname -srmo)"
    echo "ip=$(ip -Version 2>&1)"
    echo "python=$(python3 --version 2>&1)"
    echo "message=$MESSAGE"
    echo
} >"$OUTDIR/environment.txt"

# Namespace topology.
ip netns add "$NS"
ip link add "$HOST_IF" type veth peer name "$ROU_IF"
ip link set "$ROU_IF" netns "$NS"

ip addr add "$HOST_ADDR/$PREFIX" dev "$HOST_IF"
ip link set "$HOST_IF" up

ip -n "$NS" link set lo up
ip -n "$NS" addr add "$ROU_ADDR/$PREFIX" dev "$ROU_IF"
ip -n "$NS" link set "$ROU_IF" up

ip -br addr show "$HOST_IF" >"$OUTDIR/main-link.txt"
ip -n "$NS" -br addr show >"$OUTDIR/netns-links.txt"
ip -n "$NS" route show table all >"$OUTDIR/netns-routes.txt"

# Host-visible sink for the packet generated by the namespace listener.
python3 "$HELPER" sink     --message "$MESSAGE"     --bind "$HOST_ADDR"     --port "$SINK_PORT"     >"$OUTDIR/sink.log" 2>&1 &
sink_pid=$!

# Internal transport listener inside ROU namespace.
ip netns exec "$NS" python3 "$HELPER" internal     --message "$MESSAGE"     --bind "$ROU_ADDR"     --port "$INTERNAL_PORT"     --sink-addr "$HOST_ADDR"     --sink-port "$SINK_PORT"     >"$OUTDIR/internal.log" 2>&1 &
internal_pid=$!

# ROU host-side publication relay.
python3 "$HELPER" relay     --message "$MESSAGE"     --publish-addr "$PUBLISH_ADDR"     --publish-port "$PUBLISH_PORT"     --internal-bind "$HOST_ADDR"     --internal-addr "$ROU_ADDR"     --internal-port "$INTERNAL_PORT"     >"$OUTDIR/relay.log" 2>&1 &
relay_pid=$!

sleep 0.2

set +e
python3 "$HELPER" client     --message "$MESSAGE"     --publish-addr "$PUBLISH_ADDR"     --publish-port "$PUBLISH_PORT"     >"$OUTDIR/client.log" 2>&1
client_rc=$?

wait "$internal_pid"
internal_rc=$?
internal_pid=""

wait "$sink_pid"
sink_rc=$?
sink_pid=""

wait "$relay_pid"
relay_rc=$?
relay_pid=""
set -e

h1=FAIL
h2=FAIL
h3=FAIL

grep -Fxq "INTERNAL_PASS" "$OUTDIR/internal.log" && h1=PASS
grep -Fxq "SINK_PASS" "$OUTDIR/sink.log" && h2=PASS
grep -Fxq "CLIENT_PASS" "$OUTDIR/client.log" && grep -Fxq "RELAY_PASS" "$OUTDIR/relay.log" && h3=PASS

overall=FAIL
if [[ "$client_rc" -eq 0 && "$internal_rc" -eq 0 && "$sink_rc" -eq 0 && "$relay_rc" -eq 0       && "$h1" == PASS && "$h2" == PASS && "$h3" == PASS ]]; then
    overall=PASS
fi

{
    echo "EXP-010 NG1 ROU transport publication namespace relay"
    echo "H1 published socket -> relay -> netns listener: $h1"
    echo "H2 netns listener -> dependent host-visible payload: $h2"
    echo "H3 netns listener -> relay -> original client response: $h3"
    echo
    echo "OVERALL=$overall"
} | tee "$RESULT"

[[ "$overall" == PASS ]]
