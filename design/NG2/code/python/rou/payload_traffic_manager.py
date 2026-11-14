from __future__ import annotations

from dataclasses import replace
from threading import Lock
from typing import Protocol

from .network_rules import (
    ActionResult,
    NetworkRulesAdapter,
    NetworkRulesSpec,
    RoutingDomainSpec,
    StateKnowledge,
)
from .payload_rules import (
    PayloadRulesCalculator,
    PayloadTrafficStateRequest,
)
from .payload_rules_state import Convergence, PayloadRulesStateCalculator
from .payload_traffic_state import (
    PayloadTrafficStateInfo,
    project_payload_traffic_state,
)
from .profile_route_order_executor import ProfileRouteOrderExecutor


class PayloadTrafficStatePublisher(Protocol):
    def publish(self, info: PayloadTrafficStateInfo) -> None:
        ...


def _profile_priority_targets(
    current: NetworkRulesSpec | None,
    desired: NetworkRulesSpec,
) -> tuple[RoutingDomainSpec, ...] | None:
    """Return changed Profile priorities, or None when the diff is broader.

    The narrow Profile Executor path is intentionally conservative. It is valid
    only when all non-routing policy is unchanged and every routing domain keeps
    the same destinations, terminal policy and path membership.
    """

    if current is None:
        return None
    if (
        current.dispatch_rules != desired.dispatch_rules
        or current.traffic_allows != desired.traffic_allows
        or current.flow_initiation_allows != desired.flow_initiation_allows
        or current.source_nat != desired.source_nat
    ):
        return None

    current_by_name = {
        domain.name: domain
        for domain in current.routing_domains
    }
    desired_by_name = {
        domain.name: domain
        for domain in desired.routing_domains
    }
    if current_by_name.keys() != desired_by_name.keys():
        return None

    changed: list[RoutingDomainSpec] = []
    for name, target in desired_by_name.items():
        previous = current_by_name[name]
        if (
            set(previous.destinations) != set(target.destinations)
            or previous.terminal_disposition is not target.terminal_disposition
            or set(previous.ordered_paths) != set(target.ordered_paths)
        ):
            return None
        if (
            previous.ordered_paths != target.ordered_paths
            or previous.priority_prefix_length != target.priority_prefix_length
        ):
            changed.append(target)

    return tuple(changed)


def _merge_profile_priority(
    current: NetworkRulesSpec,
    target: RoutingDomainSpec,
) -> NetworkRulesSpec:
    """Change only one Profile's effective route order/live-prefix boundary."""

    by_name = {
        domain.name: domain
        for domain in current.routing_domains
    }
    previous = by_name.get(target.name)
    if previous is None:
        raise ValueError(
            f"route-priority target references unknown Profile {target.name!r}"
        )
    if (
        set(previous.destinations) != set(target.destinations)
        or previous.terminal_disposition is not target.terminal_disposition
        or set(previous.ordered_paths) != set(target.ordered_paths)
    ):
        raise ValueError(
            f"route-priority target for Profile {target.name!r} changed "
            "structural routing semantics"
        )

    replacement = replace(
        previous,
        ordered_paths=target.ordered_paths,
        priority_prefix_length=target.priority_prefix_length,
    )
    return replace(
        current,
        routing_domains=tuple(
            replacement if domain.name == target.name else domain
            for domain in current.routing_domains
        ),
    )


class PayloadTrafficManager:
    """Manager for the current payload-traffic rules domain.

    Full structural mutations share one aggregate commit boundary because this
    Manager owns one NetworkRulesAdapter owner. Pure route-priority changes are
    additionally serialized by one Direct ProfileRouteOrderExecutor per Profile.
    """

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

        self._latest_desired: NetworkRulesSpec | None = None
        self._latest_published: PayloadTrafficStateInfo | None = None

        # The aggregate owner state and shared lower-domain Adapter are committed
        # one mutation at a time. This lock is not the Profile transaction model;
        # it merely protects the current aggregate owner representation.
        self._commit_lock = Lock()

        # Profile route-order transactions have independent single-flight gates.
        self._executor_registry_lock = Lock()
        self._profile_route_executors: dict[
            str,
            ProfileRouteOrderExecutor,
        ] = {}

    def handle_request(self, request: PayloadTrafficStateRequest) -> None:
        """Handle one full desired payload snapshot.

        Pure route-priority diffs are decomposed into Profile-local Direct
        transactions. A second priority transaction for the same Profile cannot
        begin until the first has completed lower-domain apply/verify/commit.
        Broader payload changes retain the aggregate structural path.
        """

        desired = self._rules_calculator.calculate(request)

        with self._commit_lock:
            current = self._latest_desired
            priority_targets = _profile_priority_targets(
                current,
                desired,
            )

            # A valid full snapshot supersedes the previous managed intent before
            # convergence starts. Profile transactions below still build physical
            # candidates from fresh authoritative Adapter state, never from an
            # uncommitted intermediate desired projection.
            self._latest_desired = desired

            if not priority_targets:
                info = self._apply_desired_and_observe(desired)
                self._publish_if_changed(info)
                return

        for target in priority_targets:
            executor = self._profile_route_executor(target.name)
            executor.execute(target)

        # Publish only after all Profile transactions requested by this full
        # snapshot have completed (successfully or otherwise).
        with self._commit_lock:
            info = self._current_info(desired)
            self._publish_if_changed(info)

    def audit(self) -> None:
        """Run one drift/reconcile pass for the current accepted intent."""

        with self._commit_lock:
            desired = self._latest_desired
            if desired is None:
                return

            self._adapter.renew_state(self)
            info = self._current_info(desired)

            if info.rules_state.convergence is not Convergence.MATCHED:
                info = self._apply_desired_and_observe(desired)

            self._publish_if_changed(info)

    def shutdown(self) -> ActionResult:
        """Release all Adapter state/resources owned by this Manager instance."""

        with self._commit_lock:
            return self._adapter.cleanup(self)

    def _profile_route_executor(
        self,
        profile_name: str,
    ) -> ProfileRouteOrderExecutor:
        with self._executor_registry_lock:
            executor = self._profile_route_executors.get(profile_name)
            if executor is None:
                executor = ProfileRouteOrderExecutor(
                    profile_name,
                    self._apply_profile_priority_target,
                )
                self._profile_route_executors[profile_name] = executor
            return executor

    def _apply_profile_priority_target(
        self,
        target: RoutingDomainSpec,
    ) -> ActionResult:
        """Apply one Profile order from the last completed Adapter projection.

        The target is an absolute Profile priority. The candidate base is freshly
        authoritative network-rules state, so a failed earlier Profile transaction
        cannot leak its uncommitted desired order into this transaction.
        """

        with self._commit_lock:
            observed = self._adapter.get_last_state(self)
            if (
                observed.knowledge is not StateKnowledge.KNOWN
                or not observed.fresh
                or observed.rules is None
            ):
                renewed = self._adapter.renew_state(self)
                observed = self._adapter.get_last_state(self)
                if (
                    not renewed.success
                    or observed.knowledge is not StateKnowledge.KNOWN
                    or not observed.fresh
                    or observed.rules is None
                ):
                    return ActionResult(
                        False,
                        "cannot establish authoritative committed base for "
                        f"Profile {target.name!r} route-order transaction",
                    )

            try:
                candidate = _merge_profile_priority(
                    observed.rules,
                    target,
                )
            except ValueError as exc:
                return ActionResult(False, str(exc))

            action = self._adapter.apply(self, candidate)
            if not action.success:
                self._adapter.renew_state(self)
            return action

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
