from __future__ import annotations

from typing import Protocol

from .network_rules import ActionResult, NetworkRulesAdapter, NetworkRulesSpec
from .payload_rules import (
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
    """Manager for the current payload-traffic rules domain.

    This first executable slice covers RequestEvent handling and lifecycle cleanup.
    Drift/audit scheduling is a later review unit.
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

        self._latest_request: PayloadTrafficStateRequest | None = None
        self._latest_desired: NetworkRulesSpec | None = None
        self._latest_published: PayloadTrafficStateInfo | None = None

    def handle_request(self, request: PayloadTrafficStateRequest) -> None:
        """Handle one full desired payload snapshot.

        The RequestEvent has no synchronous domain reply. Publication happens through the
        injected Event Delivery Environment port.
        """

        desired = self._rules_calculator.calculate(request)

        # Accept request and its derived desired projection atomically. If pure
        # calculation rejects the request, the previous managed intent remains intact
        # and no lower-domain mutation is attempted.
        self._latest_request = request
        self._latest_desired = desired

        info = self._apply_desired_and_observe(desired)
        self._publish_if_changed(info)

    def audit(self) -> None:
        """Run one drift/reconcile pass for the current accepted intent."""

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
