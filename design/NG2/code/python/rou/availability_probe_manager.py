from __future__ import annotations

from threading import RLock
from typing import Protocol

from .availability_probe_state import ProbeObservationGeneration
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
from .probe_transport import (
    ProbeExecutionPlan,
    ProbeExecutionPlanCalculator,
)


class ProbeExecutionPlanPublisher(Protocol):
    def publish(self, plan: ProbeExecutionPlan | None) -> None:
        ...


class AvailabilityProbeManager:
    """Own only active-probe NetworkRules readiness and execution demand.

    Availability routing hysteresis is intentionally outside this Manager. The only
    generation state retained here guards physical worker lifetime across ProbeRules /
    concrete-interface replacement.
    """

    def __init__(
        self,
        adapter: NetworkRulesAdapter,
        *,
        rules_calculator: ProbeRulesCalculator | None = None,
        execution_plan_calculator: ProbeExecutionPlanCalculator | None = None,
        execution_plan_publisher: ProbeExecutionPlanPublisher | None = None,
    ) -> None:
        self._adapter = adapter
        self._state_lock = RLock()
        self._rules_calculator = rules_calculator or ProbeRulesCalculator()
        self._execution_plan_calculator = (
            execution_plan_calculator or ProbeExecutionPlanCalculator()
        )
        self._execution_plan_publisher = execution_plan_publisher

        self._latest_request: AvailabilityProbeSetRequest | None = None
        self._latest_desired: NetworkRulesSpec | None = None

        self._generation_sequence = 0
        self._active_generation: ProbeObservationGeneration | None = None

        self._latest_execution_plan_published: ProbeExecutionPlan | None = None
        self._execution_plan_was_published = False

    @property
    def observation_generation(self) -> ProbeObservationGeneration | None:
        with self._state_lock:
            return self._active_generation

    @property
    def execution_plan(self) -> ProbeExecutionPlan | None:
        with self._state_lock:
            return self._current_execution_plan_locked()

    def handle_request(self, request: AvailabilityProbeSetRequest) -> None:
        with self._state_lock:
            desired = self._rules_calculator.calculate(request)
            changed = (
                self._latest_request is None
                or not availability_probe_sets_semantically_equal(
                    self._latest_request,
                    request,
                )
            )

            if changed:
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
            self._publish_execution_plan_if_changed()

    def audit(self) -> None:
        with self._state_lock:
            desired = self._latest_desired
            if desired is None:
                return

            rules_state = self._audit_rules(desired)
            self._synchronize_generation(rules_state)
            self._publish_execution_plan_if_changed()

    def shutdown(self) -> ActionResult:
        with self._state_lock:
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

    def _synchronize_generation(
        self,
        state: NetworkRulesConvergenceState,
    ) -> None:
        request = self._latest_request
        if request is None or not any(probe.enabled for probe in request.probes):
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
        had_generation = self._active_generation is not None
        self._active_generation = None
        if had_generation:
            self._publish_execution_plan_if_changed()

    def _current_execution_plan_locked(self) -> ProbeExecutionPlan | None:
        request = self._latest_request
        generation = self._active_generation
        if request is None or generation is None:
            return None
        return self._execution_plan_calculator.calculate(
            request,
            generation,
        )

    def _publish_execution_plan_if_changed(self) -> None:
        publisher = self._execution_plan_publisher
        if publisher is None:
            return

        current = self._current_execution_plan_locked()
        if (
            self._execution_plan_was_published
            and current == self._latest_execution_plan_published
        ):
            return

        if not self._execution_plan_was_published and current is None:
            return

        publisher.publish(current)
        self._latest_execution_plan_published = current
        self._execution_plan_was_published = True
