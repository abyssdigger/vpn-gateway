from __future__ import annotations

import fcntl
from ipaddress import IPv4Address
import os
import struct
import subprocess

from rou.interface_identity import InterfaceIdentity
from rou.linux_vpn_path_adapter import LinuxVpnPathAdapter


TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000


class Runner:
    def run(self, argv):
        return subprocess.run(
            argv,
            check=True,
            text=True,
            capture_output=True,
        ).stdout


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("integration_vpn_path_private_peer requires root")
    if not os.path.exists("/dev/net/tun"):
        raise SystemExit("/dev/net/tun is unavailable")

    ns = f"ng3-peer-{os.getpid()}"
    tun_name = f"epp{os.getpid() % 10000}"
    local = IPv4Address("10.239.0.1")
    peer = IPv4Address("10.239.0.2")
    tun_fd = None

    run("ip", "netns", "add", ns)
    try:
        tun_fd = os.open("/dev/net/tun", os.O_RDWR)
        ifreq = struct.pack("16sH", tun_name.encode(), IFF_TUN | IFF_NO_PI)
        result = fcntl.ioctl(tun_fd, TUNSETIFF, ifreq)
        actual_name = result[:16].split(b"\0", 1)[0].decode()
        assert actual_name == tun_name, (actual_name, tun_name)

        run("ip", "link", "set", "dev", tun_name, "netns", ns)
        run("ip", "-n", ns, "link", "set", "dev", "lo", "up")
        run("ip", "-n", ns, "link", "set", "dev", tun_name, "up")
        run(
            "ip", "-n", ns, "addr", "add",
            f"{local}/32",
            "peer", f"{peer}/32",
            "dev", tun_name,
        )

        observed = LinuxVpnPathAdapter(
            Runner(),
            ns,
        ).observe_interfaces(require_private_peer=True)

        identity = next(
            item
            for item in observed.interfaces
            if item.ifname == tun_name
        )
        assert isinstance(identity, InterfaceIdentity)
        assert observed.private_peers[identity] == peer, observed.private_peers

        lo = next(
            item
            for item in observed.interfaces
            if item.ifname == "lo"
        )
        assert observed.private_peers[lo] is None, observed.private_peers

        print("VPN_PATH_PRIVATE_PEER_ADAPTER=PASS")
        print(f"VPN_PATH_PRIVATE_PEER_IF={identity.ifname}@{identity.ifindex}")
        print(f"VPN_PATH_PRIVATE_PEER={peer}")
    finally:
        if tun_fd is not None:
            os.close(tun_fd)
        subprocess.run(
            ("ip", "netns", "del", ns),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    main()
