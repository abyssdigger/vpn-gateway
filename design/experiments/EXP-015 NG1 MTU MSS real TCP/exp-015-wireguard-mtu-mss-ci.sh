#!/bin/sh
set -eu

ROU=vg-exp015-wgr
REMOTE=vg-exp015-wgp
TARGET=vg-exp015-wgt
HIF=exp15wh
RIF=host0
RUS=exp15wr
REMOTE_UNDERLAY=exp15ws
REMOTE_LAN=exp15wlan
TARGET_LAN=exp15wt
TCP_PORT=18081
TARGET_A=172.31.16.2
TARGET_B=172.31.16.3
TARGET_C=172.31.16.4
TARGET_D=172.31.16.5
TMP=/run/vpn-gate-exp015-wg-$$
CAPTURE="$TMP/tcpdump.txt"
CLAMP_CAPTURE="$TMP/clamp-tcpdump.txt"
TCP_LOG="$TMP/tcp-server.log"

cleanup() {
    set +e
    [ -n "${TCP_PID:-}" ] && kill "$TCP_PID" 2>/dev/null
    [ -n "${TCP_PID:-}" ] && wait "$TCP_PID" 2>/dev/null
    ip netns del "$TARGET" 2>/dev/null
    ip netns del "$REMOTE" 2>/dev/null
    ip netns del "$ROU" 2>/dev/null
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
wg genkey >"$TMP/remote.key"
wg pubkey <"$TMP/rou.key" >"$TMP/rou.pub"
wg pubkey <"$TMP/remote.key" >"$TMP/remote.pub"

for ns in "$ROU" "$REMOTE" "$TARGET"; do
    ip netns del "$ns" 2>/dev/null || true
    ip netns add "$ns"
    ip -n "$ns" link set lo up
done
ip link del "$HIF" 2>/dev/null || true

ip link add "$HIF" type veth peer name "$RIF"
ip link set "$RIF" netns "$ROU"
ip addr add 198.18.16.1/30 dev "$HIF"
ip link set "$HIF" up
ip -n "$ROU" addr add 198.18.16.2/30 dev "$RIF"
ip -n "$ROU" link set "$RIF" up

ip link add "$RUS" type veth peer name "$REMOTE_UNDERLAY"
ip link set "$RUS" netns "$ROU"
ip link set "$REMOTE_UNDERLAY" netns "$REMOTE"
ip -n "$ROU" addr add 192.0.2.2/30 dev "$RUS"
ip -n "$REMOTE" addr add 192.0.2.1/30 dev "$REMOTE_UNDERLAY"
ip -n "$ROU" link set "$RUS" up
ip -n "$REMOTE" link set "$REMOTE_UNDERLAY" up

ip link add "$REMOTE_LAN" type veth peer name "$TARGET_LAN"
ip link set "$REMOTE_LAN" netns "$REMOTE"
ip link set "$TARGET_LAN" netns "$TARGET"
ip -n "$REMOTE" addr add 172.31.16.1/24 dev "$REMOTE_LAN"
ip -n "$TARGET" addr add "$TARGET_A"/24 dev "$TARGET_LAN"
ip -n "$TARGET" addr add "$TARGET_B"/32 dev "$TARGET_LAN"
ip -n "$TARGET" addr add "$TARGET_C"/32 dev "$TARGET_LAN"
ip -n "$TARGET" addr add "$TARGET_D"/32 dev "$TARGET_LAN"
for n in 6 7 8 9 10 11; do
    ip -n "$TARGET" addr add "172.31.16.$n/32" dev "$TARGET_LAN"
done
ip -n "$REMOTE" link set "$REMOTE_LAN" up
ip -n "$TARGET" link set "$TARGET_LAN" up
ip -n "$TARGET" route add default via 172.31.16.1 dev "$TARGET_LAN"

ip -n "$ROU" link add wg0 type wireguard
ip -n "$REMOTE" link add wg0 type wireguard
ip -n "$ROU" addr add 10.23.16.1/30 dev wg0
ip -n "$REMOTE" addr add 10.23.16.2/30 dev wg0

ROU_PUB=$(cat "$TMP/rou.pub")
REMOTE_PUB=$(cat "$TMP/remote.pub")

cat "$TMP/rou.key" | ip netns exec "$ROU" wg set wg0     listen-port 51820     private-key /dev/stdin     peer "$REMOTE_PUB"     allowed-ips 10.23.16.2/32,172.31.16.0/24     endpoint 192.0.2.1:51820     persistent-keepalive 1

cat "$TMP/remote.key" | ip netns exec "$REMOTE" wg set wg0     listen-port 51820     private-key /dev/stdin     peer "$ROU_PUB"     allowed-ips 10.23.16.1/32     endpoint 192.0.2.2:51820     persistent-keepalive 1

ip -n "$ROU" link set wg0 up
ip -n "$REMOTE" link set wg0 up
ip -n "$ROU" route add "$TARGET_A"/32 dev wg0
ip -n "$ROU" route add "$TARGET_B"/32 dev wg0
ip -n "$ROU" route add "$TARGET_C"/32 dev wg0
ip -n "$ROU" route add "$TARGET_D"/32 dev wg0
for n in 6 7 8 9 10 11; do
    ip -n "$ROU" route add "172.31.16.$n/32" dev wg0
done

ip netns exec "$ROU" ping -I wg0 -c 2 -W 2 10.23.16.2 >/dev/null

ip netns exec "$ROU" sysctl -q -w net.ipv4.ip_forward=1
ip netns exec "$REMOTE" sysctl -q -w net.ipv4.ip_forward=1

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

ip netns exec "$REMOTE" nft -f - <<EOF
table ip exp15wgremote {
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

ip route replace "$TARGET_A"/32 via 198.18.16.2 dev "$HIF"
ip route replace "$TARGET_B"/32 via 198.18.16.2 dev "$HIF"
ip route replace "$TARGET_C"/32 via 198.18.16.2 dev "$HIF"
ip route replace "$TARGET_D"/32 via 198.18.16.2 dev "$HIF"
for n in 6 7 8 9 10 11; do
    ip route replace "172.31.16.$n/32" via 198.18.16.2 dev "$HIF"
done

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

ip netns exec "$TARGET" python3 "$TMP/tcp-server.py" "$TCP_PORT" >"$TCP_LOG" 2>&1 &
TCP_PID=$!
for _ in $(seq 1 20); do
    grep -q '^READY$' "$TCP_LOG" 2>/dev/null && break
    sleep 0.1
done
grep -q '^READY$' "$TCP_LOG" || {
    echo "FAIL: WireGuard target TCP server did not become ready" >&2
    cat "$TCP_LOG" >&2
    exit 1
}

H_MTU=$(cat "/sys/class/net/$HIF/mtu")
HOST0_MTU=$(ip netns exec "$ROU" cat /sys/class/net/"$RIF"/mtu)
ROU_WG_MTU=$(ip netns exec "$ROU" cat /sys/class/net/wg0/mtu)
REMOTE_WG_MTU=$(ip netns exec "$REMOTE" cat /sys/class/net/wg0/mtu)
TARGET_MTU=$(ip netns exec "$TARGET" cat /sys/class/net/"$TARGET_LAN"/mtu)
echo "MTU_HOST_VETH=$H_MTU"
echo "MTU_ROU_HOST0=$HOST0_MTU"
echo "MTU_ROU_WIREGUARD=$ROU_WG_MTU"
echo "MTU_REMOTE_WIREGUARD=$REMOTE_WG_MTU"
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

for target in "$TARGET_B" "$TARGET_C" "$TARGET_D"; do
    python3 "$TMP/tcp-client.py" "$target" "$TCP_PORT" 128 5 >/dev/null
done
echo "PASS PREFLIGHT: WireGuard mitigation targets are reachable before PMTU suppression"

ip netns exec "$ROU" nft add rule ip exp15wg output     oifname "$RIF" ip protocol icmp drop
ip netns exec "$REMOTE" nft add rule ip exp15wgremote output     oifname "$REMOTE_LAN" ip protocol icmp drop

set +e
timeout 12 python3 "$TMP/tcp-client.py" "$TARGET_B" "$TCP_PORT" 8388608 8     >"$TMP/blocked-client.log" 2>&1
BLOCKED_RC=$?
set -e

echo "PMTU_FEEDBACK_BLOCKED_TCP_RC=$BLOCKED_RC"
if [ "$BLOCKED_RC" -eq 0 ]; then
    echo "FAIL: WireGuard production-like path did not reproduce the expected PMTU black-hole" >&2
    exit 1
fi
echo "PASS B: WireGuard PMTU black-hole reproduced with ICMP feedback suppressed"
cat "$TMP/blocked-client.log"

# Variant 1: standard route-MTU clamp on every forwarded SYN/SYNACK.
ip netns exec "$ROU" nft add rule ip exp15wg forward \
    tcp flags syn tcp option maxseg size set rt mtu
set +e
timeout 12 python3 "$TMP/tcp-client.py" "$TARGET_C" "$TCP_PORT" 8388608 8 \
    >"$TMP/rtmtu-client.log" 2>&1
RTMTU_RC=$?
set -e
echo "RT_MTU_CLAMP_TCP_RC=$RTMTU_RC"
if [ "$RTMTU_RC" -eq 0 ]; then
    echo "OBSERVATION: nft rt-mtu clamp prevents WireGuard black-hole"
else
    echo "OBSERVATION: nft rt-mtu clamp is insufficient for WireGuard asymmetric forwarded path"
    cat "$TMP/rtmtu-client.log"
fi

# Variant 2: symmetric clamp to the concrete Device MTU in both directions.
ip netns exec "$ROU" nft flush chain ip exp15wg forward
DEVICE_MSS=$((ROU_WG_MTU - 40))
ip netns exec "$ROU" nft add rule ip exp15wg forward \
    iifname "$RIF" oifname "wg0" tcp flags syn \
    tcp option maxseg size set "$DEVICE_MSS"
ip netns exec "$ROU" nft add rule ip exp15wg forward \
    iifname "wg0" oifname "$RIF" tcp flags syn \
    tcp option maxseg size set "$DEVICE_MSS"

timeout 12 tcpdump -i "$HIF" -nn -vvv -s 0 -c 2 \
    "host $TARGET_D and tcp port $TCP_PORT and (tcp[tcpflags] & tcp-syn != 0)" \
    >"$CLAMP_CAPTURE" 2>&1 &
CLAMP_TCPDUMP_PID=$!
sleep 0.2
set +e
timeout 18 python3 "$TMP/tcp-client.py" "$TARGET_D" "$TCP_PORT" 8388608 15 \
    >"$TMP/device-clamp-client.log" 2>&1
DEVICE_CLAMP_RC=$?
set -e
wait "$CLAMP_TCPDUMP_PID" || true
echo "DEVICE_MTU_CLAMP_TCP_RC=$DEVICE_CLAMP_RC"
echo "DEVICE_MTU_CLAMP_MSS=$DEVICE_MSS"
echo "DEVICE_MTU_CLAMP_CAPTURE_BEGIN"
cat "$CLAMP_CAPTURE"
echo "DEVICE_MTU_CLAMP_CAPTURE_END"
CLAMP_MSS_VALUES=$(grep -o 'mss [0-9][0-9]*' "$CLAMP_CAPTURE" | awk '{print $2}' | tr '\n' ' ')
echo "DEVICE_MTU_CLAMP_MSS_VALUES=$CLAMP_MSS_VALUES"
if [ "$DEVICE_CLAMP_RC" -eq 0 ]; then
    echo "OBSERVATION: Device-MTU-40 WireGuard clamp succeeded"
else
    echo "OBSERVATION: Device-MTU-40 WireGuard clamp still failed"
    cat "$TMP/device-clamp-client.log"
fi

SWEEP_TARGETS="6 7 8 9 10 11"
SWEEP_EXTRA="12 20 32 40 60 100"
FIRST_WORKING_EXTRA=""
set -- $SWEEP_TARGETS
for extra in $SWEEP_EXTRA; do
    n=$1
    shift
    target="172.31.16.$n"
    candidate=$((ROU_WG_MTU - 40 - extra))

    ip netns exec "$ROU" nft flush chain ip exp15wg forward
    ip netns exec "$ROU" nft add rule ip exp15wg forward \
        iifname "$RIF" oifname "wg0" tcp flags syn \
        tcp option maxseg size set "$candidate"
    ip netns exec "$ROU" nft add rule ip exp15wg forward \
        iifname "wg0" oifname "$RIF" tcp flags syn \
        tcp option maxseg size set "$candidate"

    set +e
    timeout 12 python3 "$TMP/tcp-client.py" "$target" "$TCP_PORT" 8388608 8 \
        >"$TMP/sweep-$extra.log" 2>&1
    rc=$?
    set -e
    echo "MSS_SWEEP extra=$extra candidate=$candidate target=$target rc=$rc"
    if [ "$rc" -eq 0 ] && [ -z "$FIRST_WORKING_EXTRA" ]; then
        FIRST_WORKING_EXTRA=$extra
        echo "MSS_SWEEP_FIRST_WORKING_EXTRA=$extra"
        echo "MSS_SWEEP_FIRST_WORKING_MSS=$candidate"
    fi
done

[ -n "$FIRST_WORKING_EXTRA" ] || {
    echo "FAIL: no tested WireGuard MSS safety margin prevented the black-hole" >&2
    exit 1
}
echo "PASS C: WireGuard MSS sweep found a working safety margin"

# Remove experiment suppression/clamp before normal baseline capture.
ip netns exec "$ROU" nft flush chain ip exp15wg output
ip netns exec "$REMOTE" nft flush chain ip exp15wgremote output
ip netns exec "$ROU" nft flush chain ip exp15wg forward

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
echo "PASS A: production-like WireGuard large TCP round-trip succeeds"

