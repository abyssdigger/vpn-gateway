#!/bin/sh
set -eu

SRV=vg-exp020-srv
CLI=vg-exp020-cli
SIF=exp20s
CIF=exp20c
PORT=44443
USER=exp020
PASS=exp020-pass
TMP=/run/vpn-gate-exp020-$$
CERT="$TMP/server-cert.pem"
KEY="$TMP/server-key.pem"
PASSFILE="$TMP/ocpasswd"
CONF="$TMP/ocserv.conf"
OCSERV_LOG="$TMP/ocserv.log"
OC_LOG="$TMP/openconnect.log"
OC_PID="$TMP/openconnect.pid"

cleanup() {
    set +e
    if [ -f "$OC_PID" ]; then
        kill "$(cat "$OC_PID")" 2>/dev/null
        wait "$(cat "$OC_PID")" 2>/dev/null
    fi
    [ -n "${OCSERV_PID:-}" ] && kill "$OCSERV_PID" 2>/dev/null
    [ -n "${OCSERV_PID:-}" ] && wait "$OCSERV_PID" 2>/dev/null
    ip netns del "$CLI" 2>/dev/null
    ip netns del "$SRV" 2>/dev/null
    ip link del "$SIF" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT INT TERM

for cmd in ip ocserv openconnect ocpasswd openssl base64 awk grep timeout; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "FAIL: missing command $cmd" >&2
        exit 2
    }
done

[ "$(id -u)" -eq 0 ] || {
    echo "FAIL: EXP-020 requires root" >&2
    exit 2
}

echo "STAGE 1: prepare temporary state"
mkdir -m 0700 "$TMP"

echo "STAGE 2: create disposable namespaces"
ip netns del "$CLI" 2>/dev/null || true
ip netns del "$SRV" 2>/dev/null || true
ip link del "$SIF" 2>/dev/null || true

ip netns add "$SRV"
ip netns add "$CLI"
ip link add "$SIF" type veth peer name "$CIF"
ip link set "$SIF" netns "$SRV"
ip link set "$CIF" netns "$CLI"

ip -n "$SRV" link set lo up
ip -n "$CLI" link set lo up
ip -n "$SRV" addr add 192.0.2.1/30 dev "$SIF"
ip -n "$CLI" addr add 192.0.2.2/30 dev "$CIF"
ip -n "$SRV" link set "$SIF" up
ip -n "$CLI" link set "$CIF" up

echo "STAGE 3: configure probe target"
ip -n "$SRV" link add probe0 type dummy
ip -n "$SRV" addr add 10.99.0.1/32 dev probe0
ip -n "$SRV" link set probe0 up

echo "STAGE 4: generate ephemeral credentials"
openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$KEY" -out "$CERT" -days 1 \
    -subj "/CN=192.0.2.1" \
    -addext "subjectAltName=IP:192.0.2.1" \
    >/dev/null 2>&1
chmod 0600 "$KEY" "$CERT"

echo "STAGE 5: create ocserv password database"
printf '%s\n%s\n' "$PASS" "$PASS" | ocpasswd -c "$PASSFILE" "$USER" >/dev/null
chmod 0600 "$PASSFILE"

echo "STAGE 6: write ocserv configuration"
cat >"$CONF" <<EOF
auth = "plain[passwd=$PASSFILE]"
tcp-port = $PORT
udp-port = $PORT
listen-host = 192.0.2.1
run-as-user = nobody
run-as-group = daemon
socket-file = $TMP/ocserv.sock
occtl-socket-file = $TMP/occtl.sock
pid-file = $TMP/ocserv.pid
server-cert = $CERT
server-key = $KEY
device = vpns
ipv4-network = 10.23.0.0
ipv4-netmask = 255.255.255.0
max-clients = 1
max-same-clients = 1
keepalive = 5
dpd = 5
mobile-dpd = 5
route = 10.99.0.1/255.255.255.255
EOF

echo "STAGE 7: start ocserv"
ip netns exec "$SRV" ocserv -f -c "$CONF" >"$OCSERV_LOG" 2>&1 &
OCSERV_PID=$!

sleep 1
if ! kill -0 "$OCSERV_PID" 2>/dev/null; then
    echo "FAIL: ocserv exited" >&2
    cat "$OCSERV_LOG" >&2
    exit 1
fi

