#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run as root" >&2
    exit 1
fi

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
ID=exp018
NS=vpn-gate-exp018
HOST_IF=rouexp0
INSTANCE=/etc/vpn-gateway/instances/$ID.toml
ROUTER=/etc/vpn-gateway/routers/$ID.toml
STATE=/var/lib/vpn-gateway/$ID/state.json
SERVICE=rouvpn@$ID.service
STAMP=$(date -u +%Y%m%d-%H%M%SZ)
OUT="$PWD/exp-018-$STAMP"

mkdir -m 0700 "$OUT"

logrun() {
    name=$1
    shift
    {
        echo "+ $*"
        "$@"
    } >"$OUT/$name.txt" 2>&1
}

cleanup() {
    /usr/local/sbin/rou down "$ID" >/dev/null 2>&1 || true
    rm -f "$INSTANCE" "$ROUTER"
}
trap cleanup EXIT HUP INT TERM

"$ROOT/design/NG1/deploy/install.sh" >"$OUT/install.txt" 2>&1

cat >"$ROUTER" <<'EOF'
schema_version = 1

[device.oc]
enabled = true
expected_interfaces = ["vpns*/2"]
nat = "none"

[profile.corp]
enabled = true
direction = "outbound"
destinations = ["10.0.0.0/8"]
device_order = ["oc"]
EOF
chmod 0600 "$ROUTER"

cat >"$INSTANCE" <<EOF
schema_version = 1

[instance]
namespace = "$NS"
host_interface = "$HOST_IF"
host_address = "192.0.2.1/30"
inner_address = "192.0.2.2/30"
publication_bind_address = "0.0.0.0"
router_config = "$ROUTER"
state_file = "$STATE"
EOF
chmod 0600 "$INSTANCE"

logrun 01-check /usr/local/sbin/rou check "$ID"
logrun 02-up /usr/local/sbin/rou up "$ID"
logrun 03-is-active systemctl is-active "$SERVICE"
logrun 04-is-enabled systemctl is-enabled "$SERVICE"
logrun 05-show /usr/local/sbin/rou show "$ID"

grep -q '"policy_verified": true' "$OUT/05-show.txt" || {
    echo "FAIL: initial policy not verified" >&2
    exit 1
}

logrun 06-filter ip netns exec "$NS" iptables-legacy-save -t filter
for policy in ':INPUT DROP' ':FORWARD DROP' ':OUTPUT DROP'; do
    grep -q "$policy" "$OUT/06-filter.txt" || {
        echo "FAIL: missing $policy" >&2
        exit 1
    }
done

logrun 07-restart systemctl restart "$SERVICE"
sleep 1
logrun 08-show-after-restart /usr/local/sbin/rou show "$ID"
grep -q '"policy_verified": true' "$OUT/08-show-after-restart.txt" || {
    echo "FAIL: policy not verified after restart" >&2
    exit 1
}

MAINPID=$(systemctl show -p MainPID --value "$SERVICE")
[ "$MAINPID" -gt 1 ] || {
    echo "FAIL: invalid MainPID" >&2
    exit 1
}
kill -KILL "$MAINPID"

i=0
while [ "$i" -lt 20 ]; do
    if systemctl is-active --quiet "$SERVICE"; then
        NEWPID=$(systemctl show -p MainPID --value "$SERVICE")
        if [ "$NEWPID" -gt 1 ] && [ "$NEWPID" != "$MAINPID" ]; then
            break
        fi
    fi
    i=$((i + 1))
    sleep 1
done

logrun 09-show-after-sigkill /usr/local/sbin/rou show "$ID"
grep -q '"policy_verified": true' "$OUT/09-show-after-sigkill.txt" || {
    echo "FAIL: policy not verified after SIGKILL recovery" >&2
    exit 1
}

journalctl -u "$SERVICE" --no-pager -n 300 >"$OUT/10-journal.txt" 2>&1 || true

logrun 11-down /usr/local/sbin/rou down "$ID"
if ip netns list | grep -q "^$NS\b"; then
    echo "FAIL: namespace remains after down" >&2
    exit 1
fi
if ip link show dev "$HOST_IF" >/dev/null 2>&1; then
    echo "FAIL: host veth remains after down" >&2
    exit 1
fi
if systemctl is-enabled --quiet "$SERVICE"; then
    echo "FAIL: service remains enabled after down" >&2
    exit 1
fi

trap - EXIT HUP INT TERM
rm -f "$INSTANCE" "$ROUTER"

echo "EXP_018=PASS"
echo "Artifacts: $OUT"
