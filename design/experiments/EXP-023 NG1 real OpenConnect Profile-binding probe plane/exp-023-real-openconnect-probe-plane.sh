#!/bin/sh
set -eu

PROBE_TABLE=6023
PROBE_RULE_PRIORITY=22023
TERMINAL_METRIC=42760
OUTAGE_WAIT_SECONDS=180
RECOVERY_WAIT_SECONDS=180

PRIMARY_IF=
SECONDARY_IF=
PRIMARY_PEER=
SECONDARY_PEER=
TARGET=
TMP=/run/vpn-gate-exp023-$$

usage() {
    cat <<'EOF'
Usage:
  exp-023-real-openconnect-probe-plane.sh \
      [--primary-if IF | --primary-peer IPv4] \
      [--secondary-if IF | --secondary-peer IPv4] \
      --target IPv4

The experiment changes only temporary local RPDB/table state. It never modifies either
remote client automatically. Stand diagnosis/restoration is intentionally documented as
interactive commands in README.md rather than implemented here.
EOF
}

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

dump_capture() {
    tag=$1
    rc=$(cat "$TMP/$tag.rc" 2>/dev/null || printf '?')
    echo "  rc: $rc" >&2
    if [ -s "$TMP/$tag.out" ]; then
        echo "  stdout:" >&2
        sed 's/^/    /' "$TMP/$tag.out" >&2
    fi
    if [ -s "$TMP/$tag.err" ]; then
        echo "  stderr:" >&2
        sed 's/^/    /' "$TMP/$tag.err" >&2
    fi
}

fail_capture() {
    message=$1
    tag=$2
    echo "FAIL: $message" >&2
    dump_capture "$tag"
    exit 1
}

cleanup() {
    set +e
    ip rule del priority "$PROBE_RULE_PRIORITY" >/dev/null 2>&1 || true
    ip route flush table "$PROBE_TABLE" >/dev/null 2>&1 || true
    rm -rf "$TMP"
}
trap cleanup EXIT HUP INT TERM

while [ "$#" -gt 0 ]; do
    case "$1" in
        --primary-if)
            [ "$#" -ge 2 ] || fail "--primary-if requires a value"
            PRIMARY_IF=$2
            shift 2
            ;;
        --secondary-if)
            [ "$#" -ge 2 ] || fail "--secondary-if requires a value"
            SECONDARY_IF=$2
            shift 2
            ;;
        --primary-peer)
            [ "$#" -ge 2 ] || fail "--primary-peer requires a value"
            PRIMARY_PEER=$2
            shift 2
            ;;
        --secondary-peer)
            [ "$#" -ge 2 ] || fail "--secondary-peer requires a value"
            SECONDARY_PEER=$2
            shift 2
            ;;
        --target)
            [ "$#" -ge 2 ] || fail "--target requires a value"
            TARGET=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            fail "unknown argument $1"
            ;;
    esac
done

for cmd in ip ping awk grep sed seq tr; do
    command -v "$cmd" >/dev/null 2>&1 || fail "missing command $cmd"
done
[ "$(id -u)" -eq 0 ] || fail "EXP-023 requires root"
[ -n "$TARGET" ] || { usage >&2; fail "--target is required"; }

mkdir -m 0700 "$TMP"

find_if_by_peer() {
    peer=$1
    ip -o -4 addr show |
        awk -v peer="$peer" '
            index($0, " peer " peer "/") {
                print $2
                exit
            }
        '
}

if [ -z "$PRIMARY_IF" ]; then
    [ -n "$PRIMARY_PEER" ] || fail "supply --primary-if or --primary-peer"
    PRIMARY_IF=$(find_if_by_peer "$PRIMARY_PEER")
    [ -n "$PRIMARY_IF" ] ||
        fail "no local interface found with peer $PRIMARY_PEER"
fi

if [ -z "$SECONDARY_IF" ]; then
    [ -n "$SECONDARY_PEER" ] || fail "supply --secondary-if or --secondary-peer"
    SECONDARY_IF=$(find_if_by_peer "$SECONDARY_PEER")
    [ -n "$SECONDARY_IF" ] ||
        fail "no local interface found with peer $SECONDARY_PEER"
fi

[ "$PRIMARY_IF" != "$SECONDARY_IF" ] ||
    fail "primary and secondary resolved to the same interface $PRIMARY_IF"

