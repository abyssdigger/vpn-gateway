#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

for tool in python3 ip nft systemctl; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf '%s\n' "missing required tool: $tool" >&2
        exit 1
    }
done

VERSION=$(tr -d '\n\r' < "$ROOT/VERSION")
[ -n "$VERSION" ] || {
    printf '%s\n' "empty VERSION" >&2
    exit 1
}

install -d -m 0755 /usr/lib/vpn-gate-alpha
rm -rf /usr/lib/vpn-gate-alpha/rou
cp -a "$ROOT/rou" /usr/lib/vpn-gate-alpha/rou
install -m 0644 "$ROOT/VERSION" /usr/lib/vpn-gate-alpha/VERSION
install -m 0755 "$ROOT/openconnect-policy-neutral.sh" \
    /usr/lib/vpn-gate-alpha/openconnect-policy-neutral.sh
install -m 0755 "$ROOT/vpn-gate-control" /usr/sbin/vpn-gate-control

install -d -m 0755 /etc/vpn-gate-alpha
if [ ! -e /etc/vpn-gate-alpha/config.toml ]; then
    install -m 0644 "$ROOT/config.example.toml" /etc/vpn-gate-alpha/config.toml
fi

install -m 0644 "$ROOT/vpn-gate-alpha.service" \
    /etc/systemd/system/vpn-gate-alpha.service
install -d -m 0755 /usr/share/doc/vpn-gate
install -m 0644 "$ROOT/README.md" /usr/share/doc/vpn-gate/README.md
install -m 0644 "$ROOT/DEPLOYMENT.md" /usr/share/doc/vpn-gate/DEPLOYMENT.md

python3 -m compileall -q /usr/lib/vpn-gate-alpha/rou
systemctl daemon-reload

printf '%s\n' \
    "Installed VPN-GATE $VERSION." \
    "Edit /etc/vpn-gate-alpha/config.toml and prepare the VPN-specific systemd unit." \
    "Deployment guide: /usr/share/doc/vpn-gate/DEPLOYMENT.md"
