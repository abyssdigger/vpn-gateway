#!/bin/sh
set -eu

ROU=vg-exp015-rou
REMOTE=vg-exp015-oc
TARGET=vg-exp015-tgt
HIF=exp15h
RIF=host0
RUS=exp15s
REMOTE_UNDERLAY=exp15c
REMOTE_LAN=exp15lan
TARGET_LAN=exp15t
PORT=44443
USER=exp015
PASS=exp015-pass
TCP_PORT=18080
TARGET_A=172.31.15.2
TARGET_B=172.31.15.3
TMP=/run/vpn-gate-exp015-$$
CERT="$TMP/server-cert.pem"
KEY="$TMP/server-key.pem"
PASSFILE="$TMP/ocpasswd"
CONF="$TMP/ocserv.conf"
OCSERV_LOG="$TMP/ocserv.log"
OC_LOG="$TMP/openconnect.log"
OC_PID="$TMP/openconnect.pid"
TCP_LOG="$TMP/tcp-server.log"
CAPTURE="$TMP/tcpdump.txt"

cleanup() {
    set +e
    [ -n "${TCP_PID:-}" ] && kill "$TCP_PID" 2>/dev/null
    [ -n "${TCP_PID:-}" ] && wait "$TCP_PID" 2>/dev/null
    if [ -f "$OC_PID" ]; then
        kill "$(cat "$OC_PID")" 2>/dev/null
        wait "$(cat "$OC_PID")" 2>/dev/null
    fi
    [ -n "${OCSERV_PID:-}" ] && kill "$OCSERV_PID" 2>/dev/null
    [ -n "${OCSERV_PID:-}" ] && wait "$OCSERV_PID" 2>/dev/null
    ip netns del "$TARGET" 2>/dev/null
    ip netns del "$REMOTE" 2>/dev/null
    ip netns del "$ROU" 2>/dev/null
    ip link del "$HIF" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT INT TERM

for cmd in ip nft ocserv openconnect ocpasswd openssl base64 awk grep timeout tcpdump python3; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "FAIL: missing command $cmd" >&2
        exit 2
    }
done
[ "$(id -u)" -eq 0 ] || {
    echo "FAIL: EXP-015 requires root" >&2
    exit 2
}

mkdir -m 0750 "$TMP"
chgrp daemon "$TMP"

for ns in "$ROU" "$REMOTE" "$TARGET"; do
    ip netns del "$ns" 2>/dev/null || true
    ip netns add "$ns"
    ip -n "$ns" link set lo up
done
ip link del "$HIF" 2>/dev/null || true

# Host <-> production-like ROU payload boundary.
ip link add "$HIF" type veth peer name "$RIF"
ip link set "$RIF" netns "$ROU"
ip addr add 198.18.15.1/30 dev "$HIF"
ip link set "$HIF" up
ip -n "$ROU" addr add 198.18.15.2/30 dev "$RIF"
ip -n "$ROU" link set "$RIF" up

# ROU ocserv underlay <-> remote OpenConnect client.
ip link add "$RUS" type veth peer name "$REMOTE_UNDERLAY"
ip link set "$RUS" netns "$ROU"
ip link set "$REMOTE_UNDERLAY" netns "$REMOTE"
ip -n "$ROU" addr add 192.0.2.1/30 dev "$RUS"
ip -n "$REMOTE" addr add 192.0.2.2/30 dev "$REMOTE_UNDERLAY"
ip -n "$ROU" link set "$RUS" up
ip -n "$REMOTE" link set "$REMOTE_UNDERLAY" up

# Remote peer/router <-> remote LAN target.
ip link add "$REMOTE_LAN" type veth peer name "$TARGET_LAN"
ip link set "$REMOTE_LAN" netns "$REMOTE"
ip link set "$TARGET_LAN" netns "$TARGET"
ip -n "$REMOTE" addr add 172.31.15.1/29 dev "$REMOTE_LAN"
ip -n "$TARGET" addr add "$TARGET_A"/29 dev "$TARGET_LAN"
ip -n "$TARGET" addr add "$TARGET_B"/32 dev "$TARGET_LAN"
ip -n "$REMOTE" link set "$REMOTE_LAN" up
ip -n "$TARGET" link set "$TARGET_LAN" up
ip -n "$TARGET" route add default via 172.31.15.1 dev "$TARGET_LAN"

openssl req -x509 -newkey rsa:2048 -nodes     -keyout "$KEY" -out "$CERT" -days 1     -subj "/CN=192.0.2.1"     -addext "subjectAltName=IP:192.0.2.1"     >/dev/null 2>&1
chgrp daemon "$KEY" "$CERT"
chmod 0640 "$KEY" "$CERT"

printf '%s\n%s\n' "$PASS" "$PASS" | ocpasswd -c "$PASSFILE" "$USER" >/dev/null
chgrp daemon "$PASSFILE"
chmod 0640 "$PASSFILE"

