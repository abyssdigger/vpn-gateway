"""Linux lifecycle realization for Private network and ordinary-side transition.

Architecture:
- Annex B B.001 ManagedL3BoundaryLifecycle;
- Annex C C.007 ManagedNetworkEnvironmentLifecycle;
- Annex C C.009 OrdinarySidePortalLifecycle.

The legacy managed-network-domain functions at the bottom of the public surface are
compatibility orchestration facades, not a cross-Space component boundary.

Requirement traceability: VPNG0004-R4.R6, VPNG0005-R5.R1/R2/R4/R5,
VPNG0007-R7.R3/R7.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Interface, IPv4Network, ip_network
import json
import re
from typing import Protocol, Sequence

from .forwarding_gate import (
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from .interface_identity import InterfaceIdentity
from .linux_forwarding_gate import LinuxForwardingGateDriver


_IFNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class ManagedNetworkDomainError(RuntimeError):
    pass


class ManagedNetworkDomainRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one argv-only command or raise; return stdout text."""


@dataclass(frozen=True, slots=True)
class ManagedNetworkDomainSpec:
    namespace: str
    host_interface: str
    inner_interface: str
    inner_address: IPv4Interface

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
        if self.inner_address.network.prefixlen != 32:
            raise ValueError("managed L3 stack-local service address must be /32")


@dataclass(frozen=True, slots=True)
class ManagedNetworkDomainVerification:
    confirmed: bool
    errors: tuple[str, ...]
    host_boundary: InterfaceIdentity | None = None


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


@dataclass(frozen=True, slots=True)
class ManagedNetworkEnvironmentVerification:
    confirmed: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManagedNetworkEnvironmentEnsureResult:
    created: bool
    verification: ManagedNetworkEnvironmentVerification

    @property
    def confirmed(self) -> bool:
        return self.verification.confirmed


@dataclass(frozen=True, slots=True)
class ManagedL3BoundaryVerification:
    confirmed: bool
    errors: tuple[str, ...]
    private_boundary: InterfaceIdentity | None = None


@dataclass(frozen=True, slots=True)
class ManagedL3BoundaryEnsureResult:
    created: bool
    verification: ManagedL3BoundaryVerification

    @property
    def confirmed(self) -> bool:
        return self.verification.confirmed


@dataclass(frozen=True, slots=True)
class OrdinarySidePortalVerification:
    confirmed: bool
    errors: tuple[str, ...]


