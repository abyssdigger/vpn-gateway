#!/bin/sh
set -eu

ROU="vpng-exp021-rou"
HOST="vpng-exp021-host"
REMOTE="vpng-exp021-remote"

HOST_IF="host0"
DEV_IF="dev0"
REMOTE_IF="r0"

HOST_ADDR="192.0.2.2/30"
HOST_GW="192.0.2.1"
DEVICE_ADDR="198.51.100.1/30"
REMOTE_ADDR="198.51.100.2/30"
REMOTE_GW="198.51.100.2"
TARGET="203.0.113.10"
PROBE_TABLE="5001"
PROBE_RULE_PRIO="100"

cleanup() {
    ip netns del "$ROU" 2>/dev/null || true
    ip netns del "$HOST" 2>/dev/null || true
    ip netns del "$REMOTE" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

rou() {
    ip netns exec "$ROU" "$@"
}

remote() {
    ip netns exec "$REMOTE" "$@"
}

link_ifindex() {
    ns="$1"
    ifname="$2"
    ip netns exec "$ns" cat "/sys/class/net/$ifname/ifindex"
}

install_probe_nft_rules() {
    ifindex="$1"
    label="$2"

    rou nft add rule ip exp021 output \
        oif "$ifindex" ip daddr "$TARGET" \
        ip protocol icmp icmp type echo-request \
        ct state new,established \
        comment "\"exp021-$label-oif\"" counter accept

    rou nft add rule ip exp021 input \
        iif "$ifindex" ip saddr "$TARGET" \
        ip protocol icmp icmp type echo-reply \
        ct state established,related \
        comment "\"exp021-$label-iif\"" counter accept
}

install_probe_route() {
    rou ip rule del priority "$PROBE_RULE_PRIO" 2>/dev/null || true
    rou ip rule add priority "$PROBE_RULE_PRIO" \
        oif "$DEV_IF" lookup "$PROBE_TABLE"
    rou ip route replace table "$PROBE_TABLE" \
        "$TARGET/32" via "$REMOTE_GW" dev "$DEV_IF" onlink
}

create_device_link() {
    ip link add "$DEV_IF" type veth peer name "$REMOTE_IF"
    ip link set "$DEV_IF" netns "$ROU"
    ip link set "$REMOTE_IF" netns "$REMOTE"

    ip -n "$ROU" addr add "$DEVICE_ADDR" dev "$DEV_IF"
    ip -n "$ROU" link set "$DEV_IF" up

    ip -n "$REMOTE" addr add "$REMOTE_ADDR" dev "$REMOTE_IF"
    ip -n "$REMOTE" link set "$REMOTE_IF" up
}

cleanup

ip netns add "$ROU"
ip netns add "$HOST"
ip netns add "$REMOTE"

ip -n "$ROU" link set lo up
ip -n "$HOST" link set lo up
ip -n "$REMOTE" link set lo up

ip link add h0 type veth peer name "$HOST_IF"
ip link set h0 netns "$HOST"
ip link set "$HOST_IF" netns "$ROU"

ip -n "$HOST" addr add "$HOST_GW/30" dev h0
ip -n "$HOST" link set h0 up
ip -n "$ROU" addr add "$HOST_ADDR" dev "$HOST_IF"
ip -n "$ROU" link set "$HOST_IF" up
rou ip route add default via "$HOST_GW" dev "$HOST_IF"

create_device_link
ip -n "$REMOTE" addr add "$TARGET/32" dev lo

rou sysctl -q -w net.ipv4.conf.all.rp_filter=0
rou sysctl -q -w net.ipv4.conf.default.rp_filter=0
rou sysctl -q -w "net.ipv4.conf.$HOST_IF.rp_filter=0"
rou sysctl -q -w "net.ipv4.conf.$DEV_IF.rp_filter=0"

rou nft -f - <<'EOF'
table ip exp021 {
    chain input {
        type filter hook input priority 0; policy drop;
        ct state invalid drop
        iifname "lo" accept
        iifname "host0" ct state established,related accept
    }

    chain output {
        type filter hook output priority 0; policy drop;
        ct state invalid drop
        oifname "lo" accept
        oifname "host0" ct state established,related accept
        oifname "host0" ct state new accept
    }
}
EOF

OLD_IFINDEX="$(link_ifindex "$ROU" "$DEV_IF")"

if rou ping -I "$DEV_IF" -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    echo "FAIL A: production-like default-DROP unexpectedly allowed Device-local probe" >&2
    exit 1
fi
echo "PASS A: default-DROP local policy blocks Device-bound probe"

install_probe_nft_rules "$OLD_IFINDEX" "old"

if rou ping -I "$DEV_IF" -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    ROUTELESS_RESULT="success"
    echo "OBSERVATION B: interface-bound off-link probe succeeded without dedicated probe RPDB"
else
    ROUTELESS_RESULT="failure"
    echo "OBSERVATION B: interface-bound off-link probe still needs explicit probe routing"
fi

install_probe_route

if ! rou ping -I "$DEV_IF" -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    echo "FAIL C: narrow nft admission + oif probe table did not pass probe" >&2
    rou ip rule show >&2 || true
    rou ip route show table "$PROBE_TABLE" >&2 || true
    rou nft -a list table ip exp021 >&2 || true
    exit 1
fi
echo "PASS C: narrow numeric nft admission + oif probe table passes off-link probe"

ip -n "$ROU" link del "$DEV_IF"
create_device_link
rou sysctl -q -w "net.ipv4.conf.$DEV_IF.rp_filter=0"
NEW_IFINDEX="$(link_ifindex "$ROU" "$DEV_IF")"

if [ "$NEW_IFINDEX" = "$OLD_IFINDEX" ]; then
    echo "FAIL D: replacement unexpectedly reused same ifindex=$NEW_IFINDEX" >&2
    exit 1
fi

install_probe_route

if rou ping -I "$DEV_IF" -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    echo "FAIL D: fresh same-name/new-ifindex generation inherited stale nft admission" >&2
    exit 1
fi
echo "PASS D: fresh generation does not inherit old numeric probe admission"

install_probe_nft_rules "$NEW_IFINDEX" "new"

if ! rou ping -I "$DEV_IF" -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    echo "FAIL E: explicit new-generation admission did not restore probe" >&2
    exit 1
fi
echo "PASS E: explicit new-generation reprojection restores probe"

echo "OLD_IFINDEX=$OLD_IFINDEX"
echo "NEW_IFINDEX=$NEW_IFINDEX"
echo "ROUTELESS_PROBE=$ROUTELESS_RESULT"
echo "RULES_BEGIN"
rou ip rule show
echo "RULES_END"
echo "PROBE_TABLE_BEGIN"
rou ip route show table "$PROBE_TABLE"
echo "PROBE_TABLE_END"
echo "NFT_BEGIN"
rou nft -a list table ip exp021
echo "NFT_END"
echo "EXP_021_LOCAL_AVAILABILITY_PROBE=PASS"
