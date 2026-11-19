"""Linux managed network-domain infrastructure lifecycle for NG3."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Interface
import json
import re
from typing import Protocol, Sequence

from .forwarding_gate import (
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .interface_identity import InterfaceIdentity
from .linux_forwarding_gate import LinuxForwardingGateBackend
from .managed_l3_boundary import ManagedL3BoundaryBackend


_IFNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class ManagedNetworkDomainError(RuntimeError):
    pass


class ManagedNetworkDomainRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one argv-only command or raise; return stdout text."""


def _validate_boundary_link(
    host_interface: str,
    inner_interface: str,
    host_address: IPv4Interface,
    inner_address: IPv4Interface,
) -> None:
    for label, value in (
        ("host_interface", host_interface),
        ("inner_interface", inner_interface),
    ):
        if not isinstance(value, str) or not _IFNAME_RE.fullmatch(value):
            raise ValueError(f"invalid {label} {value!r}")
    if host_interface == inner_interface:
        raise ValueError("host and inner interface names must differ")
    if not isinstance(host_address, IPv4Interface):
        raise ValueError("host_address must be IPv4Interface")
    if not isinstance(inner_address, IPv4Interface):
        raise ValueError("inner_address must be IPv4Interface")
    if host_address.ip == inner_address.ip:
        raise ValueError("host and inner addresses must differ")
    if host_address.network != inner_address.network:
        raise ValueError("host and inner addresses must belong to the same IPv4 network")
    for label, address in (("host", host_address), ("inner", inner_address)):
        network = address.network
        if network.prefixlen <= 30 and address.ip in {
            network.network_address,
            network.broadcast_address,
        }:
            raise ValueError(f"{label} address is not usable in its subnet")


@dataclass(frozen=True, slots=True)
class ManagedBoundaryLinkSpec:
    host_interface: str
    inner_interface: str
    host_address: IPv4Interface
    inner_address: IPv4Interface

    def __post_init__(self) -> None:
        _validate_boundary_link(
            self.host_interface,
            self.inner_interface,
            self.host_address,
            self.inner_address,
        )


