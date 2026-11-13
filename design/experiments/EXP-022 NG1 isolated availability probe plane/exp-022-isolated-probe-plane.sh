#!/bin/sh
set -eu

ROU=vg-exp022-rou
PRI=vg-exp022-pri
ALT=vg-exp022-alt
HOST=vg-exp022-host

VPN_IF=vpn0
PRI_IF=pri0
ALT_IF=alt0
ALT_PEER_IF=altp0
LAN_IF=lan0
HOST_IF=host0

ROU_PRI_ADDR=198.18.221.2/30
PRI_ADDR=198.18.221.1/30
ROU_ALT_ADDR=198.18.222.2/30
ALT_ADDR=198.18.222.1/30
ROU_LAN_ADDR=198.18.223.2/30
HOST_ADDR=198.18.223.1/30

TARGET=203.0.113.22
PROBE_UID=65534
PROBE_GID=65534
PROBE_TABLE=6022
PROBE_RULE_PRIORITY=220
NFT_TABLE=vpng_exp22

cleanup() {
    set +e
    ip netns del "$HOST" >/dev/null 2>&1 || true
    ip netns del "$ALT" >/dev/null 2>&1 || true
    ip netns del "$PRI" >/dev/null 2>&1 || true
    ip netns del "$ROU" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

for cmd in ip nft ping setpriv grep awk; do
    command -v "$cmd" >/dev/null 2>&1 || fail "missing command $cmd"
done

[ "$(id -u)" -eq 0 ] || fail "EXP-022 requires root"

cleanup
trap cleanup EXIT HUP INT TERM

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
    ip -n "$ROU" link set "$VPN_IF" up
    ip -n "$PRI" link set "$PRI_IF" up
}

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

unbound_probe() {
    ip netns exec "$ROU" setpriv \
        --reuid "$PROBE_UID" \
        --regid "$PROBE_GID" \
        --clear-groups \
        --bounding-set=-all \
        --inh-caps=-all \
        --ambient-caps=-all \
        --no-new-privs \
        ping -n -c 1 -W 1 "$TARGET"
}

install_probe_route() {
    ip -n "$ROU" route replace table "$PROBE_TABLE" "$TARGET/32" dev "$VPN_IF"
    if ! ip -n "$ROU" route show table "$PROBE_TABLE" | grep -q '^unreachable default'; then
        ip -n "$ROU" route add table "$PROBE_TABLE" unreachable default metric 42760
    fi
}

install_probe_rule() {
    ip -n "$ROU" rule del priority "$PROBE_RULE_PRIORITY" >/dev/null 2>&1 || true
    ip -n "$ROU" rule add \
        priority "$PROBE_RULE_PRIORITY" \
        uidrange "$PROBE_UID-$PROBE_UID" \
        ipproto icmp \
        to "$TARGET/32" \
        oif "$VPN_IF" \
        lookup "$PROBE_TABLE"
}

install_probe_nft() {
    idx=$1
    ip netns exec "$ROU" nft delete table ip "$NFT_TABLE" >/dev/null 2>&1 || true
    ip netns exec "$ROU" nft -f - <<EOF
table ip $NFT_TABLE {
    chain input {
        type filter hook input priority filter; policy drop;
        meta iif $idx ip saddr $TARGET icmp type echo-reply counter accept comment "vpng-exp22:iif:$idx"
    }
    chain output {
        type filter hook output priority filter; policy drop;
        meta skuid $PROBE_UID meta oif $idx ip daddr $TARGET icmp type echo-request counter accept comment "vpng-exp22:oif:$idx"
    }
}
EOF
}

refresh_probe_plane() {
    idx=$1
    install_probe_route
    install_probe_rule
    install_probe_nft "$idx"
}

show_probe_plane() {
    echo "PROBE_RULES_BEGIN"
    ip -n "$ROU" rule show
    echo "PROBE_RULES_END"
    echo "PROBE_TABLE_BEGIN"
    ip -n "$ROU" route show table "$PROBE_TABLE"
    echo "PROBE_TABLE_END"
    echo "PROBE_NFT_BEGIN"
    ip netns exec "$ROU" nft -n list table ip "$NFT_TABLE"
    echo "PROBE_NFT_END"
}

echo "STAGE 1: create disposable topology"
for ns in "$ROU" "$PRI" "$ALT" "$HOST"; do
    ip netns add "$ns"
    ip -n "$ns" link set lo up
done

create_primary

