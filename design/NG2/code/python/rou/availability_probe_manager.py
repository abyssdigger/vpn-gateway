from __future__ import annotations

from ipaddress import IPv4Address
from threading import RLock
from typing import Protocol

from .availability_routing import AvailabilityWindowState
from .interface_identity import InterfaceIdentity
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
    ProbeMechanism,
    ProbeRulesCalculator,
    availability_probe_sets_semantically_equal,
)
from .probe_transport import (
    ProbeExecutionPlan,
    ProbeExecutionPlanCalculator,
    ProbeGoodNewsInfo,
    ProbeWindowBoundaryInfo,
)
class AvailabilityProbeStatePublisher(Protocol):
    def publish(self, info: AvailabilityProbeStateInfo) -> None:
        ...


class ProbeExecutionPlanPublisher(Protocol):
    def publish(self, plan: ProbeExecutionPlan | None) -> None:
        ...


class AvailabilityProbeManager:
    """Own the active-probe rules plane and its authoritative readiness epoch.

    Probe execution is intentionally not a synchronous dependency of this Manager.
    Production evidence uses a generation-bound good-news/window model. The Manager owns
    the proven NetworkRules lifecycle, evidence-window state, generation invalidation and
    current probe-state publication.
    """

    def __init__(
        self,
        adapter: NetworkRulesAdapter,
        publisher: AvailabilityProbeStatePublisher,
        *,
        rules_calculator: ProbeRulesCalculator | None = None,
        execution_plan_calculator: ProbeExecutionPlanCalculator | None = None,
        execution_plan_publisher: ProbeExecutionPlanPublisher | None = None,
    ) -> None:
        self._adapter = adapter
        self._publisher = publisher
        self._state_lock = RLock()
        self._rules_calculator = rules_calculator or ProbeRulesCalculator()
        self._execution_plan_calculator = (
            execution_plan_calculator or ProbeExecutionPlanCalculator()
        )
        self._execution_plan_publisher = execution_plan_publisher
        self._latest_execution_plan_published: ProbeExecutionPlan | None = None
        self._execution_plan_was_published = False

        self._latest_request: AvailabilityProbeSetRequest | None = None
        self._latest_desired: NetworkRulesSpec | None = None
        self._latest_published: dict[str, AvailabilityProbeStateInfo] = {}

        self._generation_sequence = 0
        self._active_generation: ProbeObservationGeneration | None = None
        self._window_states: dict[str, AvailabilityWindowState] = {}

    @property
    def observation_generation(self) -> ProbeObservationGeneration | None:
        """Current owner-wide READY epoch for diagnostics and evidence binding."""

        with self._state_lock:
            return self._active_generation

    @property
    def execution_plan(self) -> ProbeExecutionPlan | None:
        """Current generation-bound execution demand for the probe Agent.

        None means execution must be quiescent because no authoritative READY
        generation exists. The plan contains physical send cadence and logical
        observation-window cadence but no attempt identity or NO_REPLY semantics.
        """

        with self._state_lock:
            return self._current_execution_plan_locked()

    def handle_request(self, request: AvailabilityProbeSetRequest) -> None:
        """Accept one full desired probe snapshot and reconcile its network plane."""

        with self._state_lock:
            self._handle_request_locked(request)

    def _handle_request_locked(
        self,
        request: AvailabilityProbeSetRequest,
    ) -> None:
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
        self._synchronize_window_states()
        self._publish_execution_plan_if_changed()
        self._publish_unknown_current(rules_state)

    def handle_good_news(self, info: ProbeGoodNewsInfo) -> int:
        """Consume one execution-Agent good-news InfoEvent."""

        if not isinstance(info, ProbeGoodNewsInfo):
            raise ValueError("good-news event must be ProbeGoodNewsInfo")
        return self.note_good_news(
            info.path,
            info.target,
            info.generation,
            mechanism=info.mechanism,
        )

    def note_good_news(
        self,
        path: InterfaceIdentity,
        target: IPv4Address,
        generation: ProbeObservationGeneration,
        *,
        mechanism: ProbeMechanism = ProbeMechanism.ICMP,
    ) -> int:
        """Accept one generation-bound valid reply from a physical probe plane."""

        with self._state_lock:
            return self._note_good_news_locked(
                path,
                target,
                generation,
                mechanism=mechanism,
            )

    def _note_good_news_locked(
        self,
        path: InterfaceIdentity,
        target: IPv4Address,
        generation: ProbeObservationGeneration,
        *,
        mechanism: ProbeMechanism,
    ) -> int:
        """Apply good news while holding the Manager state lock."""

        if self._active_generation is None or generation != self._active_generation:
            return 0
        if not isinstance(path, InterfaceIdentity):
            raise ValueError("good-news path must be an InterfaceIdentity")
        if not isinstance(target, IPv4Address):
            raise ValueError("good-news target must be an IPv4Address")
        if not isinstance(mechanism, ProbeMechanism):
            raise ValueError("good-news mechanism must be a ProbeMechanism")

        request = self._latest_request
        if request is None:
            return 0

        matched = 0
        for probe in request.probes:
            if (
                not probe.enabled
                or probe.path != path
                or probe.target != target
                or probe.mechanism is not mechanism
            ):
                continue

            state = self._window_states.setdefault(
                probe.probe_id,
                AvailabilityWindowState(),
            )
            state.note_good_news()
            self._publish_if_changed(
                AvailabilityProbeStateInfo(
                    probe.probe_id,
                    AvailabilityProbeState.REACHABLE,
                    observation_generation=generation,
                )
            )
            matched += 1

        return matched

    def handle_window_boundary(
        self,
        info: ProbeWindowBoundaryInfo,
    ) -> bool:
        """Consume one execution-Agent observation-window boundary InfoEvent."""

        if not isinstance(info, ProbeWindowBoundaryInfo):
            raise ValueError(
                "window-boundary event must be ProbeWindowBoundaryInfo"
            )
        with self._state_lock:
            return self._close_intervals_locked(
                info.probe_id,
                info.generation,
                info.elapsed_intervals,
            )

    def close_interval(
        self,
        probe_id: str,
        generation: ProbeObservationGeneration,
    ) -> bool:
        """Close one logical observation window."""

        with self._state_lock:
            return self._close_interval_locked(probe_id, generation)

    def _close_interval_locked(
        self,
        probe_id: str,
        generation: ProbeObservationGeneration,
    ) -> bool:
        """Apply one boundary while holding the Manager state lock."""

        return self._close_intervals_locked(probe_id, generation, 1)

    def _close_intervals_locked(
        self,
        probe_id: str,
        generation: ProbeObservationGeneration,
        count: int,
    ) -> bool:
        """Apply one or more elapsed boundaries while holding the state lock."""

        if self._active_generation is None or generation != self._active_generation:
            return False
        if type(count) is not int or count <= 0:
            raise ValueError("boundary count must be a positive integer")

        request = self._latest_request
        if request is None:
            return False

        probe = next(
            (
                item
                for item in request.probes
                if item.probe_id == probe_id
            ),
            None,
        )
        if probe is None or not probe.enabled:
            return False

        state = self._window_states.setdefault(
            probe.probe_id,
            AvailabilityWindowState(),
        )
        state.close_intervals(probe.policy, count)

        if state.confirmed_live:
            self._publish_if_changed(
                AvailabilityProbeStateInfo(
                    probe.probe_id,
                    AvailabilityProbeState.REACHABLE,
                    observation_generation=generation,
                )
            )
        elif state.missed_intervals >= probe.policy.failure_intervals:
            self._publish_if_changed(
                AvailabilityProbeStateInfo(
                    probe.probe_id,
                    AvailabilityProbeState.UNREACHABLE,
                    reason="no good news within failure window",
                    observation_generation=generation,
                )
            )

        return True

    def audit(self) -> None:
        """Run one deterministic rules refresh/repair pass."""

        with self._state_lock:
            desired = self._latest_desired
            if desired is None:
                return

            rules_state = self._audit_rules(desired)
            self._synchronize_generation(rules_state)
            self._synchronize_window_states()
            self._publish_execution_plan_if_changed()
            self._publish_unknown_current(rules_state)

    def shutdown(self) -> ActionResult:
        """Release all NetworkRules state owned by this Manager instance."""

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
        had_generation = self._active_generation is not None
        self._active_generation = None
        self._window_states.clear()
        if had_generation:
            # Quiesce execution demand before any subsequent lower-domain transition.
            self._publish_execution_plan_if_changed()

    def _current_execution_plan_locked(self) -> ProbeExecutionPlan | None:
        request = self._latest_request
        generation = self._active_generation
        if request is None or generation is None:
            return None
        return self._execution_plan_calculator.calculate(request, generation)

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

        # Do not publish a synthetic initial quiescent state. Once execution has
        # been activated, however, None is a real RequestEvent meaning "stop".
        if not self._execution_plan_was_published and current is None:
            return

        publisher.publish(current)
        self._latest_execution_plan_published = current
        self._execution_plan_was_published = True

    def _synchronize_window_states(self) -> None:
        request = self._latest_request
        if request is None or self._active_generation is None:
            self._window_states.clear()
            return

        enabled_ids = {
            probe.probe_id
            for probe in request.probes
            if probe.enabled
        }
        for probe_id in tuple(self._window_states):
            if probe_id not in enabled_ids:
                self._window_states.pop(probe_id, None)
        for probe_id in enabled_ids:
            self._window_states.setdefault(
                probe_id,
                AvailabilityWindowState(),
            )

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
            self._window_states.pop(probe_id, None)

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
            self._window_states.pop(probe_id, None)

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
