from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Address
from math import isfinite
from typing import Callable, Generic, TypeVar
import time

from .availability_collector import (
    AvailabilityGoodNews,
    AvailabilityHysteresisPolicy,
    AvailabilityPriorityChannel,
    AvailabilityPriorityConfig,
    AvailabilityTick,
    ProfileAvailabilityAssignment,
)
from .availability_probe_manager import AvailabilityProbeManager
from .linux_probe_execution import (
    LinuxProbeExecutionAgent,
    ProbeExecutionDiagnosticPublisher,
    ProbeSendDriver,
)
from .interface_identity import InterfaceIdentity
from .network_rules import ActionResult, NetworkRulesAdapter
from .payload_rules import PayloadTrafficStateRequest
from .payload_traffic_manager import (
    PayloadTrafficManager,
    PayloadTrafficStatePublisher,
)
from .probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
    ProbeMechanism,
)
from .probe_transport import ProbeExecutionPlan


@dataclass(frozen=True)
class RuntimeAvailabilityChannel:
    """Normalized upstream availability channel before domain projection."""

    channel_id: str
    path: InterfaceIdentity
    target: IPv4Address
    mechanism: ProbeMechanism = ProbeMechanism.ICMP
    enabled: bool = True
    interval_seconds: float = field(kw_only=True)
    hysteresis: AvailabilityHysteresisPolicy = field(kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.channel_id, str) or not self.channel_id:
            raise ValueError("runtime availability channel_id must be non-empty")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError(
                "runtime availability path must be InterfaceIdentity"
            )
        if not isinstance(self.target, IPv4Address):
            raise ValueError(
                "runtime availability target must be IPv4Address"
            )
        if not isinstance(self.mechanism, ProbeMechanism):
            raise ValueError(
                "runtime availability mechanism must be ProbeMechanism"
            )
        if type(self.enabled) is not bool:
            raise ValueError("runtime availability enabled must be boolean")
        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
            or not isfinite(float(self.interval_seconds))
            or float(self.interval_seconds) <= 0
        ):
            raise ValueError(
                "runtime availability interval_seconds must be positive finite"
            )
        if not isinstance(self.hysteresis, AvailabilityHysteresisPolicy):
            raise ValueError(
                "runtime availability hysteresis must be "
                "AvailabilityHysteresisPolicy"
            )


@dataclass(frozen=True)
class RuntimeAvailabilityConfig:
    """Normalized current availability slice shared by independent projections."""

    channels: tuple[RuntimeAvailabilityChannel, ...]
    assignments: tuple[ProfileAvailabilityAssignment, ...]

    def __post_init__(self) -> None:
        ids = [item.channel_id for item in self.channels]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate runtime availability channel_id")

        profile_names = [item.profile_name for item in self.assignments]
        if len(set(profile_names)) != len(profile_names):
            raise ValueError(
                "duplicate runtime Profile availability assignment"
            )

        known = set(ids)
        for assignment in self.assignments:
            missing = set(assignment.channel_ids) - known
            if missing:
                raise ValueError(
                    f"Profile {assignment.profile_name!r} references "
                    "unknown runtime availability channel_id: "
                    + ", ".join(sorted(missing))
                )


class AvailabilityProbeSetCalculator:
    """Project normalized runtime availability into physical/logical probe demand."""

    def calculate(
        self,
        config: RuntimeAvailabilityConfig,
    ) -> AvailabilityProbeSetRequest:
        if not isinstance(config, RuntimeAvailabilityConfig):
            raise ValueError(
                "probe projection requires RuntimeAvailabilityConfig"
            )

        return AvailabilityProbeSetRequest(
            tuple(
                AvailabilityProbeRequest(
                    item.channel_id,
                    item.path,
                    item.target,
                    mechanism=item.mechanism,
                    enabled=item.enabled,
                    interval_seconds=item.interval_seconds,
                    hysteresis=item.hysteresis,
                )
                for item in config.channels
            )
        )


class AvailabilityPriorityConfigCalculator:
    """Project the same normalized slice onto payload-priority semantics."""

    def calculate(
        self,
        config: RuntimeAvailabilityConfig,
    ) -> AvailabilityPriorityConfig:
        if not isinstance(config, RuntimeAvailabilityConfig):
            raise ValueError(
                "availability priority projection requires "
                "RuntimeAvailabilityConfig"
            )

        return AvailabilityPriorityConfig(
            tuple(
                AvailabilityPriorityChannel(
                    item.channel_id,
                    item.path,
                    item.enabled,
                    item.hysteresis,
                )
                for item in config.channels
            ),
            config.assignments,
        )


_T = TypeVar("_T")


class CallbackPublisher(Generic[_T]):
    """Minimal synchronous publisher adapter for process-local wiring."""

    def __init__(self, callback: Callable[[_T], object]) -> None:
        if not callable(callback):
            raise ValueError("publisher callback must be callable")
        self._callback = callback

    def publish(self, value: _T) -> None:
        self._callback(value)


