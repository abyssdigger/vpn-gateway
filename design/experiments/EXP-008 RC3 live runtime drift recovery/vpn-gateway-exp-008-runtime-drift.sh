#!/usr/bin/env bash
set -u -o pipefail
export LC_ALL=C LANG=C

CONFIG=""
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHON_TREE="$(cd -- "$SCRIPT_DIR/../../RC3/code/python" && pwd -P)"
FAILS=0
DAEMON_PID=""
WATCHER_PID=""
IN_CHAIN="EXP008-IN"
FWD_CHAIN="EXP008-FWD"

usage() {
    cat <<'EOF'
Usage:
  sudo ./vpn-gateway-exp-008-runtime-drift.sh --config PATH [--python-tree PATH]
EOF
}

while (($#)); do
    case "$1" in
        --config)
            [[ $# -ge 2 ]] || { usage; exit 2; }
            CONFIG="$2"; shift 2 ;;
        --python-tree)
            [[ $# -ge 2 ]] || { usage; exit 2; }
            PYTHON_TREE="$2"; shift 2 ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            printf 'ERROR: unknown argument: %s\n' "$1" >&2
            usage
            exit 2 ;;
    esac
done

[[ -n "$CONFIG" ]] || { printf 'ERROR: --config is required\n' >&2; exit 2; }
[[ ${EUID:-$(id -u)} -eq 0 ]] || { printf 'ERROR: run as root\n' >&2; exit 2; }
[[ -f "$PYTHON_TREE/vpn-gatewayd.py" ]] || {
    printf 'ERROR: RC3 entry point not found under %s\n' "$PYTHON_TREE" >&2
    exit 2
}

for c in python3 ip iptables iptables-save grep sed awk tar sha256sum uname hostname date seq; do
    command -v "$c" >/dev/null 2>&1 || {
        printf 'ERROR: required command not found: %s\n' "$c" >&2
        exit 2
    }
done

TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="vpn-gateway-exp-008-$TS"
mkdir -m 0700 "$OUT" || exit 2
: >"$OUT/result.txt"

log()  { printf '%s\n' "$*" | tee -a "$OUT/result.txt"; }
pass() { log "PASS: $*"; }
fail() { log "FAIL: $*"; FAILS=$((FAILS + 1)); }

remove_jump_all() {
    local chain="$1" target="$2"
    while iptables -C "$chain" -j "$target" 2>/dev/null; do
        iptables -D "$chain" -j "$target" 2>/dev/null || break
    done
}

cleanup_foreign() {
    set +u
    remove_jump_all INPUT "$IN_CHAIN"
    remove_jump_all FORWARD "$FWD_CHAIN"
    iptables -F "$IN_CHAIN" 2>/dev/null || true
    iptables -X "$IN_CHAIN" 2>/dev/null || true
    iptables -F "$FWD_CHAIN" 2>/dev/null || true
    iptables -X "$FWD_CHAIN" 2>/dev/null || true
}

cleanup_all() {
    set +u
    if [[ -n "${WATCHER_PID:-}" ]]; then
        kill "$WATCHER_PID" 2>/dev/null || true
        wait "$WATCHER_PID" 2>/dev/null || true
    fi
    if [[ -n "${DAEMON_PID:-}" ]] && kill -0 "$DAEMON_PID" 2>/dev/null; then
        kill -TERM "$DAEMON_PID" 2>/dev/null || true
        wait "$DAEMON_PID" 2>/dev/null || true
    fi
    cleanup_foreign
}
trap cleanup_all EXIT INT TERM

capture_phase() {
    local phase="$1"
    local dir="$OUT/$phase"
    mkdir -m 0700 "$dir"
    {
        printf 'utc=%s\n' "$(date -u +%FT%TZ)"
        printf 'ip_forward='
        cat /proc/sys/net/ipv4/ip_forward
    } >"$dir/state.txt"
    ip -j addr show >"$dir/ip-addr.json" 2>"$dir/ip-addr.stderr" || true
    ip -4 route show proto 201 >"$dir/routes-proto-201.txt" 2>&1 || true
    ip -4 route show proto 202 >"$dir/routes-proto-202.txt" 2>&1 || true
    iptables-save -t filter >"$dir/filter.save" 2>"$dir/filter.stderr" || true
    iptables-save -t nat >"$dir/nat.save" 2>"$dir/nat.stderr" || true
}

firewall_clean() {
    local snap
    snap="$(iptables-save -t filter; iptables-save -t nat)" || return 1
    ! grep -Eq '(^:VPNG-|^-A .* (-j|-g) VPNG-)' <<<"$snap"
}

routes_clean() {
    [[ -z "$(ip -4 route show proto 201)" ]] &&
    [[ -z "$(ip -4 route show proto 202)" ]]
}

daemon_active_state() {
    kill -0 "$DAEMON_PID" 2>/dev/null || return 1
    [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "1" ]] || return 1
    [[ -n "$(ip -4 route show proto 201)" ]] || return 1
    [[ -n "$(ip -4 route show proto 202)" ]] || return 1
    local snap
    snap="$(iptables-save -t filter; iptables-save -t nat)" || return 1
    grep -q '^:VPNG-' <<<"$snap"
}

wait_until() {
    local timeout_tenths="$1"; shift
    local i
    for i in $(seq 1 "$timeout_tenths"); do
        "$@" && return 0
        sleep 0.1
    done
    return 1
}

input_prefix() {
    iptables-save -t filter | awk '/^-A INPUT / && / (-j|-g) VPNG-/ {print}'
}

forward_prefix() {
    iptables-save -t filter | awk '/^-A FORWARD / && / (-j|-g) VPNG-/ {print}'
}

prefix_is_first() {
    local chain="$1" baseline="$2"
    local n actual
    n="$(printf '%s\n' "$baseline" | sed '/^$/d' | wc -l)"
    actual="$(
        iptables-save -t filter |
        awk -v c="$chain" '$1=="-A" && $2==c {print}' |
        head -n "$n"
    )"
    [[ "$actual" == "$baseline" ]]
}

foreign_after_prefix() {
    local chain="$1" target="$2" baseline="$3"
    local n pos
    n="$(printf '%s\n' "$baseline" | sed '/^$/d' | wc -l)"
    pos="$(
        iptables-save -t filter |
        awk -v c="$chain" -v t="$target" '
            $1=="-A" && $2==c {i++; if ($0 ~ (" -j " t "$")) {print i; exit}}
        '
    )"
    [[ -n "$pos" && "$pos" -gt "$n" ]]
}

forward_recovery_complete() {
    prefix_is_first FORWARD "$BASE_FORWARD" &&
    foreign_after_prefix FORWARD "$FWD_CHAIN" "$BASE_FORWARD" &&
    daemon_active_state
}

start_forward_watcher() {
    local file="$1" stopfile="$2"
    : >"$file"
    rm -f "$stopfile"
    (
        while [[ ! -e "$stopfile" ]]; do
            printf '%s %s\n' "$(date +%s.%N)" "$(cat /proc/sys/net/ipv4/ip_forward)" >>"$file"
            sleep 0.01
        done
    ) &
    WATCHER_PID=$!
}

stop_forward_watcher() {
    local stopfile="$1"
    touch "$stopfile"
    wait "$WATCHER_PID" 2>/dev/null || true
    WATCHER_PID=""
}

{
    printf 'run_utc=%s\n' "$(date -u +%FT%TZ)"
    printf 'host=%s\n' "$(hostname -f 2>/dev/null || hostname)"
    printf 'os='
    sed -n 's/^PRETTY_NAME=//p' /etc/os-release | tr -d '"'
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'python=%s\n' "$(python3 --version 2>&1)"
    printf 'iptables=%s\n' "$(iptables --version 2>&1)"
    printf 'iproute2=%s\n' "$(ip -Version 2>&1)"
    printf 'config=%s\n' "$CONFIG"
    printf 'python_tree=%s\n' "$PYTHON_TREE"
    if command -v git >/dev/null 2>&1 && git -C "$PYTHON_TREE" rev-parse --show-toplevel >/dev/null 2>&1; then
        printf 'git_commit=%s\n' "$(git -C "$PYTHON_TREE" rev-parse HEAD)"
        printf 'git_status_begin\n'
        git -C "$PYTHON_TREE" status --short
        printf 'git_status_end\n'
    fi
} >"$OUT/environment.txt" 2>&1

log "EXP-008 RC3 live runtime drift recovery"
capture_phase pre

if [[ "$(cat /proc/sys/net/ipv4/ip_forward)" != "0" ]]; then
    fail "PRE requires net.ipv4.ip_forward=0"
fi
if ! firewall_clean; then
    fail "PRE contains existing VPNG firewall resources"
fi
if ! routes_clean; then
    fail "PRE contains existing proto-201/proto-202 routes"
fi
if (( FAILS != 0 )); then
    log "OVERALL=FAIL (precondition)"
    exit 1
fi

if ! (
    cd "$PYTHON_TREE" &&
    python3 ./vpn-gatewayd.py --config "$CONFIG" --check-config
) >"$OUT/config-check.txt" 2>&1; then
    fail "config boundary"
    log "OVERALL=FAIL"
    exit 1
fi

read -r RECONCILE_WAIT RECOVERY_TENTHS < <(
    python3 - "$CONFIG" <<'PY'
import math, sys, tomllib
with open(sys.argv[1], "rb") as f:
    doc = tomllib.load(f)
interval = float(doc.get("reconcile_interval", 10.0))
managed = doc.get("managed_vpns", [])
vpns = doc.get("vpn", {})
if not any(
    bool(vpns.get(pid, {}).get("peers", []))
    and bool(vpns.get(pid, {}).get("routes", []))
    for pid in managed
):
    raise SystemExit("EXP-008 requires a managed profile with peers and routes")
guard = math.ceil(interval) + 4
print(guard, guard * 10)
PY
) || exit 2

(
    cd "$PYTHON_TREE" &&
    exec python3 ./vpn-gatewayd.py --config "$CONFIG"
) >"$OUT/daemon.log" 2>&1 &
DAEMON_PID=$!

if wait_until 120 daemon_active_state; then
    capture_phase baseline-active
    pass "H1 live startup"
else
    capture_phase baseline-active
    fail "H1 live startup"
    log "OVERALL=FAIL"
    exit 1
fi

BASE_INPUT="$(input_prefix)"
BASE_FORWARD="$(forward_prefix)"
printf '%s\n' "$BASE_INPUT" >"$OUT/baseline-input-prefix.txt"
printf '%s\n' "$BASE_FORWARD" >"$OUT/baseline-forward-prefix.txt"

if [[ -z "$BASE_INPUT" || -z "$BASE_FORWARD" ]]; then
    fail "cannot capture daemon-owned INPUT/FORWARD prefixes"
    log "OVERALL=FAIL"
    exit 1
fi

# H2: delete one exact proto-202 route and wait for reconciliation.
ROUTE202="$(ip -4 route show proto 202 | head -n 1)"
if [[ -z "$ROUTE202" ]]; then
    fail "H2 no proto-202 route available for fault injection"
else
    printf '%s\n' "$ROUTE202" >"$OUT/h2-deleted-route.txt"
    read -r -a ROUTE_ARGS <<<"$ROUTE202"
    if ! ip -4 route del "${ROUTE_ARGS[@]}"; then
        fail "H2 failed to delete selected proto-202 route"
    elif wait_until "$RECOVERY_TENTHS" bash -c         'ip -4 route show proto 202 | grep -Fxq -- "$1"' _ "$ROUTE202"; then
        capture_phase h2-route-recovered
        if daemon_active_state; then
            pass "H2 proto-202 route recovery"
        else
            fail "H2 route returned but daemon ACTIVE state is incomplete"
        fi
    else
        capture_phase h2-route-timeout
        fail "H2 proto-202 route was not restored"
    fi
fi

# H3: foreign INPUT rule before prefix; narrow repair must keep forwarding on.
iptables -N "$IN_CHAIN" 2>/dev/null || true
iptables -F "$IN_CHAIN"
iptables -A "$IN_CHAIN" -j RETURN

IN_WATCH="$OUT/h3-ip-forward-watch.txt"
IN_STOP="$OUT/.h3-watch-stop"
start_forward_watcher "$IN_WATCH" "$IN_STOP"
iptables -I INPUT 1 -j "$IN_CHAIN"

if wait_until "$RECOVERY_TENTHS" prefix_is_first INPUT "$BASE_INPUT"; then
    stop_forward_watcher "$IN_STOP"
    capture_phase h3-input-repaired
    if grep -q ' 0$' "$IN_WATCH"; then
        fail "H3 INPUT-only repair observed ip_forward=0"
    elif ! foreign_after_prefix INPUT "$IN_CHAIN" "$BASE_INPUT"; then
        fail "H3 foreign INPUT jump was not preserved after daemon prefix"
    elif daemon_active_state; then
        pass "H3 INPUT-only narrow repair"
    else
        fail "H3 repaired INPUT prefix but daemon ACTIVE state is incomplete"
    fi
else
    stop_forward_watcher "$IN_STOP"
    capture_phase h3-input-timeout
    fail "H3 daemon-owned INPUT prefix was not restored"
fi

# H4: foreign FORWARD rule before prefix; heavy repair must cross forwarding=0.
iptables -N "$FWD_CHAIN" 2>/dev/null || true
iptables -F "$FWD_CHAIN"
iptables -A "$FWD_CHAIN" -j RETURN

FWD_WATCH="$OUT/h4-ip-forward-watch.txt"
FWD_STOP="$OUT/.h4-watch-stop"
start_forward_watcher "$FWD_WATCH" "$FWD_STOP"
iptables -I FORWARD 1 -j "$FWD_CHAIN"

if wait_until "$RECOVERY_TENTHS" forward_recovery_complete; then
    stop_forward_watcher "$FWD_STOP"
    capture_phase h4-forward-repaired
    if ! grep -q ' 0
kill -TERM "$DAEMON_PID" 2>/dev/null || true
if wait "$DAEMON_PID"; then
    DAEMON_PID=""
else
    rc=$?
    DAEMON_PID=""
    fail "daemon graceful shutdown returned rc=$rc"
fi

capture_phase post-daemon-cleanup

if [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "0" ]] &&
   firewall_clean &&
   routes_clean; then
    pass "H5 graceful cleanup"
