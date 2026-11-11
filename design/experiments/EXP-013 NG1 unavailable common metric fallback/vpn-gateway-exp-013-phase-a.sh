#!/bin/bash
set -euo pipefail

# EXP-013 Phase A: kernel/FIB probe for common UNAVAILABLE_METRIC.
# VPN-independent; all routing mutations stay in a disposable netns.

NS="vg-exp013"
TABLE=313
TARGET="203.0.113.13/32"
LOOKUP="203.0.113.13"
IF_A="path-a"
IF_B="path-b"
NORMAL_A=1
UNAVAILABLE_METRIC=65535
BLACKHOLE_METRIC=65536

OUT="vpn-gateway-exp-013-$(date -u +%Y%m%d-%H%M%SZ)"
mkdir -p "$OUT"

cleanup() {
    ip netns del "$NS" 2>/dev/null || true
}
trap cleanup EXIT

die() {
    echo "ERROR: $*" | tee -a "$OUT/result.txt" >&2
    exit 1
}

run_ns() {
    ip netns exec "$NS" "$@"
}

snapshot() {
    local snap="$1"
    run_ns ip -j -4 route show table "$TABLE" > "$OUT/$snap-routes.json"
    run_ns ip -4 route show table "$TABLE" > "$OUT/$snap-routes.txt"
    run_ns ip -j link show > "$OUT/$snap-links.json"
    run_ns ip -4 route get "$LOOKUP" table "$TABLE" > "$OUT/$snap-lookup.txt" 2>&1 || true
}

[ "$(id -u)" -eq 0 ] || die "must run as root"
command -v ip >/dev/null || die "ip not found"
command -v python3 >/dev/null || die "python3 not found"
ip netns list | awk '{print $1}' | grep -qx "$NS" && die "namespace $NS already exists"

{
    echo "EXP-013 Phase A"
    uname -a
    ip -Version
} > "$OUT/environment.txt"

ip netns add "$NS"
run_ns ip link set lo up
run_ns ip link add "$IF_A" type dummy
run_ns ip link add "$IF_B" type dummy
run_ns ip link set "$IF_A" up
run_ns ip link set "$IF_B" up

# A1: direct-dev multipath at one metric.
run_ns ip route add table "$TABLE" "$TARGET" proto 202 metric "$UNAVAILABLE_METRIC"     nexthop dev "$IF_A" weight 1     nexthop dev "$IF_B" weight 1
snapshot a1-multipath

python3 - "$OUT/a1-multipath-routes.json" "$IF_A" "$IF_B" "$UNAVAILABLE_METRIC" <<'PY'
import json, sys
path, a, b, metric = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
routes = json.load(open(path))
cand = [r for r in routes if r.get("metric") == metric and r.get("dst") == "203.0.113.13"]
assert len(cand) == 1, cand
nh = cand[0].get("nexthops", [])
devs = {x.get("dev") for x in nh}
assert devs == {a, b}, cand[0]
PY
echo "A1 direct-dev multipath: PASS" | tee "$OUT/result.txt"

# A2: normal outranks unavailable; unavailable outranks blackhole.
run_ns ip route add table "$TABLE" "$TARGET" dev "$IF_A" proto 202 metric "$NORMAL_A"
run_ns ip route add table "$TABLE" blackhole "$TARGET" proto 201 metric "$BLACKHOLE_METRIC"
snapshot a2-normal
grep -q "dev $IF_A" "$OUT/a2-normal-lookup.txt" || die "A2 normal route did not win"

run_ns ip route del table "$TABLE" "$TARGET" dev "$IF_A" proto 202 metric "$NORMAL_A"
snapshot a2-unavailable
grep -Eq "dev ($IF_A|$IF_B)" "$OUT/a2-unavailable-lookup.txt" || die "A2 unavailable fallback did not win"

run_ns ip route del table "$TABLE" "$TARGET" proto 202 metric "$UNAVAILABLE_METRIC"
snapshot a2-blackhole
grep -qi "blackhole" "$OUT/a2-blackhole-lookup.txt" || die "A2 blackhole did not become terminal winner"
echo "A2 metric ordering: PASS" | tee -a "$OUT/result.txt"

# Recreate fallback for interface-deletion observation.
run_ns ip route del table "$TABLE" blackhole "$TARGET" proto 201 metric "$BLACKHOLE_METRIC"
run_ns ip route add table "$TABLE" "$TARGET" proto 202 metric "$UNAVAILABLE_METRIC"     nexthop dev "$IF_A" weight 1     nexthop dev "$IF_B" weight 1
run_ns ip route add table "$TABLE" blackhole "$TARGET" proto 201 metric "$BLACKHOLE_METRIC"

A_OLD_IFINDEX="$(run_ns cat /sys/class/net/$IF_A/ifindex)"
run_ns ip link del "$IF_A"
snapshot a3-after-delete
echo "A3 one nexthop interface deleted: OBSERVED" | tee -a "$OUT/result.txt"

run_ns ip link add "$IF_A" type dummy
run_ns ip link set "$IF_A" up
A_NEW_IFINDEX="$(run_ns cat /sys/class/net/$IF_A/ifindex)"
snapshot a4-return

if [ "$A_OLD_IFINDEX" = "$A_NEW_IFINDEX" ]; then
    die "A4 same-name interface unexpectedly reused ifindex $A_OLD_IFINDEX"
fi
echo "A4 same-name/new-ifindex return: PASS old=$A_OLD_IFINDEX new=$A_NEW_IFINDEX" | tee -a "$OUT/result.txt"

# A5: exact /0 competition in a clean table.
run_ns ip route flush table "$TABLE" || true
run_ns ip route add table "$TABLE" default dev "$IF_A" proto 202 metric "$NORMAL_A"
run_ns ip route add table "$TABLE" default proto 202 metric "$UNAVAILABLE_METRIC"     nexthop dev "$IF_A" weight 1     nexthop dev "$IF_B" weight 1
run_ns ip route add table "$TABLE" blackhole default proto 201 metric "$BLACKHOLE_METRIC"
snapshot a5-default-normal
grep -q "dev $IF_A" "$OUT/a5-default-normal-lookup.txt" || die "A5 normal default did not win"

run_ns ip route del table "$TABLE" default dev "$IF_A" proto 202 metric "$NORMAL_A"
snapshot a5-default-unavailable
grep -Eq "dev ($IF_A|$IF_B)" "$OUT/a5-default-unavailable-lookup.txt" || die "A5 unavailable default did not win"

run_ns ip route del table "$TABLE" default proto 202 metric "$UNAVAILABLE_METRIC"
snapshot a5-default-blackhole
grep -qi "blackhole" "$OUT/a5-default-blackhole-lookup.txt" || die "A5 blackhole default did not become terminal winner"
echo "A5 /0 metric ordering: PASS" | tee -a "$OUT/result.txt"

echo "PHASE_A=PASS" | tee -a "$OUT/result.txt"
echo "Artifacts: $OUT"