echo "STAGE 8: compute certificate pin"
PIN=$(openssl x509 -in "$CERT" -pubkey -noout |
    openssl pkey -pubin -outform DER 2>/dev/null |
    openssl dgst -sha256 -binary |
    base64 | tr -d '\n')

echo "STAGE 9: start OpenConnect client"
set +e
(
    printf '%s\n' "$PASS" |
    ip netns exec "$CLI" openconnect \
        --protocol=anyconnect \
        --user="$USER" \
        --passwd-on-stdin \
        --servercert="pin-sha256:$PIN" \
        --interface=oc0 \
        --background \
        --pid-file="$OC_PID" \
        https://192.0.2.1:$PORT/
) >"$OC_LOG" 2>&1
OPENCONNECT_RC=$?
set -e
if [ "$OPENCONNECT_RC" -ne 0 ]; then
    echo "FAIL: OpenConnect startup returned $OPENCONNECT_RC" >&2
    cat "$OC_LOG" >&2
    exit 1
fi

echo "STAGE 10: wait for initial tunnel"
for _ in $(seq 1 30); do
    if ip -n "$CLI" link show oc0 >/dev/null 2>&1 &&
       ip netns exec "$CLI" ping -c 1 -W 1 10.99.0.1 >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! ip -n "$CLI" link show oc0 >/dev/null 2>&1; then
    echo "FAIL: OpenConnect interface oc0 did not appear" >&2
    cat "$OC_LOG" >&2
    exit 1
fi
if ! ip netns exec "$CLI" ping -c 1 -W 1 10.99.0.1 >/dev/null 2>&1; then
    echo "FAIL: initial tunnel probe did not succeed" >&2
    cat "$OC_LOG" >&2
    exit 1
fi

OLD_INDEX=$(ip -n "$CLI" -j link show oc0 |
    python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["ifindex"])')
CLIENT_PID=$(cat "$OC_PID")
echo "PASS A: OpenConnect tunnel established ifindex=$OLD_INDEX pid=$CLIENT_PID"

ip -n "$SRV" link set "$SIF" down
sleep 3

CLIENT_ALIVE=0
kill -0 "$CLIENT_PID" 2>/dev/null && CLIENT_ALIVE=1

IF_PRESENT=0
NEW_INDEX=
if ip -n "$CLI" link show oc0 >/dev/null 2>&1; then
    IF_PRESENT=1
    NEW_INDEX=$(ip -n "$CLI" -j link show oc0 |
        python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["ifindex"])')
fi

if ip netns exec "$CLI" ping -c 1 -W 1 10.99.0.1 >/dev/null 2>&1; then
    echo "FAIL: active tunnel probe succeeded while underlay was down" >&2
    exit 1
fi

echo "OUTAGE_CLIENT_ALIVE=$CLIENT_ALIVE"
echo "OUTAGE_INTERFACE_PRESENT=$IF_PRESENT"
echo "OUTAGE_OLD_IFINDEX=$OLD_INDEX"
echo "OUTAGE_CURRENT_IFINDEX=${NEW_INDEX:-absent}"
echo "PASS B: tunnel-bound active probe failed during outer outage"

ip -n "$SRV" link set "$SIF" up

RECOVERED=0
RECOVER_INDEX=
for _ in $(seq 1 45); do
    if ip -n "$CLI" link show oc0 >/dev/null 2>&1 &&
       ip netns exec "$CLI" ping -c 1 -W 1 10.99.0.1 >/dev/null 2>&1; then
        RECOVERED=1
        RECOVER_INDEX=$(ip -n "$CLI" -j link show oc0 |
            python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["ifindex"])')
        break
    fi
    sleep 1
done

if [ "$RECOVERED" -ne 1 ]; then
    echo "FAIL: OpenConnect data path did not recover after underlay restore" >&2
    echo "--- openconnect log ---" >&2
    cat "$OC_LOG" >&2
    echo "--- ocserv log ---" >&2
    cat "$OCSERV_LOG" >&2
    exit 1
fi

echo "RECOVERY_IFINDEX=$RECOVER_INDEX"
if [ "$RECOVER_INDEX" = "$OLD_INDEX" ]; then
    echo "OBSERVATION: recovery reused the same OpenConnect interface generation"
else
    echo "OBSERVATION: recovery used a different OpenConnect interface generation"
fi

echo "PASS C: active tunnel probe recovered"
echo "EXP_020_OPENCONNECT_AVAILABILITY_EVIDENCE=PASS"
