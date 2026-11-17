#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../../.." && pwd)

install -d -m 0755 /usr/lib/vpn-gate-alpha
rm -rf /usr/lib/vpn-gate-alpha/rou
cp -a "$ROOT/design/NG3/code/python/rou" /usr/lib/vpn-gate-alpha/rou

install -d -m 0755 /etc/vpn-gate-alpha
if [ ! -e /etc/vpn-gate-alpha/config.toml ]; then
    install -m 0644         "$ROOT/design/NG3/deployment/alpha/config.example.toml"         /etc/vpn-gate-alpha/config.toml
fi

install -m 0644     "$ROOT/design/NG3/deployment/alpha/vpn-gate-alpha.service"     /etc/systemd/system/vpn-gate-alpha.service

systemctl daemon-reload

printf '%s\n'     "Installed VPN-GATE alpha runtime."     "Edit /etc/vpn-gate-alpha/config.toml before starting."     "For a VPN service, use vpn-gate-alpha-openvpn.service.example as the stack-specific wrapper."
