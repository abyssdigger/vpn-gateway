#!/bin/sh
set -eu

ROU=vg-exp021-rou
PRI=vg-exp021-pri
ALT=vg-exp021-alt

VPN_IF=vpn0
PRI_IF=pri0
ALT_IF=alt0
ALT_PEER_IF=altp0

ROU_PRI_ADDR=198.18.21.2/30
PRI_ADDR=198.18.21.1/30
ROU_ALT_ADDR=198.18.22.2/30
ALT_ADDR=198.18.22.1/30

TARGET=203.0.113.21
OTHER_TARGET=203.0.113.22
TEST_PORT=2121
PROBE_UID=65534
PROBE_GID=65534
NFT_TABLE=vpng_exp21

SERVER_PID=

cleanup() {
    set +e
    if [ -n "${SERVER_PID:-}" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    ip netns del "$ALT" >/dev/null 2>&1 || true
    ip netns del "$PRI" >/dev/null 2>&1 || true
    ip netns del "$ROU" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

for cmd in ip nft ping python3 setpriv grep awk; do
    command -v "$cmd" >/dev/null 2>&1 || fail "missing command $cmd"
done

[ "$(id -u)" -eq 0 ] || fail "EXP-021 requires root"

cleanup
trap cleanup EXIT HUP INT TERM

echo "STAGE 1: create disposable namespaces"
ip netns add "$ROU"
ip netns add "$PRI"
ip netns add "$ALT"
ip -n "$ROU" link set lo up
ip -n "$PRI" link set lo up
ip -n "$ALT" link set lo up

create_primary() {
    forced_index=${1:-}

    if [ -n "$forced_index" ]; then
        ip -n "$ROU" link add name "$VPN_IF" index "$forced_index" \
            type veth peer name "$PRI_IF" netns "$PRI"
    else
        ip -n "$ROU" link add name "$VPN_IF" \
            type veth peer name "$PRI_IF" netns "$PRI"
    fi

    ip -n "$ROU" addr add "$ROU_PRI_ADDR" dev "$VPN_IF"
    ip -n "$PRI" addr add "$PRI_ADDR" dev "$PRI_IF"
    ip -n "$PRI" addr add "$TARGET/32" dev "$PRI_IF"
    ip -n "$PRI" addr add "$OTHER_TARGET/32" dev "$PRI_IF"
    ip -n "$ROU" link set "$VPN_IF" up
    ip -n "$PRI" link set "$PRI_IF" up
    ip -n "$ROU" route replace "$TARGET/32" dev "$VPN_IF"
    ip -n "$ROU" route replace "$OTHER_TARGET/32" dev "$VPN_IF"
}

create_primary

ip -n "$ROU" link add name "$ALT_IF" type veth peer name "$ALT_PEER_IF" netns "$ALT"
ip -n "$ROU" addr add "$ROU_ALT_ADDR" dev "$ALT_IF"
ip -n "$ALT" addr add "$ALT_ADDR" dev "$ALT_PEER_IF"
ip -n "$ALT" addr add "$TARGET/32" dev "$ALT_PEER_IF"
ip -n "$ROU" link set "$ALT_IF" up
ip -n "$ALT" link set "$ALT_PEER_IF" up
ip -n "$ROU" route replace default dev "$ALT_IF" metric 100

echo "STAGE 2: prove both disposable paths before firewall policy"
ip netns exec "$ROU" ping -n -c 1 -W 1 -I "$VPN_IF" "$TARGET" >/dev/null ||
    fail "primary disposable path is not reachable"
ip netns exec "$ROU" ping -n -c 1 -W 1 -I "$ALT_IF" "$TARGET" >/dev/null ||
    fail "alternate disposable path is not reachable"
echo "PASS A: primary and alternate paths both reach the same target"

echo "STAGE 3: configure unprivileged ping-socket admission inside ROU namespace"
ip netns exec "$ROU" sh -c \
    "printf '%s %s\n' '$PROBE_GID' '$PROBE_GID' > /proc/sys/net/ipv4/ping_group_range"
PING_RANGE=$(ip netns exec "$ROU" cat /proc/sys/net/ipv4/ping_group_range)
set -- $PING_RANGE
[ "$#" -eq 2 ] ||
    fail "unexpected ping_group_range field count: $PING_RANGE"
[ "$1" = "$PROBE_GID" ] && [ "$2" = "$PROBE_GID" ] ||
    fail "unexpected ping_group_range: $PING_RANGE"

probe() {
    ip netns exec "$ROU" setpriv \
        --reuid "$PROBE_UID" \
        --regid "$PROBE_GID" \
        --clear-groups \
        --bounding-set=-all \
        --inh-caps=-all \
        --ambient-caps=-all \
        --no-new-privs \
        ping -n -c 1 -W 1 -I "$VPN_IF" "$TARGET"
}

probe_other_target() {
    ip netns exec "$ROU" setpriv \
        --reuid "$PROBE_UID" \
        --regid "$PROBE_GID" \
        --clear-groups \
        --bounding-set=-all \
        --inh-caps=-all \
        --ambient-caps=-all \
        --no-new-privs \
        ping -n -c 1 -W 1 -I "$VPN_IF" "$OTHER_TARGET"
}

show_probe_caps() {
    ip netns exec "$ROU" setpriv \
        --reuid "$PROBE_UID" \
        --regid "$PROBE_GID" \
        --clear-groups \
        --bounding-set=-all \
        --inh-caps=-all \
        --ambient-caps=-all \
        --no-new-privs \
        sh -c "grep -E '^(CapInh|CapPrm|CapEff|CapBnd|CapAmb|NoNewPrivs):' /proc/self/status"
}

install_base_policy() {
    ip netns exec "$ROU" nft delete table ip "$NFT_TABLE" >/dev/null 2>&1 || true
    ip netns exec "$ROU" nft -f - <<EOF
table ip $NFT_TABLE {
    chain input {
        type filter hook input priority filter; policy drop;
    }
    chain output {
        type filter hook output priority filter; policy drop;
    }
}
EOF
}

install_probe_policy() {
    idx=$1
    ip netns exec "$ROU" nft delete table ip "$NFT_TABLE" >/dev/null 2>&1 || true
    ip netns exec "$ROU" nft -f - <<EOF
table ip $NFT_TABLE {
    chain input {
        type filter hook input priority filter; policy drop;
        meta iif $idx ip saddr $TARGET icmp type echo-reply counter accept comment "vpng-exp21:iif:$idx"
    }
    chain output {
        type filter hook output priority filter; policy drop;
        meta oif $idx ip daddr $TARGET icmp type echo-request counter accept comment "vpng-exp21:oif:$idx"
    }
}
EOF
}

verify_probe_policy() {
    idx=$1
    json=$(ip netns exec "$ROU" nft -j -n list table ip "$NFT_TABLE")
    printf '%s\n' "$json" | python3 -c '
import json
import sys

idx = int(sys.argv[1])
doc = json.load(sys.stdin)
expected = {f"vpng-exp21:iif:{idx}", f"vpng-exp21:oif:{idx}"}
seen = {
    item["rule"].get("comment")
    for item in doc.get("nftables", [])
    if isinstance(item, dict)
    and isinstance(item.get("rule"), dict)
    and isinstance(item["rule"].get("comment"), str)
}
missing = expected - seen
if missing:
    raise SystemExit("missing probe policy markers: " + ", ".join(sorted(missing)))
' "$idx"
}

echo "STAGE 4: prove detector is not armed under base default-DROP"
install_base_policy
if probe >/dev/null 2>&1; then
    fail "probe succeeded before probe policy was installed"
fi
echo "PASS B: default-DROP prevents evidence before probe admission exists"

echo "STAGE 5: install and verify narrow generation-scoped probe admission"
OLD_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$VPN_IF/ifindex")
install_probe_policy "$OLD_INDEX"
verify_probe_policy "$OLD_INDEX"
echo "PROBE_POLICY_VERIFIED_IFINDEX=$OLD_INDEX"
echo "PROBE_PROCESS_CAPABILITIES_BEGIN"
show_probe_caps
echo "PROBE_PROCESS_CAPABILITIES_END"

if ! probe >/dev/null 2>&1; then
    fail "unprivileged zero-capability ICMP probe failed after verified admission"
fi
echo "PASS C: ICMP echo succeeds with empty capability sets; CAP_NET_RAW not required in this setup"

echo "STAGE 6: prove admission is narrow"
if probe_other_target >/dev/null 2>&1; then
    fail "probe admission unexpectedly allowed a different target"
fi

ip netns exec "$PRI" python3 -c '
import socket
import time
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("'"$TARGET"'", '"$TEST_PORT"'))
s.listen()
time.sleep(300)
' >/dev/null 2>&1 &
SERVER_PID=$!
sleep 1

if ip netns exec "$ROU" setpriv \
    --reuid "$PROBE_UID" --regid "$PROBE_GID" --clear-groups \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
    python3 -c 'import socket; socket.create_connection(("'"$TARGET"'", '"$TEST_PORT"'), 1)' \
    >/dev/null 2>&1
then
    fail "probe policy unexpectedly allowed TCP to the probe target"
fi
echo "PASS D: other destination and TCP traffic remain blocked"

echo "STAGE 7: prove no silent escape through alternate Device"
ip -n "$ROU" route del "$TARGET/32" dev "$VPN_IF"
ROUTE_GET=$(ip -n "$ROU" route get "$TARGET")
printf 'ALTERNATE_ROUTE_GET=%s\n' "$ROUTE_GET"
printf '%s\n' "$ROUTE_GET" | grep -q "dev $ALT_IF" ||
    fail "ordinary route lookup did not move to alternate Device"

if probe >/dev/null 2>&1; then
    fail "Device-bound probe escaped through alternate path"
fi
if ip netns exec "$ROU" setpriv \
    --reuid "$PROBE_UID" --regid "$PROBE_GID" --clear-groups \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs \
    ping -n -c 1 -W 1 "$TARGET" >/dev/null 2>&1
then
    fail "unbound probe escaped through alternate Device despite narrow nft admission"
fi
echo "PASS E: alternate path exists, but probe evidence cannot escape through it"
ip -n "$ROU" route replace "$TARGET/32" dev "$VPN_IF"

echo "STAGE 8: same-name/new-ifindex replacement must not inherit stale admission"
ip -n "$ROU" link del "$VPN_IF"
create_primary
NEW_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$VPN_IF/ifindex")
[ "$NEW_INDEX" != "$OLD_INDEX" ] ||
    fail "automatic recreation unexpectedly reused ifindex $OLD_INDEX; cannot exercise new-ifindex phase"

if probe >/dev/null 2>&1; then
    fail "same-name/new-ifindex generation inherited stale numeric nft admission"
fi
echo "PASS F: same-name/new-ifindex=$NEW_INDEX does not inherit stale rules for $OLD_INDEX"

install_probe_policy "$NEW_INDEX"
verify_probe_policy "$NEW_INDEX"
if ! probe >/dev/null 2>&1; then
    fail "probe did not recover after new generation policy was verified"
fi
echo "PASS G: refreshed verified policy arms the new interface generation"

echo "STAGE 9: characterize exact same-ifindex reuse against stale nft state"
ip -n "$ROU" link del "$VPN_IF"

set +e
create_primary "$NEW_INDEX" 2>/tmp/vpng-exp021-force-index.err
FORCE_RC=$?
set -e

if [ "$FORCE_RC" -ne 0 ]; then
    echo "EXACT_IFINDEX_REUSE_SUPPORTED=0"
    echo "EXACT_IFINDEX_REUSE_ERROR_BEGIN"
    cat /tmp/vpng-exp021-force-index.err
    echo "EXACT_IFINDEX_REUSE_ERROR_END"
    rm -f /tmp/vpng-exp021-force-index.err
else
    rm -f /tmp/vpng-exp021-force-index.err
    REUSED_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$VPN_IF/ifindex")
    [ "$REUSED_INDEX" = "$NEW_INDEX" ] ||
        fail "requested ifindex $NEW_INDEX but kernel created $REUSED_INDEX"

    echo "EXACT_IFINDEX_REUSE_SUPPORTED=1"
    echo "EXACT_IFINDEX_REUSED=$REUSED_INDEX"

    if probe >/dev/null 2>&1; then
        echo "EXACT_IFINDEX_STALE_NFT_MATCH=1"
        echo "OBSERVATION: a fresh interface with the same numeric ifindex matches stale probe admission"
    else
        echo "EXACT_IFINDEX_STALE_NFT_MATCH=0"
        echo "OBSERVATION: exact numeric ifindex reuse did not make the stale probe admission effective"
    fi
fi

echo "STAGE 10: final owned-state dump"
ip netns exec "$ROU" nft -n list table ip "$NFT_TABLE"
ip -n "$ROU" -j link show
ip -n "$ROU" -j route show

echo "EXP_021_ICMP_GENERATION_BOUNDARY=PASS"