link_flags() {
    ip -o link show dev "$1" | sed -n 's/^[^<]*<\([^>]*\)>.*/\1/p'
}

require_iff_up() {
    ifname=$1
    flags=$(link_flags "$ifname")
    printf 'LINK_%s_FLAGS=%s\n' "$ifname" "$flags"
    printf '%s\n' "$flags" | tr ',' '\n' | grep -qx UP ||
        fail "$ifname exists but IFF_UP is not set; flags=$flags"
}

probe_capture() {
    tag=$1
    ifname=$2
    set +e
    ping -n -c 1 -W 1 -I "$ifname" "$TARGET"         >"$TMP/$tag.out" 2>"$TMP/$tag.err"
    rc=$?
    set -e
    printf '%s\n' "$rc" >"$TMP/$tag.rc"
    return "$rc"
}

echo "STAGE 1: validate supplied live bindings before mutation"
echo "PRIMARY_IF=$PRIMARY_IF"
echo "SECONDARY_IF=$SECONDARY_IF"
[ -n "$PRIMARY_PEER" ] && echo "PRIMARY_PEER=$PRIMARY_PEER"
[ -n "$SECONDARY_PEER" ] && echo "SECONDARY_PEER=$SECONDARY_PEER"
echo "TARGET=$TARGET"
require_iff_up "$PRIMARY_IF"
require_iff_up "$SECONDARY_IF"

PRIMARY_INDEX=$(cat "/sys/class/net/$PRIMARY_IF/ifindex")
SECONDARY_INDEX=$(cat "/sys/class/net/$SECONDARY_IF/ifindex")
echo "PRIMARY_IFINDEX=$PRIMARY_INDEX"
echo "SECONDARY_IFINDEX=$SECONDARY_INDEX"

if ! probe_capture initial-primary "$PRIMARY_IF"; then
    fail_capture "initial endpoint probe through $PRIMARY_IF failed" initial-primary
fi
if ! probe_capture initial-secondary "$SECONDARY_IF"; then
    fail_capture "initial endpoint probe through $SECONDARY_IF failed" initial-secondary
fi
echo "PASS A: supplied live bindings both reach endpoint"

