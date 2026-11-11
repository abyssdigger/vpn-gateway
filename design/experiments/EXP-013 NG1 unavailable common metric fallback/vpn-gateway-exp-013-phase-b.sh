#!/usr/bin/env bash
set -euo pipefail

# EXP-013 Phase B — real OpenConnect payload test for the shadow fallback model.
# ROU v0 supplies the already-proven namespace/ocserv/publication/firewall/NAT scaffold.
# During measurements only the controller process is SIGSTOP'ed; ocserv/relay keep running.
# Experiment routing lives in table 313 and RPDB priority 50. v0 table 100 is untouched.

NS=vpn-gate-rou0
HOST_IF=rouvpn0
ROU_IF=host0
HOST_ADDR=192.0.2.1
ROU_ADDR=192.0.2.2
TARGET=172.21.201.19
TARGET_CIDR=$TARGET/32
TABLE=313
RULE_PRIO=50
UNAVAILABLE_METRIC=65535
BLACKHOLE_METRIC=65536
PROTO=202
BH_PROTO=201

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROU="$HERE/../../NG1/code/python/rou_v0/rou_v0.py"
STATE=/run/vpn-gateway-rou-v0/state.json
OCCTL=/run/vpn-gateway-rou-v0/occtl.sock

OUT="vpn-gateway-exp-013-phase-b-$(date -u +%Y%m%d-%H%M%SZ)"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
RESULT="$OUT/result.txt"
ROU_LOG="$OUT/rou-v0.log"

rou_pid=
frozen=0
rule_added=0
host_route_added=0
drop_added=0
dead_if=
A=
B=

say() { printf '%s\n' "$*" | tee -a "$RESULT"; }
fail() { say "FAIL: $*"; exit 1; }
ns() { ip netns exec "$NS" "$@"; }

