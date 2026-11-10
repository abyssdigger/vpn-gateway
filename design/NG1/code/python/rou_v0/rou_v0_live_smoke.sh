#!/usr/bin/env bash
set -euo pipefail

NS="vpn-gate-rou0"
HOST_IF="rouvpn0"
TARGET="172.21.201.19"
PORT="44443"
RUNTIME="/run/vpn-gateway-rou-v0"
OCCTL_SOCKET="$RUNTIME/occtl.sock"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROU="$SCRIPT_DIR/rou_v0.py"
OUTDIR="rou-v0-live-$(date -u +%Y%m%d-%H%M%SZ)"
mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"
LOG="$OUTDIR/rou.log"
RESULT="$OUTDIR/result.txt"
WATCH="$OUTDIR/forwarding-watch.txt"
rou_pid=""
watch_pid=""
route_added=0

say() { printf '%s\n' "$*" | tee -a "$RESULT"; }
fail() { say "FAIL: $*"; exit 1; }

cleanup() {
    set +e
    [[ -n "$watch_pid" ]] && kill "$watch_pid" 2>/dev/null
    if [[ -n "$rou_pid" ]] && kill -0 "$rou_pid" 2>/dev/null; then
        kill -TERM "$rou_pid" 2>/dev/null
        wait "$rou_pid" 2>/dev/null
    fi
    (( route_added )) && ip route del "$TARGET/32" via 192.0.2.2 dev "$HOST_IF" 2>/dev/null
    if systemctl list-unit-files ocserv.service >/dev/null 2>&1; then
        systemctl start ocserv.service >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

[[ "$(id -u)" -eq 0 ]] || fail "run as root"
for x in ip ss ping python3 occtl systemctl iptables-legacy; do command -v "$x" >/dev/null || fail "missing $x"; done
[[ -x "$ROU" ]] || chmod 700 "$ROU"

systemctl is-active --quiet ocserv.service && fail "stop normal ocserv.service before this harness"
ss -H -ltn "sport = :$PORT" | grep -q . && fail "TCP $PORT busy"
ss -H -lun "sport = :$PORT" | grep -q . && fail "UDP $PORT busy"
ip netns list | awk '{print $1}' | grep -Fxq "$NS" && fail "namespace $NS already exists"
ip link show "$HOST_IF" >/dev/null 2>&1 && fail "$HOST_IF already exists"
ip route show exact "$TARGET/32" | grep -q . && fail "host already has an exact route to $TARGET/32; refusing to overwrite it"

python3 "$ROU" check | tee "$OUTDIR/check.txt"
python3 "$ROU" run >"$LOG" 2>&1 &
rou_pid=$!

wait_until() {
    local timeout="$1"; shift
    local end=$((SECONDS + timeout))
    while (( SECONDS < end )); do
        if "$@"; then return 0; fi
        kill -0 "$rou_pid" 2>/dev/null || { tail -n 100 "$LOG" >&2; return 1; }
        sleep 0.2
    done
    return 1
}

rou_ready() {
    ip netns list | awk '{print $1}' | grep -Fxq "$NS" || return 1
    ip link show "$HOST_IF" >/dev/null 2>&1 || return 1
    ss -H -ltn "sport = :$PORT" | grep -q . || return 1
    ss -H -lun "sport = :$PORT" | grep -q . || return 1
    [[ -S "$OCCTL_SOCKET" ]] || return 1
}
wait_until 15 rou_ready || fail "ROU did not reach transport-ready state"
say "PASS H1: namespace/veth/ocserv/publication startup"

both_clients() {
    local u
    u="$(occtl -s "$OCCTL_SOCKET" show users 2>/dev/null || true)"
    grep -Eq '[[:space:]]pri[[:space:]].*connected' <<<"$u" || return 1
    grep -Eq '[[:space:]]sec[[:space:]].*connected' <<<"$u" || return 1
    grep -Eq '[[:space:]]pri[[:space:]].*AES-256-GCM.*connected' <<<"$u" || return 1
    grep -Eq '[[:space:]]sec[[:space:]].*AES-256-GCM.*connected' <<<"$u" || return 1
}
wait_until 40 both_clients || { occtl -s "$OCCTL_SOCKET" show users || true; fail "both clients did not reach DTLS"; }
occtl -s "$OCCTL_SOCKET" show users >"$OUTDIR/users-initial.txt"
say "PASS H2: both real OC clients connected with DTLS through multi-peer publication relay"

state_has_two() {
    python3 - <<'PY' >/dev/null 2>&1
import json
s=json.load(open('/run/vpn-gateway-rou-v0/state.json'))
assert len(s['admitted']) == 2
assert sorted(x['metric'] for x in s['admitted']) == [10,20]
PY
}
wait_until 10 state_has_two || fail "controller did not admit two bindings"
ip -n "$NS" route show table 100 >"$OUTDIR/routes-initial.txt"
ip -n "$NS" rule show >"$OUTDIR/rules-initial.txt"
ip netns exec "$NS" iptables-legacy-save >"$OUTDIR/firewall-initial.txt"

grep -q "blackhole $TARGET" "$OUTDIR/routes-initial.txt" || fail "protected blackhole missing"
grep -q 'blackhole default' "$OUTDIR/routes-initial.txt" || fail "terminal blackhole missing"
[[ "$(grep -c "^$TARGET dev vpns" "$OUTDIR/routes-initial.txt")" -eq 2 ]] || fail "expected two unicast binding routes"
say "PASS H3: two-path profile state + protected/terminal blackholes"

ip route add "$TARGET/32" via 192.0.2.2 dev "$HOST_IF"
route_added=1
ping -c 2 -W 2 "$TARGET" >"$OUTDIR/ping-initial.txt" || fail "payload path through ROU failed"
say "PASS H4: real payload forwarding through preferred OC binding"

pri_pid="$(occtl -s "$OCCTL_SOCKET" show users | awk '$2=="pri" {print $1; exit}')"
[[ "$pri_pid" =~ ^[0-9]+$ ]] || fail "could not identify pri worker pid"
kill -TERM "$pri_pid"

one_survivor() {
    python3 - <<'PY' >/dev/null 2>&1
import json
s=json.load(open('/run/vpn-gateway-rou-v0/state.json'))
a=s['admitted']
assert len(a) == 1
assert a[0]['metric'] == 20
PY
}
wait_until 8 one_survivor || fail "preferred interface disappearance was not committed with survivor metric preserved"
ping -c 1 -W 2 "$TARGET" >"$OUTDIR/ping-survivor.txt" || fail "survivor OC binding did not carry payload"
say "PASS H5: normal preferred-interface drop preserves survivor and payload failover"

wait_until 40 both_clients || fail "pri did not reconnect after normal worker drop"
wait_until 10 state_has_two || fail "reconnected binding was not admitted"
say "PASS H6: reconnected fresh binding returns without survivor churn"

mapfile -t worker_pids < <(occtl -s "$OCCTL_SOCKET" show users | awk '$2=="pri" || $2=="sec" {print $1}')
((${#worker_pids[@]} >= 2)) || fail "need two workers for zero-path phase"
kill -TERM "${worker_pids[@]}"
zero_paths() {
    python3 - <<'PY' >/dev/null 2>&1
import json
s=json.load(open('/run/vpn-gateway-rou-v0/state.json'))
assert len(s['admitted']) == 0
PY
}
wait_until 8 zero_paths || fail "zero-binding state was not observed"
ip -n "$NS" route show table 100 >"$OUTDIR/routes-zero.txt"
! grep -q "^$TARGET dev vpns" "$OUTDIR/routes-zero.txt" || fail "unicast route survived zero-path state"
grep -q "blackhole $TARGET" "$OUTDIR/routes-zero.txt" || fail "protected blackhole absent at zero paths"
grep -q 'blackhole default' "$OUTDIR/routes-zero.txt" || fail "terminal blackhole absent at zero paths"
if ping -c 1 -W 1 "$TARGET" >"$OUTDIR/ping-zero.txt" 2>&1; then fail "payload unexpectedly passed with zero bindings"; fi
say "PASS H7: zero-binding profile is explicitly fail-closed"

wait_until 40 both_clients || fail "clients did not reconnect after zero-path phase"
wait_until 10 state_has_two || fail "two bindings not restored after zero-path phase"

watch_forwarding() {
    : >"$WATCH"
    while true; do
        ip netns exec "$NS" sysctl -n net.ipv4.ip_forward 2>/dev/null >>"$WATCH" || true
        sleep 0.01
    done
}

watch_forwarding & watch_pid=$!
sleep 0.1
pref_if="$(python3 - <<'PY'
import json
s=json.load(open('/run/vpn-gateway-rou-v0/state.json'))
print(min(s['admitted'], key=lambda x:x['metric'])['ifname'])
PY
)"
ip -n "$NS" route del "$TARGET/32" dev "$pref_if" proto 202 metric 10
route_repaired() { ip -n "$NS" route show table 100 | grep -q "^$TARGET dev $pref_if .*proto 202 .*metric 10"; }
wait_until 8 route_repaired || fail "deleted owned route was not repaired"
sleep 0.1
kill "$watch_pid" 2>/dev/null || true; wait "$watch_pid" 2>/dev/null || true; watch_pid=""
grep -qx '0' "$WATCH" || fail "route drift repair did not expose forwarding barrier"
say "PASS H8: owned route drift repaired under ip_forward=0 barrier"

: >"$WATCH"; watch_forwarding & watch_pid=$!; sleep 0.1
ip netns exec "$NS" iptables-legacy -I FORWARD 1 -i host0 -j ACCEPT
fw_repaired() { ! ip netns exec "$NS" iptables-legacy-save | grep -q -- '-A FORWARD -i host0 -j ACCEPT'; }
wait_until 8 fw_repaired || fail "foreign firewall rule was not removed"
sleep 0.1
kill "$watch_pid" 2>/dev/null || true; wait "$watch_pid" 2>/dev/null || true; watch_pid=""
grep -qx '0' "$WATCH" || fail "firewall drift repair did not expose forwarding barrier"
say "PASS H9: owned firewall drift repaired under ip_forward=0 barrier"

ip -n "$NS" link del host0
set +e
wait "$rou_pid"
rou_rc=$?
set -e
rou_pid=""
[[ "$rou_rc" -ne 0 ]] || fail "controller exited success after structural infrastructure loss"
! ip netns list | awk '{print $1}' | grep -Fxq "$NS" || fail "namespace remained after integrity failure"
! ip link show "$HOST_IF" >/dev/null 2>&1 || fail "host veth remained after integrity failure"
! ss -H -ltn "sport = :$PORT" | grep -q . || fail "TCP publication remained after integrity failure"
! ss -H -lun "sport = :$PORT" | grep -q . || fail "UDP publication remained after integrity failure"
grep -q 'structural appliance integrity failure' "$LOG" || fail "integrity failure not logged"
say "PASS H10: structural namespace integrity loss isolates and tears down ROU"

say "OVERALL=PASS"
