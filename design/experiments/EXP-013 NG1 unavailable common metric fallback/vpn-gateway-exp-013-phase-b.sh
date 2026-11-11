#!/usr/bin/env bash
set -euo pipefail

# EXP-013 Phase B: real OpenConnect payload test for the shadow fallback model.
#
# Uses the already live-verified ROU v0 only as appliance/ocserv/publication/firewall/NAT
# scaffolding. Once two real vpnsXX interfaces are present, only the controller process
# is SIGSTOP'ed. ocserv and relay continue running while this harness owns:
#   - test table 313
#   - RPDB priority 50 for the test target
#   - one host /32 route to the test target
#   - one temporary FORWARD DROP rule during B4
#
# Production table 100 is never modified.

NS="vpn-gate-rou0"
HOST_IF="rouvpn0"
ROU_IF="host0"
HOST_ADDR="192.0.2.1"
ROU_ADDR="192.0.2.2"
TARGET="172.21.201.19"
TARGET_CIDR="$TARGET/32"
TABLE=313
RULE_PRIORITY=50
NORMAL_A=10
NORMAL_B=20
UNAVAILABLE_METRIC=65535
BLACKHOLE_METRIC=65536
ROUTE_PROTO=202
BLACKHOLE_PROTO=201

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROU="$SCRIPT_DIR/../../NG1/code/python/rou_v0/rou_v0.py"
RUNTIME="/run/vpn-gateway-rou-v0"
STATE="$RUNTIME/state.json"
OCCTL_SOCKET="$RUNTIME/occtl.sock"

OUT="vpn-gateway-exp-013-phase-b-$(date -u +%Y%m%d-%H%M%SZ)"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
RESULT="$OUT/result.txt"
ROU_LOG="$OUT/rou-v0.log"

rou_pid=""
controller_frozen=0
host_route_added=0
rule_added=0
drop_rule_added=0
dead_if=""
healthy_if=""
A=""
B=""

say() { printf '%s\n' "$*" | tee -a "$RESULT"; }
fail() { say "FAIL: $*"; exit 1; }

run_ns() {
    ip netns exec "$NS" "$@"
}

wait_until() {
    local timeout="$1"; shift
    local end=$((SECONDS + timeout))
    while (( SECONDS < end )); do
        if "$@"; then return 0; fi
        if [[ -n "$rou_pid" ]] && ! kill -0 "$rou_pid" 2>/dev/null; then
            tail -n 120 "$ROU_LOG" >&2 || true
            return 1
        fi
        sleep 0.2
    done
    return 1
}

both_clients() {
    local u
    u="$(occtl -s "$OCCTL_SOCKET" show users 2>/dev/null || true)"
    grep -Eq '[[:space:]]pri[[:space:]].*connected' <<<"$u" || return 1
    grep -Eq '[[:space:]]sec[[:space:]].*connected' <<<"$u" || return 1
    grep -Eq '[[:space:]]pri[[:space:]].*AES-256-GCM.*connected' <<<"$u" || return 1
    grep -Eq '[[:space:]]sec[[:space:]].*AES-256-GCM.*connected' <<<"$u" || return 1
}

state_has_two() {
    python3 - "$STATE" <<'PY' >/dev/null 2>&1
import json, sys
s=json.load(open(sys.argv[1]))
a=s["admitted"]
assert len(a) == 2
assert sorted(x["metric"] for x in a) == [10,20]
PY
}

