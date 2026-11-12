from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
import logging
import time
from typing import Callable, Protocol

from .command_backend import CommandBackend, NamespaceBackend
from .domain import ActiveConfig
from .planner import (
    AvailabilityProvider,
    PlannerError,
    PlannerRetryRequired,
    PlannerRuntimeState,
    SnapshotCollector,
    default_snapshot_collector,
    reconcile_once,
)
from .state_store import JsonRuntimeStateStore, StateStoreError


LOG = logging.getLogger(__name__)


class WakeupSource(Protocol):
    def wait(self, timeout: float | None) -> bool:
        """Wait until an environment event occurs.

        Return True when explicitly woken by an event and False on timeout. Event content
        is intentionally irrelevant: every decision is made from a fresh snapshot.
        """
        ...


class StopPredicate(Protocol):
    def __call__(self) -> bool:
        ...


class HealthCheck(Protocol):
    def __call__(self) -> None:
        ...


@dataclass(frozen=True)
class RuntimeLoopConfig:
    retry_delay_seconds: float = 1.0
    audit_interval_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")
        if self.audit_interval_seconds <= 0:
            raise ValueError("audit_interval_seconds must be positive")


@dataclass(frozen=True)
class RuntimeLoopResult:
    reconciliations: int
    planner_failures: int
    event_wakeups: int
    audit_wakeups: int


def _close_forwarding_best_effort(
    namespace: str,
    host_backend: CommandBackend,
) -> None:
    try:
        NamespaceBackend(namespace, host_backend).run(
            ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
            check=False,
        )
    except Exception:
        LOG.exception("failed to close IPv4 forwarding during runtime containment")


def run_runtime_loop(
    config: ActiveConfig,
    namespace: str,
    host_backend: CommandBackend,
    state_store: JsonRuntimeStateStore,
    wakeups: WakeupSource,
    *,
    availability_provider: AvailabilityProvider | None = None,
    collect_snapshot: SnapshotCollector = default_snapshot_collector,
    loop_config: RuntimeLoopConfig = RuntimeLoopConfig(),
    should_stop: StopPredicate = lambda: False,
    sleep: Callable[[float], None] = time.sleep,
    health_check: HealthCheck | None = None,
    local_publication_address: IPv4Address | None = None,
) -> RuntimeLoopResult:
    """Run the long-lived production reconciliation loop.

    Startup is fail-closed. Runtime history is loaded before reconciliation and every
    verified Planner state is persisted through Planner's pre-forwarding-open commit
    callback.

    Planner retry requests and metric-slot promotion requests cause an immediate next pass
    without waiting for a netlink/event wakeup. Ordinary steady state waits for either an
    event or the periodic audit deadline; the event payload is never used as decision
    input.

    An optional service health check (for example PublicationSupervisor.check_health) runs
    before every reconcile. Health failure escapes the loop and the containment finally
    closes forwarding.
    """

    if not namespace:
        raise ValueError("namespace must be non-empty")

    _close_forwarding_best_effort(namespace, host_backend)

    try:
        loaded = state_store.load(config)
    except StateStoreError:
        _close_forwarding_best_effort(namespace, host_backend)
        raise

    committed = loaded.state
    if loaded.dropped_entries:
        LOG.warning(
            "runtime state load dropped %d incompatible entries",
            loaded.dropped_entries,
        )

    reconciliations = 0
    planner_failures = 0
    event_wakeups = 0
    audit_wakeups = 0
    immediate = True

    try:
        while not should_stop():
            if not immediate:
                woke = wakeups.wait(loop_config.audit_interval_seconds)
                if should_stop():
                    break
                if woke:
                    event_wakeups += 1
                else:
                    audit_wakeups += 1

            if health_check is not None:
                health_check()

            immediate = False
            try:
                result = reconcile_once(
                    config,
                    namespace,
                    committed,
                    host_backend,
                    availability_provider=availability_provider,
                    collect_snapshot=collect_snapshot,
                    persist_verified_state=state_store.save,
                    local_publication_address=local_publication_address,
                )
            except PlannerRetryRequired as exc:
                planner_failures += 1
                LOG.info("planner requested fresh retry: %s", exc)
                if loop_config.retry_delay_seconds:
                    sleep(loop_config.retry_delay_seconds)
                immediate = True
                continue
            except PlannerError as exc:
                planner_failures += 1
                LOG.error("planner reconciliation failed: %s", exc)
                _close_forwarding_best_effort(namespace, host_backend)
                if loop_config.retry_delay_seconds:
                    sleep(loop_config.retry_delay_seconds)
                immediate = True
                continue

            reconciliations += 1
            committed = result.state
            immediate = result.needs_immediate_reconcile
    finally:
        _close_forwarding_best_effort(namespace, host_backend)

    return RuntimeLoopResult(
        reconciliations=reconciliations,
        planner_failures=planner_failures,
        event_wakeups=event_wakeups,
        audit_wakeups=audit_wakeups,
    )
