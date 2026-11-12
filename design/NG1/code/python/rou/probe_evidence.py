from __future__ import annotations

from types import MappingProxyType
import threading
import time
from typing import Callable, Mapping

from .availability import ProbeOutcome
from .availability_supervision import TimedProbeSample
from .device_engine import InterfaceIdentity


Clock = Callable[[], float]


class ProbeEvidenceStore:
    """Thread-safe process-local registry of latest probe samples.

    The store owns sample identity. Every recorded sample receives one process-local,
    monotonically increasing sample_id. Probe workers therefore publish outcomes only;
    they do not coordinate sequence numbers with Planner/DeviceManager consumers.

    The registry is ephemeral and must never be serialized as durable runtime history.
    """

    def __init__(self, *, clock: Clock = time.monotonic):
        if not callable(clock):
            raise ValueError("clock must be callable")
        self._clock = clock
        self._lock = threading.Lock()
        self._next_sample_id = 0
        self._samples: dict[InterfaceIdentity, TimedProbeSample] = {}

    def record(
        self,
        identity: InterfaceIdentity,
        outcome: ProbeOutcome,
    ) -> TimedProbeSample:
        if not isinstance(identity, InterfaceIdentity):
            raise ValueError("identity must be InterfaceIdentity")
        if not isinstance(outcome, ProbeOutcome):
            raise ValueError("outcome must be ProbeOutcome")

        with self._lock:
            sample_id = self._next_sample_id
            monotonic_time = self._clock()
            sample = TimedProbeSample(
                outcome=outcome,
                monotonic_time=monotonic_time,
                sample_id=sample_id,
            )
            self._samples[identity] = sample
            self._next_sample_id += 1
            return sample

    def snapshot(
        self,
    ) -> Mapping[InterfaceIdentity, TimedProbeSample]:
        with self._lock:
            return MappingProxyType(dict(self._samples))

    def retain(
        self,
        identities: tuple[InterfaceIdentity, ...],
    ) -> None:
        """Drop samples for generations no longer tracked by DeviceManager.

        The global sample sequence is deliberately not rewound or reused.
        """

        if len(set(identities)) != len(identities):
            raise ValueError("identities contains duplicate interface generation")
        keep = set(identities)
        with self._lock:
            self._samples = {
                identity: sample
                for identity, sample in self._samples.items()
                if identity in keep
            }
