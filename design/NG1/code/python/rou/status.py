from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address

from .command_backend import NamespaceBackend
from .domain import ActiveConfig
from .environment import EnvironmentSnapshot
from .firewall_kernel import verify_filter_state
from .kernel_state import verify_kernel_desired_state
from .namespace_prereq import verify_namespace_prerequisites
from .nat_kernel import verify_nat_state
from .nat_state import NatProvider
from .planner import (
    PlannerProjection,
    PlannerRuntimeState,
    compile_planner_projection,
)


@dataclass(frozen=True)
class RuntimeStatus:
    ok: bool
    errors: tuple[str, ...]
    projection: PlannerProjection


def inspect_runtime_status(
    config: ActiveConfig,
    namespace: str,
    committed: PlannerRuntimeState,
    snapshot: EnvironmentSnapshot,
    backend: NamespaceBackend,
    nat_provider: NatProvider,
    *,
    local_publication_address: IPv4Address | None = None,
) -> RuntimeStatus:
    """Read-only full desired-vs-observed status using production projectors/verifiers."""

    projection = compile_planner_projection(
        config,
        committed,
        snapshot,
        nat_provider,
        None,
        local_publication_address,
    )
    errors: list[str] = []

    kernel = verify_kernel_desired_state(projection.kernel, snapshot)
    errors.extend(kernel.errors)

    forwarding_text = snapshot.sysctl_map.get("net.ipv4.ip_forward")
    if forwarding_text not in {"0", "1"}:
        errors.append(
            "net.ipv4.ip_forward is not observable as 0/1"
        )
    else:
        prereq = verify_namespace_prerequisites(
            snapshot,
            projection.bindings,
            forwarding=forwarding_text == "1",
        )
        errors.extend(prereq.errors)

    firewall = verify_filter_state(projection.firewall, backend)
    if not firewall.ok:
        errors.append("filter table mismatch")

    nat = verify_nat_state(projection.nat, backend)
    if not nat.ok:
        errors.append("nat table mismatch")

    return RuntimeStatus(
        ok=not errors,
        errors=tuple(errors),
        projection=projection,
    )
