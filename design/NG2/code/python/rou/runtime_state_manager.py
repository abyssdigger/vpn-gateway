from __future__ import annotations

from typing import Protocol

from .availability_probe_state import AvailabilityProbeStateInfo
from .payload_rules import PayloadTrafficStateRequest
from .payload_traffic_intent import (
    PayloadTrafficIntentCalculator,
    ProbeProfileEvidenceCalculator,
    ProfileProbeAssignment,
)
from .probe_rules import AvailabilityProbeSetRequest


class PayloadTrafficRequestPublisher(Protocol):
    def publish(self, request: PayloadTrafficStateRequest) -> None:
        ...


class RuntimeStateManager:
    """Initial NG2 RuntimeStateManager slice for availability-driven payload priority.

    This Engine-side state owns latest semantic snapshots only. It does not call Linux
    machinery and does not synchronously command PayloadTrafficManager.
    """

    def __init__(
        self,
        publisher: PayloadTrafficRequestPublisher,
        *,
        evidence_calculator: ProbeProfileEvidenceCalculator | None = None,
        intent_calculator: PayloadTrafficIntentCalculator | None = None,
    ) -> None:
        self._publisher = publisher
        self._evidence_calculator = (
            evidence_calculator or ProbeProfileEvidenceCalculator()
        )
        self._intent_calculator = (
            intent_calculator or PayloadTrafficIntentCalculator()
        )

        self._configured_payload: PayloadTrafficStateRequest | None = None
        self._effective_payload: PayloadTrafficStateRequest | None = None
        self._probe_request: AvailabilityProbeSetRequest | None = None
        self._assignments: tuple[ProfileProbeAssignment, ...] = ()
        self._probe_states: dict[str, AvailabilityProbeStateInfo] = {}

    @property
    def effective_payload(self) -> PayloadTrafficStateRequest | None:
        return self._effective_payload

    def update_payload_routing_inputs(
        self,
        configured_payload: PayloadTrafficStateRequest,
        probe_request: AvailabilityProbeSetRequest,
        assignments: tuple[ProfileProbeAssignment, ...],
    ) -> None:
        """Accept the current structural/admin payload and probe mapping snapshot."""

        previous_configured = self._configured_payload
        previous_probe_request = self._probe_request

        if previous_probe_request is not None:
            previous_by_id = {
                probe.probe_id: probe
                for probe in previous_probe_request.probes
            }
            current_by_id = {
                probe.probe_id: probe
                for probe in probe_request.probes
            }

            for probe_id in tuple(self._probe_states):
                if (
                    probe_id not in current_by_id
                    or previous_by_id.get(probe_id)
                    != current_by_id[probe_id]
                ):
                    self._probe_states.pop(probe_id, None)
        else:
            current_ids = {
                probe.probe_id
                for probe in probe_request.probes
            }
            for probe_id in tuple(self._probe_states):
                if probe_id not in current_ids:
                    self._probe_states.pop(probe_id, None)

        self._configured_payload = configured_payload
        self._probe_request = probe_request
        self._assignments = assignments

        self._recalculate_and_publish(
            previous_configured=previous_configured,
        )

    def handle_probe_state(self, info: AvailabilityProbeStateInfo) -> None:
        """Consume one latest-value AvailabilityProbeStateInfo projection."""

        probe_request = self._probe_request
        if probe_request is None:
            return

        current_ids = {
            probe.probe_id
            for probe in probe_request.probes
        }
        if info.probe_id not in current_ids:
            # A removal invalidation may arrive after the full desired probe snapshot
            # has already advanced. It cannot influence current payload intent.
            return

        if self._probe_states.get(info.probe_id) == info:
            return

        self._probe_states[info.probe_id] = info
        self._recalculate_and_publish(
            previous_configured=self._configured_payload,
        )

    def _recalculate_and_publish(
        self,
        *,
        previous_configured: PayloadTrafficStateRequest | None,
    ) -> None:
        configured = self._configured_payload
        probe_request = self._probe_request
        if configured is None or probe_request is None:
            return

        evidence = self._evidence_calculator.calculate(
            probe_request,
            tuple(self._probe_states.values()),
            self._assignments,
        )
        effective = self._intent_calculator.calculate(
            configured,
            previous_configured=previous_configured,
            current_effective=self._effective_payload,
            availability=evidence,
        )

        if effective == self._effective_payload:
            return

        self._effective_payload = effective
        self._publisher.publish(effective)