ip -n "$ROU" link add name "$ALT_IF" type veth peer name "$ALT_PEER_IF" netns "$ALT"
ip -n "$ROU" addr add "$ROU_ALT_ADDR" dev "$ALT_IF"
ip -n "$ALT" addr add "$ALT_ADDR" dev "$ALT_PEER_IF"
ip -n "$ALT" addr add "$TARGET/32" dev "$ALT_PEER_IF"
ip -n "$ROU" link set "$ALT_IF" up
ip -n "$ALT" link set "$ALT_PEER_IF" up

ip -n "$ROU" link add name "$LAN_IF" type veth peer name "$HOST_IF" netns "$HOST"
ip -n "$ROU" addr add "$ROU_LAN_ADDR" dev "$LAN_IF"
ip -n "$HOST" addr add "$HOST_ADDR" dev "$HOST_IF"
ip -n "$ROU" link set "$LAN_IF" up
ip -n "$HOST" link set "$HOST_IF" up

ip -n "$ROU" route replace "$TARGET/32" dev "$ALT_IF"
ip -n "$HOST" route replace "$TARGET/32" via 198.18.223.2 dev "$HOST_IF"
ip -n "$ALT" route replace 198.18.223.0/30 via 198.18.222.2 dev "$ALT_PEER_IF"
ip netns exec "$ROU" sysctl -q -w net.ipv4.ip_forward=1
ip netns exec "$ROU" sh -c \
    "printf '%s %s\n' '$PROBE_GID' '$PROBE_GID' > /proc/sys/net/ipv4/ping_group_range"

echo "STAGE 2: prove ordinary payload path is alt0"
ROUTE_GET=$(ip -n "$ROU" route get "$TARGET")
printf 'ORDINARY_ROUTE_GET=%s\n' "$ROUTE_GET"
printf '%s\n' "$ROUTE_GET" | grep -q "dev $ALT_IF" ||
    fail "ordinary route does not select alt0"
ip netns exec "$HOST" ping -n -c 1 -W 1 "$TARGET" >/dev/null ||
    fail "forwarded ordinary payload cannot reach target through alt0"
echo "PASS A: ordinary/main payload path reaches target through alt0"

echo "STAGE 3: install isolated probe plane"
OLD_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$VPN_IF/ifindex")
refresh_probe_plane "$OLD_INDEX"
show_probe_plane

RULE_TEXT=$(ip -n "$ROU" rule show priority "$PROBE_RULE_PRIORITY")
printf 'PROBE_RULE=%s\n' "$RULE_TEXT"
printf '%s\n' "$RULE_TEXT" | grep -q "uidrange $PROBE_UID-$PROBE_UID" ||
    fail "probe rule does not show uidrange selector"
printf '%s\n' "$RULE_TEXT" | grep -q "ipproto icmp" ||
    fail "probe rule does not show ipproto selector"
printf '%s\n' "$RULE_TEXT" | grep -q "to $TARGET" ||
    fail "probe rule does not show target selector"
printf '%s\n' "$RULE_TEXT" | grep -q "oif $VPN_IF" ||
    fail "probe rule does not show oif selector"
echo "PASS B: combined probe-only RPDB selector installed"

echo "STAGE 4: prove bound dedicated probe uses vpn0, not ordinary alt0"
if ! probe >/dev/null 2>&1; then
    fail "dedicated bound probe did not reach target through vpn0"
fi
echo "PASS C: dedicated uid + bound interface probe succeeds through isolated table"

echo "STAGE 5: prove selector and firewall isolation"
if unbound_probe >/dev/null 2>&1; then
    fail "unbound probe unexpectedly consumed probe plane or escaped through alt0"
fi
if ip netns exec "$ROU" ping -n -c 1 -W 1 -I "$VPN_IF" "$TARGET" >/dev/null 2>&1; then
    fail "wrong-uid bound ping unexpectedly passed dedicated probe admission"
fi
if ! ip netns exec "$HOST" ping -n -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    fail "ordinary forwarded payload was disturbed by probe plane"
fi
echo "PASS D: unbound/wrong-uid local traffic cannot use probe plane; forwarded payload is unaffected"

echo "STAGE 6: prove probe works with no payload route through vpn0"
ROUTE_GET=$(ip -n "$ROU" route get "$TARGET")
printf 'PAYLOAD_ROUTE_WHILE_PROBING=%s\n' "$ROUTE_GET"
printf '%s\n' "$ROUTE_GET" | grep -q "dev $ALT_IF" ||
    fail "ordinary payload route unexpectedly moved away from alt0"
probe >/dev/null 2>&1 ||
    fail "probe depends on ordinary payload route through vpn0"