def verify_managed_network_environment(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkEnvironmentVerification:
    """Verify only Private-network namespace + loopback materialization."""
    if spec.namespace not in _namespace_names(runner):
        return ManagedNetworkEnvironmentVerification(
            False,
            (f"namespace {spec.namespace!r} is missing",),
        )
    loopback = _single_link(
        _link_rows(runner, namespace=spec.namespace),
        "lo",
    )
    errors = []
    if loopback is None or "UP" not in loopback.get("flags", ()):
        errors.append("namespace loopback is missing or not UP")
    return ManagedNetworkEnvironmentVerification(
        confirmed=not errors,
        errors=tuple(errors),
    )


def preflight_managed_network_environment(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> bool:
    """Contain and verify existing environment; return whether it exists."""
    if spec.namespace not in _namespace_names(runner):
        return False
    _require_containment(spec, runner)
    verification = verify_managed_network_environment(spec, runner)
    if not verification.confirmed:
        raise ManagedNetworkDomainError(
            "existing managed network environment failed exact verification: "
            + "; ".join(verification.errors)
        )
    return True


def ensure_managed_network_environment(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkEnvironmentEnsureResult:
    """Create/verify Private-network namespace + loopback only."""
    existing = preflight_managed_network_environment(spec, runner)
    if existing:
        return ManagedNetworkEnvironmentEnsureResult(
            False,
            verify_managed_network_environment(spec, runner),
        )

    created = False
    try:
        runner.run(("ip", "netns", "add", spec.namespace))
        created = True
        _require_containment(spec, runner)
        runner.run(
            ("ip", "-n", spec.namespace, "link", "set", "lo", "up")
        )
        verification = verify_managed_network_environment(spec, runner)
        if not verification.confirmed:
            raise ManagedNetworkDomainError(
                "created managed network environment failed verification: "
                + "; ".join(verification.errors)
            )
        return ManagedNetworkEnvironmentEnsureResult(True, verification)
    except Exception:
        if created:
            try:
                runner.run(("ip", "netns", "del", spec.namespace))
            except Exception:
                pass
        raise


def destroy_managed_network_environment(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    """Destroy environment only after the ordinary-side transition is absent."""
    if spec.namespace not in _namespace_names(runner):
        return
    _require_containment(spec, runner)
    if _single_link(_link_rows(runner), spec.host_interface) is not None:
        raise ManagedNetworkDomainError(
            "cannot destroy managed network environment while transition host endpoint exists"
        )
    runner.run(("ip", "netns", "del", spec.namespace))
    if spec.namespace in _namespace_names(runner):
        raise ManagedNetworkDomainError(
            f"namespace {spec.namespace!r} still exists after destroy"
        )


def verify_managed_l3_boundary(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedL3BoundaryVerification:
    """Verify transition artifacts without owning Private portal address/default."""
    errors: list[str] = []
    if spec.namespace not in _namespace_names(runner):
        return ManagedL3BoundaryVerification(
            False,
            (f"namespace {spec.namespace!r} is missing",),
        )

    host = _single_link(_link_rows(runner), spec.host_interface)
    inner = _single_link(
        _link_rows(runner, namespace=spec.namespace),
        spec.inner_interface,
    )
    _verify_veth(host, spec.host_interface, "host", errors)
    _verify_veth(inner, spec.inner_interface, "inner", errors)

    if host is not None and inner is not None:
        values = (
            host.get("ifindex"),
            host.get("link_index"),
            inner.get("ifindex"),
            inner.get("link_index"),
        )
        if not all(type(value) is int for value in values):
            errors.append("veth peer identity is not fully observable")
        elif host.get("link_index") != inner.get("ifindex") or inner.get(
            "link_index"
        ) != host.get("ifindex"):
            errors.append(
                "host and namespace boundary interfaces are not reciprocal veth peers"
            )

    if host is not None and _ipv4_addresses(runner, spec.host_interface):
        errors.append("managed L3 host boundary must not carry an IPv4 address")

    if host is not None and inner is not None:
        for label, namespace, interface in (
            ("host", None, spec.host_interface),
            ("inner", spec.namespace, spec.inner_interface),
        ):
            if _sysctl_int(
                runner,
                f"net.ipv4.conf.{interface}.proxy_arp",
                namespace=namespace,
            ) != 1:
                errors.append(
                    f"{label} managed L3 endpoint Proxy ARP is not enabled"
                )
            if _sysctl_int(
                runner,
                f"net.ipv4.conf.{interface}.rp_filter",
                namespace=namespace,
            ) != 0:
                errors.append(
                    f"{label} managed L3 endpoint rp_filter is not disabled"
                )

    host_routes = _json_array(
        runner.run(("ip", "-j", "-4", "route", "show", "table", "main")),
        "host main-route snapshot",
    )
    service_routes = [
        row
        for row in host_routes
        if _route_network(row.get("dst", "default")) == spec.inner_address.network
    ]
    if len(service_routes) != 1 or not (
        service_routes[0].get("dev") == spec.host_interface
        and service_routes[0].get("gateway") is None
        and service_routes[0].get("type", "unicast") == "unicast"
    ):
        errors.append(
            "host stack-local service route does not exactly use managed L3 host boundary"
        )

    identity = None
    if inner is not None and type(inner.get("ifindex")) is int:
        try:
            identity = InterfaceIdentity(spec.inner_interface, inner["ifindex"])
        except ValueError:
            errors.append("inner boundary interface identity is invalid")

    return ManagedL3BoundaryVerification(
        confirmed=not errors,
        errors=tuple(errors),
        private_boundary=identity if not errors else None,
    )


def preflight_managed_l3_boundary(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> bool:
    """Classify absent/exact transition relative to the current environment."""
    namespace_exists = spec.namespace in _namespace_names(runner)
    host_exists = _single_link(_link_rows(runner), spec.host_interface) is not None

    if not namespace_exists:
        if host_exists:
            raise ManagedNetworkDomainError(
                "transition host endpoint exists without managed network environment"
            )
        return False

    _require_containment(spec, runner)
    inner_exists = (
        _single_link(
            _link_rows(runner, namespace=spec.namespace),
            spec.inner_interface,
        )
        is not None
    )
    if not host_exists and not inner_exists:
        return False
    if host_exists != inner_exists:
        raise ManagedNetworkDomainError(
            "ordinary-side transition is partially present; "
            f"host_endpoint_exists={host_exists} "
            f"private_endpoint_exists={inner_exists}"
        )

    verification = verify_managed_l3_boundary(spec, runner)
    if not verification.confirmed:
        raise ManagedNetworkDomainError(
            "existing ordinary-side transition failed exact verification: "
            + "; ".join(verification.errors)
        )
    return True


def ensure_managed_l3_boundary(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedL3BoundaryEnsureResult:
    """Create/verify routed-veth transition without Private portal state."""
    environment = verify_managed_network_environment(spec, runner)
    if not environment.confirmed:
        raise ManagedNetworkDomainError(
            "managed network environment is not exact before transition ensure: "
            + "; ".join(environment.errors)
        )
    existing = preflight_managed_l3_boundary(spec, runner)
    if existing:
        return ManagedL3BoundaryEnsureResult(
            False,
            verify_managed_l3_boundary(spec, runner),
        )

    created_host = False
    try:
        runner.run(
            (
                "ip", "link", "add", spec.host_interface,
                "type", "veth", "peer", "name", spec.inner_interface,
            )
        )
        created_host = True
        runner.run(
            (
                "ip", "link", "set", spec.inner_interface,
                "netns", spec.namespace,
            )
        )
        runner.run(("ip", "link", "set", spec.host_interface, "up"))
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "link", "set", spec.inner_interface, "up",
            )
        )
        runner.run(
            (
                "sysctl", "-w",
                f"net.ipv4.conf.{spec.host_interface}.proxy_arp=1",
            )
        )
        runner.run(
            (
                "sysctl", "-w",
                f"net.ipv4.conf.{spec.host_interface}.rp_filter=0",
            )
        )
        runner.run(
            (
                "ip", "netns", "exec", spec.namespace,
                "sysctl", "-w",
                f"net.ipv4.conf.{spec.inner_interface}.proxy_arp=1",
            )
        )
        runner.run(
            (
                "ip", "netns", "exec", spec.namespace,
                "sysctl", "-w",
                f"net.ipv4.conf.{spec.inner_interface}.rp_filter=0",
            )
        )
        runner.run(
            (
                "ip", "-4", "route", "replace",
                spec.inner_address.network.with_prefixlen,
                "dev", spec.host_interface,
            )
        )
        verification = verify_managed_l3_boundary(spec, runner)
        if not verification.confirmed:
            raise ManagedNetworkDomainError(
                "created ordinary-side transition failed verification: "
                + "; ".join(verification.errors)
            )
        return ManagedL3BoundaryEnsureResult(True, verification)
    except Exception:
        if created_host:
            try:
                runner.run(("ip", "link", "del", spec.host_interface))
            except Exception:
                pass
        raise


def destroy_managed_l3_boundary(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    """Remove exact/owned transition; do not infer ownership from orphan names."""
    namespace_exists = spec.namespace in _namespace_names(runner)
    if namespace_exists:
        _require_containment(spec, runner)
    host = _single_link(_link_rows(runner), spec.host_interface)
    inner = (
        _single_link(
            _link_rows(runner, namespace=spec.namespace),
            spec.inner_interface,
        )
        if namespace_exists
        else None
    )
    if host is None and inner is None:
        return
    if host is None or inner is None:
        raise ManagedNetworkDomainError(
            "cannot safely destroy partially present ordinary-side transition"
        )
    verification = verify_managed_l3_boundary(spec, runner)
    if not verification.confirmed:
        raise ManagedNetworkDomainError(
            "cannot destroy unverified ordinary-side transition: "
            + "; ".join(verification.errors)
        )
    runner.run(("ip", "link", "del", spec.host_interface))
    host_after = _single_link(_link_rows(runner), spec.host_interface)
    inner_after = _single_link(
        _link_rows(runner, namespace=spec.namespace),
        spec.inner_interface,
    )
    if host_after is not None or inner_after is not None:
        raise ManagedNetworkDomainError(
            "ordinary-side transition endpoints remain after destroy"
        )


def observe_ordinary_side_portal(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> OrdinarySidePortalVerification:
    """Observe only Private-network service address + ordinary-side default."""
    if spec.namespace not in _namespace_names(runner):
        return OrdinarySidePortalVerification(
            False,
            (f"namespace {spec.namespace!r} is missing",),
        )
    inner = _single_link(
        _link_rows(runner, namespace=spec.namespace),
        spec.inner_interface,
    )
    if inner is None:
        return OrdinarySidePortalVerification(
            False,
            (f"private boundary endpoint {spec.inner_interface!r} is missing",),
        )

    errors = []
    addresses = _ipv4_addresses(
        runner,
        spec.inner_interface,
        namespace=spec.namespace,
    )
    if addresses != frozenset((spec.inner_address,)):
        errors.append(
            "private boundary IPv4 address set does not exactly match "
            f"{spec.inner_address.with_prefixlen}"
        )

    routes = _json_array(
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "-j", "-4", "route", "show", "table", "main",
            )
        ),
        "namespace main-route snapshot",
    )
    defaults = [
        row for row in routes if row.get("dst", "default") == "default"
    ]
    if len(defaults) != 1 or not (
        defaults[0].get("dev") == spec.inner_interface
        and defaults[0].get("gateway") is None
    ):
        errors.append(
            "namespace default route does not exactly use private boundary endpoint"
        )

    return OrdinarySidePortalVerification(
        confirmed=not errors,
        errors=tuple(errors),
    )


def ensure_ordinary_side_portal(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> OrdinarySidePortalVerification:
    """Converge exact owned portal address/default on an exact transition."""
    boundary = verify_managed_l3_boundary(spec, runner)
    if not boundary.confirmed:
        raise ManagedNetworkDomainError(
            "ordinary-side transition is not exact before portal ensure: "
            + "; ".join(boundary.errors)
        )
    _require_containment(spec, runner)

    current = observe_ordinary_side_portal(spec, runner)
    if current.confirmed:
        return current

    runner.run(
        (
            "ip", "-n", spec.namespace,
            "-4", "addr", "flush", "dev", spec.inner_interface,
        )
    )
    runner.run(
        (
            "ip", "-n", spec.namespace,
            "addr", "add", spec.inner_address.with_prefixlen,
            "dev", spec.inner_interface,
        )
    )
    runner.run(
        (
            "ip", "-n", spec.namespace,
            "-4", "route", "flush", "table", "main", "default",
        )
    )
    runner.run(
        (
            "ip", "-n", spec.namespace,
            "-4", "route", "replace", "default",
            "dev", spec.inner_interface,
        )
    )
    final = observe_ordinary_side_portal(spec, runner)
    if not final.confirmed:
        raise ManagedNetworkDomainError(
            "ordinary-side portal convergence failed verification: "
            + "; ".join(final.errors)
        )
    return final


def cleanup_ordinary_side_portal(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    """Remove owned Private portal state while preserving the transition itself."""
    if spec.namespace not in _namespace_names(runner):
        return
    inner = _single_link(
        _link_rows(runner, namespace=spec.namespace),
        spec.inner_interface,
    )
    if inner is None:
        return
    _require_containment(spec, runner)
    runner.run(
        (
            "ip", "-n", spec.namespace,
            "-4", "route", "flush", "table", "main", "default",
        )
    )
    runner.run(
        (
            "ip", "-n", spec.namespace,
            "-4", "addr", "flush", "dev", spec.inner_interface,
        )
    )
    addresses = _ipv4_addresses(
        runner,
        spec.inner_interface,
        namespace=spec.namespace,
    )
    if addresses:
        raise ManagedNetworkDomainError(
            "ordinary-side portal IPv4 state remains after cleanup"
        )
    routes = _json_array(
        runner.run(
            (
                "ip", "-n", spec.namespace,
                "-j", "-4", "route", "show", "table", "main",
            )
        ),
        "namespace main-route snapshot",
    )
    if any(row.get("dst", "default") == "default" for row in routes):
        raise ManagedNetworkDomainError(
            "ordinary-side portal default route remains after cleanup"
        )


# Compatibility orchestration façade for existing controller/experiment callers.
def verify_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkDomainVerification:
    environment = verify_managed_network_environment(spec, runner)
    boundary = verify_managed_l3_boundary(spec, runner)
    portal = observe_ordinary_side_portal(spec, runner)
    errors = environment.errors + boundary.errors + portal.errors
    return ManagedNetworkDomainVerification(
        confirmed=not errors,
        errors=errors,
        host_boundary=(
            boundary.private_boundary
            if not errors
            else None
        ),
    )


def preflight_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkDomainPreflightResult:
    """Classify exact full domain or safely recoverable incomplete realization."""
    environment_exists = preflight_managed_network_environment(spec, runner)
    boundary_exists = preflight_managed_l3_boundary(spec, runner)

    if not environment_exists and not boundary_exists:
        return ManagedNetworkDomainPreflightResult(False, None)

    if environment_exists and not boundary_exists:
        # Exact Private environment with absent transition is now recoverable.
        return ManagedNetworkDomainPreflightResult(False, None)

    portal = observe_ordinary_side_portal(spec, runner)
    if not portal.confirmed:
        # Exact environment + transition with drifted/absent owned portal state
        # is recoverable by ensure_ordinary_side_portal().
        return ManagedNetworkDomainPreflightResult(False, None)

    verification = verify_managed_network_domain(spec, runner)
    if not verification.confirmed:
        raise ManagedNetworkDomainError(
            "existing managed domain failed exact verification: "
            + "; ".join(verification.errors)
        )
    return ManagedNetworkDomainPreflightResult(True, verification)


def ensure_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> ManagedNetworkDomainEnsureResult:
    """Compose the three independent lifecycle contracts in dependency order."""
    preflight_managed_network_domain(spec, runner)
    environment = ensure_managed_network_environment(spec, runner)
    boundary = ensure_managed_l3_boundary(spec, runner)
    ensure_ordinary_side_portal(spec, runner)
    verification = verify_managed_network_domain(spec, runner)
    if not verification.confirmed:
        raise ManagedNetworkDomainError(
            "decomposed managed domain failed final verification: "
            + "; ".join(verification.errors)
        )
    return ManagedNetworkDomainEnsureResult(
        created=environment.created or boundary.created,
        verification=verification,
    )


def destroy_managed_network_domain(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    """Compatibility cleanup: portal -> transition -> environment, all attempted."""
    cleanup_errors = []

    try:
        cleanup_ordinary_side_portal(spec, runner)
    except Exception as exc:
        cleanup_errors.append(
            "ordinary-side portal cleanup failed: "
            f"{type(exc).__name__}: {exc}"
        )

    try:
        destroy_managed_l3_boundary(spec, runner)
    except Exception as exc:
        cleanup_errors.append(
            "ordinary-side transition destroy failed: "
            f"{type(exc).__name__}: {exc}"
        )

    try:
        destroy_managed_network_environment(spec, runner)
    except Exception as exc:
        cleanup_errors.append(
            "managed network environment destroy failed: "
            f"{type(exc).__name__}: {exc}"
        )

    # Strong final absence can supersede earlier contained-artifact diagnostics.
    namespace_absent = spec.namespace not in _namespace_names(runner)
    host_absent = (
        _single_link(_link_rows(runner), spec.host_interface) is None
    )
    if namespace_absent and host_absent:
        return

    if cleanup_errors:
        raise ManagedNetworkDomainError("; ".join(cleanup_errors))
    raise ManagedNetworkDomainError(
        "managed domain cleanup did not confirm final absence"
    )


def _require_containment(
    spec: ManagedNetworkDomainSpec,
    runner: ManagedNetworkDomainRunner,
) -> None:
    result = converge_forwarding_gate_once(
        LinuxForwardingGateDriver(runner, spec.namespace),
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


def _sysctl_int(
    runner: ManagedNetworkDomainRunner,
    key: str,
    *,
    namespace: str | None = None,
) -> int | None:
    argv = (
        ("sysctl", "-n", key)
        if namespace is None
        else ("ip", "netns", "exec", namespace, "sysctl", "-n", key)
    )
    raw = runner.run(argv).strip()
    try:
        return int(raw)
    except ValueError:
        return None


def _route_network(value: object) -> IPv4Network | None:
    if value == "default":
        return IPv4Network("0.0.0.0/0")
    if not isinstance(value, str):
        return None
    try:
        network = ip_network(value, strict=False)
    except ValueError:
        return None
    return network if isinstance(network, IPv4Network) else None


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