cat >"$CONF" <<EOF
auth = "plain[passwd=$PASSFILE]"
tcp-port = $PORT
udp-port = $PORT
listen-host = 192.0.2.1
run-as-user = nobody
run-as-group = daemon
isolate-workers = false
log-level = 2
socket-file = $TMP/ocserv.sock
occtl-socket-file = $TMP/occtl.sock
pid-file = $TMP/ocserv.pid
server-cert = $CERT
server-key = $KEY
device = vpns
ipv4-network = 10.23.15.0
ipv4-netmask = 255.255.255.0
max-clients = 1
max-same-clients = 1
keepalive = 5
dpd = 5
mobile-dpd = 5
EOF

ip netns exec "$ROU" ocserv -f -c "$CONF" >"$OCSERV_LOG" 2>&1 &
OCSERV_PID=$!
sleep 1
kill -0 "$OCSERV_PID" 2>/dev/null || {
    echo "FAIL: ocserv exited" >&2
    cat "$OCSERV_LOG" >&2
    exit 1
}

PIN=$(openssl x509 -in "$CERT" -pubkey -noout |
    openssl pkey -pubin -outform DER 2>/dev/null |
    openssl dgst -sha256 -binary |
    base64 | tr -d '\n')

(
    printf '%s\n' "$PASS" |
    ip netns exec "$REMOTE" openconnect         --protocol=anyconnect         --user="$USER"         --passwd-on-stdin         --servercert="pin-sha256:$PIN"         --interface=oc0         --background         --pid-file="$OC_PID"         https://192.0.2.1:$PORT/
) >"$OC_LOG" 2>&1 || {
    echo "FAIL: OpenConnect startup" >&2
    cat "$OC_LOG" >&2
    exit 1
}

VPN_IF=""
for _ in $(seq 1 30); do
    VPN_IF=$(ip -n "$ROU" -o link show |
        awk -F': ' '$2 ~ /^vpns/ {sub(/@.*/, "", $2); print $2; exit}')
    [ -n "$VPN_IF" ] && ip -n "$REMOTE" link show oc0 >/dev/null 2>&1 && break
    sleep 1
done
[ -n "$VPN_IF" ] || {
    echo "FAIL: ocserv Device interface did not appear" >&2
    cat "$OCSERV_LOG" >&2
    exit 1
}
ip -n "$REMOTE" link show oc0 >/dev/null 2>&1 || {
    echo "FAIL: remote OpenConnect interface did not appear" >&2
    cat "$OC_LOG" >&2
    exit 1
}

# Production-like forwarding/NAT: ROU may translate into the Device, and the remote
# OpenConnect peer translates again toward its LAN. The final target therefore does not
# learn the VPN interface MTU from its own route.
ip netns exec "$ROU" sysctl -q -w net.ipv4.ip_forward=1
ip netns exec "$REMOTE" sysctl -q -w net.ipv4.ip_forward=1

ip netns exec "$ROU" nft -f - <<EOF
table ip exp15 {
    chain forward {
        type filter hook forward priority filter; policy accept;
    }
    chain output {
        type filter hook output priority filter; policy accept;
    }
    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        oifname "$VPN_IF" masquerade
    }
}
EOF

ip netns exec "$REMOTE" nft -f - <<EOF
table ip exp15remote {
    chain forward {
        type filter hook forward priority filter; policy accept;
    }
    chain output {
        type filter hook output priority filter; policy accept;
    }
    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        oifname "$REMOTE_LAN" masquerade
    }
}
EOF

ip -n "$ROU" route replace "$TARGET_A"/32 dev "$VPN_IF"
ip -n "$ROU" route replace "$TARGET_B"/32 dev "$VPN_IF"
ip route replace "$TARGET_A"/32 via 198.18.15.2 dev "$HIF"
ip route replace "$TARGET_B"/32 via 198.18.15.2 dev "$HIF"

