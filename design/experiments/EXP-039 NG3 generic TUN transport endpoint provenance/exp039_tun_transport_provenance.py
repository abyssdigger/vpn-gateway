from __future__ import annotations

import fcntl
import json
import os
import socket
import struct
import subprocess

TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

NAME = f"e39tun{os.getpid() % 10000}"
INNER_LOCAL = "10.39.0.1"
INNER_PEER = "10.39.0.2"
TRANSPORT_A = "198.51.100.39"
TRANSPORT_B = "203.0.113.39"


def run(*args: str) -> str:
    return subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def observe() -> tuple[object, object]:
    link = json.loads(run("ip", "-j", "-d", "link", "show", "dev", NAME))
    addr = json.loads(run("ip", "-j", "addr", "show", "dev", NAME))
    return link, addr


def connected_peer(address: str) -> tuple[str, int]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((address, 443))
        peer = sock.getpeername()
        assert peer[0] == address, peer
        return peer
    finally:
        sock.close()


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("EXP-039 requires root")
    if not os.path.exists("/dev/net/tun"):
        raise SystemExit("/dev/net/tun is unavailable")

    tun = os.open("/dev/net/tun", os.O_RDWR)
    try:
        ifreq = struct.pack("16sH", NAME.encode(), IFF_TUN | IFF_NO_PI)
        result = fcntl.ioctl(tun, TUNSETIFF, ifreq)
        actual_name = result[:16].split(b"\0", 1)[0].decode()
        assert actual_name == NAME, (actual_name, NAME)

        run("ip", "link", "set", "dev", NAME, "up")
        run(
            "ip", "addr", "add",
            f"{INNER_LOCAL}/32",
            "peer", f"{INNER_PEER}/32",
            "dev", NAME,
        )

        first_peer = connected_peer(TRANSPORT_A)
        first_link, first_addr = observe()

        second_peer = connected_peer(TRANSPORT_B)
        second_link, second_addr = observe()

        assert first_peer[0] != second_peer[0]
        assert first_link == second_link, (first_link, second_link)
        assert first_addr == second_addr, (first_addr, second_addr)

        link_text = json.dumps(first_link, sort_keys=True)
        addr_text = json.dumps(first_addr, sort_keys=True)

        flags = set(first_link[0].get("flags", []))
        assert "POINTOPOINT" in flags, flags
        assert INNER_LOCAL in addr_text, addr_text
        assert INNER_PEER in addr_text, addr_text

        for transport in (TRANSPORT_A, TRANSPORT_B):
            assert transport not in link_text, (transport, link_text)
            assert transport not in addr_text, (transport, addr_text)

        print(f"EXP039_INTERFACE={NAME}")
        print(f"EXP039_INNER_LOCAL={INNER_LOCAL}")
        print(f"EXP039_INNER_PEER={INNER_PEER}")
        print(f"EXP039_TRANSPORT_A={first_peer[0]}")
        print(f"EXP039_TRANSPORT_B={second_peer[0]}")
        print("EXP039_GENERIC_INTERFACE_STATE_UNCHANGED=1")
        print("EXP-039 generic TUN transport endpoint provenance: PASS")
    finally:
        os.close(tun)


if __name__ == "__main__":
    main()