rule_collision=$(ip rule show | awk -F: -v p="$PROBE_RULE_PRIORITY" '
    ($1 + 0) == p { print; exit }
')
[ -z "$rule_collision" ] ||
    fail "RPDB priority $PROBE_RULE_PRIORITY is already occupied: $rule_collision"

table_state=$(ip route show table "$PROBE_TABLE" 2>/dev/null || true)
[ -z "$table_state" ] ||
    fail "routing table $PROBE_TABLE is not empty: $table_state"

echo "STAGE 2: install isolated probe route and RPDB selector for primary binding"
ip route add table "$PROBE_TABLE" "$TARGET/32" dev "$PRIMARY_IF"
ip route add table "$PROBE_TABLE" unreachable default metric "$TERMINAL_METRIC"
ip rule add \
    priority "$PROBE_RULE_PRIORITY" \
    uidrange 0-0 \
    ipproto icmp \
    to "$TARGET/32" \
    oif "$PRIMARY_IF" \
    lookup "$PROBE_TABLE"

echo "PROBE_RULE=$(ip rule show priority "$PROBE_RULE_PRIORITY")"
echo "PROBE_TABLE_BEGIN"
ip route show table "$PROBE_TABLE"
echo "PROBE_TABLE_END"

set +e
ip route get "$TARGET" uid 0 ipproto icmp oif "$PRIMARY_IF" \
    >"$TMP/route-get.out" 2>"$TMP/route-get.err"
route_rc=$?
set -e
printf '%s\n' "$route_rc" >"$TMP/route-get.rc"
if [ "$route_rc" -ne 0 ]; then
    fail_capture "selector-specific route lookup failed" route-get
fi
route_get=$(cat "$TMP/route-get.out")
echo "PROBE_ROUTE_GET=$route_get"
printf '%s\n' "$route_get" | grep -q "dev $PRIMARY_IF" ||
    fail_capture "probe route lookup did not select $PRIMARY_IF" route-get
printf '%s\n' "$route_get" | grep -q "table $PROBE_TABLE" ||
    fail_capture "probe route lookup did not select table $PROBE_TABLE" route-get

if ! probe_capture isolated-primary "$PRIMARY_IF"; then
    fail_capture "isolated primary probe failed before outage" isolated-primary
fi
echo "PASS B: real primary OC probe is routed through the isolated table"

cat <<EOF
STAGE 3: create a data-path-only outage on the PRIMARY REMOTE client
ACTION REQUIRED NOW: create primary outage on pri

In another terminal on the machine that owns $PRIMARY_IF's OpenConnect session, block only
forwarded traffic to the endpoint while leaving OpenConnect running.

Example with iptables:
  sudo iptables -I FORWARD 1 -d $TARGET/32 -m comment --comment VPNG-EXP023 -j DROP

Cleanup command for that remote machine:
  sudo iptables -D FORWARD -d $TARGET/32 -m comment --comment VPNG-EXP023 -j DROP

The harness will wait up to $OUTAGE_WAIT_SECONDS seconds for:
  primary probe = FAIL
  secondary probe = PASS
EOF

OUTAGE_SEEN=0
for _ in $(seq 1 "$OUTAGE_WAIT_SECONDS"); do
    if probe_capture outage-primary "$PRIMARY_IF"; then
        :
    else
        if probe_capture outage-secondary "$SECONDARY_IF"; then
            OUTAGE_SEEN=1
            break
        fi
    fi
    sleep 1
done

if [ "$OUTAGE_SEEN" -ne 1 ]; then
    echo "FAIL: did not observe primary-fail/secondary-pass within ${OUTAGE_WAIT_SECONDS}s" >&2
    echo "  primary last probe:" >&2
    dump_capture outage-primary
    echo "  secondary last probe:" >&2
    dump_capture outage-secondary
    exit 1
fi

echo "OUTAGE_PRIMARY_PROBE:"
dump_capture outage-primary
echo "OUTAGE_SECONDARY_PROBE:"
dump_capture outage-secondary

if [ ! -e "/sys/class/net/$PRIMARY_IF/ifindex" ]; then
    fail "$PRIMARY_IF disappeared during endpoint-only outage"
fi
OUTAGE_INDEX=$(cat "/sys/class/net/$PRIMARY_IF/ifindex")
[ "$OUTAGE_INDEX" = "$PRIMARY_INDEX" ] ||
    fail "$PRIMARY_IF ifindex changed during outage: old=$PRIMARY_INDEX new=$OUTAGE_INDEX"
require_iff_up "$PRIMARY_IF"
echo "PASS C: primary condition failed while binding stayed IFF_UP with ifindex=$OUTAGE_INDEX"
echo "PASS D: alternate real OC binding still reached the endpoint"

cat <<EOF
STAGE 4: restore the PRIMARY REMOTE data path
ACTION REQUIRED NOW: restore primary data path on pri

Remove the temporary remote rule now:
  sudo iptables -D FORWARD -d $TARGET/32 -m comment --comment VPNG-EXP023 -j DROP

The harness will wait up to $RECOVERY_WAIT_SECONDS seconds for the isolated primary probe
to recover.
EOF

RECOVERED=0
for _ in $(seq 1 "$RECOVERY_WAIT_SECONDS"); do
    if probe_capture recovery-primary "$PRIMARY_IF"; then
        RECOVERED=1
        break
    fi
    sleep 1
done

if [ "$RECOVERED" -ne 1 ]; then
    fail_capture "primary isolated probe did not recover within ${RECOVERY_WAIT_SECONDS}s" recovery-primary
fi

if [ ! -e "/sys/class/net/$PRIMARY_IF/ifindex" ]; then
    fail "$PRIMARY_IF disappeared before recovery verification"
fi
RECOVERY_INDEX=$(cat "/sys/class/net/$PRIMARY_IF/ifindex")
[ "$RECOVERY_INDEX" = "$PRIMARY_INDEX" ] ||
    fail "$PRIMARY_IF recovered with a different ifindex: old=$PRIMARY_INDEX new=$RECOVERY_INDEX"
require_iff_up "$PRIMARY_IF"

echo "PASS E: isolated condition recovered on the same real OpenConnect binding"
echo "FINAL_ORDINARY_ROUTE=$(ip route get "$TARGET" 2>&1 || true)"
echo "EXP_023_REAL_OPENCONNECT_PROBE_PLANE=PASS"