cleanup() {
    set +e

    if [[ -n "$dead_if" && "$drop_rule_added" -eq 1 ]]; then
        run_ns iptables-legacy -D FORWARD -i "$ROU_IF" -o "$dead_if" -d "$TARGET_CIDR" -j DROP >/dev/null 2>&1 || true
        drop_rule_added=0
    fi

    if ip netns list 2>/dev/null | awk '{print $1}' | grep -Fxq "$NS"; then
        run_ns ip rule del priority "$RULE_PRIORITY" >/dev/null 2>&1 || true
        run_ns ip route flush table "$TABLE" >/dev/null 2>&1 || true
    fi
    rule_added=0

    if [[ "$host_route_added" -eq 1 ]]; then
        ip route del "$TARGET_CIDR" via "$ROU_ADDR" dev "$HOST_IF" >/dev/null 2>&1 || true
        host_route_added=0
    fi

    if [[ -n "$rou_pid" ]] && kill -0 "$rou_pid" 2>/dev/null; then
        if [[ "$controller_frozen" -eq 1 ]]; then
            kill -CONT "$rou_pid" 2>/dev/null || true
            controller_frozen=0
            sleep 0.2
        fi
        kill -TERM "$rou_pid" 2>/dev/null || true
        wait "$rou_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

route_snapshot() {
    local name="$1"
    run_ns ip -4 route show table "$TABLE" >"$OUT/$name-routes.txt" 2>&1 || true
    run_ns ip -j -4 route show table "$TABLE" >"$OUT/$name-routes.json" 2>&1 || true
    run_ns ip -4 rule show >"$OUT/$name-rules.txt" 2>&1 || true
    set +e
    run_ns ip -4 route get "$TARGET" from "$HOST_ADDR" iif "$ROU_IF" >"$OUT/$name-lookup.txt" 2>&1
    echo $? >"$OUT/$name-lookup.rc"
    run_ns ip -4 route get fibmatch "$TARGET" from "$HOST_ADDR" iif "$ROU_IF" >"$OUT/$name-fibmatch.txt" 2>&1
    echo $? >"$OUT/$name-fibmatch.rc"
    set -e
}

lookup_dev() {
    local out
    out="$(run_ns ip -4 route get "$TARGET" from "$HOST_ADDR" iif "$ROU_IF" 2>/dev/null || true)"
    awk '
        {
            for (i=1; i<=NF; i++) {
                if ($i=="dev" && (i+1)<=NF) {
                    print $(i+1)
                    exit
                }
            }
        }
    ' <<<"$out"
}

ping_ok() {
    ping -I "$HOST_ADDR" -c 2 -W 2 "$TARGET" >/dev/null 2>&1
}

drop_counter() {
    run_ns iptables-legacy-save -c -t filter |
        awk -v outif="$dead_if" -v dst="$TARGET_CIDR" '
            $0 ~ "^-?\\[[0-9]+:[0-9]+\\] -A FORWARD " &&
            index($0, "-i host0 ") &&
            index($0, "-o " outif " ") &&
            index($0, "-d " dst " ") &&
            index($0, "-j DROP") {
                x=$1
                gsub(/^\[/, "", x)
                split(x, a, ":")
                print a[1]
                exit
            }
        '
}

install_target_shadow() {
    run_ns ip route flush table "$TABLE" >/dev/null 2>&1 || true
    run_ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$A" proto "$ROUTE_PROTO" metric "$NORMAL_A"
    run_ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$B" proto "$ROUTE_PROTO" metric "$NORMAL_B"
    run_ns ip route add table "$TABLE" "$TARGET_CIDR" proto "$ROUTE_PROTO" metric "$UNAVAILABLE_METRIC" \
        nexthop dev "$A" weight 1 \
        nexthop dev "$B" weight 1
    run_ns ip route add table "$TABLE" blackhole "$TARGET_CIDR" proto "$BLACKHOLE_PROTO" metric "$BLACKHOLE_METRIC"
}

[[ "$(id -u)" -eq 0 ]] || fail "run as root"
for x in ip ping python3 occtl systemctl iptables-legacy iptables-legacy-save ss; do
    command -v "$x" >/dev/null || fail "missing $x"
done
[[ -f "$ROU" ]] || fail "ROU v0 implementation not found: $ROU"
systemctl is-active --quiet ocserv.service && fail "stop normal ocserv.service before this harness"
ip netns list | awk '{print $1}' | grep -Fxq "$NS" && fail "namespace $NS already exists"
ip link show "$HOST_IF" >/dev/null 2>&1 && fail "$HOST_IF already exists"
ip route show exact "$TARGET_CIDR" | grep -q . && fail "host already has exact route to $TARGET_CIDR"
ss -H -ltn "sport = :44443" | grep -q . && fail "TCP 44443 busy"
ss -H -lun "sport = :44443" | grep -q . && fail "UDP 44443 busy"

{
    echo "EXP-013 Phase B"
    date -u
    uname -a
    ip -Version
    iptables-legacy --version
} >"$OUT/environment.txt"

python3 "$ROU" check >"$OUT/rou-check.txt"
python3 "$ROU" run >"$ROU_LOG" 2>&1 &
rou_pid=$!

rou_ready() {
    ip netns list | awk '{print $1}' | grep -Fxq "$NS" || return 1
    ip link show "$HOST_IF" >/dev/null 2>&1 || return 1
    [[ -S "$OCCTL_SOCKET" ]]
}
wait_until 15 rou_ready || fail "ROU did not reach transport-ready state"
wait_until 40 both_clients || { occtl -s "$OCCTL_SOCKET" show users >"$OUT/users-failed.txt" 2>&1 || true; fail "both OC clients did not reach DTLS"; }
wait_until 10 state_has_two || fail "ROU v0 did not admit two real interfaces"

occtl -s "$OCCTL_SOCKET" show users >"$OUT/users-initial.txt"
cp "$STATE" "$OUT/state-before-freeze.json"
ip -n "$NS" -j link show >"$OUT/links-before-freeze.json"
ip -n "$NS" route show table 100 >"$OUT/table100-before-freeze.txt"
run_ns iptables-legacy-save -c >"$OUT/firewall-before-freeze.txt"

read -r A B < <(python3 - "$STATE" <<'PY'
import json, sys
s=json.load(open(sys.argv[1]))
a=sorted(s["admitted"], key=lambda x: x["metric"])
print(a[0]["ifname"], a[1]["ifname"])
PY
)
[[ "$A" == vpns* && "$B" == vpns* && "$A" != "$B" ]] || fail "unexpected admitted interfaces A=$A B=$B"

kill -STOP "$rou_pid"
controller_frozen=1
sleep 0.2
kill -0 "$rou_pid" 2>/dev/null || fail "controller disappeared after SIGSTOP"
say "PASS B0: real ROU/ocserv has two DTLS interfaces A=$A B=$B; controller frozen only"

# All experiment routing is isolated from v0 table 100.
run_ns ip rule add priority "$RULE_PRIORITY" iif "$ROU_IF" to "$TARGET_CIDR" lookup "$TABLE"
rule_added=1
ip route add "$TARGET_CIDR" via "$ROU_ADDR" dev "$HOST_IF"
host_route_added=1

install_target_shadow
route_snapshot b1-initial
[[ "$(lookup_dev)" == "$A" ]] || fail "B1 expected preferred normal route via $A"
ping_ok || fail "B1 payload failed with both normal routes + shadow fallback"
say "PASS B1: normal A wins over persistent common-metric shadow fallback; payload works"

# Demote A by removing only its normal route. A remains in shadow fallback.
run_ns ip route del table "$TABLE" "$TARGET_CIDR" dev "$A" proto "$ROUTE_PROTO" metric "$NORMAL_A"
route_snapshot b2-a-demoted
[[ "$(lookup_dev)" == "$B" ]] || fail "B2 expected normal B after A demotion"
ping_ok || fail "B2 payload failed after preferred A was demoted"
grep -q "metric $UNAVAILABLE_METRIC" "$OUT/b2-a-demoted-routes.txt" || fail "B2 shadow fallback disappeared"
say "PASS B2: A demotion removes only normal A; B normal wins and fallback remains"

# Demote B too. Only healthy A+B common-metric fallback remains above blackhole.
run_ns ip route del table "$TABLE" "$TARGET_CIDR" dev "$B" proto "$ROUTE_PROTO" metric "$NORMAL_B"
route_snapshot b3-all-fallback
selected="$(lookup_dev)"
if [[ "$selected" != "$A" && "$selected" != "$B" ]]; then
    fail "B3 lookup did not select a fallback member: selected=$selected"
fi
ping_ok || fail "B3 payload failed with both real VPN paths healthy in common fallback"
say "PASS B3: all paths demoted; common-metric fallback carries real payload via $selected"

# B4: make the branch selected for this fixed src/dst flow fail while interface stays UP.
dead_if="$selected"
if [[ "$dead_if" == "$A" ]]; then healthy_if="$B"; else healthy_if="$A"; fi

run_ns iptables-legacy -I FORWARD 1 -i "$ROU_IF" -o "$dead_if" -d "$TARGET_CIDR" -j DROP
drop_rule_added=1
run_ns iptables-legacy-save -c -t filter >"$OUT/b4-filter-before.txt"

if ping_ok; then
    fail "B4 fixed flow unexpectedly succeeded although selected fallback branch $dead_if was blocked"
fi
first_count="$(drop_counter)"
[[ "$first_count" =~ ^[0-9]+$ && "$first_count" -gt 0 ]] || fail "B4 DROP rule did not see the failed flow"
say "PASS B4a: fixed flow hashes to blocked $dead_if and is not transparently retried"

# Prove the other VPN path is healthy while the selected fallback member stays blocked.
run_ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$healthy_if" proto "$ROUTE_PROTO" metric 1
[[ "$(lookup_dev)" == "$healthy_if" ]] || fail "B4 expected temporary normal route via $healthy_if"
ping_ok || fail "B4 alternate real VPN path $healthy_if did not carry payload"
run_ns ip route del table "$TABLE" "$TARGET_CIDR" dev "$healthy_if" proto "$ROUTE_PROTO" metric 1

selected_again="$(lookup_dev)"
[[ "$selected_again" == "$dead_if" ]] || fail "B4 fallback hash changed unexpectedly: before=$dead_if after=$selected_again"
if ping_ok; then
    fail "B4 fixed flow succeeded after returning to common fallback despite blocked selected member"
fi
second_count="$(drop_counter)"
[[ "$second_count" =~ ^[0-9]+$ && "$second_count" -gt "$first_count" ]] || fail "B4 second failed flow did not hit blocked member again"

run_ns iptables-legacy -D FORWARD -i "$ROU_IF" -o "$dead_if" -d "$TARGET_CIDR" -j DROP
drop_rule_added=0
ping_ok || fail "B4 payload did not recover after removing the experiment DROP"
route_snapshot b4-after-unblock
say "PASS B4: alternate member is healthy, but common fallback does not retry a flow whose selected member is blocked"

# Promotion/failback: restore A normal while B remains represented only by fallback.
run_ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$A" proto "$ROUTE_PROTO" metric "$NORMAL_A"
route_snapshot b5-a-promoted
[[ "$(lookup_dev)" == "$A" ]] || fail "B5 promoted A did not regain normal priority"
ping_ok || fail "B5 payload failed after A promotion"
say "PASS B5: promotion restores normal A above unchanged shado fallback"

# B6: same ordering with default routes on the two real VPN interfaces.
run_ns ip route flush table "$TABLE"
run_ns ip route add table "$TABLE" default dev "$A" proto "$ROUTE_PROTO" metric "$NORMAL_A"
run_ns ip route add table "$TABLE" default dev "$B" proto "$ROUTE_PROTO" metric "$NORMAL_B"
run_ns ip route add table "$TABLE" default proto "$ROUTE_PROTO" metric "$UNAVAILABLE_METRIC" \
    nexthop dev "$A" weight 1 \
    nexthop dev "$B" weight 1
run_ns ip route add table "$TABLE" blackhole default proto "$BLACKHOLE_PROTO" metric "$BLACKHOLE_METRIC"

route_snapshot b6-default-a
[[ "$(lookup_dev)" == "$A" ]] || fail "B6 default normal A did not win"
ping_ok || fail "B6 payload failed through default normal A"

run_ns ip route del table "$TABLE" default dev "$A" proto "$ROUTE_PROTO" metric "$NORMAL_A"
route_snapshot b6-default-b
[[ "$(lookup_dev)" == "$B" ]] || fail "B6 default normal B did not win after A demotion"
ping_ok || fail "B6 payload failed through default normal B"

run_ns ip route del table "$TABLE" default dev "$B" proto "$ROUTE_PROTO" metric "$NORMAL_B"
route_snapshot b6-default-fallback
selected_default="$(lookup_dev)"
if [[ "$selected_default" != "$A" && "$selected_default" != "$B" ]]; then
    fail "B6 default fallback did not select a VPN member: $selected_default"
fi
ping_ok || fail "B6 payload failed through healthy default common fallback
run_ns ip route del table "$TABLE" default proto "$ROUTE_PROTO" metric "$UNAVAILABLE_METRIC"
route_snapshot b6-default-blackhole
if ping_ok; then
    fail "B6 payload unexpectedly passed with only terminal blackhole default"
fi
say "PASS B6: real-VPN default ordering normal > common fallback > blackhole"

say "PHASE_B=PASS"
say "Artifacts: $OUT"