@dataclass(frozen=True, slots=True)
class ManagedNetworkDomainSpec:
    namespace: str
    host_interface: str
    inner_interface: str
    host_address: IPv4Interface | None
    inner_address: IPv4Interface
    primary_backend: ManagedL3BoundaryBackend | None = None
    additional_boundaries: tuple[ManagedBoundaryLinkSpec, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not _NAMESPACE_RE.fullmatch(
            self.namespace
        ):
            raise ValueError(f"invalid namespace name {self.namespace!r}")
        for label, value in (
            ("host_interface", self.host_interface),
            ("inner_interface", self.inner_interface),
        ):
            if not isinstance(value, str) or not _IFNAME_RE.fullmatch(value):
                raise ValueError(f"invalid {label} {value!r}")
        if self.host_interface == self.inner_interface:
            raise ValueError("host and inner interface names must differ")
        if not isinstance(self.inner_address, IPv4Interface):
            raise ValueError("inner_address must be IPv4Interface")

        if self.primary_backend is None:
            if not isinstance(self.host_address, IPv4Interface):
                raise ValueError(
                    "transitional addressed primary boundary requires host_address"
                )
            _validate_boundary_link(
                self.host_interface,
                self.inner_interface,
                self.host_address,
                self.inner_address,
            )
        else:
            if (
                self.primary_backend
                is not ManagedL3BoundaryBackend.ROUTED_VETH_PROXY_ARP
            ):
                raise ValueError(
                    "managed network-domain lifecycle currently materializes only "
                    "routed-veth-proxy-arp; alternate backends share the contract "
                    "but require their own lifecycle Driver"
                )
            if self.host_address is not None:
                raise ValueError(
                    "routed managed L3 primary boundary must not have host_address"
                )
            if self.inner_address.network.prefixlen != 32:
                raise ValueError(
                    "routed managed L3 stack-local service address must be /32"
                )

        if not isinstance(self.additional_boundaries, tuple) or any(
            not isinstance(item, ManagedBoundaryLinkSpec)
            for item in self.additional_boundaries
        ):
            raise ValueError(
                "additional_boundaries must contain ManagedBoundaryLinkSpec values"
            )
        names = [
            self.host_interface,
            self.inner_interface,
            *(
                name
                for item in self.additional_boundaries
                for name in (item.host_interface, item.inner_interface)
            ),
        ]
        if len(set(names)) != len(names):
            raise ValueError("managed boundary interface names must be globally unique")

        primary_network = (
            self.host_address.network
            if self.host_address is not None
            else self.inner_address.network
        )
        networks = [
            primary_network,
            *(item.host_address.network for item in self.additional_boundaries),
        ]
        for index, left in enumerate(networks):
            for right in networks[index + 1:]:
                if left.overlaps(right):
                    raise ValueError("managed boundary IPv4 networks must not overlap")

    @property
    def routed_primary(self) -> bool:
        return (
            self.primary_backend
            is ManagedL3BoundaryBackend.ROUTED_VETH_PROXY_ARP
        )

    @property
    def host_boundary_gateway(self):
        return None if self.routed_primary else self.inner_address.ip


@dataclass(frozen=True, slots=True)
class ManagedNetworkDomainVerification:
    confirmed: bool
    errors: tuple[str, ...]
    host_boundary: InterfaceIdentity | None = None
    boundary_interfaces: tuple[InterfaceIdentity, ...] = ()


@dataclass(frozen=True, slots=True)
class ManagedNetworkDomainPreflightResult:
    existing: bool
    verification: ManagedNetworkDomainVerification | None

    @property
    def confirmed(self) -> bool:
        return (
            (not self.existing and self.verification is None)
            or (
                self.existing
                and self.verification is not None
                and self.verification.confirmed
            )
        )


@dataclass(frozen=True, slots=True)
class ManagedNetworkDomainEnsureResult:
    created: bool
    verification: ManagedNetworkDomainVerification

    @property
    def confirmed(self) -> bool:
        return self.verification.confirmed


def verify_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkDomainVerification:
    """Read-only exact infrastructure verification."""
    namespaces = _namespace_names(runner)
    if spec.namespace not in namespaces:
        return ManagedNetworkDomainVerification(
            False,
            (f"namespace {spec.namespace!r} is missing",),
        )

    errors: list[str] = []
    host_links = _link_rows(runner)
    namespace_links = _link_rows(runner, namespace=spec.namespace)

    host = _single_link(host_links, spec.host_interface)
    inner = _single_link(namespace_links, spec.inner_interface)
    loopback = _single_link(namespace_links, "lo")

    _verify_veth(
        host,
        spec.host_interface,
        "host",
        errors,
    )
    _verify_veth(
        inner,
        spec.inner_interface,
        "inner",
        errors,
    )
    if loopback is None or "UP" not in loopback.get("flags", ()):
        errors.append("namespace loopback is missing or not UP")

    if host is not None and inner is not None:
        host_ifindex = host.get("ifindex")
        host_peer = host.get("link_index")
        inner_ifindex = inner.get("ifindex")
        inner_peer = inner.get("link_index")
        if not all(
            type(value) is int
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
                "host and namespace boundary interfaces are not reciprocal veth peers"
            )

    if host is not None:
        host_addresses = _ipv4_addresses(
            runner,
            spec.host_interface,
        )
        if host_addresses != frozenset((spec.host_address,)):
            errors.append(
                "host boundary IPv4 address set does not exactly match "
                f"{spec.host_address.with_prefixlen}"
            )

    if inner is not None:
        inner_addresses = _ipv4_addresses(
            runner,
            spec.inner_interface,
            namespace=spec.namespace,
        )
        if inner_addresses != frozenset((spec.inner_address,)):
            errors.append(
                "inner boundary IPv4 address set does not exactly match "
                f"{spec.inner_address.with_prefixlen}"
            )

    boundary_interfaces: list[InterfaceIdentity] = []
    if inner is not None and type(inner.get("ifindex")) is int:
        try:
            boundary_interfaces.append(
                InterfaceIdentity(spec.inner_interface, inner["ifindex"])
            )
        except ValueError:
            errors.append("inner boundary interface identity is invalid")

    for extra in spec.additional_boundaries:
        extra_host = _single_link(host_links, extra.host_interface)
        extra_inner = _single_link(namespace_links, extra.inner_interface)
        _verify_veth(extra_host, extra.host_interface, "additional host", errors)
        _verify_veth(extra_inner, extra.inner_interface, "additional inner", errors)

        if extra_host is not None and extra_inner is not None:
            host_ifindex = extra_host.get("ifindex")
            host_peer = extra_host.get("link_index")
            inner_ifindex = extra_inner.get("ifindex")
            inner_peer = extra_inner.get("link_index")
            if not all(
                type(value) is int
                for value in (host_ifindex, host_peer, inner_ifindex, inner_peer)
            ):
                errors.append(
                    f"additional boundary {extra.inner_interface!r} peer identity is not fully observable"
                )
            elif host_peer != inner_ifindex or inner_peer != host_ifindex:
                errors.append(
                    f"additional boundary {extra.inner_interface!r} is not a reciprocal veth pair"
                )

        if extra_host is not None:
            observed = _ipv4_addresses(runner, extra.host_interface)
            if observed != frozenset((extra.host_address,)):
                errors.append(
                    f"additional host boundary {extra.host_interface!r} IPv4 address set differs"
                )
        if extra_inner is not None:
            observed = _ipv4_addresses(
                runner,
                extra.inner_interface,
                namespace=spec.namespace,
            )
            if observed != frozenset((extra.inner_address,)):
                errors.append(
                    f"additional inner boundary {extra.inner_interface!r} IPv4 address set differs"
                )
            if type(extra_inner.get("ifindex")) is int:
                try:
                    boundary_interfaces.append(
                        InterfaceIdentity(
                            extra.inner_interface,
                            extra_inner["ifindex"],
                        )
                    )
                except ValueError:
                    errors.append(
                        f"additional inner boundary {extra.inner_interface!r} identity is invalid"
                    )

    routes = _json_array(
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "-j", "-4",
                "route", "show", "table", "main",
            )
        ),
        "namespace main-route snapshot",
    )
    defaults = [
        row
        for row in routes
        if row.get("dst", "default") == "default"
    ]
    if len(defaults) != 1 or not (
        defaults[0].get("gateway") == str(spec.host_address.ip)
        and defaults[0].get("dev") == spec.inner_interface
    ):
        errors.append(
            "namespace default route does not exactly use configured host address "
            "and inner boundary"
        )

    primary_boundary = (
        boundary_interfaces[0]
        if boundary_interfaces
        and boundary_interfaces[0].ifname == spec.inner_interface
        else None
    )
    return ManagedNetworkDomainVerification(
        confirmed=not errors,
        errors=tuple(errors),
        host_boundary=primary_boundary if not errors else None,
        boundary_interfaces=tuple(boundary_interfaces) if not errors else (),
    )


