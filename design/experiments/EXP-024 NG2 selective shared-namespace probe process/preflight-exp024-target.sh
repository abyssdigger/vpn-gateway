#!/bin/sh
set -u

EXP024_NAMESPACES="vpng2-probe-rou vpng2-probe-pri vpng2-probe-alt"
EXP024_ROOT_LINKS="vpn0 pri0 alt0 altp0"
EXP023_RULE_PRIORITY=22023
EXP023_TABLE=6023
PING_COPY=/tmp/vpng2-ping-nocap

failures=0
warnings=0

pass() {
    printf 'PASS: %s\n' "$*"
}

warn() {
    warnings=$((warnings + 1))
    printf 'WARN: %s\n' "$*" >&2
}

fail() {
    failures=$((failures + 1))
    printf 'FAIL: %s\n' "$*" >&2
}

section() {
    printf '\n=== %s ===\n' "$*"
}

section "identity / platform"
printf 'DATE_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf 'HOSTNAME=%s\n' "$(hostname)"
printf 'KERNEL=%s\n' "$(uname -srmo)"

if [ "$(id -u)" -ne 0 ]; then
    fail "run preflight as root; exact nft/netns observations are required"
fi

if [ -r /etc/os-release ]; then
    . /etc/os-release
    printf 'OS_ID=%s\n' "${ID:-unknown}"
    printf 'OS_VERSION_ID=%s\n' "${VERSION_ID:-unknown}"
    printf 'OS_PRETTY_NAME=%s\n' "${PRETTY_NAME:-unknown}"
    if [ "${ID:-}" = "debian" ] && [ "\${VERSION_ID:-}" = "13" ]; then
        pass "target is Debian 13"
    else
        fail "EXP-024 target confirmation requires Debian 13"
    fi
else
    fail "/etc/os-release is unavailable"
fi

section "required tools"
for cmd in ip nft ping setpriv python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        printf '%-10s %s\n' "$cmd" "$(command -v "$cmd")"
    else
        fail "missing required command: $cmd"
    fi
done
command -v ip >/dev/null 2>&1 && ip -V 2>&1 || true
command -v nft >/dev/null 2>&1 && nft --version 2>&1 || true
command -v python3 >/dev/null 2>&1 && python3 --version 2>&1 || true
if command -v getcap >/dev/null 2>&1 && command -v ping >/dev/null 2>&1; then
    printf 'PING_FILE_CAPS=%s\n' "$(getcap "$(command -v ping)" 2>/dev/null || true)"
fi

section "current root-network snapshot"
printf '%s\n' '-- ip -br link --'
ip -br link 2>&1 || fail "cannot list root links"
printf '%s\n' '-- ip -4 route show table main --'
ip -4 route show table main 2>&1 || fail "cannot list root IPv4 routes"
printf '%s\n' '-- ip -4 rule show --'
ip -4 rule show 2>&1 || fail "cannot list root IPv4 RPDB"
printf '%s\n' '-- nft list tables --'
nft list tables 2>&1 || fail "cannot list nft tables"
printf '%s\n' '-- ip netns list --'
ip netns list 2>&1 || fail "cannot list network namespaces"

section "EXP-024 collision check"
for ns in $EXP024_NAMESPACES; do
    if ip netns list | awk '{print $1}' | grep -Fxq "$ns"; then
        fail "EXP-024 namespace already exists: $ns"
    else
        pass "namespace absent: $ns"
    fi
done

for ifname in $EXP024_ROOT_LINKS; do
    if ip link show dev "$ifname" >/dev/null 2>&1; then
        fail "EXP-024 temporary root link name already exists: $ifname"
    else
        pass "root link name free: $ifname"
    fi
done

if [ -e "$PING_COPY" ]; then
    warn "stale $PING_COPY exists; EXP-024 cleanup would remove it"
    ls -l "$PING_COPY" 2>&1 || true
else
    pass "no stale capability-free ping copy"
fi

section "known EXP-023 local leftovers"
rule_state=$(ip -4 rule show priority "$EXP023_RULE_PRIORITY" 2>/dev/null || true)
if [ -n "$rule_state" ]; then
    warn "EXP-023 RPDB priority $EXP023_RULE_PRIORITY is still occupied: $rule_state"
else
    pass "EXP-023 RPDB priority $EXP023_RULE_PRIORITY is clear"
fi

table_state=$(ip -4 route show table "$EXP023_TABLE" 2>/dev/null || true)
if [ -n "$table_state" ]; then
    warn "EXP-023 routing table $EXP023_TABLE is not empty"
    printf '%s\n' "$table_state"
else
    pass "EXP-023 routing table $EXP023_TABLE is empty"
fi

section "OpenConnect stand visibility (informational)"
for ifname in vpns00 vpns01; do
    if ip link show dev "$ifname" >/dev/null 2>&1; then
        printf '%s\n' "-- $ifname --"
        ip -br addr show dev "$ifname" 2>&1 || true
        printf 'IFINDEX=%s\n' "$(cat "/sys/class/net/$ifname/ifindex" 2>/dev/null || printf '?')"
    else
        warn "$ifname is absent; this does not block disposable EXP-024, but differs from yesterday's dual-OC stand"
    fi
done

section "remote EXP-023 cleanup reminder"
cat <<'EOF'
The server cannot inspect the remote pri host.
Before EXP-024, verify on pri that yesterday's temporary outage rule is absent:

  sudo iptables -S FORWARD | grep -F VPNG-EXP023 || true

Expected: no output.
EOF

section "result"
if [ "$failures" -ne 0 ]; then
    printf 'EXP_024_TARGET_PREFLIGHT=FAIL failures=%s warnings=%s\n' "$failures" "$warnings"
    exit 1
fi

if [ "$warnings" -ne 0 ]; then
    printf 'EXP_024_TARGET_PREFLIGHT=WARN failures=0 warnings=%s\n' "$warnings"
    exit 2
fi

printf 'EXP_024_TARGET_PREFLIGHT=PASS\n'
exit 0