@dataclass
class LinuxAvailabilityRuntimeAssembly:
    """Executable Linux availability wiring around an existing PayloadTrafficManager."""

    probe_manager: AvailabilityProbeManager
    payload_manager: PayloadTrafficManager
    agent: LinuxProbeExecutionAgent
    probe_calculator: AvailabilityProbeSetCalculator = field(
        default_factory=AvailabilityProbeSetCalculator
    )
    priority_calculator: AvailabilityPriorityConfigCalculator = field(
        default_factory=AvailabilityPriorityConfigCalculator
    )
    _stopped: bool = field(default=False, init=False, repr=False)

    def _require_active(self) -> None:
        if self._stopped:
            raise RuntimeError("availability runtime has been stopped")

    def configure(self, config: RuntimeAvailabilityConfig) -> None:
        self._require_active()
        priority = self.priority_calculator.calculate(config)
        probes = self.probe_calculator.calculate(config)

        # Ordered assembly, not a cross-Manager transaction.
        self.payload_manager.configure_availability(priority)
        self.probe_manager.handle_request(probes)

    def start(self) -> None:
        self._require_active()
        self.agent.start()

    def stop(self) -> ActionResult:
        """Terminally quiesce probe work and clean probe-owned network rules."""

        self._stopped = True
        try:
            result = self.probe_manager.shutdown()
        finally:
            self.agent.stop()
        return result


def build_linux_availability_runtime(
    probe_adapter: NetworkRulesAdapter,
    payload_manager: PayloadTrafficManager,
    driver: ProbeSendDriver,
    diagnostic_publisher: ProbeExecutionDiagnosticPublisher,
    *,
    timeout_seconds: int,
    clock: Callable[[], float] = time.monotonic,
) -> LinuxAvailabilityRuntimeAssembly:
    """Wire the current Linux probe execution path directly to payload priority."""

    good_news = CallbackPublisher(
        payload_manager.handle_availability_good_news
    )
    tick = CallbackPublisher(
        payload_manager.handle_availability_tick
    )
    agent = LinuxProbeExecutionAgent(
        driver,
        good_news,
        tick,
        diagnostic_publisher,
        timeout_seconds=timeout_seconds,
        clock=clock,
    )
    probe_manager = AvailabilityProbeManager(
        probe_adapter,
        execution_plan_publisher=CallbackPublisher(agent.update_plan),
    )
    return LinuxAvailabilityRuntimeAssembly(
        probe_manager,
        payload_manager,
        agent,
    )


@dataclass(frozen=True)
class NetworkPolicyRuntimeStopResult:
    probe_cleanup: ActionResult
    payload_cleanup: ActionResult

    @property
    def success(self) -> bool:
        return self.probe_cleanup.success and self.payload_cleanup.success


@dataclass
class LinuxNetworkPolicyRuntime:
    """Outer owner of the current Linux network-policy Managers/Agent."""

    payload_manager: PayloadTrafficManager
    availability: LinuxAvailabilityRuntimeAssembly
    _stopped: bool = field(default=False, init=False, repr=False)

    def _require_active(self) -> None:
        if self._stopped:
            raise RuntimeError("network-policy runtime has been stopped")

    def handle_payload_request(
        self,
        request: PayloadTrafficStateRequest,
    ) -> None:
        self._require_active()
        self.payload_manager.handle_request(request)

    def configure_availability(
        self,
        config: RuntimeAvailabilityConfig,
    ) -> None:
        self._require_active()
        self.availability.configure(config)

    def start(self) -> None:
        self._require_active()
        self.availability.start()

    def audit(self) -> None:
        self._require_active()
        try:
            self.availability.probe_manager.audit()
        finally:
            self.payload_manager.audit()

    def stop(self) -> NetworkPolicyRuntimeStopResult:
        self._stopped = True
        probe_result: ActionResult
        try:
            probe_result = self.availability.stop()
        finally:
            payload_result = self.payload_manager.shutdown()
        return NetworkPolicyRuntimeStopResult(
            probe_result,
            payload_result,
        )


def build_linux_network_policy_runtime(
    adapter: NetworkRulesAdapter,
    payload_publisher: PayloadTrafficStatePublisher,
    probe_driver: ProbeSendDriver,
    diagnostic_publisher: ProbeExecutionDiagnosticPublisher,
    *,
    timeout_seconds: int,
    clock: Callable[[], float] = time.monotonic,
) -> LinuxNetworkPolicyRuntime:
    """Build both network-policy owners on one owner-composing Adapter."""

    payload_manager = PayloadTrafficManager(
        adapter,
        payload_publisher,
    )
    availability = build_linux_availability_runtime(
        adapter,
        payload_manager,
        probe_driver,
        diagnostic_publisher,
        timeout_seconds=timeout_seconds,
        clock=clock,
    )
    return LinuxNetworkPolicyRuntime(
        payload_manager,
        availability,
    )

