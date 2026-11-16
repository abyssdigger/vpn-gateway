from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Interface
import json
import re

from .linux_driver import (
    LinuxCommandRunner,
    LinuxNetworkExecutor,
    NetworkNamespaceLinuxRunner,
)


_IFNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
LOCAL_INTERFACE = "host0"


class LinuxInstanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class LinuxInstanceSpec:
    namespace: str
    host_interface: str
    host_address: IPv4Interface
    inner_address: IPv4Interface

    def __post_init__(self) -> None:
        if not isinstance(self.host_address, IPv4Interface):
            raise ValueError("host address must be an IPv4 interface")
        if not isinstance(self.inner_address, IPv4Interface):
            raise ValueError("inner address must be an IPv4 interface")
        if not _NAMESPACE_RE.fullmatch(self.namespace):
            raise ValueError(f"invalid namespace name {self.namespace!r}")
        if not _IFNAME_RE.fullmatch(self.host_interface):
            raise ValueError(
                f"invalid host interface name {self.host_interface!r}"
            )
        if self.host_interface == LOCAL_INTERFACE:
            raise ValueError(
                f"host interface must differ from {LOCAL_INTERFACE!r}"
            )
        if self.host_address.ip == self.inner_address.ip:
            raise ValueError("host and inner addresses must differ")
        if self.host_address.network != self.inner_address.network:
            raise ValueError(
                "host and inner addresses must belong to the same IPv4 network"
            )
        for label, address in (
            ("host", self.host_address),
            ("inner", self.inner_address),
        ):
            network = address.network
            if network.prefixlen <= 30 and address.ip in {
                network.network_address,
                network.broadcast_address,
            }:
                raise ValueError(
                    f"{label} address is not usable in its subnet"
                )


@dataclass(frozen=True)
class LinuxInstanceVerification:
    ok: bool
    errors: tuple[str, ...]


def _json_array(text: str, what: str) -> list[dict]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LinuxInstanceError(f"invalid {what} JSON: {exc}") from None
    if not isinstance(value, list) or not all(
        isinstance(item, dict) for item in value
    ):
        raise LinuxInstanceError(f"{what} JSON must be an array of objects")
    return value


def _namespace_names(host: LinuxCommandRunner) -> tuple[str, ...]:
    result = host.run(("ip", "netns", "list"))
    return tuple(
        line.split(maxsplit=1)[0]
        for line in result.stdout.splitlines()
        if line.strip()
    )


def _link_detail(
    runner: LinuxCommandRunner,
    ifname: str,
) -> dict | None:
    result = runner.run(
        ("ip", "-j", "-d", "link", "show", "dev", ifname),
        check=False,
    )
    if result.returncode != 0:
        lowered = result.stderr.lower()
        if (
            "does not exist" in lowered
            or "cannot find device" in lowered
            or "device not found" in lowered
        ):
            return None
        raise LinuxInstanceError(
            f"cannot inspect interface {ifname!r}: {result.stderr.strip()}"
        )
    values = _json_array(result.stdout, f"interface {ifname!r}")
    if len(values) != 1:
        raise LinuxInstanceError(
            f"interface {ifname!r} snapshot is ambiguous"
        )
    return values[0]


def _address_present(
    runner: LinuxCommandRunner,
    ifname: str,
    address: IPv4Interface,
) -> bool:
    result = runner.run(
        ("ip", "-j", "-4", "addr", "show", "dev", ifname),
        check=False,
    )
    if result.returncode != 0:
        return False
    values = _json_array(result.stdout, f"address snapshot for {ifname!r}")
    if len(values) != 1:
        return False
    addresses = {
        (item.get("local"), item.get("prefixlen"))
        for item in values[0].get("addr_info", ())
        if isinstance(item, dict) and item.get("family") == "inet"
    }
    return (
        str(address.ip),
        address.network.prefixlen,
    ) in addresses


def _close_namespace_forwarding(
    spec: LinuxInstanceSpec,
    host: LinuxCommandRunner,
) -> None:
    runner = NetworkNamespaceLinuxRunner(host, spec.namespace)
    result = LinuxNetworkExecutor(runner).close_forwarding_verified()
    if not result.success:
        raise LinuxInstanceError(
            "cannot establish protective forwarding closure: "
            + (result.diagnostic or "unknown failure")
        )


