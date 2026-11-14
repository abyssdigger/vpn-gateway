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

    This executable slice covers RequestEvent handling, one deterministic audit/reconcile
    pass and lifecycle cleanup. Audit scheduling/cadence remains a runtime concern.
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

        self._reconciling = False
        self._pending_desired: NetworkRulesSpec | None = None
        self._audit_pending = False

    def handle_request(self, request: PayloadTrafficStateRequest) -> None:
        """Handle one full desired payload snapshot.

        A lower-domain reconcile is transactional from this Manager's perspective.
        Superseding requests received re-entrantly while one reconcile is active are
        coalesced as the next desired projection; they never interleave the active
        Adapter call.
        """

        desired = self._rules_calculator.calculate(request)

        if self._reconciling:
            self._pending_desired = desired
            return

        self._run_serialized(initial_desired=desired)

    def audit(self) -> None:
        """Run one drift/reconcile pass for the current accepted intent."""

        if self._latest_desired is None:
            return

        if self._reconciling:
            self._audit_pending = True
            return

        self._run_serialized(audit_requested=True)

    def _run_serialized(
        self,
        *,
        initial_desired: NetworkRulesSpec | None = None,
        audit_requested: bool = False,
    ) -> None:
        self._reconciling = True
        try:
            next_desired = initial_desired
            audit_due = audit_requested

            while next_desired is not None or audit_due:
                if next_desired is not None:
                    desired = next_desired
                    next_desired = None

                    # Accept the derived desired projection only after pure calculation
                    # succeeds. Re-entrant requests can replace _pending_desired but
                    # cannot alter this already-started reconcile.
                    self._latest_desired = desired
                    self._pending_desired = None

                    info = self._apply_desired_and_observe(desired)
                    self._publish_if_changed(info)
                else:
                    audit_due = False
                    self._audit_pending = False
                    self._audit_once()

                if self._pending_desired is not None:
                    next_desired = self._pending_desired
                    self._pending_desired = None

                if self._audit_pending:
                    audit_due = True
                    self._audit_pending = False
        finally:
            self._reconciling = False

    def _audit_once(self) -> None:
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
