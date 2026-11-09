#!/usr/bin/env bash
set -u -o pipefail
export LC_ALL=C LANG=C

CONFIG=""
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHON_TREE="$(cd -- "$SCRIPT_DIR/../../RC3/code/python" && pwd -P)"
FAILS=0
DAEMON_PID=""
STOP_REQUESTED=0

usage() {
    cat <<'EOF'
Usage:
  sudo ./vpn-gateway-exp-007-rc3-live-smoke.sh --config PATH [--python-tree PATH]
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

for c in python3 ip iptables-save sysctl grep sed awk tar sha256sum uname hostname date; do
    command -v "$c" >/dev/null 2>&1 || {
        printf 'ERROR: required command not found: %s\n' "$c" >&2
        exit 2
    }
done

TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="vpn-gateway-exp-007-$TS"
mkdir -m 0700 "$OUT" || exit 2

log()  { printf '%s\n' "$*" | tee -a "$OUT/result.txt"; }
pass() { log "PASS: $*"; }
fail() { log "FAIL: $*"; FAILS=$((FAILS + 1)); }

cleanup_process() {
    if [[ -n "${DAEMON_PID:-}" ]] && kill -0 "$DAEMON_PID" 2>/dev/null; then
        kill -TERM "$DAEMON_PID" 2>/dev/null || true
        wait "$DAEMON_PID" 2>/dev/null || true
    fi
}
trap cleanup_process EXIT INT TERM

capture_phase() {
    local phase="$1"
    local dir="$OUT/$phase"
    mkdir -m 0700 "$dir"

    {
        printf 'utc=%s\n' "$(date -u +%FT%TZ)"
        printf 'ip_forward='
        cat /proc/sys/net/ipv4/ip_forward
        printf 'ipv6_all_forwarding='
        cat /proc/sys/net/ipv6/conf/all/forwarding
        printf 'ipv6_default_forwarding='
        cat /proc/sys/net/ipv6/conf/default/forwarding
        printf 'ipv6_default_disable_ipv6='
        cat /proc/sys/net/ipv6/conf/default/disable_ipv6
    } >"$dir/sysctl.txt" 2>&1

    ip -j addr show >"$dir/ip-addr.json" 2>"$dir/ip-addr.stderr" || true
    ip -j -N -4 route show table main >"$dir/routes-main.json" 2>"$dir/routes-main.stderr" || true
    ip -4 route show proto 201 >"$dir/routes-proto-201.txt" 2>&1 || true
    ip -4 route show proto 202 >"$dir/routes-proto-202.txt" 2>&1 || true
    iptables-save -t filter >"$dir/filter.save" 2>"$dir/filter.stderr" || true
    iptables-save -t nat >"$dir/nat.save" 2>"$dir/nat.stderr" || true
    {
        grep -E '(^:VPNG-|^-A .* (-j|-g) VPNG-)' "$dir/filter.save" || true
        grep -E '(^:VPNG-|^-A .* (-j|-g) VPNG-)' "$dir/nat.save" || true
    } >"$dir/vpng-firewall.txt"
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

active_owned_state_present() {
    [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "1" ]] || return 1
    local snap
    snap="$(iptables-save -t filter; iptables-save -t nat)" || return 1
    grep -q '^:VPNG-' <<<"$snap" || return 1
    [[ -n "$(ip -4 route show proto 201)" ]] || return 1
    [[ -n "$(ip -4 route show proto 202)" ]] || return 1
}

wait_active() {
    local i
    for i in $(seq 1 100); do
        kill -0 "$DAEMON_PID" 2>/dev/null || return 1
        if active_owned_state_present; then
            return 0
        fi
        sleep 0.1
    done
    return 1
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

: >"$OUT/result.txt"
log "EXP-007 RC3 live daemon lifecycle smoke"

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

if (
    cd "$PYTHON_TREE" &&
    python3 ./vpn-gatewayd.py --config "$CONFIG" --check-config
) >"$OUT/config-check.txt" 2>&1; then
    pass "H1 config boundary"
else
    fail "H1 config boundary"
    log "OVERALL=FAIL"
    exit 1
fi

RECONCILE_WAIT="$(
    python3 - "$CONFIG" <<'PY'
import math, sys, tomllib
with open(sys.argv[1], "rb") as f:
    doc = tomllib.load(f)
interval = float(doc.get("reconcile_interval", 10.0))
print(max(2, math.ceil(interval) + 2))
PY
)" || exit 2

(
    cd "$PYTHON_TREE" &&
    exec python3 ./vpn-gatewayd.py --config "$CONFIG"
) >"$OUT/daemon.log" 2>&1 &
DAEMON_PID=$!

if wait_active; then
    capture_phase active-initial
    pass "H2 startup materialization"
else
    capture_phase active-initial
    fail "H2 startup materialization"
    log "OVERALL=FAIL"
    exit 1
fi

sleep "$RECONCILE_WAIT"

if kill -0 "$DAEMON_PID" 2>/dev/null && active_owned_state_present; then
    capture_phase active-stable
    pass "H3 steady reconciliation"
else
    capture_phase active-stable
    fail "H3 steady reconciliation"
fi

STOP_REQUESTED=1
kill -TERM "$DAEMON_PID" 2>/dev/null || true
if wait "$DAEMON_PID"; then
    DAEMON_PID=""
else
    rc=$?
    DAEMON_PID=""
    fail "daemon graceful shutdown returned rc=$rc"
fi

capture_phase post

if [[ "$(cat /proc/sys/net/ipv4/ip_forward)" == "0" ]] &&
   firewall_clean &&
   routes_clean; then
    pass "H4 graceful cleanup"
else
    fail "H4 graceful cleanup"
fi

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
