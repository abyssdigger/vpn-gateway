#!/usr/bin/env python3
"""EXP-089: direct owned WireGuard base lifecycle without a service unit."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile


NS = "exp089-managed"
IFNAME = "wg0"
OWNER_ALIAS = "vpn-gate:managed-vpn:wg-main"
ADDRESS_A = "10.200.0.1/32"
ADDRESS_B = "10.200.0.2/32"
PROBE = "10.201.0.1/32"
ENDPOINT = "198.51.100.10:51820"
LISTEN_PORT = 51989


def run(
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        check=False,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed rc={result.returncode}: {args!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def ns(
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return run(
        "ip",
        "netns",
        "exec",
        NS,
        *args,
        check=check,
        input_text=input_text,
    )


def cleanup() -> None:
    run("ip", "netns", "del", NS, check=False)


def keypair() -> tuple[str, str]:
    private = run("wg", "genkey").stdout.strip()
    public = run("wg", "pubkey", input_text=private + "\n").stdout.strip()
    return private, public


def read_secret_file(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError(f"secret file cannot be opened safely: {exc}") from None
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("secret reference is not a regular file")
        if metadata.st_uid != os.geteuid():
            raise RuntimeError("secret file owner does not match effective uid")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError("secret file grants group/other access")
        value = os.read(fd, 4096).decode("ascii").strip()
    finally:
        os.close(fd)
    if not value:
        raise RuntimeError("secret file is empty")
    return value


def link_json() -> dict[str, object] | None:
    result = ns("ip", "-d", "-j", "link", "show", "dev", IFNAME, check=False)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    if len(data) != 1:
        raise RuntimeError(f"unexpected link inventory: {data!r}")
    return data[0]


def link_kind(link: dict[str, object]) -> str | None:
    linkinfo = link.get("linkinfo")
    if not isinstance(linkinfo, dict):
        return None
    kind = linkinfo.get("info_kind")
    return kind if isinstance(kind, str) else None


def ownership_state() -> str:
    link = link_json()
    if link is None:
        return "absent"
    if link_kind(link) != "wireguard":
        return "foreign"
    if link.get("ifalias") != OWNER_ALIAS:
        return "foreign"
    return "owned"


def public_key_for_private(private: str) -> str:
    return run("wg", "pubkey", input_text=private + "\n").stdout.strip()


def base_config(private: str, peer_public: str) -> str:
    return "\n".join(
        (
            "[Interface]",
            f"PrivateKey = {private}",
            f"ListenPort = {LISTEN_PORT}",
            "",
            "[Peer]",
            f"PublicKey = {peer_public}",
            f"Endpoint = {ENDPOINT}",
            f"AllowedIPs = {PROBE}",
            "",
        )
    )


def exact_state(
    address: str,
    private: str,
    peer_public: str,
) -> bool:
    if ownership_state() != "owned":
        return False

    addr_data = json.loads(
        ns("ip", "-j", "addr", "show", "dev", IFNAME).stdout
    )
    addresses = {
        f"{item['local']}/{item['prefixlen']}"
        for item in addr_data[0].get("addr_info", [])
        if item.get("family") == "inet"
    }
    if addresses != {address}:
        return False

    if ns("wg", "show", IFNAME, "public-key").stdout.strip() != public_key_for_private(private):
        return False
    if ns("wg", "show", IFNAME, "listen-port").stdout.strip() != str(LISTEN_PORT):
        return False

    allowed = ns("wg", "show", IFNAME, "allowed-ips").stdout.strip().split("\t")
    if len(allowed) != 2 or allowed[0] != peer_public or allowed[1] != PROBE:
        return False

    endpoint = ns("wg", "show", IFNAME, "endpoints").stdout.strip().split("\t")
    if len(endpoint) != 2 or endpoint[0] != peer_public or endpoint[1] != ENDPOINT:
        return False

    return True


def ifindex() -> int:
    link = link_json()
    if link is None:
        raise RuntimeError("interface absent")
    value = link.get("ifindex")
    if not isinstance(value, int):
        raise RuntimeError(f"invalid ifindex: {link!r}")
    return value


def create_owned(
    address: str,
    private: str,
    peer_public: str,
) -> None:
    ns("ip", "link", "add", IFNAME, "type", "wireguard")
    try:
        ns("ip", "link", "set", "dev", IFNAME, "alias", OWNER_ALIAS)
        ns(
            "wg",
            "setconf",
            IFNAME,
            "/dev/stdin",
            input_text=base_config(private, peer_public),
        )
        ns("ip", "addr", "add", address, "dev", IFNAME)
        ns("ip", "link", "set", IFNAME, "up")
    except Exception:
        ns("ip", "link", "del", IFNAME, check=False)
        raise


def converge_present(
    address: str,
    private: str,
    peer_public: str,
) -> int:
    state = ownership_state()
    if state == "foreign":
        raise RuntimeError("same-name interface exists without owned postcondition")
    if state == "owned" and exact_state(address, private, peer_public):
        return ifindex()
    if state == "owned":
        ns("ip", "link", "del", IFNAME)
        if ownership_state() != "absent":
            raise RuntimeError("old owned generation did not disappear")

    create_owned(address, private, peer_public)
    if not exact_state(address, private, peer_public):
        raise RuntimeError("new owned generation failed exact verification")
    return ifindex()


def converge_absent() -> None:
    state = ownership_state()
    if state == "absent":
        return
    if state == "foreign":
        raise RuntimeError("refusing to delete foreign same-name interface")
    ns("ip", "link", "del", IFNAME)
    if ownership_state() != "absent":
        raise RuntimeError("owned interface still present after delete")


def require_foreign_preserved() -> None:
    link = link_json()
    if link is None or link_kind(link) != "dummy":
        raise RuntimeError("foreign dummy interface was mutated or deleted")


def main() -> None:
    cleanup()
    try:
        run("ip", "netns", "add", NS)
        ns("ip", "link", "set", "lo", "up")
        private, _ = keypair()
        _, peer_public = keypair()

        with tempfile.TemporaryDirectory(prefix="exp089-") as directory:
            root = Path(directory)
            secret = root / "wg.key"
            secret.write_text(private + "\n", encoding="ascii")
            secret.chmod(0o600)
            loaded = read_secret_file(secret)
            if loaded != private:
                raise RuntimeError("valid secret content mismatch")

            secret.chmod(0o640)
            try:
                read_secret_file(secret)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("group-readable secret was accepted")
            secret.chmod(0o600)

            symlink = root / "wg-link.key"
            symlink.symlink_to(secret)
            try:
                read_secret_file(symlink)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("secret symlink was accepted")
            print("EXP089_SECRET_FILE_GATE=PASS")

            ns("ip", "link", "add", IFNAME, "type", "dummy")
            try:
                converge_present(ADDRESS_A, loaded, peer_public)
            except RuntimeError:
                require_foreign_preserved()
            else:
                raise RuntimeError("foreign same-name interface was adopted")
            print("EXP089_FOREIGN_PRESENT_REJECTED=PASS")
            ns("ip", "link", "del", IFNAME)

            first_ifindex = converge_present(ADDRESS_A, loaded, peer_public)
            print(f"EXP089_START_IFINDEX={first_ifindex}")
            print("EXP089_START_CONFIRMED=PASS")

            same_ifindex = converge_present(ADDRESS_A, loaded, peer_public)
            if same_ifindex != first_ifindex:
                raise RuntimeError("idempotent converge recreated exact interface")
            print("EXP089_IDEMPOTENT_PRESENT=PASS")

            second_ifindex = converge_present(ADDRESS_B, loaded, peer_public)
            if not exact_state(ADDRESS_B, loaded, peer_public):
                raise RuntimeError("changed generation not confirmed")
            print(
                "EXP089_RESTART_IFINDEX="
                f"before={first_ifindex};after={second_ifindex}"
            )
            print("EXP089_CHANGED_GENERATION_RESTART=PASS")

            converge_absent()
            print("EXP089_STOP_CONFIRMED=PASS")

            ns("ip", "link", "add", IFNAME, "type", "dummy")
            try:
                converge_absent()
            except RuntimeError:
                require_foreign_preserved()
            else:
                raise RuntimeError("foreign same-name interface was deleted")
            print("EXP089_FOREIGN_STOP_REJECTED=PASS")

        print("EXP089_RESULT=PASS")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
