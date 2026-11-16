from __future__ import annotations

from dataclasses import replace
from threading import Lock
from typing import Protocol

from .availability_collector import (
    AvailabilityChannelState,
    AvailabilityGoodNews,
    AvailabilityPendingInput,
    AvailabilityPriorityChannel,
    AvailabilityPriorityConfig,
    AvailabilityTick,
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


class PayloadTrafficStatePublisher(Protocol):
    def publish(self, info: PayloadTrafficStateInfo) -> None:
        ...


class PayloadTrafficManager:
    """Own structural payload policy plus optional availability priority."""

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
        self._state_calculator = state_calculator or PayloadRulesStateCalculator()

        self._latest_configured: PayloadTrafficStateRequest | None = None
        self._latest_effective: PayloadTrafficStateRequest | None = None
        self._last_verified_effective: PayloadTrafficStateRequest | None = None
        self._latest_desired: NetworkRulesSpec | None = None
        self._latest_published: PayloadTrafficStateInfo | None = None

        self._availability = AvailabilityPriorityConfig((), ())
        self._channel_states: dict[str, AvailabilityChannelState] = {}
        self._pending_inputs: dict[str, AvailabilityPendingInput] = {}

        self._serial_lock = Lock()
        self._reconciling = False
        self._pending_request: PayloadTrafficStateRequest | None = None
        self._pending_availability: AvailabilityPriorityConfig | None = None
        self._availability_work_pending = False
        self._audit_pending = False

    def handle_request(self, request: PayloadTrafficStateRequest) -> None:
        if not isinstance(request, PayloadTrafficStateRequest):
            raise ValueError("payload request must be PayloadTrafficStateRequest")

        # Structural payload validation remains independent of availability.
        self._rules_calculator.calculate(request)

        with self._serial_lock:
            self._pending_request = request
            if self._reconciling:
                return
            self._reconciling = True
        self._drain_serialized_work()

    def configure_availability(
        self,
        config: AvailabilityPriorityConfig,
    ) -> None:
        if not isinstance(config, AvailabilityPriorityConfig):
            raise ValueError(
                "availability config must be AvailabilityPriorityConfig"
            )

        with self._serial_lock:
            self._pending_availability = config
            if self._reconciling:
                return
            self._reconciling = True
        self._drain_serialized_work()

    def handle_availability_good_news(
        self,
        info: AvailabilityGoodNews,
    ) -> bool:
        if not isinstance(info, AvailabilityGoodNews):
            raise ValueError("good-news input must be AvailabilityGoodNews")

        with self._serial_lock:
            channel = self._current_channel_locked(info.channel)
            if channel is None:
                return False
            self._pending_inputs.setdefault(
                channel.channel_id,
                AvailabilityPendingInput(),
            ).note_good_news(channel.policy)
            self._availability_work_pending = True
            if self._reconciling:
                return True
            self._reconciling = True

        self._drain_serialized_work()
        return True

    def handle_availability_tick(self, info: AvailabilityTick) -> bool:
        if not isinstance(info, AvailabilityTick):
            raise ValueError("tick input must be AvailabilityTick")

        with self._serial_lock:
            channel = self._current_channel_locked(info.channel)
            if channel is None:
                return False
            self._pending_inputs.setdefault(
                channel.channel_id,
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
            availability: AvailabilityPriorityConfig | None = None
            run_availability = False
            run_audit = False

            with self._serial_lock:
                if self._pending_request is not None:
                    request = self._pending_request
                    self._pending_request = None
                elif self._pending_availability is not None:
                    availability = self._pending_availability
                    self._pending_availability = None
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
                if availability is not None:
                    self._apply_availability_config(availability)
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
        self._validate_availability_against_payload(
            request,
            self._availability,
        )
        self._latest_configured = request
        self._reconcile_payload(previous_configured=previous)

    def _apply_availability_config(
        self,
        config: AvailabilityPriorityConfig,
    ) -> None:
        self._validate_availability_against_payload(
            self._latest_configured,
            config,
        )

        previous_by_id = {
            item.channel_id: item for item in self._availability.channels
        }
        current_by_id = {
            item.channel_id: item for item in config.channels
        }

        for channel_id in tuple(self._channel_states):
            if channel_id not in current_by_id:
                self._channel_states.pop(channel_id, None)
                self._pending_inputs.pop(channel_id, None)

        for channel_id, channel in current_by_id.items():
            previous = previous_by_id.get(channel_id)
            state = self._channel_states.get(channel_id)
            pending = self._pending_inputs.setdefault(
                channel_id,
                AvailabilityPendingInput(),
            )

            if not channel.enabled:
                if state is None:
                    state = AvailabilityChannelState()
                    self._channel_states[channel_id] = state
                state.disable()
                pending.clear()
                continue

            same_path = (
                previous is not None
                and previous.enabled
                and previous.path == channel.path
            )
            if state is None or not same_path:
                self._channel_states[channel_id] = AvailabilityChannelState()
                pending.clear()
                continue

            if previous != channel:
                state.reset_policy_progress()
                pending.clear()

        self._availability = config
        if self._latest_configured is not None:
            self._reconcile_payload(
                previous_configured=self._latest_configured,
            )

    def _process_availability_inputs(self) -> None:
        channels = {
            item.channel_id: item
            for item in self._availability.channels
            if item.enabled
        }
        if not channels:
            return

        with self._serial_lock:
            snapshots = tuple(
                (
                    channel,
                    self._pending_inputs.setdefault(
                        channel.channel_id,
                        AvailabilityPendingInput(),
                    ).take(),
                )
                for channel in channels.values()
            )

        changed = False
        for channel, (good_news, tick_pending) in snapshots:
            state = self._channel_states.setdefault(
                channel.channel_id,
                AvailabilityChannelState(),
            )
            changed = (
                state.process(
                    channel.policy,
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

        effective, preferred_prefixes = self._calculate_effective_request(
            configured,
            previous_configured=previous_configured,
        )
        desired = self._rules_calculator.calculate(effective)
        desired = self._apply_preferred_prefixes(
            desired,
            preferred_prefixes,
        )

        if self._latest_desired is not None and desired == self._latest_desired:
            self._latest_effective = effective
            return

        self._latest_effective = effective
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
    ) -> tuple[PayloadTrafficStateRequest, dict[str, int | None]]:
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
        assignments = {
            item.profile_name: item
            for item in self._availability.assignments
        }
        channels = {
            item.channel_id: item
            for item in self._availability.channels
        }

        result: list[PayloadProfileRequest] = []
        preferred_prefixes: dict[str, int | None] = {}

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
                    path.identity for path in previous.ordered_paths
                )
            )
            verified_order = (
                None
                if verified is None
                else tuple(
                    path.identity for path in verified.ordered_paths
                )
            )
            rebase = (
                previous_order != configured_order
                or verified_order is None
                or set(verified_order) != set(configured_order)
            )
            current_order = configured_order if rebase else verified_order
            assert current_order is not None

            assignment = assignments.get(profile.name)
            active_by_path: dict[
                object,
                list[AvailabilityPriorityChannel],
            ] = {}
            if assignment is not None:
                for channel_id in assignment.channel_ids:
                    channel = channels[channel_id]
                    if not channel.enabled:
                        continue
                    active_by_path.setdefault(
                        channel.path,
                        [],
                    ).append(channel)

            if not active_by_path:
                effective_order = configured_order
                preferred_prefixes[profile.name] = None
            else:
                problem_paths = {
                    path
                    for path, path_channels in active_by_path.items()
                    if all(
                        self._channel_states.get(channel.channel_id)
                        is not None
                        and self._channel_states[
                            channel.channel_id
                        ].availability_problems
                        for channel in path_channels
                    )
                }
                effective_order = calculate_availability_path_order(
                    configured_order,
                    current_order,
                    frozenset(problem_paths),
                )
                preferred_prefixes[profile.name] = (
                    None
                    if not problem_paths
                    else len(configured_order) - len(problem_paths)
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
                )
            )

        return PayloadTrafficStateRequest(tuple(result)), preferred_prefixes

    @staticmethod
    def _apply_preferred_prefixes(
        desired: NetworkRulesSpec,
        preferred_prefixes: dict[str, int | None],
    ) -> NetworkRulesSpec:
        return replace(
            desired,
            routing_domains=tuple(
                replace(
                    domain,
                    preferred_prefix_length=preferred_prefixes.get(
                        domain.name
                    ),
                )
                for domain in desired.routing_domains
            ),
        )

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
            and self._latest_effective is not None
        ):
            self._last_verified_effective = self._latest_effective

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

    def _current_channel_locked(
        self,
        channel: AvailabilityPriorityChannel,
    ) -> AvailabilityPriorityChannel | None:
        for current in self._availability.channels:
            if current.channel_id != channel.channel_id:
                continue
            if not current.enabled or current != channel:
                return None
            return current
        return None

    @staticmethod
    def _validate_availability_against_payload(
        payload: PayloadTrafficStateRequest | None,
        config: AvailabilityPriorityConfig,
    ) -> None:
        if payload is None:
            return

        profiles = {
            item.name: item
            for item in payload.profiles
        }
        channels = {
            item.channel_id: item
            for item in config.channels
        }

        for assignment in config.assignments:
            profile = profiles.get(assignment.profile_name)
            if profile is None:
                raise ValueError(
                    "availability assignment references unknown Profile "
                    f"{assignment.profile_name!r}"
                )
            eligible = {
                path.identity
                for path in profile.ordered_paths
            }
            for channel_id in assignment.channel_ids:
                channel = channels[channel_id]
                if channel.path not in eligible:
                    raise ValueError(
                        f"availability channel {channel_id!r} path is not "
                        f"eligible for Profile {assignment.profile_name!r}"
                    )