else
    fail "H5 graceful cleanup"
fi

cleanup_foreign
capture_phase post-harness-cleanup

if (( FAILS == 0 )); then
    log "OVERALL=PASS"
    RC=0
else
    log "OVERALL=FAIL failures=$FAILS"
    RC=1
fi

tar -czf "$OUT.tar.gz" "$OUT"
sha256sum "$OUT.tar.gz" >"$OUT.tar.gz.sha256"
log "archive=$OUT.tar.gz"
log "sha256_file=$OUT.tar.gz.sha256"

exit "$RC"
 "$FWD_WATCH"; then
        fail "H4 FORWARD repair did not observe protective ip_forward=0"
    else
        pass "H4 FORWARD barrier repair"
    fi
else
    stop_forward_watcher "$FWD_STOP"
    capture_phase h4-forward-timeout
    if prefix_is_first FORWARD "$BASE_FORWARD"; then
        fail "H4 FORWARD prefix repaired but full ACTIVE recovery did not complete"
    else
        fail "H4 daemon-owned FORWARD prefix was not restored"
    fi
fi

kill -TERM "$DAEMON_PID" 2>/dev/null || true
if wait "$DAEMON_PID"; then
    DAEMON_PID=""
else
    rc=$?
    DAEMON_PID=""
    fail "daemon graceful shutdown returned rc=$rc"
fi

capture_phase post-daemon-cleanup

if [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "0" ]] &&
   firewall_clean &&
   routes_clean; then
    pass "H5 graceful cleanup"
else
    fail "H5 graceful cleanup"
fi

cleanup_foreign
capture_phase post-harness-cleanup

if (( FAILS == 0 )); then
    log "OVERALL=PASS"
    RC=0
else
    log "OVERALL=FAIL failures=$FAILS"
    RC=1
fi

tar -czf "$OUT.tar.gz" "$OUT"
sha256sum "$OUT.tar.gz" >"$OUT.tar.gz.sha256"
log "archive=$OUT.tar.gz"
log "sha256_file=$OUT.tar.gz.sha256"

exit "$RC"
