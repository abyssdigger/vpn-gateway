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
}
EOF

ip netns exec "$SRC" ping -c 1 -W 1 "$TARGET" >/dev/null
echo "PASS A: numeric iif=$OLD_INDEX admits original generation"

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
echo "PASS B: same-name/new-ifindex=$NEW_INDEX does not inherit iif=$OLD_INDEX rule"

ip netns exec "$ROU" nft add rule ip vpng_exp17 input \
    meta iif "$NEW_INDEX" ip protocol icmp counter accept

ip netns exec "$SRC" ping -c 1 -W 1 "$TARGET" >/dev/null
echo "PASS C: explicit rule for fresh ifindex restores admission"

ip netns exec "$ROU" nft -n list chain ip vpng_exp17 input
echo "EXP_017_PRELIMINARY_IIF=PASS"
