"""Selected production host-boundary contribution for Release-1 alpha/controller use.

This composes:
- stateful host-return dependencies + nft owner from EXP-053;
- selected paired-RPDB host bootstrap owner from EXP-059/060.

The old main-table bootstrap route representation is deliberately not used.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json

from .controller_boundary_contribution import ControllerBoundaryContribution
from .host_boundary_route_convergence import (
    cleanup_host_boundary_route_dependencies_once,
    prepare_host_boundary_route_dependencies_once,
)
from .linux_host_bootstrap import (
    HostBootstrapLinuxDesired,
    build_linux_host_bootstrap_desired,
)
from .linux_host_bootstrap_backend import (
    LinuxHostBootstrapBackend,
    cleanup_host_bootstrap_once,
    converge_host_bootstrap_once,
)
from .linux_host_boundary_policy import (
    HostBoundaryLinuxDesired,
    HostBoundaryReturnRouteSpec,
    HostBoundaryRuleSpec,
    build_linux_host_boundary_desired,
)
from .linux_host_boundary_routes import LinuxHostBoundaryRouteBackend
from .linux_host_return_nft import (
    LinuxHostReturnNftBackend,
    converge_host_return_nft_once,
)
from .release1_config import Release1Config
from .release1_host_boundary import build_release1_host_boundary_plan
from .linux_policy_platform import (
    NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION,
    NG3_HOST_BOUNDARY_LINUX_ALLOCATION,
)
from .managed_network_domain import ManagedNetworkDomainSpec
from .linux_nft_scaffold import NftScriptRunner


@dataclass(frozen=True, slots=True)
class SelectedHostBoundaryDesired:
    return_owner: HostBoundaryLinuxDesired
    bootstrap_owner: HostBootstrapLinuxDesired


@dataclass(frozen=True, slots=True)
class SelectedHostBoundaryObservation:
    exact: bool
    conflicts: tuple[str, ...]


def build_selected_host_boundary_desired(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
) -> SelectedHostBoundaryDesired:
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")
    if not isinstance(domain_spec, ManagedNetworkDomainSpec):
        raise ValueError("domain_spec must be ManagedNetworkDomainSpec")

    plan = build_release1_host_boundary_plan(config)

    # Compile the EXP-053 return owner but deliberately discard its historical
    # main-table bootstrap route representation. Bootstrap is owned exclusively
    # by the selected EXP-059/060 paired-RPDB backend below.
    historical = build_linux_host_boundary_desired(
        plan,
        host_interface=domain_spec.host_interface,
        inner_gateway=domain_spec.inner_address.ip,
        allocation=NG3_HOST_BOUNDARY_LINUX_ALLOCATION,
    )
    return_owner = replace(
        historical,
        underlay_pins=(),
        bootstrap_routes=(),
    )

    bootstrap_owner = build_linux_host_bootstrap_desired(
        plan,
        host_interface=domain_spec.host_interface,
        inner_gateway=domain_spec.inner_address.ip,
        allocation=NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION,
    )
    return SelectedHostBoundaryDesired(
        return_owner=return_owner,
        bootstrap_owner=bootstrap_owner,
    )


@dataclass(slots=True)
class SelectedLinuxHostBoundaryContribution(ControllerBoundaryContribution):
    route_backend: LinuxHostBoundaryRouteBackend
    return_nft_backend: LinuxHostReturnNftBackend
    bootstrap_backend: LinuxHostBootstrapBackend
    desired: SelectedHostBoundaryDesired

    def observe(self) -> SelectedHostBoundaryObservation:
        conflicts: list[str] = []

        bootstrap = self.bootstrap_backend.observe(self.desired.bootstrap_owner)
        conflicts.extend(
            f"bootstrap: {item}" for item in bootstrap.conflicts
        )

        nft = self.return_nft_backend.observe(
            self.desired.return_owner.return_nft
        )
        conflicts.extend(f"return nft: {item}" for item in nft.conflicts)

        route_exact, route_conflicts = _observe_reserved_return_routes(
            self.route_backend,
            self.desired.return_owner.return_route,
        )
        rule_exact, rule_conflicts = _observe_reserved_return_rules(
            self.route_backend,
            self.desired.return_owner.return_rule,
        )
        conflicts.extend(route_conflicts)
        conflicts.extend(rule_conflicts)

        return SelectedHostBoundaryObservation(
            exact=(
                not conflicts
                and bootstrap.exact
                and nft.exact
                and route_exact
                and rule_exact
            ),
            conflicts=tuple(conflicts),
        )

    def converge(self) -> None:
        if not isinstance(self.desired, SelectedHostBoundaryDesired):
            raise ValueError("desired must be SelectedHostBoundaryDesired")

        initial = self.observe()
        if initial.conflicts:
            raise RuntimeError(
                "selected host-boundary owner conflict: "
                + "; ".join(initial.conflicts)
            )
        if initial.exact:
            return

        # Stateful-return dependencies are dormant until the packet mark exists.
        prepare_host_boundary_route_dependencies_once(
            self.route_backend,
            self.desired.return_owner,
        )
        converge_host_return_nft_once(
            self.return_nft_backend,
            self.desired.return_owner.return_nft,
        )
        # Bootstrap capture is exposed last.
        converge_host_bootstrap_once(
            self.bootstrap_backend,
            self.desired.bootstrap_owner,
        )
        final = self.observe()
        if final.conflicts:
            raise RuntimeError(
                "selected host-boundary postcondition conflict: "
                + "; ".join(final.conflicts)
            )
        if not final.exact:
            raise RuntimeError(
                "selected host-boundary fresh postcondition is not exact"
            )

    def cleanup(self) -> None:
        errors: list[str] = []

        # Stop ordinary-side capture before retiring return machinery.
        try:
            cleanup_host_bootstrap_once(
                self.bootstrap_backend,
                self.desired.bootstrap_owner,
            )
        except Exception as exc:
            errors.append(f"bootstrap cleanup: {exc}")

        try:
            converge_host_return_nft_once(self.return_nft_backend, None)
        except Exception as exc:
            errors.append(f"return nft cleanup: {exc}")

        try:
            cleanup_host_boundary_route_dependencies_once(
                self.route_backend,
                self.desired.return_owner,
            )
        except Exception as exc:
            errors.append(f"return route cleanup: {exc}")

        if errors:
            raise RuntimeError("; ".join(errors))


def build_selected_linux_host_boundary_contribution(
    config: Release1Config,
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
) -> SelectedLinuxHostBoundaryContribution | None:
    desired = build_selected_host_boundary_desired(config, domain_spec)
    if (
        not desired.bootstrap_owner.routes
        and desired.return_owner.return_route is None
        and desired.return_owner.return_rule is None
        and desired.return_owner.return_nft is None
    ):
        return None

    route_backend = LinuxHostBoundaryRouteBackend(runner)
    return_nft_backend = LinuxHostReturnNftBackend(runner)
    bootstrap_backend = LinuxHostBootstrapBackend(
        runner,
        NG3_HOST_BOOTSTRAP_LINUX_ALLOCATION,
    )
    return SelectedLinuxHostBoundaryContribution(
        route_backend=route_backend,
        return_nft_backend=return_nft_backend,
        bootstrap_backend=bootstrap_backend,
        desired=desired,
    )


def _observe_reserved_return_routes(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryReturnRouteSpec | None,
) -> tuple[bool, list[str]]:
    raw = backend.runner.run(
        backend._cmd("ip", "-j", "-4", "route", "show", "table", "all")
    )
    try:
        rows = json.loads(raw)
    except (TypeError, ValueError):
        raise RuntimeError("invalid host return route JSON") from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("host return route JSON must be an array of objects")

    table = NG3_HOST_BOUNDARY_LINUX_ALLOCATION.return_table
    scoped = [
        row for row in rows
        if _decimal(row.get("table")) == table
    ]
    if desired is None:
        if scoped:
            return False, [
                "reserved host return table is occupied while no return route is desired"
            ]
        return True, []

    if len(scoped) != 1:
        return False, [
            "reserved host return table does not contain exactly one desired owner route"
        ]
    row = scoped[0]
    exact = (
        row.get("dst", "default") == "default"
        and row.get("type", "unicast") == "unicast"
        and row.get("dev") == desired.interface
        and row.get("gateway") == str(desired.via)
        and _decimal(row.get("protocol")) == desired.protocol
        and row.get("metric") in (None, 0, "0")
    )
    if not exact:
        return False, ["reserved host return route differs from exact desired owner"]
    return True, []


def _observe_reserved_return_rules(
    backend: LinuxHostBoundaryRouteBackend,
    desired: HostBoundaryRuleSpec | None,
) -> tuple[bool, list[str]]:
    raw = backend.runner.run(
        backend._cmd("ip", "-j", "-4", "rule", "show")
    )
    try:
        rows = json.loads(raw)
    except (TypeError, ValueError):
        raise RuntimeError("invalid host return rule JSON") from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("host return rule JSON must be an array of objects")

    priority = NG3_HOST_BOUNDARY_LINUX_ALLOCATION.return_rule_priority
    scoped = [
        row for row in rows
        if _decimal(row.get("priority")) == priority
    ]
    if desired is None:
        if scoped:
            return False, [
                "reserved host return RPDB priority is occupied while no return rule is desired"
            ]
        return True, []

    if len(scoped) != 1:
        return False, [
            "reserved host return RPDB priority does not contain exactly one desired owner rule"
        ]
    row = scoped[0]
    fwmark = _number(row.get("fwmark"))
    mask = row.get("fwmask")
    exact = (
        row.get("src") in (None, "all")
        and _decimal(row.get("table")) == desired.table
        and fwmark == desired.mark
        and (mask is None or _number(mask) == 0xFFFFFFFF)
        and all(
            key not in row
            for key in ("iif", "oif", "dst", "sport", "dport", "ipproto")
        )
    )
    if not exact:
        return False, ["reserved host return RPDB rule differs from exact desired owner"]
    return True, []


def _decimal(value: object) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _number(value: object) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None
