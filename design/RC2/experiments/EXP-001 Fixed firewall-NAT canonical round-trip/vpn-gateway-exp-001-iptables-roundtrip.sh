#!/bin/bash
set -euo pipefail

# VPN-GATE EXP-001
# Fixed firewall/NAT canonical round-trip on Debian 13 / iptables-nft.
#
# Safety model:
#   - host firewall is never modified;
#   - every apply/save cycle runs inside a disposable network namespace;
#   - namespaces are removed on normal exit and by EXIT trap;
#   - only filter + nat tables are exercised;
#   - no traffic is generated.
#
# Run:
#   sudo ./vpn-gateway-exp-001-iptables-roundtrip.sh
#
# The script creates:
#   vpn-gateway-exp-001-YYYYmmdd-HHMMSS/
#   vpn-gateway-exp-001-YYYYmmdd-HHMMSS.tar.gz

export LC_ALL=C
export LANG=C

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

for cmd in ip iptables iptables-save iptables-restore diff awk sed uname date tar sha256sum; do
    need_cmd "$cmd"
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    die "EXP-001 requires root/CAP_NET_ADMIN to create disposable network namespaces; run with sudo"
fi

STAMP="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="${PWD}/vpn-gateway-exp-001-${STAMP}"
mkdir -m 0700 "$OUT"

PAYLOAD="$OUT/payload.rules"
META="$OUT/environment.txt"
SUMMARY="$OUT/result.txt"

ACTIVE_NS=""

cleanup_ns() {
    if [[ -n "$ACTIVE_NS" ]]; then
        ip netns del "$ACTIVE_NS" >/dev/null 2>&1 || true
        ACTIVE_NS=""
    fi
}
trap cleanup_ns EXIT INT TERM HUP

cat >"$PAYLOAD" <<'RULES'
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:VPNG-INGRESS - [0:0]
:VPNG-RESERVED - [0:0]
:VPNG-BACKUP-INPUT - [0:0]
:VPNG-BACKUP-FORWARD - [0:0]
:VPNG-PRIMARY-INPUT - [0:0]
:VPNG-PRIMARY-FORWARD - [0:0]

-A INPUT -j VPNG-BACKUP-INPUT
-A INPUT -j VPNG-PRIMARY-INPUT

-A FORWARD -j VPNG-INGRESS
-A FORWARD -j VPNG-RESERVED
-A FORWARD -j VPNG-BACKUP-FORWARD
-A FORWARD -j VPNG-PRIMARY-FORWARD

-A VPNG-INGRESS -i wg0 -m conntrack --ctstate INVALID -j DROP
-A VPNG-INGRESS -i wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A VPNG-INGRESS -i wg0 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INGRESS -i vpns0 -m conntrack --ctstate INVALID -j DROP
-A VPNG-INGRESS -i vpns0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A VPNG-INGRESS -i vpns0 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INGRESS -j RETURN

-A VPNG-RESERVED -d 172.20.126.0/29 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-RESERVED -d 172.20.130.0/29 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-RESERVED -j RETURN

-A VPNG-BACKUP-INPUT -i wg0 -m conntrack --ctstate INVALID -j DROP
-A VPNG-BACKUP-INPUT -i wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A VPNG-BACKUP-INPUT -i wg0 -s 172.20.126.0/29 -d 172.20.126.1/32 -m conntrack --ctstate NEW -j ACCEPT
-A VPNG-BACKUP-INPUT -i wg0 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-BACKUP-INPUT -j RETURN

-A VPNG-PRIMARY-INPUT -i vpns0 -m conntrack --ctstate INVALID -j DROP
-A VPNG-PRIMARY-INPUT -i vpns0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A VPNG-PRIMARY-INPUT -i vpns0 -s 172.20.130.0/29 -d 172.20.130.1/32 -m conntrack --ctstate NEW -j ACCEPT
-A VPNG-PRIMARY-INPUT -i vpns0 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-PRIMARY-INPUT -j RETURN

-A VPNG-BACKUP-FORWARD -d 100.64.0.0/10 -o wg0 -m conntrack --ctstate INVALID -j DROP
-A VPNG-BACKUP-FORWARD -s 10.200.200.8/32 -d 100.64.0.0/10 -o wg0 -j ACCEPT
-A VPNG-BACKUP-FORWARD -d 100.64.0.0/10 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-BACKUP-FORWARD -d 192.168.0.0/16 -o wg0 -m conntrack --ctstate INVALID -j DROP
-A VPNG-BACKUP-FORWARD -s 10.200.200.8/32 -d 192.168.0.0/16 -o wg0 -j ACCEPT
-A VPNG-BACKUP-FORWARD -d 192.168.0.0/16 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-BACKUP-FORWARD -j RETURN

-A VPNG-PRIMARY-FORWARD -d 10.0.0.0/8 -o vpns0 -m conntrack --ctstate INVALID -j DROP
-A VPNG-PRIMARY-FORWARD -s 10.200.200.8/32 -d 10.0.0.0/8 -o vpns0 -j ACCEPT
-A VPNG-PRIMARY-FORWARD -s 10.200.201.0/24 -d 10.0.0.0/8 -o vpns0 -j ACCEPT
-A VPNG-PRIMARY-FORWARD -d 10.0.0.0/8 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-PRIMARY-FORWARD -j RETURN
COMMIT

*nat
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
:VPNG-BACKUP-NAT - [0:0]
:VPNG-PRIMARY-NAT - [0:0]

-A POSTROUTING -j VPNG-BACKUP-NAT
-A POSTROUTING -j VPNG-PRIMARY-NAT

