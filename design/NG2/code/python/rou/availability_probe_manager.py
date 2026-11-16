from __future__ import annotations

from typing import Protocol

from .availability_probe_state import (
    AvailabilityProbeState,
    AvailabilityProbeStateInfo,
    ProbeObservationGeneration,
)
from .network_rules import (
    ActionResult,
    NetworkRulesAdapter,
    NetworkRulesConvergenceState,
    NetworkRulesSpec,
    RulesConvergence,
    StateKnowledge,
    assess_network_rules_convergence,
    network_rules_semantically_equal,
)
from .probe_rules import (
    AvailabilityProbeSetRequest,
    ProbeRulesCalculator,
    availability_probe_sets_semantically_equal,
)
class AvailabilityProbeStatePublisher(Protocol):
    def publish(self, info: AvailabilityProbeStateInfo) -> None:
        ...


class AvailabilityProbeManager:
    """Own the active-probe rules plane and its authoritative readiness epoch.

    Probe execution is intentionally not a synchronous dependency of this Manager.
    Production evidence arrives through the good-news/window model that is integrated
    separately.  This class currently owns only the already-proven NetworkRules lifecycle,
    generation invalidation and publication invalidation boundary.
    """

    def __init__(
        self,
        adapter: NetworkRulesAdapter,
        publisher: AvailabilityProbeStatePublisher,
        *,
        rules_calculator: ProbeRulesCalculator | None = None,
    ) -> None:
        self._adapter = adapter
        self._publisher = publisher
        self._rules_calculator = rules_calculator or ProbeRulesCalculator()

        self._latest_request: AvailabilityProbeSetRequest | None = None
        self._latest_desired: NetworkRulesSpec | None = None
        self._latest_published: dict[str, AvailabilityProbeStateInfo] = {}

        self._generation_sequence = 0
        self._active_generation: ProbeObservationGeneration | None = None

    @property
    def observation_generation(self) -> ProbeObservationGeneration | None:
        """Current owner-wide READY epoch for diagnostics and evidence binding."""

        return self._active_generation

    def handle_request(self, request: AvailabilityProbeSetRequest) -> None:
        """Accept one full desired probe snapshot and reconcile its network plane."""

        desired = self._rules_calculator.calculate(request)

        changed = (
            self._latest_request is None
            or not availability_probe_sets_semantically_equal(
                self._latest_request,
                request,
            )
        )

        if changed:
            previous_request = self._latest_request
            previous_desired = self._latest_desired
            physical_changed = (
                previous_desired is None
                or not network_rules_semantically_equal(
                    previous_desired,
                    desired,
                )
            )

            if physical_changed:
                self._invalidate_generation()
            else:
                self._invalidate_changed_logical_probes(
                    previous_request,
                    request,
                )

            self._publish_removed_invalidations(request)
            self._latest_request = request
            self._latest_desired = desired

            if physical_changed:
                rules_state = self._apply_desired_and_observe(desired)
            else:
                rules_state = self._audit_rules(desired)
        else:
            assert self._latest_desired is not None
            rules_state = self._audit_rules(self._latest_desired)

        self._synchronize_generation(rules_state)
        self._publish_unknown_current(rules_state)

    def audit(self) -> None:
        """Run one deterministic rules refresh/repair pass."""

        desired = self._latest_desired
        if desired is None:
            return

        rules_state = self._audit_rules(desired)
        self._synchronize_generation(rules_state)
        self._publish_unknown_current(rules_state)

    def shutdown(self) -> ActionResult:
        """Release all NetworkRules state owned by this Manager instance."""

        self._invalidate_generation()
        return self._adapter.cleanup(self)

    def _audit_rules(
        self,
        desired: NetworkRulesSpec,
    ) -> NetworkRulesConvergenceState:
        self._adapter.renew_state(self)
        rules_state = self._current_rules_state(desired)

        if self._rules_ready(rules_state):
            return rules_state

        self._invalidate_generation()
        return self._apply_desired_and_observe(desired)

    def _apply_desired_and_observe(
        self,
        desired: NetworkRulesSpec,
    ) -> NetworkRulesConvergenceState:
        action = self._adapter.apply(self, desired)
        if not action.success:
            self._adapter.renew_state(self)
        return self._current_rules_state(desired)

    def _current_rules_state(
        self,
        desired: NetworkRulesSpec,
    ) -> NetworkRulesConvergenceState:
        observed = self._adapter.get_last_state(self)
        return assess_network_rules_convergence(desired, observed)

    @staticmethod
    def _rules_ready(state: NetworkRulesConvergenceState) -> bool:
        return (
            state.knowledge is StateKnowledge.KNOWN
            and state.convergence is RulesConvergence.MATCHED
        )

    def _synchronize_generation(self, state: NetworkRulesConvergenceState) -> None:
        request = self._latest_request
        if (
            request is None
            or not any(probe.enabled for probe in request.probes)
        ):
            self._invalidate_generation()
            return

        if not self._rules_ready(state):
            self._invalidate_generation()
            return

        if self._active_generation is None:
            self._generation_sequence += 1
            self._active_generation = ProbeObservationGeneration(
                self._generation_sequence
            )

    def _invalidate_generation(self) -> None:
        self._active_generation = None

    def _invalidate_changed_logical_probes(
        self,
        previous: AvailabilityProbeSetRequest | None,
        current: AvailabilityProbeSetRequest,
    ) -> None:
        if previous is None:
            return

        previous_by_id = {
            item.probe_id: item
            for item in previous.probes
        }
        current_by_id = {
            item.probe_id: item
            for item in current.probes
        }

        for probe_id in previous_by_id.keys() & current_by_id.keys():
            if previous_by_id[probe_id] == current_by_id[probe_id]:
                continue
            self._latest_published.pop(probe_id, None)

    def _publish_removed_invalidations(
        self,
        request: AvailabilityProbeSetRequest,
    ) -> None:
        live_ids = {item.probe_id for item in request.probes}
        removed_ids = sorted(
            probe_id
            for probe_id in self._latest_published
            if probe_id not in live_ids
        )

        for probe_id in removed_ids:
            info = AvailabilityProbeStateInfo(
                probe_id,
                AvailabilityProbeState.UNKNOWN,
                reason="probe no longer requested",
            )
            if self._latest_published.get(probe_id) != info:
                self._publisher.publish(info)
            self._latest_published.pop(probe_id, None)

    def _publish_unknown_current(
        self,
        rules_state: NetworkRulesConvergenceState,
    ) -> None:
        request = self._latest_request
        if request is None:
            return

        reason = (
            "no authoritative probe evidence for current rules generation"
            if self._rules_ready(rules_state)
            else "probe rules are not ready"
        )

        for probe in sorted(request.probes, key=lambda item: item.probe_id):
            if not probe.enabled:
                self._publish_if_changed(
                    AvailabilityProbeStateInfo(
                        probe.probe_id,
                        AvailabilityProbeState.UNKNOWN,
                        reason="probe disabled",
                    )
                )
                continue

            latest = self._latest_published.get(probe.probe_id)
            if (
                self._rules_ready(rules_state)
                and self._active_generation is not None
                and latest is not None
                and latest.state is not AvailabilityProbeState.UNKNOWN
                and latest.observation_generation == self._active_generation
            ):
                continue

            self._publish_if_changed(
                AvailabilityProbeStateInfo(
                    probe.probe_id,
                    AvailabilityProbeState.UNKNOWN,
                    reason=reason,
                )
            )

    def _publish_if_changed(
        self,
        info: AvailabilityProbeStateInfo,
    ) -> None:
        if self._latest_published.get(info.probe_id) == info:
            return
        self._publisher.publish(info)
        self._latest_published[info.probe_id] = info
