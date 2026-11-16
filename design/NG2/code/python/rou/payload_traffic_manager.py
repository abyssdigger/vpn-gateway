from __future__ import annotations

from threading import Lock
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

        self._serial_lock = Lock()
        self._reconciling = False
        self._pending_desired: NetworkRulesSpec | None = None
        self._audit_pending = False

    def handle_request(self, request: PayloadTrafficStateRequest) -> None:
        """Handle one full desired payload snapshot.

        Exactly one reconcile executor drains this Manager's pending work. A
        superseding request may replace pending desired state while the executor is
        inside a lower-domain transaction, but it cannot enter that transaction.
        """

        desired = self._rules_calculator.calculate(request)

        with self._serial_lock:
            self._pending_desired = desired
            if self._reconciling:
                return
            self._reconciling = True

        self._drain_serialized_work()

    def audit(self) -> None:
        """Run one drift/reconcile pass for the current accepted intent."""

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
            desired: NetworkRulesSpec | None = None
            run_audit = False

            with self._serial_lock:
                if self._pending_desired is not None:
                    desired = self._pending_desired
                    self._pending_desired = None
                elif self._audit_pending:
                    run_audit = True
                    self._audit_pending = False
                else:
                    self._reconciling = False
                    return

            try:
                if desired is not None:
                    # Only this executor writes _latest_desired. Newer requests may
                    # replace _pending_desired concurrently, but this desired projection
                    # remains immutable for the active Adapter transaction.
                    self._latest_desired = desired
                    info = self._apply_desired_and_observe(desired)
                    self._publish_if_changed(info)
                    continue

                if run_audit:
                    self._audit_once()
            except Exception:
                # Unexpected Machinery/publisher exceptions must not strand executor
                # ownership forever. Pending latest-value work remains queued for the
                # next event/audit trigger.
                with self._serial_lock:
                    self._reconciling = False
                raise

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
