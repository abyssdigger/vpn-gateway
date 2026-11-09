#!/usr/bin/env bash
set -u -o pipefail
export LC_ALL=C LANG=C

FAILS=0
TMPDIR_EXP="$(mktemp -d /tmp/vpng-exp006.XXXXXX)"
NS_A="vpng-e6-a-$$"
NS_GW="vpng-e6-gw-$$"
NS_LAN="vpng-e6-lan-$$"
NS_DST="vpng-e6-dst-$$"
SERVER_PID=""
CLIENT_PID=""

log()  { printf '%s\n' "$*"; }
pass() { log "PASS: $*"; }
fail() { log "FAIL: $*"; FAILS=$((FAILS + 1)); }

cleanup() {
    set +u
    [[ -n "${CLIENT_PID:-}" ]] && kill "$CLIENT_PID" 2>/dev/null || true
    [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
    for ns in "$NS_A" "$NS_GW" "$NS_LAN" "$NS_DST"; do
        ip netns del "$ns" 2>/dev/null || true
    done
    rm -rf "$TMPDIR_EXP"
}
trap cleanup EXIT INT TERM

need() {
    command -v "$1" >/dev/null 2>&1 || {
        log "ERROR: required command not found: $1"
        exit 2
    }
}

ns() {
    local n="$1"; shift
    ip netns exec "$n" "$@"
}

for c in ip iptables iptables-save iptables-restore python3 grep awk sed sha256sum sysctl diff seq; do
    need "$c"
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    log "ERROR: run as root"
    exit 2
fi

IPT_VER="$(iptables --version 2>&1)"
log "EXP-006 target preflight"
log "  OS:       $(sed -n 's/^PRETTY_NAME=//p' /etc/os-release | tr -d '"')"
log "  kernel:   $(uname -r)"
log "  iptables: $IPT_VER"

if [[ "$IPT_VER" != *"(nf_tables)"* ]]; then
    log "ERROR: EXP-006 requires iptables-nft backend"
    exit 2
fi
if [[ "$IPT_VER" != *"v1.8.11"* ]]; then
    log "ERROR: expected target iptables v1.8.11; refusing to record a different target as EXP-006"
    exit 2
fi

log

###############################################################################
# EXP-006.1 — repeated declaration of existing chain under --noflush
###############################################################################
exp_006_1() {
    log "== EXP-006.1: existing chain replacement with --noflush =="

    ip netns add "$NS_A" || return 1
    ip -n "$NS_A" link set lo up || return 1

    cat <<'RULES' | ns "$NS_A" iptables-restore --noflush || return 1
*filter
:VPNG-INGRESS - [0:0]
:FOREIGN - [0:0]
-A FORWARD -j VPNG-INGRESS
-A FORWARD -j FOREIGN
-A VPNG-INGRESS -s 192.0.2.1/32 -j DROP
-A FOREIGN -s 198.51.100.1/32 -j DROP
COMMIT
RULES

    cat <<'RULES' | ns "$NS_A" iptables-restore --noflush || return 1
*filter
:VPNG-INGRESS - [0:0]
-A VPNG-INGRESS -s 192.0.2.2/32 -j REJECT --reject-with icmp-host-prohibited
COMMIT
RULES

    local s
    s="$(ns "$NS_A" iptables-save -t filter)" || return 1

    if grep -Fq -- '-A VPNG-INGRESS -s 192.0.2.1/32 -j DROP' <<<"$s"; then
        log "  old VPNG-INGRESS rule survived redeclaration"
        return 1
    fi
    grep -Fq -- '-A VPNG-INGRESS -s 192.0.2.2/32 -j REJECT --reject-with icmp-host-prohibited' <<<"$s" || {
        log "  replacement VPNG-INGRESS rule missing"
        return 1
    }
    grep -Fq -- '-A FORWARD -j FOREIGN' <<<"$s" || {
        log "  foreign FORWARD jump was lost"
        return 1
    }
    grep -Fq -- '-A FOREIGN -s 198.51.100.1/32 -j DROP' <<<"$s" || {
        log "  foreign chain/rule was lost"
        return 1
    }

    return 0
}

###############################################################################
# Shared topology for EXP-006.2 / EXP-006.3
###############################################################################
setup_topology() {
    ip netns add "$NS_GW" || return 1
    ip netns add "$NS_LAN" || return 1
    ip netns add "$NS_DST" || return 1

    ip link add e6g-lan type veth peer name e6l0 || return 1
    ip link set e6g-lan netns "$NS_GW" || return 1
    ip link set e6l0 netns "$NS_LAN" || return 1

    ip link add e6g-vpn type veth peer name e6d0 || return 1
    ip link set e6g-vpn netns "$NS_GW" || return 1
    ip link set e6d0 netns "$NS_DST" || return 1

    for nsn in "$NS_GW" "$NS_LAN" "$NS_DST"; do
        ip -n "$nsn" link set lo up || return 1
    done

    ip -n "$NS_GW" addr add 10.66.1.1/24 dev e6g-lan || return 1
    ip -n "$NS_GW" addr add 10.66.2.1/24 dev e6g-vpn || return 1
    ip -n "$NS_LAN" addr add 10.66.1.2/24 dev e6l0 || return 1
    ip -n "$NS_DST" addr add 10.66.2.2/24 dev e6d0 || return 1

    ip -n "$NS_GW" link set e6g-lan up || return 1
    ip -n "$NS_GW" link set e6g-vpn up || return 1
    ip -n "$NS_LAN" link set e6l0 up || return 1
    ip -n "$NS_DST" link set e6d0 up || return 1

    ip -n "$NS_LAN" route add default via 10.66.1.1 || return 1
    ip -n "$NS_DST" route add default via 10.66.2.1 || return 1

    ns "$NS_GW" sysctl -q -w net.ipv4.ip_forward=1 || return 1
    return 0
}

load_full_filter_initial() {
    cat <<'RULES' | ns "$NS_GW" iptables-restore || return 1
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:VPNG-OC-INPUT - [0:0]
:VPNG-INPUT-GUARD - [0:0]
:VPNG-INGRESS - [0:0]
:VPNG-RESERVED - [0:0]
:VPNG-OC-FORWARD - [0:0]
:VPNG-FORWARD-DENY - [0:0]
-A INPUT -j VPNG-OC-INPUT
-A INPUT -j VPNG-INPUT-GUARD
-A FORWARD -j VPNG-INGRESS
-A FORWARD -j VPNG-RESERVED
-A FORWARD -j VPNG-OC-FORWARD
-A FORWARD -j VPNG-FORWARD-DENY
-A VPNG-OC-INPUT -i e6g-vpn -m conntrack --ctstate INVALID -j DROP
-A VPNG-OC-INPUT -i e6g-vpn -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
-A VPNG-OC-INPUT -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-OC-INPUT -j RETURN
-A VPNG-INPUT-GUARD -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INPUT-GUARD -j RETURN
-A VPNG-INGRESS -i e6g-vpn -m conntrack --ctstate INVALID -j DROP
-A VPNG-INGRESS -i e6g-vpn -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
-A VPNG-INGRESS -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INGRESS -j RETURN
-A VPNG-RESERVED -j RETURN
-A VPNG-OC-FORWARD -s 10.66.1.2/32 -d 10.66.2.0/24 -o e6g-vpn -m conntrack --ctstate NEW,ESTABLISHED,RELATED -j ACCEPT
-A VPNG-OC-FORWARD -d 10.66.2.0/24 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-OC-FORWARD -j RETURN
-A VPNG-FORWARD-DENY -m conntrack --ctstate INVALID -j DROP
-A VPNG-FORWARD-DENY -j REJECT --reject-with icmp-host-prohibited
COMMIT
RULES
}

load_nat_initial() {
    cat <<'RULES' | ns "$NS_GW" iptables-restore || return 1
*nat
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
:VPNG-OC-NAT - [0:0]
-A POSTROUTING -j VPNG-OC-NAT
-A VPNG-OC-NAT -o e6g-vpn -m addrtype ! --src-type LOCAL -j MASQUERADE
-A VPNG-OC-NAT -j RETURN
COMMIT
RULES
}

apply_isolation_filter() {
    cat <<'RULES' | ns "$NS_GW" iptables-restore --noflush || return 1
*filter
:VPNG-OC-INPUT - [0:0]
:VPNG-INPUT-GUARD - [0:0]
:VPNG-INGRESS - [0:0]
:VPNG-RESERVED - [0:0]
:VPNG-OC-FORWARD - [0:0]
:VPNG-FORWARD-DENY - [0:0]
-A VPNG-OC-INPUT -j RETURN
-A VPNG-INPUT-GUARD -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INPUT-GUARD -j RETURN
-A VPNG-INGRESS -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INGRESS -j RETURN
-A VPNG-RESERVED -j RETURN
-A VPNG-OC-FORWARD -d 10.66.2.0/24 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-OC-FORWARD -j RETURN
-A VPNG-FORWARD-DENY -m conntrack --ctstate INVALID -j DROP
-A VPNG-FORWARD-DENY -j REJECT --reject-with icmp-host-prohibited
COMMIT
RULES
}

apply_full_filter_replace() {
    cat <<'RULES' | ns "$NS_GW" iptables-restore --noflush || return 1
*filter
:VPNG-OC-INPUT - [0:0]
:VPNG-INPUT-GUARD - [0:0]
:VPNG-INGRESS - [0:0]
:VPNG-RESERVED - [0:0]
:VPNG-OC-FORWARD - [0:0]
:VPNG-FORWARD-DENY - [0:0]
-A VPNG-OC-INPUT -i e6g-vpn -m conntrack --ctstate INVALID -j DROP
-A VPNG-OC-INPUT -i e6g-vpn -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
-A VPNG-OC-INPUT -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-OC-INPUT -j RETURN
-A VPNG-INPUT-GUARD -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INPUT-GUARD -j RETURN
-A VPNG-INGRESS -i e6g-vpn -m conntrack --ctstate INVALID -j DROP
-A VPNG-INGRESS -i e6g-vpn -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
-A VPNG-INGRESS -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INGRESS -j RETURN
-A VPNG-RESERVED -j RETURN
-A VPNG-OC-FORWARD -s 10.66.1.2/32 -d 10.66.2.0/24 -o e6g-vpn -m conntrack --ctstate NEW,ESTABLISHED,RELATED -j ACCEPT
-A VPNG-OC-FORWARD -d 10.66.2.0/24 -j REJECT --reject-with icmp-host-prohibited
-A VPNG-OC-FORWARD -j RETURN
-A VPNG-FORWARD-DENY -m conntrack --ctstate INVALID -j DROP
-A VPNG-FORWARD-DENY -j REJECT --reject-with icmp-host-prohibited
COMMIT
RULES
}

apply_input_only_repair() {
    cat <<'RULES' | ns "$NS_GW" iptables-restore --noflush || return 1
*filter
:VPNG-OC-INPUT - [0:0]
:VPNG-INPUT-GUARD - [0:0]
-D INPUT -j VPNG-OC-INPUT
-D INPUT -j VPNG-INPUT-GUARD
-I INPUT 1 -j VPNG-INPUT-GUARD
-I INPUT 1 -j VPNG-OC-INPUT
-A VPNG-OC-INPUT -i e6g-vpn -m conntrack --ctstate INVALID -j DROP
-A VPNG-OC-INPUT -i e6g-vpn -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
-A VPNG-OC-INPUT -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-OC-INPUT -j RETURN
-A VPNG-INPUT-GUARD -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited
-A VPNG-INPUT-GUARD -j RETURN
COMMIT
RULES
}

start_echo_server() {
    local logf="$TMPDIR_EXP/server.log"
    ip netns exec "$NS_DST" python3 -u - 23456 >"$logf" 2>&1 <<'PY' &
import socketserver, sys
port = int(sys.argv[1])
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        while True:
            data = self.request.recv(4096)
            if not data:
                return
            self.request.sendall(data)
class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
with Server(("10.66.2.2", port), Handler) as s:
    s.serve_forever()
PY
    SERVER_PID=$!
    sleep 0.3
    kill -0 "$SERVER_PID" 2>/dev/null || {
        log "  echo server failed:"
        cat "$logf"
        return 1
    }
}

tcp_once() {
    ns "$NS_LAN" python3 - 10.66.2.2 23456 <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket()
s.settimeout(1.5)
s.connect((host, port))
s.sendall(b"exp006")
data = s.recv(6)
s.close()
raise SystemExit(0 if data == b"exp006" else 1)
PY
}

start_persistent_client() {
    local logf="$1"
    : >"$logf"
    ip netns exec "$NS_LAN" python3 -u - 10.66.2.2 23456 >"$logf" 2>&1 <<'PY' &
import socket, sys, time
host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect((host, port))
except Exception as e:
    print(f"{time.time():.6f} FAIL connect {type(e).__name__}:{e}", flush=True)
    raise SystemExit(1)
seq = 0
while True:
    seq += 1
    payload = f"{seq:08d}".encode()
    try:
        s.sendall(payload)
        got = s.recv(len(payload))
        if got != payload:
            print(f"{time.time():.6f} FAIL short seq={seq} got={got!r}", flush=True)
            raise SystemExit(1)
        print(f"{time.time():.6f} OK seq={seq}", flush=True)
    except socket.timeout:
        print(f"{time.time():.6f} FAIL timeout seq={seq}", flush=True)
        time.sleep(0.1)
        continue
    except Exception as e:
        print(f"{time.time():.6f} FAIL io seq={seq} {type(e).__name__}:{e}", flush=True)
        raise SystemExit(1)
    time.sleep(0.1)
PY
    CLIENT_PID=$!
}

stop_client() {
    if [[ -n "$CLIENT_PID" ]]; then
        kill "$CLIENT_PID" 2>/dev/null || true
        wait "$CLIENT_PID" 2>/dev/null || true
        CLIENT_PID=""
    fi
}

wait_for_ok() {
    local f="$1" want="$2" i n
    for i in $(seq 1 60); do
        n="$(grep -c ' OK ' "$f" 2>/dev/null || true)"
        if (( n >= want )); then
            return 0
        fi
        sleep 0.1
    done
    return 1
}

normalize_iptables_save() {
    sed -E \
        -e '/^# Generated by iptables-save /d' \
        -e '/^# Completed on /d' \
        -e 's/\[[0-9]+:[0-9]+\]/[0:0]/g'
}

nat_snapshot() {
    ns "$NS_GW" iptables-save -t nat |
        normalize_iptables_save
}

forward_snapshot() {
    ns "$NS_GW" iptables-save -t filter |
        normalize_iptables_save |
        awk '
            /^:VPNG-(INGRESS|RESERVED|OC-FORWARD|FORWARD-DENY) / {print}
            /^-A FORWARD / {print}
            /^-A VPNG-(INGRESS|RESERVED|OC-FORWARD|FORWARD-DENY) / {print}
        '
}

host_probe_lan() {
    ns "$NS_LAN" python3 - 10.66.1.1 2222 <<'PY'
import socket, sys
s = socket.socket(); s.settimeout(0.7)
try:
    s.connect((sys.argv[1], int(sys.argv[2])))
except OSError:
    pass
finally:
    s.close()
PY
}

host_probe_vpn() {
    ns "$NS_DST" python3 - 10.66.2.1 2222 <<'PY'
import socket, sys
s = socket.socket(); s.settimeout(0.7)
try:
    s.connect((sys.argv[1], int(sys.argv[2])))
except OSError:
    pass
finally:
    s.close()
PY
}

foreign_packets() {
    ns "$NS_GW" iptables -L FOREIGN-F2B -v -n -x | awk 'NR > 2 {sum += $1} END {print sum + 0}'
}

###############################################################################
# EXP-006.2 — full -> isolation -> full
###############################################################################
exp_006_2() {
    log "== EXP-006.2: full -> isolation -> full =="

    load_full_filter_initial || return 1
    load_nat_initial || return 1
    start_echo_server || return 1

    tcp_once || {
        log "  baseline forwarded TCP failed"
        return 1
    }

    local client_log="$TMPDIR_EXP/client-0062.log"
    start_persistent_client "$client_log"
    wait_for_ok "$client_log" 5 || {
        log "  persistent flow did not establish"
        cat "$client_log"
        return 1
    }

    apply_isolation_filter || return 1

    if ns "$NS_GW" iptables -C VPNG-INGRESS -i e6g-vpn \
        -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null; then
        log "  exact established ACCEPT survived isolation replacement"
        ns "$NS_GW" iptables-save -t filter | sed -n '/^:VPNG-INGRESS /p;/^-A VPNG-INGRESS /p'
        return 1
    fi
    ns "$NS_GW" iptables -C VPNG-INGRESS -i e6g-vpn \
        -j REJECT --reject-with icmp-host-prohibited || {
        log "  isolation ingress REJECT missing"
        ns "$NS_GW" iptables-save -t filter | sed -n '/^:VPNG-INGRESS /p;/^-A VPNG-INGRESS /p'
        return 1
    }

    sleep 1.0
    if ! grep -q ' FAIL ' "$client_log"; then
        log "  established flow was not blocked by isolation"
        cat "$client_log"
        return 1
    fi

    stop_client
    apply_full_filter_replace || return 1

    ns "$NS_GW" iptables -C VPNG-INGRESS -i e6g-vpn \
        -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT || {
        log "  exact established ACCEPT missing after full restore"
        ns "$NS_GW" iptables-save -t filter | sed -n '/^:VPNG-INGRESS /p;/^-A VPNG-INGRESS /p'
        return 1
    }

    tcp_once || {
        log "  forwarded TCP did not recover after full restore"
        return 1
    }

    return 0
}

###############################################################################
# EXP-006.3 — narrow INPUT repair while forwarding remains active
###############################################################################
exp_006_3() {
    log "== EXP-006.3: INPUT-only repair with live forwarding =="

    apply_full_filter_replace || return 1

    local flow_log="$TMPDIR_EXP/client-0063.log"
    start_persistent_client "$flow_log"
    wait_for_ok "$flow_log" 8 || {
        log "  persistent flow did not establish"
        cat "$flow_log"
        return 1
    }

    local fwd_before nat_before ipf_before
    fwd_before="$(forward_snapshot)" || return 1
    nat_before="$(nat_snapshot)" || return 1
    ipf_before="$(ns "$NS_GW" sysctl -n net.ipv4.ip_forward)" || return 1
    [[ "$ipf_before" == "1" ]] || {
        log "  expected namespace ip_forward=1 before INPUT repair"
        return 1
    }

    ns "$NS_GW" iptables -N FOREIGN-F2B || return 1
    ns "$NS_GW" iptables -A FOREIGN-F2B -s 10.66.1.2/32 -p tcp --dport 2222 -j REJECT --reject-with tcp-reset || return 1
    ns "$NS_GW" iptables -A FOREIGN-F2B -j RETURN || return 1
    ns "$NS_GW" iptables -I INPUT 1 -p tcp --dport 2222 -j FOREIGN-F2B || return 1

    local first
    first="$(ns "$NS_GW" iptables-save -t filter | awk '/^-A INPUT / {print; exit}')"
    grep -Fq -- '-j FOREIGN-F2B' <<<"$first" || {
        log "  failed to create foreign INPUT drift at position 1"
        return 1
    }

    apply_input_only_repair || return 1
    sleep 0.8

    local input_rules
    input_rules="$(ns "$NS_GW" iptables-save -t filter | grep '^-A INPUT ')" || return 1
    local r1 r2 r3
    r1="$(sed -n '1p' <<<"$input_rules")"
    r2="$(sed -n '2p' <<<"$input_rules")"
    r3="$(sed -n '3p' <<<"$input_rules")"
    [[ "$r1" == '-A INPUT -j VPNG-OC-INPUT' ]] || {
        log "  INPUT rule #1 is not VPNG-OC-INPUT: $r1"
        return 1
    }
    [[ "$r2" == '-A INPUT -j VPNG-INPUT-GUARD' ]] || {
        log "  INPUT rule #2 is not VPNG-INPUT-GUARD: $r2"
        return 1
    }
    grep -Fq -- '-j FOREIGN-F2B' <<<"$r3" || {
        log "  foreign INPUT rule was not preserved after daemon prefix: $r3"
        return 1
    }

    local fwd_after nat_after ipf_after
    fwd_after="$(forward_snapshot)" || return 1
    nat_after="$(nat_snapshot)" || return 1
    ipf_after="$(ns "$NS_GW" sysctl -n net.ipv4.ip_forward)" || return 1

    [[ "$fwd_before" == "$fwd_after" ]] || {
        log "  FORWARD-related rule state changed during INPUT-only repair"
        diff -u <(printf '%s\n' "$fwd_before") <(printf '%s\n' "$fwd_after") || true
        return 1
    }
    [[ "$nat_before" == "$nat_after" ]] || {
        log "  NAT state changed during INPUT-only repair"
        diff -u <(printf '%s\n' "$nat_before") <(printf '%s\n' "$nat_after") || true
        return 1
    }
    [[ "$ipf_after" == "1" ]] || {
        log "  ip_forward changed during INPUT-only repair: $ipf_after"
        return 1
    }

    if grep -q ' FAIL ' "$flow_log"; then
        log "  live forwarded TCP saw a failure during INPUT-only repair"
        cat "$flow_log"
        return 1
    fi

    # Host filter still sees ordinary INPUT after our prefix.
    ns "$NS_GW" iptables -Z FOREIGN-F2B || return 1
    host_probe_lan || return 1
    sleep 0.1
    local c1 c2
    c1="$(foreign_packets)"
    [[ -n "$c1" && "$c1" -ge 1 ]] || {
        log "  foreign host filter did not see ordinary LAN INPUT after repair"
        return 1
    }

    # Managed VPN INPUT is rejected by VPNG rules before the foreign host filter.
    host_probe_vpn || return 1
    sleep 0.1
    c2="$(foreign_packets)"
    [[ "$c2" == "$c1" ]] || {
        log "  foreign host filter saw managed VPN ingress after daemon prefix (before=$c1 after=$c2)"
        return 1
    }

    # Also test drift inside daemon-owned INPUT chains, not only built-in jump order.
    ns "$NS_GW" iptables -F VPNG-INPUT-GUARD || return 1
    ns "$NS_GW" iptables -A VPNG-INPUT-GUARD -j RETURN || return 1
    apply_input_only_repair || return 1
    sleep 0.4
    ns "$NS_GW" iptables-save -t filter | grep -Fq -- '-A VPNG-INPUT-GUARD -i e6g-vpn -j REJECT --reject-with icmp-host-prohibited' || {
        log "  INPUT-only repair did not restore VPNG-INPUT-GUARD contents"
        return 1
    }

    if grep -q ' FAIL ' "$flow_log"; then
        log "  live forwarded TCP saw a failure while repairing daemon-owned INPUT chain"
        cat "$flow_log"
        return 1
    fi

    stop_client
    return 0
}

###############################################################################
# EXP-006.4 — failed restore must not partially mutate table
###############################################################################
exp_006_4() {
    log "== EXP-006.4: failed restore is transactionally clean =="

    cat <<'RULES' | ns "$NS_A" iptables-restore || return 1
*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:VPNG-INGRESS - [0:0]
-A FORWARD -j VPNG-INGRESS
-A VPNG-INGRESS -s 192.0.2.10/32 -j DROP
COMMIT
RULES

    local before after err rc
    before="$(ns "$NS_A" iptables-save -t filter)" || return 1

    err="$TMPDIR_EXP/restore-error.txt"
    cat <<'RULES' | ns "$NS_A" iptables-restore --noflush >"$err" 2>&1
*filter
:VPNG-INGRESS - [0:0]
-A VPNG-INGRESS -s 203.0.113.10/32 -j DROP
-A VPNG-INGRESS --definitely-invalid-option -j DROP
COMMIT
RULES
    rc=$?

    if (( rc == 0 )); then
        log "  intentionally invalid restore unexpectedly succeeded"
        cat "$err"
        return 1
    fi

    after="$(ns "$NS_A" iptables-save -t filter)" || return 1
    if [[ "$before" != "$after" ]]; then
        log "  table changed after failed restore"
        diff -u <(printf '%s\n' "$before") <(printf '%s\n' "$after") || true
        log "  restore stderr:"
        cat "$err"
        return 1
    fi

    log "  expected restore failure rc=$rc"
    sed 's/^/  stderr: /' "$err"
    return 0
}

###############################################################################
# Run
###############################################################################
if exp_006_1; then pass "EXP-006.1"; else fail "EXP-006.1"; fi
log

if setup_topology; then
    if exp_006_2; then pass "EXP-006.2"; else fail "EXP-006.2"; fi
    log
    if exp_006_3; then pass "EXP-006.3"; else fail "EXP-006.3"; fi
else
    fail "shared topology setup for EXP-006.2/3"
fi
log

if exp_006_4; then pass "EXP-006.4"; else fail "EXP-006.4"; fi
log

if (( FAILS == 0 )); then
    log "EXP-006 RESULT: PASS"
    exit 0
else
    log "EXP-006 RESULT: FAIL ($FAILS subexperiment(s))"
    exit 1
fi