def preflight_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkDomainPreflightResult:
    """Contain/verify existing infrastructure without creating absent state."""
    namespace_exists = spec.namespace in _namespace_names(runner)
    current_host_links = _link_rows(runner)
    host_exists = _single_link(
        current_host_links,
        spec.host_interface,
    ) is not None
    additional_host_exists = any(
        _single_link(current_host_links, item.host_interface) is not None
        for item in spec.additional_boundaries
    )

    if namespace_exists:
        _require_containment(spec, runner)

    if not namespace_exists and not host_exists and not additional_host_exists:
        return ManagedNetworkDomainPreflightResult(
            existing=False,
            verification=None,
        )

    if namespace_exists != host_exists or (
        not namespace_exists and additional_host_exists
    ):
        raise ManagedNetworkDomainError(
            "managed network-domain infrastructure is partially present; "
            f"namespace_exists={namespace_exists} "
            f"host_boundary_exists={host_exists} "
            f"additional_host_boundary_exists={additional_host_exists}"
        )

    verification = verify_managed_network_domain(spec, runner)
    if not verification.confirmed:
        raise ManagedNetworkDomainError(
            "existing managed network domain failed exact verification: "
            + "; ".join(verification.errors)
        )
    return ManagedNetworkDomainPreflightResult(
        existing=True,
        verification=verification,
    )


