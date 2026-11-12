#!/bin/sh
set -eu

NS=vpng-exp016
SRC=192.0.2.1
NET=203.0.113.0/24
DST=203.0.113.77

cleanup() {
    ip netns del "$NS" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM
cleanup

HOST_BEFORE=$(sysctl -n net.ipv4.fib_multipath_hash_policy)

ip netns add "$NS"
ip -n "$NS" link set lo up
ip -n "$NS" link add ecmp0 type dummy
ip -n "$NS" link add ecmp1 type dummy
ip -n "$NS" link set ecmp0 up
ip -n "$NS" link set ecmp1 up
ip -n "$NS" addr add "$SRC/32" dev lo

ORIGINAL=$(ip netns exec "$NS" sysctl -n net.ipv4.fib_multipath_hash_policy)

ACCEPTED=""
for value in 0 1 2 3 4; do
    if ip netns exec "$NS" sysctl -q -w "net.ipv4.fib_multipath_hash_policy=$value"         >/dev/null 2>&1
    then
        ACCEPTED="$ACCEPTED $value"
    fi
done
echo "ACCEPTED_POLICIES:$ACCEPTED"

case " $ACCEPTED " in
    *" 1 "*) ;;
    *)
        echo "FAIL: policy 1 is not accepted by target kernel" >&2
        exit 1
        ;;
esac

ip netns exec "$NS" sysctl -q -w     "net.ipv4.fib_multipath_hash_policy=$ORIGINAL" >/dev/null

ip -n "$NS" route add "$NET"     nexthop dev ecmp0 weight 1     nexthop dev ecmp1 weight 1

route_dev() {
    policy=$1
    sport=$2
    dport=$3

    ip netns exec "$NS" sysctl -q -w         "net.ipv4.fib_multipath_hash_policy=$policy" >/dev/null

    output=$(ip netns exec "$NS" ip -4 route get "$DST" from "$SRC"         ipproto tcp sport "$sport" dport "$dport")

    echo "$output" | awk '
        {
            for (i = 1; i <= NF; i++) {
                if ($i == "dev") {
                    print $(i + 1)
                    exit
                }
            }
        }
    '
}

SAME=""
i=0
while [ "$i" -lt 8 ]; do
    dev=$(route_dev 1 40000 443)
    [ -n "$dev" ] || {
        echo "FAIL: could not determine route for repeated flow" >&2
        exit 1
    }
    if [ -z "$SAME" ]; then
        SAME=$dev
    elif [ "$dev" != "$SAME" ]; then
        echo "FAIL: same 5-tuple changed nexthop under policy 1" >&2
        exit 1
    fi
    i=$((i + 1))
done
echo "PASS A: policy 1 keeps repeated 5-tuple on $SAME"

POLICY0_DEVS=""
POLICY1_DEVS=""
port=40000
while [ "$port" -lt 40064 ]; do
    dev0=$(route_dev 0 "$port" 443)
    dev1=$(route_dev 1 "$port" 443)
    POLICY0_DEVS="$POLICY0_DEVS $dev0"
    POLICY1_DEVS="$POLICY1_DEVS $dev1"
    port=$((port + 1))
done

unique_count() {
    printf '%s\n' "$1" | tr ' ' '\n' | sed '/^$/d' | sort -u | wc -l
}

COUNT0=$(unique_count "$POLICY0_DEVS")
COUNT1=$(unique_count "$POLICY1_DEVS")

if [ "$COUNT0" -ne 1 ]; then
    echo "FAIL: policy 0 changed nexthop when only L4 source port changed" >&2
    echo "policy0:$POLICY0_DEVS" >&2
    exit 1
fi
echo "PASS B: policy 0 ignores L4-only variation for fixed L3 tuple"

if [ "$COUNT1" -lt 2 ]; then
    echo "FAIL: policy 1 did not distribute sampled L4 flows across both nexthops" >&2
    echo "policy1:$POLICY1_DEVS" >&2
    exit 1
fi
echo "PASS C: policy 1 uses L4 flow variation across both nexthops"

HOST_AFTER=$(sysctl -n net.ipv4.fib_multipath_hash_policy)
if [ "$HOST_AFTER" != "$HOST_BEFORE" ]; then
    echo "FAIL: namespace sysctl write changed host hash policy" >&2
    exit 1
fi
echo "PASS D: fib_multipath_hash_policy is namespace-isolated"

ip netns exec "$NS" sysctl -q -w     "net.ipv4.fib_multipath_hash_policy=$ORIGINAL" >/dev/null

echo "ORIGINAL_POLICY=$ORIGINAL"
echo "SELECTED_PRODUCTION_CANDIDATE=1"
echo "EXP_016_ECMP_HASH_POLICY=PASS"
