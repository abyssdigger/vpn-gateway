from __future__ import annotations

import threading
import time
from typing import Callable, Mapping

from .availability import (
    AvailabilityPolicy,
    ProbeOutcome,
)
from .availability_supervision import (
    DetectorFreshnessPolicy,
    SupervisedAvailabilityState,
    reconcile_supervised_availability,
)
from .device_engine import InterfaceIdentity
from .domain import Availability
from .probe_evidence import ProbeEvidenceStore


Clock = Callable[[], float]


class AvailabilityController:
    """Process-local owner of probe evidence and normalized availability state.

    This is a future DeviceManager building block, not a production runtime provider yet.

    Lifecycle rule: the controller object owns both ephemeral domains and they reset
    together when the controller process/object is recreated:

    - latest TimedProbeSample registry and sample-id sequence;
    - consumed-sample/hysteresis state.

    No method persists either domain.
    """

    def __init__(
        self,
        *,
        availability_policy: AvailabilityPolicy,
        freshness_policy: DetectorFreshnessPolicy,
        clock: Clock = time.monotonic,
    ):
        if not isinstance(availability_policy, AvailabilityPolicy):
            raise ValueError(
                "availability_policy must be AvailabilityPolicy"
            )
        if not isinstance(freshness_policy, DetectorFreshnessPolicy):
            raise ValueError(
                "freshness_policy must be DetectorFreshnessPolicy"
            )
        if not callable(clock):
            raise ValueError("clock must be callable")

        self._availability_policy = availability_policy
        self._freshness_policy = freshness_policy
        self._clock = clock
        self._evidence = ProbeEvidenceStore(clock=clock)
        self._state = SupervisedAvailabilityState.empty()
        self._state_lock = threading.Lock()

    def record(
        self,
        identity: InterfaceIdentity,
        outcome: ProbeOutcome,
    ) -> None:
        """Publish one completed probe outcome.

        Probe workers call this method. Sample identity/timestamp assignment is owned by the
        controller's evidence store.
        """

        self._evidence.record(identity, outcome)

    def reconcile(
        self,
        tracked_interfaces: tuple[InterfaceIdentity, ...],
    ) -> Mapping[InterfaceIdentity, Availability]:
        """Consume fresh evidence exactly once and advance normalized availability.

        Detector supervision errors propagate unchanged. Controller state is committed only
        after a complete successful reconcile.

        The policy consequence of such an error is intentionally outside this object.
        """

        with self._state_lock:
            samples = self._evidence.snapshot()
            now = self._clock()
            update = reconcile_supervised_availability(
                self._state,
                tracked_interfaces,
                samples,
                now_monotonic=now,
                freshness_policy=self._freshness_policy,
                availability_policy=self._availability_policy,
            )

            self._state = update.next_state
            self._evidence.retain(tracked_interfaces)
            return update.availability

    def state(self) -> SupervisedAvailabilityState:
        """Return the current immutable process-local controller state."""

        with self._state_lock:
            return self._state

    def evidence_snapshot(self):
        """Return an immutable diagnostic snapshot of current probe evidence."""

        return self._evidence.snapshot()
