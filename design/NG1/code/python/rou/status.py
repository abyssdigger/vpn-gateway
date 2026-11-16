from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address

from .command_backend import NamespaceBackend
from .config import validate_active_config
from .domain import ActiveConfig
from .environment import EnvironmentSnapshot
from .kernel_state import verify_kernel_desired_state
from .namespace_prereq import verify_namespace_prerequisites
from .nft_policy import (
    observe_nft_ruleset_inventory,
    verify_nft_ruleset_ownership,
    verify_nft_table,
)
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
    *,
    local_publication_address: IPv4Address | None = None,
) -> RuntimeStatus:
    """Read-only full desired-vs-observed status using production projectors/verifiers."""

    validate_active_config(config)
    if backend.namespace != namespace:
        raise ValueError(
            f"status namespace mismatch: requested {namespace!r}, "
            f"backend is {backend.namespace!r}"
        )

    projection = compile_planner_projection(
        config,
        committed,
        snapshot,
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

    ownership = verify_nft_ruleset_ownership(
        observe_nft_ruleset_inventory(backend)
    )
    if not ownership.ok:
        errors.append(
            "foreign nft tables present: "
            + repr(ownership.foreign_tables)
        )

    firewall = verify_nft_table(projection.firewall, backend)
    if not firewall.ok:
        errors.append("nft filter table mismatch")

    nat = verify_nft_table(projection.nat, backend)
    if not nat.ok:
        errors.append("nft NAT table mismatch")

    return RuntimeStatus(
        ok=not errors,
        errors=tuple(errors),
        projection=projection,
    )