def verify_linux_instance(
    spec: LinuxInstanceSpec,
    host: LinuxCommandRunner,
) -> LinuxInstanceVerification:
    errors: list[str] = []

    if spec.namespace not in _namespace_names(host):
        return LinuxInstanceVerification(
            False,
            (f"namespace {spec.namespace!r} is missing",),
        )

    host_detail = _link_detail(host, spec.host_interface)
    if host_detail is None:
        errors.append(f"host interface {spec.host_interface!r} is missing")
    else:
        if host_detail.get("linkinfo", {}).get("info_kind") != "veth":
            errors.append(
                f"host interface {spec.host_interface!r} is not a veth"
            )
        if "UP" not in host_detail.get("flags", ()):
            errors.append(
                f"host interface {spec.host_interface!r} is not UP"
            )
        if not _address_present(
            host,
            spec.host_interface,
            spec.host_address,
        ):
            errors.append(
                "host IPv4 interface "
                f"{spec.host_address.with_prefixlen} is missing"
            )

    ns = NetworkNamespaceLinuxRunner(host, spec.namespace)
    loopback_detail = _link_detail(ns, "lo")
    if loopback_detail is None or "UP" not in loopback_detail.get("flags", ()):
        errors.append("namespace loopback is missing or not UP")

    inner_detail = _link_detail(ns, LOCAL_INTERFACE)
    if inner_detail is None:
        errors.append(f"inner interface {LOCAL_INTERFACE!r} is missing")
    else:
        if inner_detail.get("linkinfo", {}).get("info_kind") != "veth":
            errors.append(
                f"inner interface {LOCAL_INTERFACE!r} is not a veth"
            )
        if "UP" not in inner_detail.get("flags", ()):
            errors.append(f"inner interface {LOCAL_INTERFACE!r} is not UP")
        if not _address_present(ns, LOCAL_INTERFACE, spec.inner_address):
            errors.append(
                "inner IPv4 interface "
                f"{spec.inner_address.with_prefixlen} is missing"
            )

    if host_detail is not None and inner_detail is not None:
        host_ifindex = host_detail.get("ifindex")
        host_peer = host_detail.get("link_index")
        inner_ifindex = inner_detail.get("ifindex")
        inner_peer = inner_detail.get("link_index")
        if not all(
            isinstance(value, int)
            for value in (
                host_ifindex,
                host_peer,
                inner_ifindex,
                inner_peer,
            )
        ):
            errors.append("veth peer identity is not fully observable")
        elif (
            host_peer != inner_ifindex
            or inner_peer != host_ifindex
        ):
            errors.append(
                "host and namespace veth interfaces are not the expected peer pair"
            )

    routes = ns.run(
        ("ip", "-j", "-4", "route", "show", "table", "main"),
        check=False,
    )
    if routes.returncode != 0:
        errors.append("cannot observe namespace main routing table")
    else:
        route_values = _json_array(
            routes.stdout,
            "namespace main routing table",
        )
        if not any(
            item.get("dst", "default") == "default"
            and item.get("gateway") == str(spec.host_address.ip)
            and item.get("dev") == LOCAL_INTERFACE
            for item in route_values
        ):
            errors.append("namespace underlay default route is missing")

    return LinuxInstanceVerification(not errors, tuple(errors))


def create_linux_instance(
    spec: LinuxInstanceSpec,
    host: LinuxCommandRunner,
) -> None:
    if spec.namespace in _namespace_names(host):
        raise LinuxInstanceError(
            f"refusing to reuse existing namespace {spec.namespace!r}"
        )
    if _link_detail(host, spec.host_interface) is not None:
        raise LinuxInstanceError(
            f"refusing to reuse existing host interface {spec.host_interface!r}"
        )

    created_namespace = False
    try:
        host.run(("ip", "netns", "add", spec.namespace))
        created_namespace = True
        _close_namespace_forwarding(spec, host)

        host.run(
            (
                "ip",
                "link",
                "add",
                spec.host_interface,
                "type",
                "veth",
                "peer",
                "name",
                LOCAL_INTERFACE,
            )
        )
        host.run(
            (
                "ip",
                "link",
                "set",
                LOCAL_INTERFACE,
                "netns",
                spec.namespace,
            )
        )
        host.run(
            (
                "ip",
                "addr",
                "add",
                spec.host_address.with_prefixlen,
                "dev",
                spec.host_interface,
            )
        )
        host.run(("ip", "link", "set", spec.host_interface, "up"))

        ns = NetworkNamespaceLinuxRunner(host, spec.namespace)
        ns.run(("ip", "link", "set", "lo", "up"))
        ns.run(
            (
                "ip",
                "addr",
                "add",
                spec.inner_address.with_prefixlen,
                "dev",
                LOCAL_INTERFACE,
            )
        )
        ns.run(("ip", "link", "set", LOCAL_INTERFACE, "up"))
        ns.run(
            (
                "ip",
                "route",
                "replace",
                "default",
                "via",
                str(spec.host_address.ip),
                "dev",
                LOCAL_INTERFACE,
            )
        )

        verified = verify_linux_instance(spec, host)
        if not verified.ok:
            raise LinuxInstanceError(
                "created instance failed verification: "
                + "; ".join(verified.errors)
            )
    except Exception:
        if created_namespace:
            host.run(
                ("ip", "netns", "del", spec.namespace),
                check=False,
            )
        host.run(
            ("ip", "link", "del", spec.host_interface),
            check=False,
        )
        raise


def ensure_linux_instance(
    spec: LinuxInstanceSpec,
    host: LinuxCommandRunner,
) -> None:
    namespace_exists = spec.namespace in _namespace_names(host)
    host_link_exists = _link_detail(host, spec.host_interface) is not None

    if namespace_exists:
        _close_namespace_forwarding(spec, host)

    if not namespace_exists and not host_link_exists:
        create_linux_instance(spec, host)
        return

    if namespace_exists != host_link_exists:
        raise LinuxInstanceError(
            "instance infrastructure is partially present; "
            f"namespace_exists={namespace_exists} "
            f"host_link_exists={host_link_exists}"
        )

    verified = verify_linux_instance(spec, host)
    if not verified.ok:
        raise LinuxInstanceError(
            "existing instance failed infrastructure verification: "
            + "; ".join(verified.errors)
        )


def destroy_linux_instance(
    spec: LinuxInstanceSpec,
    host: LinuxCommandRunner,
) -> None:
    if spec.namespace in _namespace_names(host):
        try:
            _close_namespace_forwarding(spec, host)
        except Exception:
            pass
        host.run(
            ("ip", "netns", "del", spec.namespace),
            check=False,
        )

    host.run(
        ("ip", "link", "del", spec.host_interface),
        check=False,
    )

    errors = []
    if spec.namespace in _namespace_names(host):
        errors.append(f"namespace {spec.namespace!r} still exists")
    if _link_detail(host, spec.host_interface) is not None:
        errors.append(
            f"host interface {spec.host_interface!r} still exists"
        )
    if errors:
        raise LinuxInstanceError("; ".join(errors))
