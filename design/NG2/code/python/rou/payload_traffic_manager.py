from __future__ import annotations

from threading import Lock
from typing import Protocol

from .availability_collector import (
    AvailabilityChannelState,
    AvailabilityPendingInput,
    ProfileProbeAssignment,
    calculate_availability_path_order,
)
from .network_rules import ActionResult, NetworkRulesAdapter, NetworkRulesSpec
from .payload_rules import (
    PayloadProfileRequest,
    PayloadRulesCalculator,
    PayloadTrafficStateRequest,
)
from .payload_rules_state import Convergence, PayloadRulesStateCalculator
from .payload_traffic_state import (
    PayloadTrafficStateInfo,
    project_payload_traffic_state,
)
from .probe_rules import (
    AvailabilityProbeRequest,
    AvailabilityProbeSetRequest,
)
from .probe_transport import (
    LogicalProbeChannel,
    ProbeGoodNewsInfo,
    ProbeTickInfo,
)


class PayloadTrafficStatePublisher(Protocol):
    def publish(self, info: PayloadTrafficStateInfo) -> None:
        ...


class PayloadTrafficManager:
    """Own payload policy, availability priority state and one reconcile executor."""

    def __init__(
        self,
        adapter: NetworkRulesAdapter,
        publisher: PayloadTrafficStatePublisher,
        *,
        rules_calculator: PayloadRulesCalculator | None = None,
        state_calculator: PayloadRulesStateCalculator | None = None,
    ) -> None:
        self._adapter = adapter
        self._publisher = publisher
        self._rules_calculator = rules_calculator or PayloadRulesCalculator()
        self._state_calculator = (
            state_calculator or PayloadRulesStateCalculator()
        )

        self._latest_configured: PayloadTrafficStateRequest | None = None
        self._latest_effective_desired: PayloadTrafficStateRequest | None = None
        self._last_verified_effective: PayloadTrafficStateRequest | None = None
        self._latest_desired: NetworkRulesSpec | None = None
        self._latest_published: PayloadTrafficStateInfo | None = None

        self._probe_request: AvailabilityProbeSetRequest | None = None
        self._assignments: tuple[ProfileProbeAssignment, ...] = ()
        self._channel_states: dict[str, AvailabilityChannelState] = {}
        self._pending_inputs: dict[str, AvailabilityPendingInput] = {}

        self._serial_lock = Lock()
        self._reconciling = False
        self._pending_request: PayloadTrafficStateRequest | None = None
        self._pending_availability_config: tuple[
            AvailabilityProbeSetRequest,
            tuple[ProfileProbeAssignment, ...],
        ] | None = None
        self._availability_work_pending = False
        self._audit_pending = False

    def handle_request(self, request: PayloadTrafficStateRequest) -> None:
        """Accept one full structural/admin payload snapshot."""

        if not isinstance(request, PayloadTrafficStateRequest):
            raise ValueError("payload request must be PayloadTrafficStateRequest")

        # Validate pure payload semantics before entering current intent.
        self._rules_calculator.calculate(request)

        with self._serial_lock:
            self._pending_request = request
            if self._reconciling:
                return
            self._reconciling = True

        self._drain_serialized_work()

    def configure_availability(
        self,
        request: AvailabilityProbeSetRequest,
        assignments: tuple[ProfileProbeAssignment, ...],
    ) -> None:
        """Accept latest logical availability-channel configuration.

        This is configuration/control input, not probe evidence. Policy-only changes keep
        the current availability_problems flag but reset hysteresis progress.
        """

        if not isinstance(request, AvailabilityProbeSetRequest):
            raise ValueError(
                "availability config requires AvailabilityProbeSetRequest"
            )
        if any(
            not isinstance(item, ProfileProbeAssignment)
            for item in assignments
        ):
            raise ValueError(
                "availability assignments must contain ProfileProbeAssignment"
            )
        self._validate_assignment_references(request, assignments)

        with self._serial_lock:
            self._pending_availability_config = (request, assignments)
            if self._reconciling:
                return
            self._reconciling = True

        self._drain_serialized_work()

    def handle_probe_good_news(self, info: ProbeGoodNewsInfo) -> bool:
        if not isinstance(info, ProbeGoodNewsInfo):
            raise ValueError("good-news input must be ProbeGoodNewsInfo")

        with self._serial_lock:
            probe = self._current_probe_for_channel_locked(info.channel)
            if probe is None:
                return False
            pending = self._pending_inputs.setdefault(
                probe.probe_id,
                AvailabilityPendingInput(),
            )
            pending.note_good_news(probe.policy)
            self._availability_work_pending = True
            if self._reconciling:
                return True
            self._reconciling = True

        self._drain_serialized_work()
        return True

    def handle_probe_tick(self, info: ProbeTickInfo) -> bool:
        if not isinstance(info, ProbeTickInfo):
            raise ValueError("tick input must be ProbeTickInfo")

        with self._serial_lock:
            probe = self._current_probe_for_channel_locked(info.channel)
            if probe is None:
                return False
            self._pending_inputs.setdefault(
                probe.probe_id,
                AvailabilityPendingInput(),
            ).note_tick()
            self._availability_work_pending = True
            if self._reconciling:
                return True
            self._reconciling = True

        self._drain_serialized_work()
        return True

    def audit(self) -> None:
        with self._serial_lock:
            if self._latest_desired is None and not self._reconciling:
                return
            self._audit_pending = True
            if self._reconciling:
                return
            self._reconciling = True

        self._drain_serialized_work()

    def _drain_serialized_work(self) -> None:
        while True:
            request: PayloadTrafficStateRequest | None = None
            availability_config: tuple[
                AvailabilityProbeSetRequest,
                tuple[ProfileProbeAssignment, ...],
            ] | None = None
            run_availability = False
            run_audit = False

            with self._serial_lock:
                if self._pending_request is not None:
                    request = self._pending_request
                    self._pending_request = None
                elif self._pending_availability_config is not None:
                    availability_config = self._pending_availability_config
                    self._pending_availability_config = None
                elif self._availability_work_pending:
                    run_availability = True
                    self._availability_work_pending = False
                elif self._audit_pending:
                    run_audit = True
                    self._audit_pending = False
                else:
                    self._reconciling = False
                    return

            try:
                if request is not None:
                    self._apply_payload_request(request)
                    continue

                if availability_config is not None:
                    self._apply_availability_config(*availability_config)
                    continue

                if run_availability:
                    self._process_availability_inputs()
                    continue

                if run_audit:
                    self._audit_once()
            except Exception:
                with self._serial_lock:
                    self._reconciling = False
                raise

    def _apply_payload_request(
        self,
        request: PayloadTrafficStateRequest,
    ) -> None:
        previous = self._latest_configured
        self._validate_config_against_payload(
            request,
            self._probe_request,
            self._assignments,
        )
        self._latest_configured = request
        self._reconcile_payload(previous_configured=previous)

    def _apply_availability_config(
        self,
        request: AvailabilityProbeSetRequest,
        assignments: tuple[ProfileProbeAssignment, ...],
    ) -> None:
        self._validate_config_against_payload(
            self._latest_configured,
            request,
            assignments,
        )

        previous_by_id = (
            {
                item.probe_id: item
                for item in self._probe_request.probes
            }
            if self._probe_request is not None
            else {}
        )
        current_by_id = {
            item.probe_id: item
            for item in request.probes
        }

        for probe_id in tuple(self._channel_states):
            if probe_id not in current_by_id:
                self._channel_states.pop(probe_id, None)
                self._pending_inputs.pop(probe_id, None)

        for probe_id, probe in current_by_id.items():
            previous = previous_by_id.get(probe_id)
            state = self._channel_states.get(probe_id)
            pending = self._pending_inputs.setdefault(
                probe_id,
                AvailabilityPendingInput(),
            )

            if not probe.enabled:
                if state is None:
                    state = AvailabilityChannelState()
                    self._channel_states[probe_id] = state
                state.disable()
                pending.clear()
                continue

            same_channel = (
                previous is not None
                and previous.enabled
                and previous.path == probe.path
                and previous.target == probe.target
                and previous.mechanism is probe.mechanism
            )

            if state is None or not same_channel:
                self._channel_states[probe_id] = AvailabilityChannelState()
                pending.clear()
                continue

            if previous != probe:
                state.reset_policy_progress()
                pending.clear()

        self._probe_request = request
        self._assignments = assignments

        if self._latest_configured is not None:
            self._reconcile_payload(
                previous_configured=self._latest_configured,
            )

    def _process_availability_inputs(self) -> None:
        request = self._probe_request
        if request is None:
            return

        with self._serial_lock:
            snapshots = tuple(
                (
                    probe,
                    self._pending_inputs.setdefault(
                        probe.probe_id,
                        AvailabilityPendingInput(),
                    ).take(),
                )
                for probe in request.probes
                if probe.enabled
            )

        changed = False
        for probe, (good_news, tick_pending) in snapshots:
            state = self._channel_states.setdefault(
                probe.probe_id,
                AvailabilityChannelState(),
            )
            changed = (
                state.process(
                    probe.policy,
                    pending_good_news=good_news,
                    tick_pending=tick_pending,
                )
                or changed
            )

        if changed and self._latest_configured is not None:
            self._reconcile_payload(
                previous_configured=self._latest_configured,
            )

    def _reconcile_payload(
        self,
        *,
        previous_configured: PayloadTrafficStateRequest | None,
    ) -> None:
        configured = self._latest_configured
        if configured is None:
            return

        effective = self._calculate_effective_request(
            configured,
            previous_configured=previous_configured,
        )
        desired = self._rules_calculator.calculate(effective)

        self._latest_effective_desired = effective
        self._latest_desired = desired

        info = self._apply_desired_and_observe(desired)
        if info.rules_state.convergence is Convergence.MATCHED:
            self._last_verified_effective = effective
        self._publish_if_changed(info)

    def _calculate_effective_request(
        self,
        configured: PayloadTrafficStateRequest,
        *,
        previous_configured: PayloadTrafficStateRequest | None,
    ) -> PayloadTrafficStateRequest:
        previous_by_name = (
            {}
            if previous_configured is None
            else {
                item.name: item
                for item in previous_configured.profiles
            }
        )
        verified_by_name = (
            {}
            if self._last_verified_effective is None
            else {
                item.name: item
                for item in self._last_verified_effective.profiles
            }
        )
        assignment_by_name = {
            item.profile_name: item
            for item in self._assignments
        }
        probes_by_id = (
            {}
            if self._probe_request is None
            else {
                item.probe_id: item
                for item in self._probe_request.probes
            }
        )

        result: list[PayloadProfileRequest] = []
        for profile in configured.profiles:
            configured_paths = {
                path.identity: path
                for path in profile.ordered_paths
            }
            configured_order = tuple(configured_paths)

            previous = previous_by_name.get(profile.name)
            verified = verified_by_name.get(profile.name)
            previous_order = (
                None
                if previous is None
                else tuple(
                    path.identity
                    for path in previous.ordered_paths
                )
            )
            verified_order = (
                None
                if verified is None
                else tuple(
                    path.identity
                    for path in verified.ordered_paths
                )
            )

            rebase = (
                previous_order != configured_order
                or verified_order is None
                or set(verified_order) != set(configured_order)
            )
            current_order = (
                configured_order
                if rebase
                else verified_order
            )
            assert current_order is not None

            problem_paths = set()
            assignment = assignment_by_name.get(profile.name)
            if assignment is not None:
                for probe_id in assignment.probe_ids:
                    probe = probes_by_id.get(probe_id)
                    if probe is None or not probe.enabled:
                        continue
                    state = self._channel_states.get(probe_id)
                    if (
                        state is not None
                        and state.availability_problems
                    ):
                        problem_paths.add(probe.path)

            effective_order = calculate_availability_path_order(
                configured_order,
                current_order,
                frozenset(problem_paths),
            )
            no_problem_prefix_length = (
                len(configured_order) - len(problem_paths)
            )

            result.append(
                PayloadProfileRequest(
                    name=profile.name,
                    direction=profile.direction,
                    destinations=profile.destinations,
                    ordered_paths=tuple(
                        configured_paths[identity]
                        for identity in effective_order
                    ),
                    no_problem_prefix_length=no_problem_prefix_length,
                )
            )

        return PayloadTrafficStateRequest(tuple(result))

    def _audit_once(self) -> None:
        desired = self._latest_desired
        if desired is None:
            return

        self._adapter.renew_state(self)
        info = self._current_info(desired)

        if info.rules_state.convergence is not Convergence.MATCHED:
            info = self._apply_desired_and_observe(desired)

        if (
            info.rules_state.convergence is Convergence.MATCHED
            and self._latest_effective_desired is not None
        ):
            self._last_verified_effective = self._latest_effective_desired

        self._publish_if_changed(info)

    def shutdown(self) -> ActionResult:
        return self._adapter.cleanup(self)

    def _apply_desired_and_observe(
        self,
        desired: NetworkRulesSpec,
    ) -> PayloadTrafficStateInfo:
        action = self._adapter.apply(self, desired)
        if not action.success:
            self._adapter.renew_state(self)
        return self._current_info(desired)

    def _current_info(
        self,
        desired: NetworkRulesSpec,
    ) -> PayloadTrafficStateInfo:
        observed = self._adapter.get_last_state(self)
        rules_state = self._state_calculator.calculate(desired, observed)
        return project_payload_traffic_state(
            desired,
            observed,
            rules_state,
        )

    def _publish_if_changed(self, info: PayloadTrafficStateInfo) -> None:
        if info == self._latest_published:
            return
        self._publisher.publish(info)
        self._latest_published = info

    def _current_probe_for_channel_locked(
        self,
        channel: LogicalProbeChannel,
    ) -> AvailabilityProbeRequest | None:
        request = self._probe_request
        if request is None:
            return None

        for probe in request.probes:
            if probe.probe_id != channel.probe_id:
                continue
            if not probe.enabled:
                return None
            if (
                probe.path != channel.path
                or probe.target != channel.target
                or probe.mechanism is not channel.mechanism
                or probe.policy != channel.policy
            ):
                return None
            return probe
        return None

    @staticmethod
    def _validate_assignment_references(
        request: AvailabilityProbeSetRequest,
        assignments: tuple[ProfileProbeAssignment, ...],
    ) -> None:
        probe_ids = {
            item.probe_id
            for item in request.probes
        }
        profile_names = []
        for assignment in assignments:
            profile_names.append(assignment.profile_name)
            missing = set(assignment.probe_ids) - probe_ids
            if missing:
                raise ValueError(
                    f"Profile {assignment.profile_name!r} references "
                    "unknown probe_id: "
                    + ", ".join(sorted(missing))
                )
        if len(set(profile_names)) != len(profile_names):
            raise ValueError("duplicate Profile probe assignment")

    @staticmethod
    def _validate_config_against_payload(
        payload: PayloadTrafficStateRequest | None,
        request: AvailabilityProbeSetRequest | None,
        assignments: tuple[ProfileProbeAssignment, ...],
    ) -> None:
        if payload is None or request is None:
            return

        profiles_by_name = {
            item.name: item
            for item in payload.profiles
        }
        probes_by_id = {
            item.probe_id: item
            for item in request.probes
        }

        for assignment in assignments:
            profile = profiles_by_name.get(assignment.profile_name)
            if profile is None:
                raise ValueError(
                    f"probe assignment references unknown Profile "
                    f"{assignment.profile_name!r}"
                )
            eligible = {
                path.identity
                for path in profile.ordered_paths
            }
            for probe_id in assignment.probe_ids:
                probe = probes_by_id[probe_id]
                if probe.path not in eligible:
                    raise ValueError(
                        f"probe {probe_id!r} path is not eligible for "
                        f"Profile {assignment.profile_name!r}"
                    )
