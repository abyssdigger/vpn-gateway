from __future__ import annotations

from threading import Lock
from typing import Callable

from .network_rules import ActionResult, RoutingDomainSpec


class ProfileRouteOrderExecutor:
    """Direct single-flight Executor for one Profile route-order transaction.

    The Executor owns the caller-visible transaction boundary. It does not
    choose the desired order and it does not claim Linux/kernel atomicity.

    The lower operation is bound once when the Executor is created and must
    return only after the corresponding lower-domain apply/materialize/verify/
    commit attempt has completed. Consequently execute() itself has Direct
    completion semantics.

    A second execute() call for the same Executor blocks until the active call
    has returned. Different Profile executors have independent gates.
    """

    def __init__(
        self,
        profile_name: str,
        operation: Callable[[RoutingDomainSpec], ActionResult],
    ) -> None:
        if not profile_name:
            raise ValueError("profile route-order executor requires a profile name")
        self._profile_name = profile_name
        self._operation = operation
        self._single_flight = Lock()

    @property
    def profile_name(self) -> str:
        return self._profile_name

    def execute(
        self,
        target: RoutingDomainSpec,
    ) -> ActionResult:
        if target.name != self._profile_name:
            raise ValueError(
                "profile route-order executor target does not match its Profile"
            )

        with self._single_flight:
            return self._operation(target)