cleanup() {
    set +e
    if [[ "$drop_added" -eq 1 && -n "$dead_if" ]]; then
        ns iptables-legacy -D FORWARD -i "$ROU_IF" -o "$dead_if" -d "$TARGET_CIDR" -j DROP >/dev/null 2>&1
    fi
    if ip netns list 2>/dev/null | awk '{print $1}' | grep -Fxq "$NS"; then
        ns ip rule del priority "$RULE_PRIO" >/dev/null 2>&1
        ns ip route flush table "$TABLE" >/dev/null 2>&1
    fi
    if [[ "$host_route_added" -eq 1 ]]; then
        ip route del "$TARGET_CIDR" via "$ROU_ADDR" dev "$HOST_IF" >/dev/null 2>&1
    fi
    if [[ -n "$rou_pid" ]] && kill -0 "$rou_pid" 2>/dev/null; then
        [[ "$frozen" -eq 1 ]] && kill -CONT "$rou_pid" 2>/dev/null
        sleep 0.2
        kill -TERM "$rou_pid" 2>/dev/null
        wait "$rou_pid" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

wait_for() {
    local timeout=$1; shift
    local end=$((SECONDS + timeout))
    while ((SECONDS < end)); do
        "$@" && return 0
        [[ -n "$rou_pid" ]] && ! kill -0 "$rou_pid" 2>/dev/null && return 1
        sleep 0.2
    done
    return 1
}

both_clients() {
    local u
    u="$(occtl -s "$OCCTL" show users 2>/dev/null || true)"
    grep -Eq '[[:space:]]pri[[:space:]].*AES-256-GCM.*connected' <<<"$u" &&
    grep -Eq '[[:space:]]sec[[:space:]].*AES-256-GCM.*connected' <<<"$u"
}

two_bindings() {
    python3 - "$STATE" <<'PY' >/dev/null 2>&1
import json, sys
a=json.load(open(sys.argv[1]))["admitted"]
assert len(a)==2
assert sorted(x["metric"] for x in a)==[10,20]
PY
}

lookup_dev() {
    ns ip -4 route get "$TARGET" from "$HOST_ADDR" iif "$ROU_IF" 2>/dev/null |
        awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'
}

ping_ok() {
    ping -I "$HOST_ADDR" -c 2 -W 2 "$TARGET" >/dev/null 2>&1
}

snapshot() {
    local n=$1
    ns ip -4 route show table "$TABLE" >"$OUT/$n-routes.txt" 2>&1 || true
    ns ip -j -4 route show table "$TABLE" >"$OUT/$n-routes.json" 2>&1 || true
    set +e
    ns ip -4 route get "$TARGET" from "$HOST_ADDR" iif "$ROU_IF" >"$OUT/$n-lookup.txt" 2>&1
    echo $? >"$OUT/$n-lookup.rc"
    ns ip -4 route get fibmatch "$TARGET" from "$HOST_ADDR" iif "$ROU_IF" >"$OUT/$n-fibmatch.txt" 2>&1
    echo $? >"$OUT/$n-fibmatch.rc"
    set -e
}

drop_count() {
    ns iptables-legacy -L FORWARD 1 -v -n -x | awk 'NR==3 {print $1}'
}

install_shadow() {
    ns ip route flush table "$TABLE" >/dev/null 2>&1 || true
    ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$A" proto "$PROTO" metric 10
    ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$B" proto "$PROTO" metric 20
    ns ip route add table "$TABLE" "$TARGET_CIDR" proto "$PROTO" metric "$UNAVAILABLE_METRIC" \
        nexthop dev "$A" weight 1 nexthop dev "$B" weight 1
    ns ip route add table "$TABLE" blackhole "$TARGET_CIDR" proto "$BH_PROTO" metric "$BLACKHOLE_METRIC"
}

[[ "$(id -u)" -eq 0 ]] || fail "run as root"
for x in ip ping python3 occtl systemctl iptables-legacy ss; do
    command -v "$x" >/dev/null || fail "missing $x"
done
[[ -f "$ROU" ]] || fail "missing $ROU"
systemctl is-active --quiet ocserv.service && fail "stop normal ocserv.service first"
ip netns list | awk '{print $1}' | grep -Fxq "$NS" && fail "$NS already exists"
ip link show "$HOST_IF" >/dev/null 2>&1 && fail "$HOST_IF already exists"
ip route show exact "$TARGET_CIDR" | grep -q . && fail "host exact route to $TARGET_CIDR already exists"
ss -H -ltn 'sport = :44443' | grep -q . && fail "TCP/44443 busy"
ss -H -lun 'sport = :44443' | grep -q . && fail "UDP/44443 busy"

python3 "$ROU" check >"$OUT/rou-check.txt"
python3 "$ROU" run >"$ROU_LOG" 2>&1 &
rou_pid=$!

rou_ready() {
    ip netns list | awk '{print $1}' | grep -Fxq "$NS" &&
    [[ -S "$OCCTL" ]]
}
wait_for 15 rou_ready || fail "ROU did not become ready"
if ! wait_for 120 both_clients; then
    occtl -s "$OCCTL" show users >"$OUT/users-failed.txt" 2>&1 || true
    ss -H -ltn 'sport = :44443' >"$OUT/listeners-tcp-failed.txt" 2>&1 || true
    ss -H -lun 'sport = :44443' >"$OUT/listeners-udp-failed.txt" 2>&1 || true
    tail -n 200 "$ROU_LOG" >"$OUT/rou-v0-tail-failed.txt" 2>&1 || true
    fail "pri/sec did not reach DTLS within 120s; inspect users-failed.txt and rou-v0-tail-failed.txt"
fi
wait_for 10 two_bindings || fail "two vpnsXX bindings not admitted"

cp "$STATE" "$OUT/state-before-freeze.json"
occtl -s "$OCCTL" show users >"$OUT/users.txt"
read -r A B < <(python3 - "$STATE" <<'PY'
import json, sys
a=sorted(json.load(open(sys.argv[1]))["admitted"], key=lambda x:x["metric"])
print(a[0]["ifname"], a[1]["ifname"])
PY
)
[[ "$A" == vpns* && "$B" == vpns* && "$A" != "$B" ]] || fail "unexpected A=$A B=$B"

kill -STOP "$rou_pid"
frozen=1
sleep 0.2
say "PASS B0: two real DTLS bindings A=$A B=$B; only controller frozen"

ns ip rule add priority "$RULE_PRIO" iif "$ROU_IF" to "$TARGET_CIDR" lookup "$TABLE"
rule_added=1
ip route add "$TARGET_CIDR" via "$ROU_ADDR" dev "$HOST_IF"
host_route_added=1

install_shadow
snapshot b1
[[ "$(lookup_dev)" == "$A" ]] || fail "B1 normal A did not win"
ping_ok || fail "B1 payload failed"
say "PASS B1: normal A wins above persistent shadow fallback"

ns ip route del table "$TABLE" "$TARGET_CIDR" dev "$A" proto "$PROTO" metric 10
snapshot b2
[[ "$(lookup_dev)" == "$B" ]] || fail "B2 normal B did not win after A demotion"
ping_ok || fail "B2 payload failed"
grep -q "metric $UNAVAILABLE_METRIC" "$OUT/b2-routes.txt" || fail "B2 shadow fallback disappeared"
say "PASS B2: demoting A removes only its normal route; B wins"

ns ip route del table "$TABLE" "$TARGET_CIDR" dev "$B" proto "$PROTO" metric 20
snapshot b3
selected="$(lookup_dev)"
[[ "$selected" == "$A" || "$selected" == "$B" ]] || fail "B3 no fallback member selected"
ping_ok || fail "B3 healthy common fallback did not carry payload"
say "PASS B3: common fallback carries real payload via $selected"

dead_if="$selected"
[[ "$dead_if" == "$A" ]] && healthy_if="$B" || healthy_if="$A"
ns iptables-legacy -I FORWARD 1 -i "$ROU_IF" -o "$dead_if" -d "$TARGET_CIDR" -j DROP
drop_added=1

ping_ok && fail "B4 selected blocked member $dead_if was transparently bypassed"
c1="$(drop_count)"
[[ "$c1" =~ ^[0-9]+$ && "$c1" -gt 0 ]] || fail "B4 DROP counter stayed zero"
say "PASS B4a: fixed flow hits blocked fallback member $dead_if and is not retried"

ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$healthy_if" proto "$PROTO" metric 1
[[ "$(lookup_dev)" == "$healthy_if" ]] || fail "B4 temporary normal healthy path did not win"
ping_ok || fail "B4 alternate path $healthy_if is not healthy"
ns ip route del table "$TABLE" "$TARGET_CIDR" dev "$healthy_if" proto "$PROTO" metric 1

[[ "$(lookup_dev)" == "$dead_if" ]] || fail "B4 fallback hash changed for fixed flow"
ping_ok && fail "B4 fixed flow succeeded after returning to blocked common fallback"
c2="$(drop_count)"
[[ "$c2" =~ ^[0-9]+$ && "$c2" -gt "$c1" ]] || fail "B4 DROP counter did not increase"

ns iptables-legacy -D FORWARD -i "$ROU_IF" -o "$dead_if" -d "$TARGET_CIDR" -j DROP
drop_added=0
ping_ok || fail "B4 payload did not recover after unblock"
say "PASS B4: alternate path is healthy; ECMP fallback does not retry failed selected member"

ns ip route add table "$TABLE" "$TARGET_CIDR" dev "$A" proto "$PROTO" metric 10
snapshot b5
[[ "$(lookup_dev)" == "$A" ]] || fail "B5 promoted A did not regain priority"
ping_ok || fail "B5 payload failed"
say "PASS B5: promotion restores normal A above unchanged shadow fallback"

ns ip route flush table "$TABLE"
ns ip route add table "$TABLE" default dev "$A" proto "$PROTO" metric 10
ns ip route add table "$TABLE" default dev "$B" proto "$PROTO" metric 20
ns ip route add table "$TABLE" default proto "$PROTO" metric "$UNAVAILABLE_METRIC" \
    nexthop dev "$A" weight 1 nexthop dev "$B" weight 1
ns ip route add table "$TABLE" blackhole default proto "$BH_PROTO" metric "$BLACKHOLE_METRIC"

[[ "$(lookup_dev)" == "$A" ]] || fail "B6 default A did not win"
ping_ok || fail "B6 default A payload failed"
ns ip route del table "$TABLE" default dev "$A" proto "$PROTO" metric 10
[[ "$(lookup_dev)" == "$B" ]] || fail "B6 default B did not win"
ping_ok || fail "B6 default B payload failed"
ns ip route del table "$TABLE" default dev "$B" proto "$PROTO" metric 20
selected="$(lookup_dev)"
[[ "$selected" == "$A" || "$selected" == "$B" ]] || fail "B6 default fallback not selected"
ping_ok || fail "B6 default fallback payload failed"
ns ip route del table "$TABLE" default proto "$PROTO" metric "$UNAVAILABLE_METRIC"
snapshot b6-blackhole
ping_ok && fail "B6 payload passed with only blackhole default"
say "PASS B6: real-VPN /0 ordering normal > common fallback > blackhole"

say "PHASE_B=PASS"
say "Artifacts: $OUT"
