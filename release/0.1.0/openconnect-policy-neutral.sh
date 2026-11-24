#!/bin/sh
set -eu

# OpenConnect invokes this script inside the VPN-GATE managed network namespace.
# It configures only the VPN-owned tunnel interface address/link state. It does not
# install routes, RPDB rules, nftables state, NAT, DNS settings, or host-global state.

case "${reason:-}" in
    pre-init)
        exit 0
        ;;
    connect|reconnect)
        : "${TUNDEV:?OpenConnect did not provide TUNDEV}"
        : "${INTERNAL_IP4_ADDRESS:?OpenConnect did not provide INTERNAL_IP4_ADDRESS}"
        ip link set dev "$TUNDEV" up
        ip -4 addr replace "${INTERNAL_IP4_ADDRESS}/32" dev "$TUNDEV"
        ;;
    disconnect|attempt-reconnect)
        # OpenConnect owns the tunnel device lifecycle; do not mutate VPN-GATE policy here.
        ;;
esac

exit 0