-A VPNG-BACKUP-NAT -o wg0 -m addrtype ! --src-type LOCAL -j MASQUERADE
-A VPNG-BACKUP-NAT -j RETURN
-A VPNG-PRIMARY-NAT -o vpns0 -m addrtype ! --src-type LOCAL -j MASQUERADE
-A VPNG-PRIMARY-NAT -j RETURN
COMMIT
RULES

normalize_save() {
    # This is intentionally NOT the future daemon normalizer.
    # EXP-001 removes only volatile iptables-save comments and blank lines.
    # Any remaining difference is evidence that canonical text is not stable
    # enough for direct comparison and must be studied explicitly.
    awk '
        /^#/ { next }
        NF == 0 { next }
        { print }
    ' "$1" >"$2"
}

save_tables() {
    local ns="$1"
    local dst="$2"

    {
        ip netns exec "$ns" iptables-save -t filter
        ip netns exec "$ns" iptables-save -t nat
    } >"$dst"
}

new_namespace() {
    local label="$1"
    ACTIVE_NS="vpng-exp1-${label}-$$"
    ip netns add "$ACTIVE_NS"
}

drop_namespace() {
    cleanup_ns
}

apply_payload_and_save() {
    local label="$1"
    local source_rules="$2"
    local raw="$OUT/${label}.raw"
    local norm="$OUT/${label}.norm"

    new_namespace "$label"

    # --noflush is deliberate: this is the mode selected by RC2.
    ip netns exec "$ACTIVE_NS" iptables-restore --noflush <"$source_rules"

    save_tables "$ACTIVE_NS" "$raw"
    normalize_save "$raw" "$norm"

    drop_namespace
}

{
    printf 'experiment=EXP-001\n'
    printf 'utc_started=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'hostname=%s\n' "$(hostname 2>/dev/null || printf unknown)"
    printf 'kernel=%s\n' "$(uname -a)"
    printf 'debian_version=%s\n' "$(cat /etc/debian_version 2>/dev/null || printf unknown)"
    printf 'os_release_begin\n'
    cat /etc/os-release 2>/dev/null || true
    printf 'os_release_end\n'
    printf 'iptables=%s\n' "$(iptables --version 2>&1)"
    printf 'iptables_save=%s\n' "$(iptables-save --version 2>&1)"
    printf 'iptables_restore=%s\n' "$(iptables-restore --version 2>&1)"
    printf 'ip=%s\n' "$(ip -V 2>&1)"
    if command -v nft >/dev/null 2>&1; then
        printf 'nft=%s\n' "$(nft --version 2>&1)"
    fi
    printf 'iptables_path=%s\n' "$(command -v iptables)"
    if command -v update-alternatives >/dev/null 2>&1; then
        printf 'iptables_alternatives_begin\n'
        update-alternatives --display iptables 2>&1 || true
        printf 'iptables_alternatives_end\n'
    fi
    printf 'payload_sha256=%s\n' "$(sha256sum "$PAYLOAD" | awk '{print $1}')"
} >"$META"

# H1: same declarative payload, three fresh namespaces.
apply_payload_and_save "payload-run-1" "$PAYLOAD"
apply_payload_and_save "payload-run-2" "$PAYLOAD"
apply_payload_and_save "payload-run-3" "$PAYLOAD"

# H2: restore canonical save output into a fresh namespace, then save again.
# Use RAW save output: iptables-restore accepts iptables-save comments.
apply_payload_and_save "replay-save-1" "$OUT/payload-run-1.raw"

compare_pair() {
    local a="$1"
    local b="$2"
    local diff_file="$3"

    if diff -u "$a" "$b" >"$diff_file"; then
        printf 'PASS'
    else
        printf 'FAIL'
    fi
}

H1_12="$(compare_pair \
    "$OUT/payload-run-1.norm" \
    "$OUT/payload-run-2.norm" \
    "$OUT/diff-payload-1-vs-2.txt")"

H1_13="$(compare_pair \
    "$OUT/payload-run-1.norm" \
    "$OUT/payload-run-3.norm" \
    "$OUT/diff-payload-1-vs-3.txt")"

H2="$(compare_pair \
    "$OUT/payload-run-1.norm" \
    "$OUT/replay-save-1.norm" \
    "$OUT/diff-save-vs-replay.txt")"

if [[ "$H1_12" == PASS && "$H1_13" == PASS ]]; then
    H1=PASS
else
    H1=FAIL
fi

{
    printf 'EXP-001 fixed firewall/NAT canonical round-trip\n'
    printf 'H1 same payload on fresh namespaces: %s\n' "$H1"
    printf '  run1_vs_run2=%s\n' "$H1_12"
    printf '  run1_vs_run3=%s\n' "$H1_13"
    printf 'H2 save -> restore -> save: %s\n' "$H2"
    printf '\n'
    if [[ "$H1" == PASS && "$H2" == PASS ]]; then
        printf 'OVERALL=PASS\n'
        printf 'Interpretation: after removing only volatile comments/blank lines,\n'
        printf 'the daemon-owned filter+nat representation is text-stable in this test.\n'
        printf 'This supports a minimal canonical-text comparator for the tested subset.\n'
    else
        printf 'OVERALL=NEEDS_REVIEW\n'
        printf 'Interpretation: canonical text is not fully stable under the tested path.\n'
        printf 'Inspect the generated diff files before designing any normalizer/parser.\n'
    fi
} >"$SUMMARY"

ARCHIVE="${OUT}.tar.gz"
tar -C "$(dirname "$OUT")" -czf "$ARCHIVE" "$(basename "$OUT")"

printf '\nEXP-001 complete.\n'
cat "$SUMMARY"
printf '\nResult directory: %s\n' "$OUT"
printf 'Archive for review: %s\n' "$ARCHIVE"
