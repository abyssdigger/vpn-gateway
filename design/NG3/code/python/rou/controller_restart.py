"""Bounded NG3 controller restart composition.

Architecture: structured Annex A A.001 ProductLifecycleControl.
The component spec owns normative requirement traceability.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .controller_startup import (
    ControllerStartupResult,
    ControllerStartupSession,
    ValidatedPolicyLoader,
    start_controller_once,
)
from .controller_stop import (
    ControllerStopResult,
    stop_controller_once,
)
from .instance_lock import InstanceLockSpec
from .linux_nft_scaffold import NftScriptRunner
from .managed_network_domain import ManagedNetworkDomainSpec
from .network_policy_layout import NetworkPolicyPlatformSpace


class ControllerRestartStatus(str, Enum):
    READY = "ready"
    STOP_FAILED = "stop_failed"
    START_FAILED = "start_failed"


@dataclass(frozen=True, slots=True)
class ControllerRestartResult:
    status: ControllerRestartStatus
    stop: ControllerStopResult
    start: ControllerStartupResult | None

    @property
    def ready(self) -> bool:
        return (
            self.status is ControllerRestartStatus.READY
            and self.start is not None
            and self.start.ready
        )

    @property
    def session(self) -> ControllerStartupSession | None:
        if not self.ready or self.start is None:
            return None
        return self.start.session


def restart_controller_once(
    current_session: ControllerStartupSession,
    lock_spec: InstanceLockSpec,
    domain_spec: ManagedNetworkDomainSpec,
    runner: NftScriptRunner,
    platform: NetworkPolicyPlatformSpace,
    load_validated_policy: ValidatedPolicyLoader,
) -> ControllerRestartResult:
    """Stop the current READY session, then perform one ordinary bounded start.

    Startup is never invoked unless stop reached its confirmed STOPPED
    postcondition. No restart-specific retry or recovery state is hidden here.
    """
    stopped = stop_controller_once(
        current_session,
        domain_spec,
        runner,
    )
    if not stopped.stopped:
        return ControllerRestartResult(
            status=ControllerRestartStatus.STOP_FAILED,
            stop=stopped,
            start=None,
        )

    started = start_controller_once(
        lock_spec,
        domain_spec,
        runner,
        platform,
        load_validated_policy,
    )
    return ControllerRestartResult(
        status=(
            ControllerRestartStatus.READY
            if started.ready
            else ControllerRestartStatus.START_FAILED
        ),
        stop=stopped,
        start=started,
    )