def ensure_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkDomainEnsureResult:
    """Create absent infrastructure or verify an already complete contained domain."""
    preflight = preflight_managed_network_domain(spec, runner)

    if not preflight.existing:
        _create_managed_network_domain(spec, runner)
        verification = verify_managed_network_domain(spec, runner)
        if not verification.confirmed:
            _best_effort_destroy_created(spec, runner)
            raise ManagedNetworkDomainError(
                "created managed network domain failed verification: "
                + "; ".join(verification.errors)
            )
        return ManagedNetworkDomainEnsureResult(
            created=True,
            verification=verification,
        )

    assert preflight.verification is not None
    return ManagedNetworkDomainEnsureResult(
        created=False,
        verification=preflight.verification,
    )


def destroy_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    """Best-effort containment/removal followed by fresh absence verification."""
    if spec.namespace in _namespace_names(runner):
        try:
            _require_containment(spec, runner)
        except Exception:
            pass
        try:
            runner.run(("ip", "netns", "del", spec.namespace))
        except Exception:
            pass

    for host_interface in (
        spec.host_interface,
        *(item.host_interface for item in spec.additional_boundaries),
    ):
        if _single_link(_link_rows(runner), host_interface) is not None:
            try:
                runner.run(("ip", "link", "del", host_interface))
            except Exception:
                pass

    errors = []
    if spec.namespace in _namespace_names(runner):
        errors.append(f"namespace {spec.namespace!r} still exists")
    current_host_links = _link_rows(runner)
    for host_interface in (
        spec.host_interface,
        *(item.host_interface for item in spec.additional_boundaries),
    ):
        if _single_link(current_host_links, host_interface) is not None:
            errors.append(f"host interface {host_interface!r} still exists")
    if errors:
        raise ManagedNetworkDomainError("; ".join(errors))


def _create_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    created_namespace = False
    created_veth = False
    try:
        runner.run(("ip", "netns", "add", spec.namespace))
        created_namespace = True
        _require_containment(spec, runner)

        runner.run(
            (
                "ip", "link", "add", spec.host_interface,
                "type", "veth",
                "peer", "name", spec.inner_interface,
            )
        )
        created_veth = True
        runner.run(
            (
                "ip", "link", "set", spec.inner_interface,
                "netns", spec.namespace,
            )
        )
        runner.run(
            (
                "ip", "addr", "add",
                spec.host_address.with_prefixlen,
                "dev", spec.host_interface,
            )
        )
        runner.run(("ip", "link", "set", spec.host_interface, "up"))
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "link", "set", "lo", "up",
            )
        )
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "addr", "add",
                spec.inner_address.with_prefixlen,
                "dev", spec.inner_interface,
            )
        )
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "link", "set", spec.inner_interface, "up",
            )
        )
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "-4", "route", "replace", "default",
                "via", str(spec.host_address.ip),
                "dev", spec.inner_interface,
            )
        )

        for extra in spec.additional_boundaries:
            runner.run(
                (
                    "ip", "link", "add", extra.host_interface,
                    "type", "veth",
                    "peer", "name", extra.inner_interface,
                )
            )
            runner.run(
                (
                    "ip", "link", "set", extra.inner_interface,
                    "netns", spec.namespace,
                )
            )
            runner.run(
                (
                    "ip", "addr", "add",
                    extra.host_address.with_prefixlen,
                    "dev", extra.host_interface,
                )
            )
            runner.run(("ip", "link", "set", extra.host_interface, "up"))
            runner.run(
                (
                    "ip", "-n", spec.namespace,
                    "addr", "add",
                    extra.inner_address.with_prefixlen,
                    "dev", extra.inner_interface,
                )
            )
            runner.run(
                (
                    "ip", "-n", spec.namespace,
                    "link", "set", extra.inner_interface, "up",
                )
            )
    except Exception:
        if created_namespace:
            try:
                runner.run(("ip", "netns", "del", spec.namespace))
            except Exception:
                pass
        current_host_links = _link_rows(runner)
        for host_interface in (
            spec.host_interface,
            *(item.host_interface for item in spec.additional_boundaries),
        ):
            if _single_link(current_host_links, host_interface) is not None:
                try:
                    runner.run(("ip", "link", "del", host_interface))
                except Exception:
                    pass
        raise


