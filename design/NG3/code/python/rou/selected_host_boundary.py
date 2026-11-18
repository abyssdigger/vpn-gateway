"""Selected production host-boundary contribution for Release-1 alpha/controller use.

This composes:
- stateful host-return dependencies + nft owner from EXP-053;
- selected paired-RPDB host bootstrap owner from EXP-059/060.

The old main-table bootstrap route representation is deliberately not used.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

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

    def converge(self) -> None:
        if not isinstance(self.desired, SelectedHostBoundaryDesired):
            raise ValueError("desired must be SelectedHostBoundaryDesired")

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
