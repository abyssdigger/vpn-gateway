#!/bin/sh
set -eu

A=vpng-wga
B=vpng-wgb
TMP=""

cleanup_netns() {
    ip netns del "$A" 2>/dev/null || true
    ip netns del "$B" 2>/dev/null || true
}

cleanup() {
    cleanup_netns
    if [ -n "$TMP" ]; then
        rm -rf "$TMP"
    fi
}
trap cleanup EXIT HUP INT TERM
cleanup_netns

umask 077
TMP=$(mktemp -d /run/vpng-exp019.XXXXXX)
wg genkey >"$TMP/a.key"
wg genkey >"$TMP/b.key"
wg pubkey <"$TMP/a.key" >"$TMP/a.pub"
wg pubkey <"$TMP/b.key" >"$TMP/b.pub"

ip netns add "$A"
ip netns add "$B"

ip link add a0 type veth peer name b0
ip link set a0 netns "$A"
ip link set b0 netns "$B"

ip -n "$A" link set lo up
ip -n "$B" link set lo up
ip -n "$A" addr add 192.0.2.1/30 dev a0
ip -n "$B" addr add 192.0.2.2/30 dev b0
ip -n "$A" link set a0 up
ip -n "$B" link set b0 up

ip -n "$A" link add wg0 type wireguard
ip -n "$B" link add wg0 type wireguard
ip -n "$A" addr add 10.23.0.1/30 dev wg0
ip -n "$B" addr add 10.23.0.2/30 dev wg0

A_PUB=$(cat "$TMP/a.pub")
B_PUB=$(cat "$TMP/b.pub")

ip netns exec "$A" test -r "$TMP/a.key" || {
    echo "FAIL: namespace A cannot read ephemeral private-key file" >&2
    exit 1
}
ip netns exec "$B" test -r "$TMP/b.key" || {
    echo "FAIL: namespace B cannot read ephemeral private-key file" >&2
    exit 1
}

ip netns exec "$A" wg set wg0     listen-port 51820     private-key "$TMP/a.key"     peer "$B_PUB"     allowed-ips 10.23.0.2/32     endpoint 192.0.2.2:51820     persistent-keepalive 1

ip netns exec "$B" wg set wg0     listen-port 51820     private-key "$TMP/b.key"     peer "$A_PUB"     allowed-ips 10.23.0.1/32     endpoint 192.0.2.1:51820     persistent-keepalive 1

ip -n "$A" link set wg0 up
ip -n "$B" link set wg0 up

ip netns exec "$A" ping -I wg0 -c 2 -W 2 10.23.0.2 >/dev/null

A_IFINDEX_BEFORE=$(ip -n "$A" -j link show dev wg0 |
    python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["ifindex"])')
HS_BEFORE=$(ip netns exec "$A" wg show wg0 latest-handshakes |
    awk 'NR==1 {print $2}')

case "$HS_BEFORE" in
    ''|0)
        echo "FAIL: no successful WireGuard handshake after proven tunnel ping" >&2
        exit 1
        ;;
esac

echo "PASS A: WireGuard tunnel established ifindex=$A_IFINDEX_BEFORE handshake=$HS_BEFORE"

ip -n "$B" link set b0 down

A_IFINDEX_DOWN=$(ip -n "$A" -j link show dev wg0 |
    python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["ifindex"])')
if [ "$A_IFINDEX_DOWN" != "$A_IFINDEX_BEFORE" ]; then
    echo "FAIL: wg0 generation changed when only underlay failed" >&2
    exit 1
fi

if ip netns exec "$A" ping -I wg0 -c 1 -W 1 10.23.0.2 >/dev/null 2>&1; then
    echo "FAIL: tunnel probe succeeded with remote underlay down" >&2
    exit 1
fi

HS_DOWN=$(ip netns exec "$A" wg show wg0 latest-handshakes |
    awk 'NR==1 {print $2}')

echo "PASS B: wg0 remains same generation while active tunnel probe fails"
echo "HANDSHAKE_BEFORE=$HS_BEFORE"
echo "HANDSHAKE_DURING_OUTAGE=$HS_DOWN"

sleep 2
ip -n "$B" link set b0 up
sleep 1

ip netns exec "$A" ping -I wg0 -c 2 -W 2 10.23.0.2 >/dev/null

A_IFINDEX_AFTER=$(ip -n "$A" -j link show dev wg0 |
    python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["ifindex"])')
if [ "$A_IFINDEX_AFTER" != "$A_IFINDEX_BEFORE" ]; then
    echo "FAIL: wg0 generation changed across underlay recovery" >&2
    exit 1
fi

HS_AFTER=$(ip netns exec "$A" wg show wg0 latest-handshakes |
    awk 'NR==1 {print $2}')

echo "PASS C: active tunnel probe recovered on the same wg0 generation"
echo "HANDSHAKE_AFTER_RECOVERY=$HS_AFTER"

if [ "$HS_DOWN" = "$HS_BEFORE" ]; then
    echo "OBSERVATION: outage did not create a new successful handshake"
fi
if [ "$HS_AFTER" = "$HS_BEFORE" ]; then
    echo "OBSERVATION: recovered data path did not require a new successful handshake"
fi

echo "EXP_019_WIREGUARD_AVAILABILITY_EVIDENCE=PASS"
