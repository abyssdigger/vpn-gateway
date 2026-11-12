#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: install.sh must run as root" >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC_ROU=$(CDPATH= cd -- "$SCRIPT_DIR/../code/python/rou" && pwd)

LIB_ROOT=/usr/local/lib/vpn-gateway
TARGET_ROU=$LIB_ROOT/rou
WRAPPER=/usr/local/sbin/rou
UNIT=/etc/systemd/system/rouvpn@.service

install -d -m 0755 "$LIB_ROOT"
install -d -m 0755 /usr/local/sbin
install -d -m 0755 /etc/vpn-gateway
install -d -m 0700 /etc/vpn-gateway/instances
install -d -m 0700 /etc/vpn-gateway/routers
install -d -m 0700 /var/lib/vpn-gateway

STAGE=$(mktemp -d "$LIB_ROOT/.rou-stage.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT HUP INT TERM
cp -a "$SRC_ROU" "$STAGE/rou"

OLD="$LIB_ROOT/.rou-old"
rm -rf "$OLD"
if [ -e "$TARGET_ROU" ]; then
    mv "$TARGET_ROU" "$OLD"
fi
mv "$STAGE/rou" "$TARGET_ROU"
rm -rf "$OLD"
rmdir "$STAGE"
trap - EXIT HUP INT TERM

find "$TARGET_ROU" -type d -exec chmod 0755 {} +
find "$TARGET_ROU" -type f -exec chmod 0644 {} +

install -m 0755 "$SCRIPT_DIR/rou" "$WRAPPER"
install -m 0644 "$SCRIPT_DIR/rouvpn@.service" "$UNIT"

systemctl daemon-reload

echo "Installed VPN-GATE NG1 ROU."
echo "Create /etc/vpn-gateway/instances/<id>.toml and router config, then run:"
echo "  rou check <id>"
echo "  rou up <id>"