echo "PASS E: probe remains functional while ordinary payload routing has no vpn0 path"

echo "STAGE 7: break only primary condition path"
ip -n "$PRI" link set "$PRI_IF" down
if probe >/dev/null 2>&1; then
    fail "bound probe escaped through alternate path during primary outage"
fi
ip netns exec "$HOST" ping -n -c 1 -W 1 "$TARGET" >/dev/null ||
    fail "alternate ordinary payload path failed during primary outage"
echo "PASS F: condition fails on vpn0 while alternate payload path remains live"
ip -n "$PRI" link set "$PRI_IF" up
probe >/dev/null 2>&1 || fail "probe did not recover after primary path restore"
echo "PASS G: condition recovers on the same concrete interface"

echo "STAGE 8: same-name/new-ifindex recreation"
ip -n "$ROU" link del "$VPN_IF"
echo "AFTER_DELETE_RULES_BEGIN"
ip -n "$ROU" rule show
echo "AFTER_DELETE_RULES_END"
echo "AFTER_DELETE_TABLE_BEGIN"
ip -n "$ROU" route show table "$PROBE_TABLE"
echo "AFTER_DELETE_TABLE_END"

create_primary
NEW_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$VPN_IF/ifindex")
[ "$NEW_INDEX" != "$OLD_INDEX" ] ||
    fail "automatic recreation unexpectedly reused ifindex $OLD_INDEX"

if probe >/dev/null 2>&1; then
    fail "same-name/new-ifindex probe became effective before probe-plane refresh"
fi
echo "PASS H: same-name/new-ifindex=$NEW_INDEX is not probe-ready from stale control state"

refresh_probe_plane "$NEW_INDEX"
probe >/dev/null 2>&1 ||
    fail "refreshed probe plane did not admit new interface generation"
echo "PASS I: refreshed probe plane admits new interface generation"

echo "STAGE 9: characterize exact-ifindex reuse"
ip -n "$ROU" link del "$VPN_IF"
echo "EXACT_REUSE_AFTER_DELETE_RULES_BEGIN"
ip -n "$ROU" rule show
echo "EXACT_REUSE_AFTER_DELETE_RULES_END"
echo "EXACT_REUSE_AFTER_DELETE_TABLE_BEGIN"
ip -n "$ROU" route show table "$PROBE_TABLE"
echo "EXACT_REUSE_AFTER_DELETE_TABLE_END"

set +e
create_primary "$NEW_INDEX" 2>/tmp/vpng-exp022-force-index.err
FORCE_RC=$?
set -e

if [ "$FORCE_RC" -ne 0 ]; then
    echo "EXACT_IFINDEX_REUSE_SUPPORTED=0"
    echo "EXACT_IFINDEX_REUSE_ERROR_BEGIN"
    cat /tmp/vpng-exp022-force-index.err
    echo "EXACT_IFINDEX_REUSE_ERROR_END"
    rm -f /tmp/vpng-exp022-force-index.err
else
    rm -f /tmp/vpng-exp022-force-index.err
    REUSED_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$VPN_IF/ifindex")
    [ "$REUSED_INDEX" = "$NEW_INDEX" ] ||
        fail "requested ifindex $NEW_INDEX but kernel created $REUSED_INDEX"

    echo "EXACT_IFINDEX_REUSE_SUPPORTED=1"
    echo "EXACT_IFINDEX_REUSED=$REUSED_INDEX"

    if probe >/dev/null 2>&1; then
        fail "exact-ifindex reuse unexpectedly restored full probe plane without probe route"
    fi
    echo "PASS J: exact-ifindex reuse alone does not restore full probe plane"

    install_probe_route
    if probe >/dev/null 2>&1; then
        echo "EXACT_REUSE_STALE_RULE_NFT_REACTIVATED=1"
        echo "OBSERVATION: recreating only the probe route reactivated stale RPDB+nft state"
    else
        echo "EXACT_REUSE_STALE_RULE_NFT_REACTIVATED=0"
        echo "OBSERVATION: stale RPDB+nft state did not become sufficient after route recreation"
    fi

    refresh_probe_plane "$REUSED_INDEX"
    probe >/dev/null 2>&1 ||
        fail "fully refreshed exact-reuse probe plane did not work"
    echo "PASS K: full refresh produces a working current probe plane"
fi

echo "STAGE 10: final isolation dump"
show_probe_plane
echo "ORDINARY_ROUTE_FINAL=$(ip -n "$ROU" route get "$TARGET")"
echo "EXP_022_ISOLATED_PROBE_PLANE=PASS"
