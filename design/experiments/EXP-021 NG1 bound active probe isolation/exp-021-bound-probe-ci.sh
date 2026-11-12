#!/bin/sh
set -eu

R=vpng-exp021-r
A=vpng-exp021-a
B=vpng-exp021-b

cleanup() {
    ip netns del "$R" 2>/dev/null || true
    ip netns del "$A" 2>/dev/null || true
    ip netns del "$B" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM
cleanup

for cmd in ip ping setpriv; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "FAIL: required command missing: $cmd" >&2
        exit 1
    }
done

ip netns add "$R"
ip netns add "$A"
ip netns add "$B"

ip link add rA type veth peer name aR
ip link add rB type veth peer name bR
ip link set rA netns "$R"
ip link set aR netns "$A"
ip link set rB netns "$R"
ip link set bR netns "$B"

ip -n "$R" addr add 192.0.2.1/30 dev rA
ip -n "$A" addr add 192.0.2.2/30 dev aR
ip -n "$R" addr add 192.0.2.5/30 dev rB
ip -n "$B" addr add 192.0.2.6/30 dev bR

for ns_if in "$R lo" "$R rA" "$R rB" "$A lo" "$A aR" "$B lo" "$B bR"; do
    set -- $ns_if
    ip -n "$1" link set "$2" up
done

ip -n "$A" addr add 198.18.21.1/32 dev lo
ip -n "$B" addr add 198.18.21.1/32 dev lo

ip -n "$R" route add 198.18.21.1/32 via 192.0.2.2 dev rA metric 10
ip -n "$R" route add 198.18.21.1/32 via 192.0.2.6 dev rB metric 20

ip netns exec "$R" ping -c 1 -W 1 198.18.21.1 >/dev/null
ip netns exec "$R" ping -I rB -c 1 -W 1 198.18.21.1 >/dev/null
echo "PASS A: ordinary and B-bound probes succeed while both paths are healthy"

ip -n "$B" link set bR down

ip netns exec "$R" ping -c 1 -W 1 198.18.21.1 >/dev/null
if ip netns exec "$R" ping -I rB -c 1 -W 1 198.18.21.1 >/dev/null 2>&1; then
    echo "FAIL: B-bound probe borrowed the healthy A path" >&2
    exit 1
fi
echo "PASS B: bound probe fails on broken B while unbound probe still succeeds via A"

ip -n "$B" link set bR up
ip netns exec "$R" ping -I rB -c 1 -W 1 198.18.21.1 >/dev/null

PING_GROUP_RANGE=$(ip netns exec "$R" sysctl -n net.ipv4.ping_group_range)
echo "PING_GROUP_RANGE=$PING_GROUP_RANGE"

if ip netns exec "$R" setpriv     --no-new-privs     --bounding-set=-net_raw     --inh-caps=-all     --ambient-caps=-all     ping -I rB -c 1 -W 1 198.18.21.1 >/dev/null 2>&1; then
    echo "REDUCED_PRIVILEGE_BOUND_PING=PASS"
else
    echo "REDUCED_PRIVILEGE_BOUND_PING=FAIL"
fi

echo "EXP_021_BOUND_PROBE_ISOLATION=PASS"
