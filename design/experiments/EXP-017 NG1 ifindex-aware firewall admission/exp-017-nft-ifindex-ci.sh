#!/bin/sh
set -eu

ROU=vpng-exp17-rou
SRC=vpng-exp17-src
SRC_HOST=src0
ROU_IF=vpn0
SRC_ADDR=198.18.17.1/30
ROU_ADDR=198.18.17.2/30
TARGET=198.18.17.2

cleanup() {
    ip netns del "$SRC" >/dev/null 2>&1 || true
    ip netns del "$ROU" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM
cleanup

ip netns add "$ROU"
ip netns add "$SRC"

make_link() {
    ip -n "$SRC" link add "$SRC_HOST" type veth peer name "$ROU_IF" netns "$ROU"
    ip -n "$SRC" addr add "$SRC_ADDR" dev "$SRC_HOST"
    ip -n "$ROU" addr add "$ROU_ADDR" dev "$ROU_IF"
    ip -n "$SRC" link set lo up
    ip -n "$ROU" link set lo up
    ip -n "$SRC" link set "$SRC_HOST" up
    ip -n "$ROU" link set "$ROU_IF" up
}

make_link
OLD_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$ROU_IF/ifindex")

ip netns exec "$ROU" nft -f - <<EOF
table ip vpng_exp17 {
    chain input {
        type filter hook input priority filter; policy drop;
        meta iif $OLD_INDEX ip protocol icmp counter accept
    }
    chain output {
        type filter hook output priority filter; policy drop;
        meta oif $OLD_INDEX ip protocol icmp counter accept
    }
}
EOF

ip netns exec "$SRC" ping -c 1 -W 1 "$TARGET" >/dev/null
ip netns exec "$ROU" ping -c 1 -W 1 198.18.17.1 >/dev/null
echo "PASS A: numeric iif/oif=$OLD_INDEX admit original generation"

# Deleting either veth endpoint removes the pair. Recreate the same interface names.
ip -n "$SRC" link del "$SRC_HOST"
make_link
NEW_INDEX=$(ip netns exec "$ROU" cat "/sys/class/net/$ROU_IF/ifindex")

if [ "$NEW_INDEX" = "$OLD_INDEX" ]; then
    echo "FAIL: recreated interface unexpectedly reused ifindex $OLD_INDEX" >&2
    exit 1
fi

if ip netns exec "$SRC" ping -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    echo "FAIL: fresh same-name generation matched old numeric iif rule" >&2
    exit 1
fi
echo "PASS B: same-name/new-ifindex=$NEW_INDEX does not inherit old iif/oif rules"
echo "JSON_AFTER_B_BEGIN"
ip netns exec "$ROU" nft -j list table ip vpng_exp17
echo "JSON_AFTER_B_END"

# Update only ingress generation. SRC -> ROU must work again, while ROU -> SRC must still
# fail because OUTPUT remains pinned to old oif.
ip netns exec "$ROU" nft add rule ip vpng_exp17 input \
    meta iif "$NEW_INDEX" ip protocol icmp counter \
    comment '"exp17-new-iif"' accept

# The echo request should now reach INPUT, but the echo reply must still be blocked by
# stale OUTPUT. Therefore end-to-end ping remains unsuccessful; prove ingress admission
# by observing the counter on the new-iif rule instead of requiring a reply.
if ip netns exec "$SRC" ping -c 1 -W 1 "$TARGET" >/dev/null 2>&1; then
    echo "FAIL: ping succeeded before new oif generation was admitted" >&2
    exit 1
fi

NEW_IIF_PKTS=$(ip netns exec "$ROU" nft -a list chain ip vpng_exp17 input |
    awk '
        /comment "exp17-new-iif"/ && /counter packets/ {
            for (i = 1; i <= NF; i++) {
                if ($i == "packets") {
                    print $(i + 1)
                    exit
                }
            }
        }
    ')
case "$NEW_IIF_PKTS" in
    ''|*[!0-9]*)
        echo "FAIL: could not read new-iif counter: $NEW_IIF_PKTS" >&2
        exit 1
        ;;
    0)
        echo "FAIL: new iif rule did not see ingress request" >&2
        exit 1
        ;;
esac
echo "PASS C: new iif admits ingress, stale oif still blocks reply"

ip netns exec "$ROU" nft add rule ip vpng_exp17 output \
    meta oif "$NEW_INDEX" ip protocol icmp counter accept
ip netns exec "$ROU" ping -c 1 -W 1 198.18.17.1 >/dev/null
ip netns exec "$SRC" ping -c 1 -W 1 "$TARGET" >/dev/null
echo "PASS D: explicit new oif restores both local egress and full echo flow"

ip netns exec "$ROU" nft -n list table ip vpng_exp17
echo "EXP_017_PRELIMINARY_IIF_OIF=PASS"
