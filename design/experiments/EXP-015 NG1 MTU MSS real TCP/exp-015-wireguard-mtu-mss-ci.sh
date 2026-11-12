#!/bin/sh
set -eu

ROU=vg-exp015-wgr
SRV=vg-exp015-wgs
HIF=exp15wh
RIF=host0
RUS=exp15wr
SIF=exp15ws
TCP_PORT=18081
TARGET_A=10.99.16.1
TARGET_B=10.99.16.2
TMP=/run/vpn-gate-exp015-wg-$$
CAPTURE="$TMP/tcpdump.txt"
TCP_LOG="$TMP/tcp-server.log"

cleanup() {
    set +e
    [ -n "${TCP_PID:-}" ] && kill "$TCP_PID" 2>/dev/null
    [ -n "${TCP_PID:-}" ] && wait "$TCP_PID" 2>/dev/null
    ip netns del "$ROU" 2>/dev/null
    ip netns del "$SRV" 2>/dev/null
    ip link del "$HIF" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT INT TERM

for cmd in ip nft wg awk grep timeout tcpdump python3; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "FAIL: missing command $cmd" >&2
        exit 2
    }
done

[ "$(id -u)" -eq 0 ] || {
    echo "FAIL: EXP-015 WireGuard requires root" >&2
    exit 2
}

umask 077
mkdir -m 0700 "$TMP"
wg genkey >"$TMP/rou.key"
wg genkey >"$TMP/srv.key"
wg pubkey <"$TMP/rou.key" >"$TMP/rou.pub"
wg pubkey <"$TMP/srv.key" >"$TMP/srv.pub"

ip netns del "$ROU" 2>/dev/null || true
ip netns del "$SRV" 2>/dev/null || true
ip link del "$HIF" 2>/dev/null || true

ip netns add "$ROU"
ip netns add "$SRV"

ip link add "$HIF" type veth peer name "$RIF"
ip link set "$RIF" netns "$ROU"
ip addr add 198.18.16.1/30 dev "$HIF"
ip link set "$HIF" up
ip -n "$ROU" addr add 198.18.16.2/30 dev "$RIF"
ip -n "$ROU" link set "$RIF" up
ip -n "$ROU" link set lo up

ip link add "$RUS" type veth peer name "$SIF"
ip link set "$RUS" netns "$ROU"
ip link set "$SIF" netns "$SRV"
ip -n "$ROU" addr add 192.0.2.2/30 dev "$RUS"
ip -n "$SRV" addr add 192.0.2.1/30 dev "$SIF"
ip -n "$ROU" link set "$RUS" up
ip -n "$SRV" link set "$SIF" up
ip -n "$SRV" link set lo up

ip -n "$SRV" link add probe0 type dummy
ip -n "$SRV" addr add "$TARGET_A"/32 dev probe0
ip -n "$SRV" addr add "$TARGET_B"/32 dev probe0
ip -n "$SRV" link set probe0 up

ip -n "$ROU" link add wg0 type wireguard
ip -n "$SRV" link add wg0 type wireguard
ip -n "$ROU" addr add 10.23.16.1/30 dev wg0
ip -n "$SRV" addr add 10.23.16.2/30 dev wg0

ROU_PUB=$(cat "$TMP/rou.pub")
SRV_PUB=$(cat "$TMP/srv.pub")

cat "$TMP/rou.key" | ip netns exec "$ROU" wg set wg0     listen-port 51820     private-key /dev/stdin     peer "$SRV_PUB"     allowed-ips 10.23.16.2/32,"$TARGET_A"/32,"$TARGET_B"/32     endpoint 192.0.2.1:51820     persistent-keepalive 1

cat "$TMP/srv.key" | ip netns exec "$SRV" wg set wg0     listen-port 51820     private-key /dev/stdin     peer "$ROU_PUB"     allowed-ips 10.23.16.1/32     endpoint 192.0.2.2:51820     persistent-keepalive 1

ip -n "$ROU" link set wg0 up
ip -n "$SRV" link set wg0 up
ip -n "$ROU" route add "$TARGET_A"/32 dev wg0
ip -n "$ROU" route add "$TARGET_B"/32 dev wg0

ip netns exec "$ROU" ping -I wg0 -c 2 -W 2 10.23.16.2 >/dev/null

ip netns exec "$ROU" sysctl -q -w net.ipv4.ip_forward=1
ip netns exec "$ROU" nft -f - <<'EOF'
table ip exp15wg {
    chain forward {
        type filter hook forward priority filter; policy accept;
    }
    chain output {
        type filter hook output priority filter; policy accept;
    }
    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        oifname "wg0" masquerade
    }
}
EOF

ip route replace "$TARGET_A"/32 via 198.18.16.2 dev "$HIF"
ip route replace "$TARGET_B"/32 via 198.18.16.2 dev "$HIF"

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
pattern=(b"VPN-GATE-EXP015-WG-" * ((length // 19) + 1))[:length]
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

ip netns exec "$SRV" python3 "$TMP/tcp-server.py" "$TCP_PORT" >"$TCP_LOG" 2>&1 &
TCP_PID=$!
for _ in $(seq 1 20); do
    grep -q '^READY$' "$TCP_LOG" 2>/dev/null && break
    sleep 0.1
done
grep -q '^READY$' "$TCP_LOG" || {
    echo "FAIL: WireGuard TCP server did not become ready" >&2
    cat "$TCP_LOG" >&2
    exit 1
}

H_MTU=$(cat "/sys/class/net/$HIF/mtu")
HOST0_MTU=$(ip netns exec "$ROU" cat /sys/class/net/"$RIF"/mtu)
WG_MTU=$(ip netns exec "$ROU" cat /sys/class/net/wg0/mtu)
echo "MTU_HOST_VETH=$H_MTU"
echo "MTU_ROU_HOST0=$HOST0_MTU"
echo "MTU_WIREGUARD=$WG_MTU"

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
    echo "FAIL: no WireGuard MSS values captured" >&2
    exit 1
}
echo "PASS A: WireGuard baseline large TCP round-trip succeeds"

ip netns exec "$ROU" nft add rule ip exp15wg output     oifname "$RIF" ip protocol icmp drop

set +e
timeout 12 python3 "$TMP/tcp-client.py" "$TARGET_B" "$TCP_PORT" 8388608 8     >"$TMP/blocked-client.log" 2>&1
BLOCKED_RC=$?
set -e

echo "PMTU_FEEDBACK_BLOCKED_TCP_RC=$BLOCKED_RC"
if [ "$BLOCKED_RC" -eq 0 ]; then
    echo "OBSERVATION: WireGuard large TCP completed with ROU->host ICMP feedback blocked"
    echo "EXP_015_WIREGUARD_BASELINE=PASS_NO_BLACKHOLE"
else
    echo "OBSERVATION: WireGuard large TCP failed with ROU->host ICMP feedback blocked"
    cat "$TMP/blocked-client.log"
    echo "EXP_015_WIREGUARD_BASELINE=PASS_BLACKHOLE_REPRODUCED"
fi