def _best_effort_destroy_created(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    try:
        destroy_managed_network_domain(spec, runner)
    except Exception:
        pass


def _require_containment(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    result = converge_forwarding_gate_once(
        LinuxForwardingGateBackend(runner, spec.namespace),
        ForwardingGateState.DISABLED,
    )
    if not result.confirmed:
        raise ManagedNetworkDomainError(
            "cannot confirm managed-domain forwarding containment"
            + (
                f": {result.diagnostic}"
                if result.diagnostic
                else ""
            )
        )


def _namespace_names(
    runner: ManagedNetworkDomainRunner,
) -> tuple[str, ...]:
    stdout = runner.run(("ip", "netns", "list"))
    return tuple(
        line.split(maxsplit=1)[0]
        for line in stdout.splitlines()
        if line.strip()
    )


def _link_rows(
    runner: ManagedNetworkDomainRunner,
    *,
    namespace: str | None = None,
) -> list[dict]:
    if namespace is None:
        argv = ("ip", "-j", "-d", "link", "show")
        what = "host link snapshot"
    else:
        argv = ("ip", "-n", namespace, "-j", "-d", "link", "show")
        what = f"namespace {namespace!r} link snapshot"
    return _json_array(runner.run(argv), what)


def _single_link(
    rows: list[dict],
    ifname: str,
) -> dict | None:
    matches = [
        row
        for row in rows
        if row.get("ifname") == ifname
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ManagedNetworkDomainError(
            f"interface {ifname!r} snapshot is ambiguous"
        )
    return matches[0]


def _verify_veth(
    detail: dict | None,
    ifname: str,
    label: str,
    errors: list[str],
) -> None:
    if detail is None:
        errors.append(f"{label} interface {ifname!r} is missing")
        return
    if detail.get("linkinfo", {}).get("info_kind") != "veth":
        errors.append(f"{label} interface {ifname!r} is not a veth")
    if "UP" not in detail.get("flags", ()):
        errors.append(f"{label} interface {ifname!r} is not UP")


def _ipv4_addresses(
    runner: ManagedNetworkDomainRunner,
    ifname: str,
    *,
    namespace: str | None = None,
) -> frozenset[IPv4Interface]:
    if namespace is None:
        argv = ("ip", "-j", "-4", "addr", "show", "dev", ifname)
    else:
        argv = (
            "ip", "-n", namespace,
            "-j", "-4", "addr", "show", "dev", ifname,
        )
    rows = _json_array(runner.run(argv), f"IPv4 address snapshot for {ifname!r}")
    if len(rows) != 1:
        return frozenset()
    result = set()
    for item in rows[0].get("addr_info", ()):
        if not isinstance(item, dict) or item.get("family") != "inet":
            continue
        local = item.get("local")
        prefixlen = item.get("prefixlen")
        if not isinstance(local, str) or type(prefixlen) is not int:
            continue
        result.add(IPv4Interface(f"{local}/{prefixlen}"))
    return frozenset(result)


def _json_array(text: str, what: str) -> list[dict]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManagedNetworkDomainError(
            f"invalid {what} JSON: {exc}"
        ) from None
    if not isinstance(value, list) or not all(
        isinstance(item, dict)
        for item in value
    ):
        raise ManagedNetworkDomainError(
            f"{what} JSON must be an array of objects"
        )
    return value