cat >"$TMP/tcp-server.py" <<'PY'
import socket, struct, sys
port=int(sys.argv[1])
s=socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", port))
s.listen(5)
print("READY", flush=True)
while True:
    c,_=s.accept()
    with c:
        header=b""
        while len(header)<4:
            chunk=c.recv(4-len(header))
            if not chunk:
                break
            header+=chunk
        if len(header)!=4:
            continue
        length=struct.unpack("!I", header)[0]
        data=bytearray()
        while len(data)<length:
            chunk=c.recv(min(65536, length-len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data)!=length:
            continue
        c.sendall(struct.pack("!I", length))
        c.sendall(data)
PY

cat >"$TMP/tcp-client.py" <<'PY'
import hashlib, socket, struct, sys
addr=sys.argv[1]
port=int(sys.argv[2])
length=int(sys.argv[3])
timeout=float(sys.argv[4])
pattern=(b"VPN-GATE-EXP015-" * ((length // 16) + 1))[:length]
expected=hashlib.sha256(pattern).hexdigest()
s=socket.create_connection((addr,port), timeout=timeout)
s.settimeout(timeout)
s.sendall(struct.pack("!I", length))
s.sendall(pattern)
header=b""
while len(header)<4:
    chunk=s.recv(4-len(header))
    if not chunk:
        raise SystemExit("short reply header")
    header+=chunk
reply_len=struct.unpack("!I",header)[0]
data=bytearray()
while len(data)<reply_len:
    chunk=s.recv(min(65536, reply_len-len(data)))
    if not chunk:
        raise SystemExit("short reply body")
    data.extend(chunk)
actual=hashlib.sha256(data).hexdigest()
if reply_len != length or actual != expected:
    raise SystemExit("payload mismatch")
print(f"TCP_ROUNDTRIP_BYTES={length}")
print(f"TCP_ROUNDTRIP_SHA256={actual}")
PY

ip netns exec "$TARGET" python3 "$TMP/tcp-server.py" "$TCP_PORT" >"$TCP_LOG" 2>&1 &
TCP_PID=$!
for _ in $(seq 1 20); do
    grep -q '^READY$' "$TCP_LOG" 2>/dev/null && break
    sleep 0.1
done
grep -q '^READY$' "$TCP_LOG" || {
    echo "FAIL: target TCP server did not become ready" >&2
    cat "$TCP_LOG" >&2
    exit 1
}

H_MTU=$(cat "/sys/class/net/$HIF/mtu")
HOST0_MTU=$(ip netns exec "$ROU" cat /sys/class/net/"$RIF"/mtu)
ROU_VPN_MTU=$(ip netns exec "$ROU" cat /sys/class/net/"$VPN_IF"/mtu)
REMOTE_OC_MTU=$(ip netns exec "$REMOTE" cat /sys/class/net/oc0/mtu)
TARGET_MTU=$(ip netns exec "$TARGET" cat /sys/class/net/"$TARGET_LAN"/mtu)
echo "MTU_HOST_VETH=$H_MTU"
echo "MTU_ROU_HOST0=$HOST0_MTU"
echo "MTU_ROU_OPENC0=$ROU_VPN_MTU"
echo "MTU_REMOTE_OPENCONNECT=$REMOTE_OC_MTU"
echo "MTU_REMOTE_TARGET_LAN=$TARGET_MTU"

low=0
high=1472
while [ "$low" -lt "$high" ]; do
    mid=$(( (low + high + 1) / 2 ))
    if ping -I "$HIF" -M do -c 1 -W 1 -s "$mid" "$TARGET_A" >/dev/null 2>&1; then
        low=$mid
    else
        high=$((mid - 1))
    fi
done
echo "DF_MAX_ICMP_PAYLOAD=$low"
echo "DF_MAX_IP_PACKET=$((low + 28))"

timeout 12 tcpdump -i "$HIF" -nn -vvv -s 0 -c 2     "tcp port $TCP_PORT and (tcp[tcpflags] & tcp-syn != 0)"     >"$CAPTURE" 2>&1 &
TCPDUMP_PID=$!
sleep 0.2
python3 "$TMP/tcp-client.py" "$TARGET_A" "$TCP_PORT" 8388608 15
wait "$TCPDUMP_PID" || true

echo "TCP_MSS_CAPTURE_BEGIN"
cat "$CAPTURE"
echo "TCP_MSS_CAPTURE_END"
MSS_VALUES=$(grep -o 'mss [0-9][0-9]*' "$CAPTURE" | awk '{print $2}' | tr '\n' ' ')
echo "TCP_MSS_VALUES=$MSS_VALUES"
[ -n "$MSS_VALUES" ] || {
    echo "FAIL: no MSS values captured" >&2
    exit 1
}
echo "PASS A: production-like OpenConnect large TCP round-trip succeeds"

# Fresh target address and no prior transport to it. Suppress ROU-generated ICMP feedback
# toward the host to expose any dependence on PMTUD for host -> remote-LAN TCP.
ip netns exec "$ROU" nft add rule ip exp15 output     oifname "$RIF" ip protocol icmp drop

set +e
timeout 12 python3 "$TMP/tcp-client.py" "$TARGET_B" "$TCP_PORT" 8388608 8     >"$TMP/blocked-client.log" 2>&1
BLOCKED_RC=$?
set -e

echo "PMTU_FEEDBACK_BLOCKED_TCP_RC=$BLOCKED_RC"
if [ "$BLOCKED_RC" -eq 0 ]; then
    echo "OBSERVATION: production-like OpenConnect TCP completed with PMTU feedback blocked"
    echo "EXP_015_OPENCONNECT_PRODUCTION_PATH=PASS_NO_BLACKHOLE"
else
    echo "OBSERVATION: production-like OpenConnect TCP failed with PMTU feedback blocked"
    cat "$TMP/blocked-client.log"
    echo "EXP_015_OPENCONNECT_PRODUCTION_PATH=PASS_BLACKHOLE_REPRODUCED"
fi
