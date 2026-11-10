from __future__ import annotations

import errno
import logging
import select
import shlex
import signal
import socket
import time
from ipaddress import IPv4Network
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from .config import ConfigLoader
from .constants import (
    BLACKHOLE_METRIC,
    BLACKHOLE_ROUTE_PROTO,
    DEFAULT_FAILURE_REMINDER_INTERVAL,
    DEFAULT_LOCK_PATH,
    FIRST_UNICAST_METRIC,
    KERNEL_ROUTE_PROTO,
    LOG,
    ROUTE_METRIC_STEP,
    VPNG_CHAIN_PREFIX,
    VPN_ROUTE_PROTO,
)
from .errors import (
    CleanupError,
    FirewallInspectionError,
    KernelError,
    PlanValidationError,
    ReconciliationError,
)
from .interfaces import (
    InterfaceBinding,
    InterfaceRecord,
    InterfaceSelectorKind,
    ProfileInterfaceState,
    resolve_profile_interface_state,
)
from .kernel import KernelInterface
from .models import (
    ApplyStateResult,
    DaemonState,
    DiagnosticFact,
    FirewallCheck,
    FirewallDriftScope,
    FirewallSafety,
    GatewayConfig,
    ProfileResult,
    RUNTIME_REASON_TEXT,
    ReconciliationPlan,
    ReconciliationSnapshot,
    RouteSpec,
    RouteType,
    RouteVerifyResult,
    RuntimeReasonCode,
)
from .policy import (
    FilterPolicy,
    FirewallNatPolicy,
    NatPolicy,
    PolicyChain,
    desired_full_policy,
    desired_isolation_filter,
)
from .profile import VpnProfile
from .runtime import InstanceLock, SystemdNotifier

class VpnGatewayDaemon:
    """
    Sole orchestration owner.

    Normal startup order is deliberately encoded at the top level:
        LOCK -> CLEANUP -> LOAD/VALIDATE -> APPLY -> RUN

    The config is therefore NOT read in __init__.
    """

    def __init__(
        self,
        *,
        config_path: Path,
        kernel: KernelInterface,
        config_loader: ConfigLoader,
        notifier: SystemdNotifier | None = None,
        lock_path: Path = DEFAULT_LOCK_PATH,
        failure_reminder_interval: float = DEFAULT_FAILURE_REMINDER_INTERVAL,
    ) -> None:
        self.config_path = config_path
        self.kernel = kernel
        self.config_loader = config_loader
        self.notifier = notifier or SystemdNotifier()
        self.lock_path = lock_path
        self.failure_reminder_interval = failure_reminder_interval

        self.state = DaemonState.STARTING
        self.config: GatewayConfig | None = None
        self.profiles: Mapping[str, VpnProfile] = MappingProxyType({})

        self._shutdown_requested = False
        self._last_reconcile_log_signature: tuple[object, ...] | None = None
        self._last_reconcile_log_at: float | None = None
        self._host_prerequisite_latched = False

        self._signal_wakeup_reader: socket.socket | None = None
        self._signal_wakeup_writer: socket.socket | None = None
        self._previous_wakeup_fd = -1
        self._previous_signal_handlers: dict[int, object] = {}

        # The daemon-owned Netlink listener is an orchestration event source,
        # not a policy/materialization operation of KernelInterface.
        self._netlink_socket: socket.socket | None = None

    # ---- Lifecycle -------------------------------------------------------

    def serve(self) -> None:
        """
        Full normal lifecycle with signal-safe STARTING checkpoints.

        A failed startup still does not run an ad-hoc rollback transaction.
        A requested graceful shutdown is different: once the daemon owns the
        lifetime lock, it stops at the nearest completed phase boundary and
        performs universal cleanup if APPLY may have created kernel state.
        """
        self._install_signal_handlers()
        try:
            # Signal before ownership: nothing is ours to clean.
            if self._shutdown_requested:
                self.state = DaemonState.STOPPING
                return

            with InstanceLock(self.lock_path):
                self.cleanup()
                if self._startup_shutdown_checkpoint(
                    kernel_may_be_dirty=False
                ):
                    return

                # Architectural boundary: config is first read only here,
                # AFTER lock + cleanup.
                config = self.config_loader.load_runtime(self.config_path)
                self._install_config(config)
                if self._startup_shutdown_checkpoint(
                    kernel_may_be_dirty=False
                ):
                    return

                self.apply()

                # Critical boundary: APPLY may have enabled ip_forward.
                # Never emit READY=1 or enter RUN if shutdown was requested.
                if self._startup_shutdown_checkpoint(
                    kernel_may_be_dirty=True
                ):
                    return

                # apply() sets ACTIVE or DEGRADED from verified ProfileResult.
                self.notifier.ready()

                # run() returns only for a requested graceful shutdown.
                self.run()

                self.state = DaemonState.STOPPING
                self.notifier.stopping()
                self.cleanup()
        finally:
            self._restore_signal_handlers()

    def _startup_shutdown_checkpoint(
        self,
        *,
        kernel_may_be_dirty: bool,
    ) -> bool:
        """Return True when STARTING must terminate gracefully now."""
        if not self._shutdown_requested:
            return False

        self.state = DaemonState.STOPPING
        if kernel_may_be_dirty:
            self.cleanup()
        return True

    def _install_config(self, config: GatewayConfig) -> None:
        self.config = config
        profiles = {
            profile_id: VpnProfile(profile_config)
            for profile_id, profile_config in config.vpns.items()
        }
        self.profiles = MappingProxyType(profiles)

    def cleanup(self) -> None:
        """Universal marker-based cleanup used before startup and on stop."""
        try:
            self.kernel.set_ip_forward(False)
            if self.kernel.get_ip_forward():
                raise CleanupError("ip_forward remains enabled after disable")

            vpn_routes = self.kernel.list_routes_by_proto(VPN_ROUTE_PROTO)
            for route in sorted(vpn_routes, key=self._route_sort_key):
                self.kernel.delete_route(route)

            snapshot = self.kernel.iptables_save()
            cleanup_payload = self._build_firewall_cleanup_payload(snapshot)
            if cleanup_payload:
                self.kernel.iptables_restore(cleanup_payload, noflush=True)

            blackhole_routes = self.kernel.list_routes_by_proto(
                BLACKHOLE_ROUTE_PROTO
            )
            blackhole_conflicts = tuple(
                route
                for route in blackhole_routes
                if not (
                    route.route_type is RouteType.BLACKHOLE
                    and route.metric == BLACKHOLE_METRIC
                )
            )
            if blackhole_conflicts:
                raise CleanupError(
                    "reserved proto-201 marker conflict: "
                    f"{blackhole_conflicts!r}"
                )

            for route in sorted(
                blackhole_routes,
                key=self._route_sort_key,
            ):
                self.kernel.delete_route(route)

            if self.kernel.list_routes_by_proto(VPN_ROUTE_PROTO):
                raise CleanupError("proto-202 VPN routes remain after cleanup")

            remaining_blackholes = self.kernel.list_routes_by_proto(
                BLACKHOLE_ROUTE_PROTO
            )
            remaining_conflicts = tuple(
                route
                for route in remaining_blackholes
                if not (
                    route.route_type is RouteType.BLACKHOLE
                    and route.metric == BLACKHOLE_METRIC
                )
            )
            if remaining_conflicts:
                raise CleanupError(
                    "reserved proto-201 marker conflict remains: "
                    f"{remaining_conflicts!r}"
                )
            if remaining_blackholes:
                raise CleanupError("owned blackhole routes remain after cleanup")

            remaining_fw = self._parse_iptables_save(
                self.kernel.iptables_save()
            )
            self._require_no_vpng_firewall_resources(remaining_fw)
        except (KernelError, FirewallInspectionError) as exc:
            raise CleanupError(str(exc)) from exc

    def apply(self) -> None:
        """Apply one fail-hard RC3 startup reconciliation."""
        if self.config is None:
            raise RuntimeError("config not installed")

        self._check_global_ipv6_prerequisites()
        interfaces = self.kernel.list_interfaces()
        self._check_interface_ipv6_prerequisites(interfaces)
        snapshot = self._build_reconciliation_snapshot(interfaces)

        initial_routes = self.kernel.list_routes()
        plan = self._build_plan(
            all_kernel_routes=initial_routes,
            desired_routes_by_profile=snapshot.desired_routes_by_profile,
        )
        self._validate_plan(
            plan,
            all_kernel_routes=initial_routes,
            desired_routes_by_profile=snapshot.desired_routes_by_profile,
        )

        self._restore_filter_policy(snapshot.desired_full_policy.filter)
        self._restore_nat_policy(snapshot.desired_full_policy.nat)
        firewall = self._check_firewall_nat_policy(
            snapshot.desired_full_policy
        )
        if firewall.safety is not FirewallSafety.SAFE:
            detail = firewall.reason.detail if firewall.reason else None
            raise ReconciliationError(
                "firewall/NAT verification failed during startup: "
                f"{firewall.safety.name}: {detail or 'no detail'}"
            )

        self._apply_plan(plan)
        verified = self._verify_plan(
            all_kernel_routes=self.kernel.list_routes(),
            desired_routes_by_profile=snapshot.desired_routes_by_profile,
        )
        results = self._require_complete_profile_results(
            verified.profile_results
        )
        expected_profiles = frozenset(self.profiles)
        if verified.verified_profiles != expected_profiles:
            failed = sorted(expected_profiles - verified.verified_profiles)
            raise ReconciliationError(
                "initial route verification did not complete for profiles: "
                f"{failed!r}"
            )

        self._commit_owned(
            verified_routes_by_profile=verified.owned_routes_by_profile,
            verified_profiles=verified.verified_profiles,
            interface_state_by_profile=snapshot.interface_state_by_profile,
            prefix_metric_allocations_by_profile=(
                snapshot.prefix_metric_allocations_by_profile
            ),
            prefix_metric_cursor_by_profile=(
                snapshot.prefix_metric_cursor_by_profile
            ),
        )

        self.kernel.set_ip_forward(True)
        if not self.kernel.get_ip_forward():
            raise KernelError("ip_forward remains disabled after enable")

        self.state = (
            DaemonState.ACTIVE
            if all(
                result.result is ApplyStateResult.SUCCESS
                for result in results.values()
            )
            else DaemonState.DEGRADED
        )

    def run(self) -> None:
        """
        Serialized reconciliation loop driven by Netlink and a periodic timer.

        Netlink data is only a wakeup hint. Policy is always derived from a
        fresh full inventory, so message loss or coalescing cannot become a
        policy fact. ENOBUFS therefore requests the same full reconciliation.
        """
        reader = self._signal_wakeup_reader
        if reader is None:
            raise RuntimeError("signal wakeup reader is not installed")
        if self.config is None:
            raise RuntimeError("config not installed")

        if self._netlink_socket is None:
            self._netlink_socket = self._open_netlink_socket()
        netlink = self._netlink_socket

        interval = self.config.reconcile_interval
        now = time.monotonic()
        next_reconcile = now + interval

        watchdog_interval = self.notifier.watchdog_interval()
        next_watchdog = (
            None
            if watchdog_interval is None
            else now + watchdog_interval
        )

        while not self._shutdown_requested:
            now = time.monotonic()
            deadline = next_reconcile
            if next_watchdog is not None:
                deadline = min(deadline, next_watchdog)
            timeout = max(0.0, deadline - now)

            try:
                readable, _, _ = select.select(
                    [reader, netlink],
                    [],
                    [],
                    timeout,
                )
            except InterruptedError:
                continue

            if reader in readable:
                while True:
                    try:
                        data = reader.recv(4096)
                    except BlockingIOError:
                        break
                    if not data:
                        break

            if self._shutdown_requested:
                break

            netlink_triggered = False
            if netlink in readable:
                netlink_triggered = self._drain_netlink_socket(netlink)

            now = time.monotonic()
            if next_watchdog is not None and now >= next_watchdog:
                self.notifier.watchdog()
                next_watchdog = now + watchdog_interval

            if not netlink_triggered and now < next_reconcile:
                continue

            self.reconcile()
            next_reconcile = time.monotonic() + interval

    # ---- Runtime reconciliation ----------------------------------------

    def reconcile(self) -> None:
        """Run one serialized RC3 reconciliation pass."""
        if self.config is None:
            raise RuntimeError("config not installed")

        pass_incidents: list[DiagnosticFact] = []

        if self._host_prerequisite_latched:
            facts = [
                DiagnosticFact(
                    RuntimeReasonCode.IPV6_PREREQUISITE_FAILED,
                    "restart required after prior IPv6 prerequisite violation",
                )
            ]
            disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="IPv6 prerequisite violation latched"
            )
            if disable_fact is not None:
                facts.append(disable_fact)
            isolation_fact = self._best_effort_apply_isolation_filter()
            if isolation_fact is not None:
                facts.append(isolation_fact)
            self.state = DaemonState.ISOLATED
            self._log_reconcile_outcome(
                ("isolated", "ipv6-prerequisite-latched",
                 *(("reason", fact.code) for fact in facts)),
                level=logging.ERROR,
                facts=tuple(facts),
            )
            return

        try:
            interfaces = self.kernel.list_interfaces()
        except KernelError as exc:
            facts = [
                DiagnosticFact(
                    RuntimeReasonCode.INTERFACE_INVENTORY_FAILED,
                    str(exc),
                )
            ]
            disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="interface inventory failed"
            )
            if disable_fact is not None:
                facts.append(disable_fact)
            isolation_fact = self._best_effort_apply_isolation_filter()
            if isolation_fact is not None:
                facts.append(isolation_fact)
            self.state = DaemonState.ISOLATED
            self._log_reconcile_outcome(
                (
                    "isolated",
                    "interface-inventory-failed",
                    *(("reason", fact.code) for fact in facts),
                ),
                level=logging.ERROR,
                facts=tuple(facts),
            )
            return

        try:
            self._check_global_ipv6_prerequisites()
            self._check_interface_ipv6_prerequisites(interfaces)
        except (KernelError, ReconciliationError) as exc:
            self._host_prerequisite_latched = True
            facts = [
                DiagnosticFact(
                    RuntimeReasonCode.IPV6_PREREQUISITE_FAILED,
                    str(exc),
                )
            ]
            disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="IPv6 prerequisite violation"
            )
            if disable_fact is not None:
                facts.append(disable_fact)
            isolation_fact = self._best_effort_apply_isolation_filter()
            if isolation_fact is not None:
                facts.append(isolation_fact)
            self.state = DaemonState.ISOLATED
            self._log_reconcile_outcome(
                ("isolated", "ipv6-prerequisite-failed",
                 *(("reason", fact.code) for fact in facts)),
                level=logging.ERROR,
                facts=tuple(facts),
            )
            return

        try:
            snapshot = self._build_reconciliation_snapshot(interfaces)
        except ReconciliationError as exc:
            facts = [
                DiagnosticFact(
                    RuntimeReasonCode.SNAPSHOT_PROJECTION_FAILED,
                    str(exc),
                )
            ]
            disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="snapshot projection failed"
            )
            if disable_fact is not None:
                facts.append(disable_fact)
            isolation_fact = self._best_effort_apply_isolation_filter()
            if isolation_fact is not None:
                facts.append(isolation_fact)
            self.state = DaemonState.ISOLATED
            self._log_reconcile_outcome(
                (
                    "isolated",
                    "snapshot-projection-failed",
                    *(("reason", fact.code) for fact in facts),
                ),
                level=logging.ERROR,
                facts=tuple(facts),
            )
            return

        policy_transition = self._snapshot_changes_policy(snapshot)
        forwarding_intentionally_disabled = False

        if policy_transition:
            disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="policy-changing interface transition"
            )
            forwarding_intentionally_disabled = True
            if disable_fact is not None:
                pass_incidents.append(disable_fact)

        firewall = self._check_firewall_nat_policy(
            snapshot.desired_full_policy
        )

        if firewall.safety is FirewallSafety.UNKNOWN:
            if firewall.reason is not None:
                pass_incidents.append(firewall.reason)
            disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="firewall/NAT UNKNOWN"
            )
            if disable_fact is not None:
                pass_incidents.append(disable_fact)
            self.state = DaemonState.ISOLATED
            self._log_reconcile_outcome(
                (
                    "isolated",
                    "firewall-unknown",
                    *(("reason", fact.code) for fact in pass_incidents),
                ),
                level=logging.ERROR,
                facts=tuple(pass_incidents),
            )
            return

        heavy_repair = policy_transition

        if firewall.safety is FirewallSafety.UNSAFE:
            if firewall.reason is not None:
                pass_incidents.append(firewall.reason)

            if (
                firewall.scope is FirewallDriftScope.INPUT_ONLY
                and not policy_transition
            ):
                try:
                    self._restore_filter_policy(
                        snapshot.desired_full_policy.filter,
                        input_only=True,
                    )
                    repaired = self._check_firewall_nat_policy(
                        snapshot.desired_full_policy
                    )
                except (KernelError, FirewallInspectionError) as exc:
                    repaired = FirewallCheck(
                        FirewallSafety.UNKNOWN,
                        DiagnosticFact(
                            RuntimeReasonCode.FIREWALL_REPAIR_FAILED,
                            str(exc),
                        ),
                    )

                if repaired.safety is not FirewallSafety.SAFE:
                    if repaired.reason is not None:
                        pass_incidents.append(repaired.reason)
                    disable_fact = self._best_effort_disable_forwarding(
                        high_severity_context="INPUT-only repair failed"
                    )
                    if disable_fact is not None:
                        pass_incidents.append(disable_fact)
                    isolation_fact = self._best_effort_apply_isolation_filter()
                    if isolation_fact is not None:
                        pass_incidents.append(isolation_fact)
                    self.state = DaemonState.ISOLATED
                    self._log_reconcile_outcome(
                        (
                            "isolated",
                            "input-repair-failed",
                            *(("reason", fact.code)
                              for fact in pass_incidents),
                        ),
                        level=logging.ERROR,
                        facts=tuple(pass_incidents),
                    )
                    return
            else:
                heavy_repair = True

        if heavy_repair:
            if not forwarding_intentionally_disabled:
                disable_fact = self._best_effort_disable_forwarding(
                    high_severity_context="transit firewall/NAT repair"
                )
                forwarding_intentionally_disabled = True
                if disable_fact is not None:
                    pass_incidents.append(disable_fact)

            try:
                self._repair_firewall_nat_with_barrier(snapshot)
            except (KernelError, FirewallInspectionError, ReconciliationError) as exc:
                pass_incidents.append(
                    DiagnosticFact(
                        RuntimeReasonCode.FIREWALL_REPAIR_FAILED,
                        str(exc),
                    )
                )
                self.state = DaemonState.ISOLATED
                self._log_reconcile_outcome(
                    (
                        "isolated",
                        "firewall-repair-failed",
                        *(("reason", fact.code)
                          for fact in pass_incidents),
                    ),
                    level=logging.ERROR,
                    facts=tuple(pass_incidents),
                )
                return

        try:
            profile_results = self._reconcile_routes_snapshot(snapshot)
        except (KernelError, PlanValidationError, ReconciliationError) as exc:
            self.state = DaemonState.DEGRADED
            forwarding_on, forwarding_query_error = (
                self._query_forwarding_state()
            )
            facts = list(pass_incidents)
            facts.append(
                DiagnosticFact(
                    RuntimeReasonCode.ROUTE_PASS_INCOMPLETE,
                    f"{type(exc).__name__}: {exc}",
                )
            )
            if forwarding_query_error is not None:
                facts.append(forwarding_query_error)
            self._log_reconcile_outcome(
                (
                    "degraded",
                    "route-pass-incomplete",
                    ("ip-forward", forwarding_on),
                    *(("reason", fact.code) for fact in facts),
                ),
                level=logging.WARNING if forwarding_on else logging.ERROR,
                facts=tuple(facts),
            )
            return

        forwarding_enabled, forwarding_enable_fact = (
            self._best_effort_enable_forwarding()
        )

        if (
            forwarding_intentionally_disabled
            and forwarding_enabled
            and forwarding_enable_fact is not None
            and forwarding_enable_fact.code
                is RuntimeReasonCode.FORWARDING_RESTORED
        ):
            forwarding_enable_fact = None

        all_success = all(
            result.result is ApplyStateResult.SUCCESS
            for result in profile_results.values()
        )
        self.state = (
            DaemonState.ACTIVE
            if all_success and forwarding_enabled
            else DaemonState.DEGRADED
        )

        profile_signature: list[tuple[object, ...]] = []
        current_facts: list[DiagnosticFact] = []
        for profile_id, result in sorted(profile_results.items()):
            item: list[object] = [profile_id, result.result]
            if result.reason is not None:
                item.append(result.reason.code)
                current_facts.append(result.reason)
            profile_signature.append(tuple(item))

        if forwarding_enable_fact is not None:
            current_facts.append(forwarding_enable_fact)

        recovered_from: tuple[DiagnosticFact, ...] = ()
        if self.state is DaemonState.ACTIVE:
            recovered_from = tuple(pass_incidents)
        else:
            current_facts[0:0] = pass_incidents

        signature = (
            self.state,
            ("policy-transition", policy_transition),
            tuple(profile_signature),
            ("ip-forward", forwarding_enabled),
            *(("reason", fact.code) for fact in current_facts),
        )
        if self.state is DaemonState.ACTIVE:
            level = logging.WARNING if recovered_from else logging.INFO
        elif forwarding_enabled:
            level = logging.WARNING
        else:
            level = logging.ERROR

        self._log_reconcile_outcome(
            signature,
            level=level,
            facts=tuple(current_facts),
            recovered_from=recovered_from,
        )

    def _reconcile_routes_snapshot(
        self,
        snapshot: ReconciliationSnapshot,
    ) -> Mapping[str, ProfileResult]:
        """Reconcile routes using the same snapshot as firewall/NAT."""
        desired = snapshot.desired_routes_by_profile
        actual = self.kernel.list_routes()
        plan = self._build_plan(
            all_kernel_routes=actual,
            desired_routes_by_profile=desired,
        )
        self._validate_plan(
            plan,
            all_kernel_routes=actual,
            desired_routes_by_profile=desired,
        )
        self._apply_plan(plan)

        verified = self._verify_plan(
            all_kernel_routes=self.kernel.list_routes(),
            desired_routes_by_profile=desired,
        )
        route_results = self._require_complete_profile_results(
            verified.profile_results
        )
        self._commit_owned(
            verified_routes_by_profile=verified.owned_routes_by_profile,
            verified_profiles=verified.verified_profiles,
            interface_state_by_profile=snapshot.interface_state_by_profile,
            prefix_metric_allocations_by_profile=(
                snapshot.prefix_metric_allocations_by_profile
            ),
            prefix_metric_cursor_by_profile=(
                snapshot.prefix_metric_cursor_by_profile
            ),
        )
        return route_results

    # ---- Snapshot / host prerequisites -----------------------------------

    def _check_global_ipv6_prerequisites(self) -> None:
        checks = (
            (
                "net.ipv6.conf.all.forwarding",
                self.kernel.get_ipv6_all_forwarding(),
                False,
            ),
            (
                "net.ipv6.conf.default.forwarding",
                self.kernel.get_ipv6_default_forwarding(),
                False,
            ),
            (
                "net.ipv6.conf.default.disable_ipv6",
                self.kernel.get_ipv6_default_disabled(),
                True,
            ),
        )
        violations = [
            f"{name}={int(actual)} expected={int(expected)}"
            for name, actual, expected in checks
            if actual is not expected
        ]
        if violations:
            raise ReconciliationError(
                "IPv6 host prerequisites are not satisfied: "
                + "; ".join(violations)
            )

    def _check_interface_ipv6_prerequisites(
        self,
        interfaces: Sequence[InterfaceRecord],
    ) -> None:
        if self.config is None:
            raise RuntimeError("config not installed")

        selectors = tuple(
            cfg.interface for cfg in self.config.vpns.values()
        )
        for record in interfaces:
            if not any(
                selector.matches(record.name) for selector in selectors
            ):
                continue
            if not self.kernel.get_interface_ipv6_disabled(record.name):
                raise ReconciliationError(
                    "IPv6 must be disabled on every interface matching a "
                    f"managed selector: {record.name!r}"
                )

    def _build_reconciliation_snapshot(
        self,
        interfaces: Sequence[InterfaceRecord],
    ) -> ReconciliationSnapshot:
        if self.config is None:
            raise RuntimeError("config not installed")

        interface_tuple = tuple(interfaces)
        try:
            interface_state = self._resolve_profile_interfaces(interface_tuple)
            (
                prefix_metric_allocations,
                prefix_metric_cursors,
            ) = self._build_prefix_metric_state(interface_state)
            desired_routes = self._derive_desired_routes(
                interface_state_by_profile=interface_state,
                prefix_metric_allocations_by_profile=(
                    prefix_metric_allocations
                ),
            )
            full_policy = desired_full_policy(self.config, interface_state)
        except ValueError as exc:
            raise ReconciliationError(
                f"reconciliation snapshot projection failed: {exc}"
            ) from exc

        return ReconciliationSnapshot(
            interfaces=interface_tuple,
            interface_state_by_profile=interface_state,
            prefix_metric_allocations_by_profile=prefix_metric_allocations,
            prefix_metric_cursor_by_profile=prefix_metric_cursors,
            desired_routes_by_profile=desired_routes,
            desired_full_policy=full_policy,
        )

    def _snapshot_changes_policy(
        self,
        snapshot: ReconciliationSnapshot,
    ) -> bool:
        for profile_id, state in snapshot.interface_state_by_profile.items():
            profile = self.profiles[profile_id]
            committed = profile.committed_active_bindings
            if committed is None or committed != state.active_bindings:
                return True
            if profile.config.interface.kind is InterfaceSelectorKind.PREFIX:
                desired_metrics = snapshot.prefix_metric_allocations_by_profile[
                    profile_id
                ]
                if dict(profile.committed_prefix_metrics) != dict(desired_metrics):
                    return True
        return False

    # ---- Route plan ------------------------------------------------------

    def _resolve_profile_interfaces(
        self,
        interface_records: Sequence[InterfaceRecord],
    ) -> Mapping[str, ProfileInterfaceState]:
        state: dict[str, ProfileInterfaceState] = {}
        records = tuple(interface_records)

        for profile_id in sorted(self.profiles, key=str.casefold):
            cfg = self.profiles[profile_id].config
            previous = (
                self.profiles[profile_id].committed_active_bindings or ()
            )
            state[profile_id] = resolve_profile_interface_state(
                cfg.interface,
                records,
                cfg.network,
                previous_active_bindings=previous,
            )

        return MappingProxyType(state)

    @staticmethod
    def _valid_prefix_metric(metric: int) -> bool:
        return (
            FIRST_UNICAST_METRIC <= metric < BLACKHOLE_METRIC
            and (metric - FIRST_UNICAST_METRIC) % ROUTE_METRIC_STEP == 0
        )

    @staticmethod
    def _advance_prefix_metric(metric: int) -> int:
        candidate = metric + ROUTE_METRIC_STEP
        if candidate >= BLACKHOLE_METRIC:
            return FIRST_UNICAST_METRIC
        return candidate

    @staticmethod
    def _prefix_metric_capacity() -> int:
        if (
            FIRST_UNICAST_METRIC <= 0
            or ROUTE_METRIC_STEP <= 0
            or FIRST_UNICAST_METRIC >= BLACKHOLE_METRIC
        ):
            raise ReconciliationError(
                "invalid UNICAST/BLACKHOLE metric constants"
            )
        return (
            (BLACKHOLE_METRIC - 1 - FIRST_UNICAST_METRIC)
            // ROUTE_METRIC_STEP
        ) + 1

    def _allocate_prefix_metrics(
        self,
        profile_id: str,
        state: ProfileInterfaceState,
    ) -> tuple[Mapping[InterfaceBinding, int], int]:
        profile = self.profiles[profile_id]
        committed = dict(profile.committed_prefix_metrics)
        cursor = profile.committed_prefix_metric_cursor

        if not self._valid_prefix_metric(cursor):
            raise ReconciliationError(
                f"{profile_id}: invalid committed prefix metric cursor "
                f"{cursor}"
            )

        capacity = self._prefix_metric_capacity()
        if len(state.active_bindings) > capacity:
            raise ReconciliationError(
                f"{profile_id}: prefix metric allocator exhausted "
                f"({len(state.active_bindings)} active bindings, "
                f"{capacity} available slots)"
            )

        allocations: dict[InterfaceBinding, int] = {}
        used: set[int] = set()

        for binding in state.active_bindings:
            if binding not in committed:
                continue
            metric = committed[binding]
            if not self._valid_prefix_metric(metric):
                raise ReconciliationError(
                    f"{profile_id}: invalid committed prefix metric {metric}"
                )
            if metric in used:
                raise ReconciliationError(
                    f"{profile_id}: duplicate committed prefix metric {metric}"
                )
            allocations[binding] = metric
            used.add(metric)

        for binding in state.active_bindings:
            if binding in allocations:
                continue

            candidate = cursor
            for _ in range(capacity):
                if candidate not in used:
                    allocations[binding] = candidate
                    used.add(candidate)
                    cursor = self._advance_prefix_metric(candidate)
                    break
                candidate = self._advance_prefix_metric(candidate)
            else:
                raise ReconciliationError(
                    f"{profile_id}: prefix metric allocator exhausted"
                )

        return MappingProxyType(allocations), cursor

    def _build_prefix_metric_state(
        self,
        interface_state_by_profile: Mapping[str, ProfileInterfaceState],
    ) -> tuple[
        Mapping[str, Mapping[InterfaceBinding, int]],
        Mapping[str, int],
    ]:
        allocations: dict[str, Mapping[InterfaceBinding, int]] = {}
        cursors: dict[str, int] = {}

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            if profile.config.interface.kind is not InterfaceSelectorKind.PREFIX:
                continue
            metrics, cursor = self._allocate_prefix_metrics(
                profile_id,
                interface_state_by_profile[profile_id],
            )
            allocations[profile_id] = metrics
            cursors[profile_id] = cursor

        return MappingProxyType(allocations), MappingProxyType(cursors)

    def _binding_metrics(
        self,
        profile_id: str,
        state: ProfileInterfaceState,
        prefix_metric_allocations_by_profile: Mapping[
            str, Mapping[InterfaceBinding, int]
        ],
    ) -> tuple[tuple[InterfaceBinding, int], ...]:
        cfg = self.profiles[profile_id].config
        selector = cfg.interface
        result: list[tuple[InterfaceBinding, int]] = []

        if selector.kind is InterfaceSelectorKind.EXACT:
            for binding in state.active_bindings:
                result.append((binding, FIRST_UNICAST_METRIC))
        elif selector.kind is InterfaceSelectorKind.PREFIX:
            metrics = prefix_metric_allocations_by_profile.get(profile_id)
            if metrics is None:
                raise ReconciliationError(
                    f"{profile_id}: missing prefix metric allocation"
                )
            if set(metrics) != set(state.active_bindings):
                raise ReconciliationError(
                    f"{profile_id}: prefix metric allocation does not "
                    "match active bindings"
                )
            for binding in state.active_bindings:
                result.append((binding, metrics[binding]))
        elif selector.kind is InterfaceSelectorKind.EXACT_LIST:
            slot_by_name = {
                name: index for index, name in enumerate(selector.values)
            }
            for binding in state.active_bindings:
                metric = (
                    FIRST_UNICAST_METRIC
                    + slot_by_name[binding.name] * ROUTE_METRIC_STEP
                )
                if metric >= BLACKHOLE_METRIC:
                    raise ReconciliationError(
                        f"{profile_id}: explicit interface list makes "
                        "UNICAST route metric reach BLACKHOLE_METRIC"
                    )
                result.append((binding, metric))
        else:
            raise ReconciliationError(
                f"{profile_id}: unsupported interface selector kind "
                f"{selector.kind!r}"
            )
        return tuple(result)

    def _derive_desired_routes(
        self,
        *,
        interface_state_by_profile: Mapping[str, ProfileInterfaceState],
        prefix_metric_allocations_by_profile: Mapping[
            str, Mapping[InterfaceBinding, int]
        ],
    ) -> Mapping[str, frozenset[RouteSpec]]:
        """Derive BLACKHOLE + direct interface routes from one snapshot."""
        expected = frozenset(self.profiles)
        actual = frozenset(interface_state_by_profile)
        if actual != expected:
            raise ReconciliationError(
                "incomplete interface-state snapshot: "
                f"missing={sorted(expected - actual)!r}, "
                f"unexpected={sorted(actual - expected)!r}"
            )

        desired: dict[str, frozenset[RouteSpec]] = {}
        for profile_id in sorted(self.profiles, key=str.casefold):
            cfg = self.profiles[profile_id].config
            state = interface_state_by_profile[profile_id]
            routes: set[RouteSpec] = set()

            for destination in cfg.routes:
                routes.add(
                    RouteSpec(
                        destination=destination,
                        route_type=RouteType.BLACKHOLE,
                        via=None,
                        interface=None,
                        metric=BLACKHOLE_METRIC,
                        proto=BLACKHOLE_ROUTE_PROTO,
                        onlink=False,
                    )
                )

            for binding, metric in self._binding_metrics(
                profile_id,
                state,
                prefix_metric_allocations_by_profile,
            ):
                for destination in cfg.routes:
                    routes.add(
                        RouteSpec(
                            destination=destination,
                            route_type=RouteType.UNICAST,
                            via=None,
                            interface=binding.name,
                            metric=metric,
                            proto=VPN_ROUTE_PROTO,
                            onlink=False,
                        )
                    )

            desired[profile_id] = frozenset(routes)

        return MappingProxyType(desired)

    def _require_complete_desired_snapshot(
        self,
        desired_routes_by_profile: Mapping[
            str,
            frozenset[RouteSpec],
        ],
    ) -> None:
        expected = frozenset(self.profiles)
        actual = frozenset(desired_routes_by_profile)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ReconciliationError(
                "incomplete desired route snapshot: "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )

    def _build_plan(
        self,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> ReconciliationPlan:
        """
        Pure route-plan construction from ACTUAL + DESIRED + OWNED.

        Authoritative scope is exact protected destinations only:
        - desired + actual + owned -> keep;
        - desired + missing actual -> add;
        - desired + actual + not owned -> replace;
        - actual exact + non-desired -> delete;
        - more-/less-specific overlaps -> diagnostics only.
        """
        self._require_complete_desired_snapshot(
            desired_routes_by_profile
        )

        route_adds: set[RouteSpec] = set()
        route_deletes: set[RouteSpec] = set()
        route_replaces: set[RouteSpec] = set()

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            desired = desired_routes_by_profile[profile_id]
            owned = profile.owned_routes
            protected = frozenset(profile.config.routes)

            actual_exact = frozenset(
                route
                for route in all_kernel_routes
                if route.destination in protected
            )

            for route in actual_exact:
                if route in desired:
                    if route not in owned:
                        route_replaces.add(route)
                    continue

                route_deletes.add(route)

            actual_exact_set = set(actual_exact)
            for route in desired:
                if route not in actual_exact_set:
                    route_adds.add(route)

        return ReconciliationPlan(
            route_adds=frozenset(route_adds),
            route_deletes=frozenset(route_deletes),
            route_replaces=frozenset(route_replaces),
        )

    def _validate_plan(
        self,
        plan: ReconciliationPlan,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> None:
        """
        Validate route-plan safety before any side effect.

        `route_replaces` expresses authoritative canonicalization of an exact
        desired RouteSpec that already exists in ACTUAL but is not OWNED.
        This avoids encoding delete+recreate as an illegal add/delete overlap.
        """
        self._require_complete_desired_snapshot(
            desired_routes_by_profile
        )

        operation_sets = {
            "add": plan.route_adds,
            "delete": plan.route_deletes,
            "replace": plan.route_replaces,
        }
        operation_names = tuple(operation_sets)
        for index, left_name in enumerate(operation_names):
            for right_name in operation_names[index + 1:]:
                overlap = (
                    operation_sets[left_name]
                    & operation_sets[right_name]
                )
                if overlap:
                    raise PlanValidationError(
                        f"route plan operations overlap "
                        f"({left_name}/{right_name}): {overlap!r}"
                    )

        desired_owners: dict[RouteSpec, str] = {}
        desired_all: set[RouteSpec] = set()
        protected_destinations: dict[IPv4Network, str] = {}
        owned_owners: dict[RouteSpec, set[str]] = {}

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            for destination in profile.config.routes:
                previous = protected_destinations.get(destination)
                if previous is not None and previous != profile_id:
                    raise PlanValidationError(
                        "multiple managed profiles claim exact protected "
                        f"destination {destination}: "
                        f"{previous!r}, {profile_id!r}"
                    )
                protected_destinations[destination] = profile_id

            for route in desired_routes_by_profile[profile_id]:
                previous = desired_owners.get(route)
                if previous is not None and previous != profile_id:
                    raise PlanValidationError(
                        "multiple managed profiles claim exact RouteSpec "
                        f"{route!r}: {previous!r}, {profile_id!r}"
                    )
                desired_owners[route] = profile_id
                desired_all.add(route)

            for route in profile.owned_routes:
                owned_owners.setdefault(route, set()).add(profile_id)

        actual = set(all_kernel_routes)

        for route in plan.route_adds:
            if route not in desired_all:
                raise PlanValidationError(
                    f"route add is not in current DESIRED: {route!r}"
                )
            if route in actual:
                raise PlanValidationError(
                    f"route add already exists in ACTUAL; "
                    f"replace/keep required: {route!r}"
                )

        for route in plan.route_replaces:
            if route.proto == KERNEL_ROUTE_PROTO:
                raise PlanValidationError(
                    f"proto kernel route must never be replaced: {route!r}"
                )
            if route not in desired_all:
                raise PlanValidationError(
                    f"route replace is not in current DESIRED: {route!r}"
                )
            if route not in actual:
                raise PlanValidationError(
                    f"route replace is absent from ACTUAL: {route!r}"
                )
            if route in owned_owners:
                raise PlanValidationError(
                    f"already OWNED desired route must be kept, "
                    f"not replaced: {route!r}"
                )

        exact_scope = frozenset(protected_destinations)

        for route in plan.route_deletes:
            if route.proto == KERNEL_ROUTE_PROTO:
                raise PlanValidationError(
                    f"proto kernel route must never be deleted: {route!r}"
                )
            if route not in actual:
                raise PlanValidationError(
                    f"route delete is absent from ACTUAL: {route!r}"
                )

            owners = owned_owners.get(route)
            if owners:
                justified = any(
                    route.destination
                    in self.profiles[profile_id].config.routes
                    for profile_id in owners
                )
                if not justified:
                    raise PlanValidationError(
                        "owned route delete has no current configured "
                        f"ownership justification: {route!r}"
                    )
                if route in desired_all:
                    raise PlanValidationError(
                        f"OWNED desired route must be kept: {route!r}"
                    )
                continue

            if route.destination not in exact_scope:
                raise PlanValidationError(
                    "foreign route delete is outside authoritative exact "
                    f"protected scope: {route!r}"
                )
            if route in desired_all:
                raise PlanValidationError(
                    "foreign exact desired route must use replace "
                    f"canonicalization, not delete: {route!r}"
                )

    @staticmethod
    def _route_sort_key(route: RouteSpec) -> tuple[object, ...]:
        return (
            int(route.destination.network_address),
            route.destination.prefixlen,
            route.route_type.value,
            -1 if route.via is None else int(route.via),
            route.interface or "",
            -1 if route.metric is None else route.metric,
            -1 if route.proto is None else route.proto,
            route.onlink,
        )

    def _apply_plan(self, plan: ReconciliationPlan) -> None:
        """Apply one validated route plan with BLACKHOLE guards first."""
        blackhole_adds = sorted(
            (
                route
                for route in plan.route_adds
                if route.route_type is RouteType.BLACKHOLE
            ),
            key=self._route_sort_key,
        )
        remaining_adds = sorted(
            (
                route
                for route in plan.route_adds
                if route.route_type is not RouteType.BLACKHOLE
            ),
            key=self._route_sort_key,
        )

        for route in blackhole_adds:
            self.kernel.add_route(route)
        for route in sorted(plan.route_deletes, key=self._route_sort_key):
            self.kernel.delete_route(route)
        for route in sorted(plan.route_replaces, key=self._route_sort_key):
            self.kernel.replace_route(route)
        for route in remaining_adds:
            self.kernel.add_route(route)

    def _verify_plan(
        self,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> RouteVerifyResult:
        """Verify exact route state, then derive functional availability."""
        self._require_complete_desired_snapshot(desired_routes_by_profile)

        profile_results: dict[str, ProfileResult] = {}
        owned_routes: dict[str, frozenset[RouteSpec]] = {}
        verified_profiles: set[str] = set()

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            desired = desired_routes_by_profile[profile_id]
            protected = frozenset(profile.config.routes)
            actual_exact = frozenset(
                route
                for route in all_kernel_routes
                if route.destination in protected
            )

            if actual_exact != desired:
                profile_results[profile_id] = ProfileResult(
                    result=ApplyStateResult.FAIL,
                    reason=DiagnosticFact(
                        code=RuntimeReasonCode.PROFILE_ROUTE_MISMATCH,
                        detail=(
                            f"desired={sorted(desired, key=self._route_sort_key)!r}; "
                            f"actual_exact={sorted(actual_exact, key=self._route_sort_key)!r}"
                        ),
                    ),
                )
                owned_routes[profile_id] = profile.owned_routes
                continue

            verified_profiles.add(profile_id)
            owned_routes[profile_id] = desired
            missing = [
                destination
                for destination in profile.config.routes
                if not any(
                    route.route_type is RouteType.UNICAST
                    and route.destination == destination
                    for route in desired
                )
            ]
            if missing:
                profile_results[profile_id] = ProfileResult(
                    result=ApplyStateResult.FAIL,
                    reason=DiagnosticFact(
                        RuntimeReasonCode.PROFILE_NO_UNICAST_PATH,
                        "no desired UNICAST path for: "
                        + ", ".join(str(item) for item in missing),
                    ),
                )
            else:
                profile_results[profile_id] = ProfileResult(
                    result=ApplyStateResult.SUCCESS
                )

        return RouteVerifyResult(
            profile_results=MappingProxyType(profile_results),
            owned_routes_by_profile=MappingProxyType(owned_routes),
            verified_profiles=frozenset(verified_profiles),
        )

    def _require_complete_profile_results(
        self,
        results: Mapping[str, ProfileResult],
    ) -> Mapping[str, ProfileResult]:
        """
        Safety guard against vacuous all([]) / partial verify results.

        A completed pass must return exactly the managed profile key set.
        """
        expected = frozenset(self.profiles)
        actual = frozenset(results)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ReconciliationError(
                "incomplete profile results: "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )
        return MappingProxyType(dict(results))

    def _commit_owned(
        self,
        *,
        verified_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
        verified_profiles: frozenset[str],
        interface_state_by_profile: Mapping[str, ProfileInterfaceState],
        prefix_metric_allocations_by_profile: Mapping[
            str, Mapping[InterfaceBinding, int]
        ],
        prefix_metric_cursor_by_profile: Mapping[str, int],
    ) -> None:
        """Commit verified route, binding-order and allocator state."""
        expected = frozenset(self.profiles)
        if frozenset(verified_routes_by_profile) != expected:
            raise ReconciliationError("incomplete verified routes mapping")
        if frozenset(interface_state_by_profile) != expected:
            raise ReconciliationError("incomplete verified interfaces mapping")
        if not verified_profiles <= expected:
            raise ReconciliationError("verified profile set contains unknown profile")

        expected_prefix = frozenset(
            profile_id
            for profile_id, profile in self.profiles.items()
            if profile.config.interface.kind is InterfaceSelectorKind.PREFIX
        )
        if frozenset(prefix_metric_allocations_by_profile) != expected_prefix:
            raise ReconciliationError(
                "incomplete prefix metric allocation mapping"
            )
        if frozenset(prefix_metric_cursor_by_profile) != expected_prefix:
            raise ReconciliationError(
                "incomplete prefix metric cursor mapping"
            )

        for profile_id in sorted(verified_profiles):
            state = interface_state_by_profile[profile_id]
            profile = self.profiles[profile_id]
            if profile.config.interface.kind is InterfaceSelectorKind.PREFIX:
                profile.commit_verified_state(
                    routes=verified_routes_by_profile[profile_id],
                    active_bindings=state.active_bindings,
                    prefix_metrics=prefix_metric_allocations_by_profile[
                        profile_id
                    ],
                    prefix_metric_cursor=prefix_metric_cursor_by_profile[
                        profile_id
                    ],
                )
            else:
                profile.commit_verified_state(
                    routes=verified_routes_by_profile[profile_id],
                    active_bindings=state.active_bindings,
                )

    # ---- RC3 firewall/NAT policy ----------------------------------------

    @staticmethod
    def _policy_chain_map(
        chains: Sequence[PolicyChain],
    ) -> Mapping[str, tuple[str, ...]]:
        return MappingProxyType(
            {chain.name: chain.rules for chain in chains}
        )

    @classmethod
    def _input_policy_chain_names(
        cls,
        policy: FilterPolicy,
    ) -> frozenset[str]:
        names: set[str] = set()
        for rule in policy.input_jumps:
            target = cls._jump_target(rule)
            if target is None:
                raise FirewallInspectionError(
                    f"INPUT policy jump has no target: {rule!r}"
                )
            names.add(target)
        return frozenset(names)

    @classmethod
    def _rule_delete_form(cls, rule: str, chain: str) -> str:
        prefix = f"-A {chain}"
        if not rule.startswith(prefix):
            raise FirewallInspectionError(
                f"cannot transform rule for deletion: {rule!r}"
            )
        return rule.replace(prefix, f"-D {chain}", 1)

    @staticmethod
    def _insert_form(rule: str, chain: str, position: int) -> str:
        prefix = f"-A {chain}"
        if not rule.startswith(prefix):
            raise FirewallInspectionError(
                f"cannot transform policy jump for insertion: {rule!r}"
            )
        return rule.replace(prefix, f"-I {chain} {position}", 1)

    def _compare_filter_policy(
        self,
        parsed: Mapping[str, Mapping[str, object]],
        desired: FilterPolicy,
    ) -> FirewallCheck:
        table = parsed.get("filter")
        if table is None:
            raise FirewallInspectionError(
                "iptables-save missing 'filter' table"
            )
        chains = table["chains"]
        rules = table["rules"]
        assert isinstance(chains, set)
        assert isinstance(rules, dict)

        desired_map = self._policy_chain_map(desired.chains)
        expected_chains = set(desired_map)
        actual_owned = {
            chain for chain in chains if chain.startswith(VPNG_CHAIN_PREFIX)
        }
        input_chains = self._input_policy_chain_names(desired)

        input_drift: list[str] = []
        transit_drift: list[str] = []

        missing = expected_chains - actual_owned
        extra = actual_owned - expected_chains
        for chain in sorted(missing):
            target = input_drift if chain in input_chains else transit_drift
            target.append(f"missing filter chain {chain}")
        if extra:
            transit_drift.append(
                f"unexpected filter VPNG chains {sorted(extra)!r}"
            )

        for chain, expected_rules in desired_map.items():
            if chain not in actual_owned:
                continue
            actual_rules = tuple(rules.get(chain, ()))
            if actual_rules == expected_rules:
                continue
            target = input_drift if chain in input_chains else transit_drift
            target.append(f"filter/{chain} rules differ")

        for builtin, expected_prefix, target in (
            ("INPUT", desired.input_jumps, input_drift),
            ("FORWARD", desired.forward_jumps, transit_drift),
        ):
            actual = tuple(rules.get(builtin, ()))
            if actual[:len(expected_prefix)] != expected_prefix:
                target.append(f"filter/{builtin} VPNG jump prefix differs")
            if any(
                (self._jump_target(rule) or "").startswith(VPNG_CHAIN_PREFIX)
                for rule in actual[len(expected_prefix):]
            ):
                target.append(f"filter/{builtin} has extra VPNG jump")

        if not input_drift and not transit_drift:
            return FirewallCheck(FirewallSafety.SAFE, None)

        scope = (
            FirewallDriftScope.TRANSIT
            if transit_drift
            else FirewallDriftScope.INPUT_ONLY
        )
        detail = "; ".join((*transit_drift, *input_drift))
        return FirewallCheck(
            FirewallSafety.UNSAFE,
            DiagnosticFact(RuntimeReasonCode.FIREWALL_DRIFT, detail),
            scope,
        )

    def _compare_nat_policy(
        self,
        parsed: Mapping[str, Mapping[str, object]],
        desired: NatPolicy,
    ) -> FirewallCheck:
        table = parsed.get("nat")
        if table is None:
            raise FirewallInspectionError(
                "iptables-save missing 'nat' table"
            )
        chains = table["chains"]
        rules = table["rules"]
        assert isinstance(chains, set)
        assert isinstance(rules, dict)

        desired_map = self._policy_chain_map(desired.chains)
        expected_chains = set(desired_map)
        actual_owned = {
            chain for chain in chains if chain.startswith(VPNG_CHAIN_PREFIX)
        }

        drift: list[str] = []
        missing = expected_chains - actual_owned
        extra = actual_owned - expected_chains
        if missing:
            drift.append(f"missing nat VPNG chains {sorted(missing)!r}")
        if extra:
            drift.append(f"unexpected nat VPNG chains {sorted(extra)!r}")

        for chain, expected_rules in desired_map.items():
            if chain not in actual_owned:
                continue
            actual_rules = tuple(rules.get(chain, ()))
            if actual_rules != expected_rules:
                drift.append(f"nat/{chain} rules differ")

        postrouting = tuple(rules.get("POSTROUTING", ()))
        expected_prefix = desired.postrouting_jumps
        if postrouting[:len(expected_prefix)] != expected_prefix:
            drift.append("nat/POSTROUTING VPNG jump prefix differs")
        if any(
            (self._jump_target(rule) or "").startswith(VPNG_CHAIN_PREFIX)
            for rule in postrouting[len(expected_prefix):]
        ):
            drift.append("nat/POSTROUTING has extra VPNG jump")

        if not drift:
            return FirewallCheck(FirewallSafety.SAFE, None)

        return FirewallCheck(
            FirewallSafety.UNSAFE,
            DiagnosticFact(
                RuntimeReasonCode.FIREWALL_DRIFT,
                "; ".join(drift),
            ),
            FirewallDriftScope.TRANSIT,
        )

    def _compare_firewall_nat_policy(
        self,
        snapshot: str,
        desired: FirewallNatPolicy,
    ) -> FirewallCheck:
        parsed = self._parse_iptables_save(snapshot)
        filter_check = self._compare_filter_policy(parsed, desired.filter)
        nat_check = self._compare_nat_policy(parsed, desired.nat)

        if (
            filter_check.safety is FirewallSafety.SAFE
            and nat_check.safety is FirewallSafety.SAFE
        ):
            return FirewallCheck(FirewallSafety.SAFE, None)

        if nat_check.safety is FirewallSafety.UNSAFE:
            details = []
            if filter_check.reason is not None:
                details.append(filter_check.reason.detail or "filter drift")
            if nat_check.reason is not None:
                details.append(nat_check.reason.detail or "nat drift")
            return FirewallCheck(
                FirewallSafety.UNSAFE,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_DRIFT,
                    "; ".join(details),
                ),
                FirewallDriftScope.TRANSIT,
            )

        return filter_check

    def _check_firewall_nat_policy(
        self,
        desired: FirewallNatPolicy,
    ) -> FirewallCheck:
        try:
            snapshot = self.kernel.iptables_save()
        except KernelError as exc:
            return FirewallCheck(
                FirewallSafety.UNKNOWN,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_INVENTORY_FAILED,
                    str(exc),
                ),
            )
        try:
            return self._compare_firewall_nat_policy(snapshot, desired)
        except FirewallInspectionError as exc:
            return FirewallCheck(
                FirewallSafety.UNKNOWN,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_INSPECTION_FAILED,
                    str(exc),
                ),
            )

    def _check_filter_policy(
        self,
        desired: FilterPolicy,
    ) -> FirewallCheck:
        try:
            parsed = self._parse_iptables_save(self.kernel.iptables_save())
            return self._compare_filter_policy(parsed, desired)
        except KernelError as exc:
            return FirewallCheck(
                FirewallSafety.UNKNOWN,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_INVENTORY_FAILED,
                    str(exc),
                ),
            )
        except FirewallInspectionError as exc:
            return FirewallCheck(
                FirewallSafety.UNKNOWN,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_INSPECTION_FAILED,
                    str(exc),
                ),
            )

    def _check_nat_policy(
        self,
        desired: NatPolicy,
    ) -> FirewallCheck:
        try:
            parsed = self._parse_iptables_save(self.kernel.iptables_save())
            return self._compare_nat_policy(parsed, desired)
        except KernelError as exc:
            return FirewallCheck(
                FirewallSafety.UNKNOWN,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_INVENTORY_FAILED,
                    str(exc),
                ),
            )
        except FirewallInspectionError as exc:
            return FirewallCheck(
                FirewallSafety.UNKNOWN,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_INSPECTION_FAILED,
                    str(exc),
                ),
            )

    def _build_filter_restore_payload(
        self,
        desired: FilterPolicy,
        snapshot: str,
        *,
        input_only: bool = False,
    ) -> str:
        parsed = self._parse_iptables_save(snapshot)
        table = parsed.get("filter")
        if table is None:
            raise FirewallInspectionError(
                "iptables-save missing 'filter' table"
            )
        rules = table["rules"]
        assert isinstance(rules, dict)

        desired_map = self._policy_chain_map(desired.chains)
        if input_only:
            chain_names = self._input_policy_chain_names(desired)
            builtins = (("INPUT", desired.input_jumps),)
        else:
            chain_names = frozenset(desired_map)
            builtins = (
                ("INPUT", desired.input_jumps),
                ("FORWARD", desired.forward_jumps),
            )

        lines: list[str] = ["*filter"]
        for builtin, _ in builtins:
            for rule in rules.get(builtin, ()):
                target = self._jump_target(rule)
                if target and target.startswith(VPNG_CHAIN_PREFIX):
                    lines.append(self._rule_delete_form(rule, builtin))

        for chain in sorted(chain_names):
            lines.append(f":{chain} - [0:0]")

        for builtin, jumps in builtins:
            for position, rule in enumerate(jumps, start=1):
                lines.append(self._insert_form(rule, builtin, position))

        for chain in sorted(chain_names):
            lines.extend(desired_map[chain])
        lines.append("COMMIT")
        return "\n".join(lines) + "\n"

    def _build_nat_restore_payload(
        self,
        desired: NatPolicy,
        snapshot: str,
    ) -> str:
        parsed = self._parse_iptables_save(snapshot)
        table = parsed.get("nat")
        if table is None:
            raise FirewallInspectionError(
                "iptables-save missing 'nat' table"
            )
        rules = table["rules"]
        assert isinstance(rules, dict)

        desired_map = self._policy_chain_map(desired.chains)
        lines: list[str] = ["*nat"]
        for rule in rules.get("POSTROUTING", ()):
            target = self._jump_target(rule)
            if target and target.startswith(VPNG_CHAIN_PREFIX):
                lines.append(self._rule_delete_form(rule, "POSTROUTING"))

        for chain in sorted(desired_map):
            lines.append(f":{chain} - [0:0]")
        for position, rule in enumerate(desired.postrouting_jumps, start=1):
            lines.append(self._insert_form(rule, "POSTROUTING", position))
        for chain in sorted(desired_map):
            lines.extend(desired_map[chain])
        lines.append("COMMIT")
        return "\n".join(lines) + "\n"

    def _restore_filter_policy(
        self,
        desired: FilterPolicy,
        *,
        input_only: bool = False,
    ) -> None:
        snapshot = self.kernel.iptables_save()
        payload = self._build_filter_restore_payload(
            desired,
            snapshot,
            input_only=input_only,
        )
        self.kernel.iptables_restore(payload, noflush=True)

    def _restore_nat_policy(self, desired: NatPolicy) -> None:
        snapshot = self.kernel.iptables_save()
        payload = self._build_nat_restore_payload(desired, snapshot)
        self.kernel.iptables_restore(payload, noflush=True)

    def _best_effort_apply_isolation_filter(
        self,
    ) -> DiagnosticFact | None:
        if self.config is None:
            raise RuntimeError("config not installed")

        isolation = desired_isolation_filter(self.config)
        try:
            self._restore_filter_policy(isolation)
            checked = self._check_filter_policy(isolation)
        except (KernelError, FirewallInspectionError) as exc:
            return DiagnosticFact(
                RuntimeReasonCode.FIREWALL_REPAIR_FAILED,
                str(exc),
            )

        if checked.safety is FirewallSafety.SAFE:
            return None
        detail = (
            checked.reason.detail
            if checked.reason is not None
            else checked.safety.name
        )
        return DiagnosticFact(
            RuntimeReasonCode.FIREWALL_REPAIR_FAILED,
            f"isolation filter verification failed: {detail}",
        )

    def _repair_firewall_nat_with_barrier(
        self,
        snapshot: ReconciliationSnapshot,
    ) -> None:
        if self.config is None:
            raise RuntimeError("config not installed")

        isolation = desired_isolation_filter(self.config)
        self._restore_filter_policy(isolation)
        isolation_check = self._check_filter_policy(isolation)
        if isolation_check.safety is not FirewallSafety.SAFE:
            detail = (
                isolation_check.reason.detail
                if isolation_check.reason is not None
                else isolation_check.safety.name
            )
            raise ReconciliationError(
                f"isolation filter verification failed: {detail}"
            )

        self._restore_nat_policy(snapshot.desired_full_policy.nat)
        nat_check = self._check_nat_policy(snapshot.desired_full_policy.nat)
        if nat_check.safety is not FirewallSafety.SAFE:
            detail = (
                nat_check.reason.detail
                if nat_check.reason is not None
                else nat_check.safety.name
            )
            raise ReconciliationError(
                f"NAT verification failed after isolation: {detail}"
            )

        self._restore_filter_policy(snapshot.desired_full_policy.filter)
        full_check = self._check_firewall_nat_policy(
            snapshot.desired_full_policy
        )
        if full_check.safety is not FirewallSafety.SAFE:
            detail = (
                full_check.reason.detail
                if full_check.reason is not None
                else full_check.safety.name
            )
            raise ReconciliationError(
                f"full firewall/NAT verification failed: {detail}"
            )

    # ---- iptables parsing / cleanup -------------------------------------

    @staticmethod
    def _parse_iptables_save(
        snapshot: str,
    ) -> Mapping[str, Mapping[str, object]]:
        tables: dict[str, dict[str, object]] = {}
        current: dict[str, object] | None = None

        for raw_line in snapshot.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("*"):
                name = line[1:]
                if not name or name in tables:
                    raise FirewallInspectionError(
                        f"invalid/duplicate iptables-save table line: {line!r}"
                    )
                current = {"chains": set(), "rules": {}}
                tables[name] = current
                continue
            if line == "COMMIT":
                if current is None:
                    raise FirewallInspectionError("COMMIT outside table")
                current = None
                continue
            if current is None:
                raise FirewallInspectionError(
                    f"iptables-save line outside table: {line!r}"
                )
            if line.startswith(":"):
                chain = line[1:].split(None, 1)[0]
                if not chain:
                    raise FirewallInspectionError(
                        f"invalid chain declaration: {line!r}"
                    )
                chains = current["chains"]
                assert isinstance(chains, set)
                chains.add(chain)
                rules = current["rules"]
                assert isinstance(rules, dict)
                rules.setdefault(chain, [])
                continue
            if line.startswith("-A "):
                parts = line.split(None, 2)
                if len(parts) < 3:
                    raise FirewallInspectionError(
                        f"invalid rule line: {line!r}"
                    )
                try:
                    shlex.split(line, posix=True)
                except ValueError as exc:
                    raise FirewallInspectionError(
                        "cannot parse iptables-save rule quoting: "
                        f"{line!r}: {exc}"
                    ) from exc
                chain = parts[1]
                rules = current["rules"]
                assert isinstance(rules, dict)
                rules.setdefault(chain, []).append(line)
                continue
            raise FirewallInspectionError(
                f"unsupported iptables-save line: {line!r}"
            )

        if current is not None:
            raise FirewallInspectionError("iptables-save table missing COMMIT")
        return MappingProxyType(tables)

    @staticmethod
    def _jump_target(rule: str) -> str | None:
        """
        Return the actual jump/goto target from one iptables-save rule.

        iptables-save quotes comment text. A plain str.split() would therefore
        misread a comment such as "x -j VPNG-FOO" as a real daemon-owned jump.
        Parse shell-style quoting and recognize both jump and goto references
        to the reserved VPNG-* namespace.
        """
        try:
            tokens = shlex.split(rule, posix=True)
        except ValueError as exc:
            raise FirewallInspectionError(
                f"cannot parse iptables-save rule quoting: {rule!r}: {exc}"
            ) from exc

        for index, token in enumerate(tokens):
            if token not in ("-j", "--jump", "-g", "--goto"):
                continue
            if index + 1 >= len(tokens):
                raise FirewallInspectionError(
                    f"iptables-save rule has target option without value: "
                    f"{rule!r}"
                )
            return tokens[index + 1]
        return None

    def _build_firewall_cleanup_payload(self, snapshot: str) -> str:
        """Build exact deletions for the reserved VPNG-* namespace."""
        parsed = self._parse_iptables_save(snapshot)
        payload: list[str] = []

        for table_name in ("filter", "nat"):
            table = parsed.get(table_name)
            if table is None:
                raise FirewallInspectionError(
                    f"iptables-save missing {table_name!r} table"
                )
            chains = table["chains"]
            rules = table["rules"]
            assert isinstance(chains, set)
            assert isinstance(rules, dict)

            owned_chains = sorted(
                chain for chain in chains if chain.startswith(VPNG_CHAIN_PREFIX)
            )
            delete_rules: list[str] = []
            for chain, chain_rules in rules.items():
                for rule in chain_rules:
                    target = self._jump_target(rule)
                    if target is None or not target.startswith(VPNG_CHAIN_PREFIX):
                        continue
                    prefix = f"-A {chain}"
                    if not rule.startswith(prefix):
                        raise FirewallInspectionError(
                            f"cannot transform rule for cleanup: {rule!r}"
                        )
                    delete_rules.append(
                        rule.replace(prefix, f"-D {chain}", 1)
                    )

            if not owned_chains and not delete_rules:
                continue

            payload.append(f"*{table_name}")
            payload.extend(delete_rules)
            for chain in owned_chains:
                payload.append(f"-F {chain}")
            for chain in owned_chains:
                payload.append(f"-X {chain}")
            payload.append("COMMIT")

        if not payload:
            return ""
        return "\n".join(payload) + "\n"

    @classmethod
    def _require_no_vpng_firewall_resources(
        cls,
        parsed: Mapping[str, Mapping[str, object]],
    ) -> None:
        for table_name in ("filter", "nat"):
            table = parsed.get(table_name)
            if table is None:
                raise CleanupError(f"missing {table_name!r} table after cleanup")
            chains = table["chains"]
            rules = table["rules"]
            assert isinstance(chains, set)
            assert isinstance(rules, dict)
            leftover_chains = sorted(
                chain for chain in chains if chain.startswith(VPNG_CHAIN_PREFIX)
            )
            if leftover_chains:
                raise CleanupError(
                    f"VPNG chains remain in {table_name}: {leftover_chains!r}"
                )
            for chain, chain_rules in rules.items():
                for rule in chain_rules:
                    target = cls._jump_target(rule)
                    if target and target.startswith(VPNG_CHAIN_PREFIX):
                        raise CleanupError(
                            f"VPNG jump remains in {table_name}/{chain}: {rule}"
                        )

    # ---- ip_forward ------------------------------------------------------

    def _best_effort_disable_forwarding(
        self,
        *,
        high_severity_context: str,
    ) -> DiagnosticFact | None:
        """
        Return None only when forwarding is confirmed disabled.

        A non-None DiagnosticFact records an incident in the current reconciliation
        pass.  The helper deliberately does not log by itself: final state
        decides whether the pass outcome is ERROR or a recovered WARNING.
        """
        try:
            if not self.kernel.get_ip_forward():
                return None

            self.kernel.set_ip_forward(False)
            if self.kernel.get_ip_forward():
                return DiagnosticFact(
                    code=RuntimeReasonCode.FORWARDING_DISABLE_FAILED,
                    detail=(
                        f"{high_severity_context}: ip_forward remains enabled "
                        "after successful write"
                    ),
                )
        except KernelError as exc:
            return DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_DISABLE_FAILED,
                detail=f"{high_severity_context}: {exc}",
            )

        return None

    def _best_effort_enable_forwarding(
        self,
    ) -> tuple[bool, DiagnosticFact | None]:
        """
        Return (confirmed_enabled, fact).

        Read before write.  If forwarding was already ON, return (True, None).
        If an unexpected OFF is successfully restored, return a recovered
        FORWARDING_RESTORED fact.  Failure returns FORWARDING_ENABLE_FAILED.
        The caller decides whether a restored fact is independent or merely
        duplicates an earlier firewall-isolation incident in the same pass.
        """
        try:
            if self.kernel.get_ip_forward():
                return True, None

            self.kernel.set_ip_forward(True)
            enabled = self.kernel.get_ip_forward()
        except KernelError as exc:
            return False, DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_ENABLE_FAILED,
                detail=str(exc),
            )

        if not enabled:
            return (
                False,
                DiagnosticFact(
                    code=RuntimeReasonCode.FORWARDING_ENABLE_FAILED,
                    detail="ip_forward remains disabled after successful write",
                ),
            )

        return (
            True,
            DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_RESTORED,
                detail="ip_forward was OFF before the enable step",
            ),
        )

    def _query_forwarding_state(
        self,
    ) -> tuple[bool, DiagnosticFact | None]:
        """
        Return (confirmed_on, error) without emitting an intermediate log.

        Query failure is conservatively treated as not confirmed ON.  The
        caller includes the error in the final reconciliation signature, so
        severity remains a property of the final current-state diagnosis.
        """
        try:
            return self.kernel.get_ip_forward(), None
        except KernelError as exc:
            return False, DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_QUERY_FAILED,
                detail=str(exc),
            )

    # ---- Events / signals / logging -------------------------------------

    def _install_signal_handlers(self) -> None:
        """
        Install handlers before startup phases and create selector wakeup fd.

        Handlers perform no cleanup/kernel work; they only set a flag.
        """
        if self._signal_wakeup_reader is not None:
            return

        reader, writer = socket.socketpair()
        reader.setblocking(False)
        writer.setblocking(False)

        self._signal_wakeup_reader = reader
        self._signal_wakeup_writer = writer
        self._previous_wakeup_fd = signal.set_wakeup_fd(
            writer.fileno(),
            warn_on_full_buffer=False,
        )

        def request_shutdown(signum: int, frame: object) -> None:
            del signum, frame
            self._shutdown_requested = True

        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            self._previous_signal_handlers[signum] = signal.getsignal(signum)

        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def _restore_signal_handlers(self) -> None:
        """Restore process-global signal state; useful for tests/embedding."""
        try:
            signal.set_wakeup_fd(self._previous_wakeup_fd)
        finally:
            self._previous_wakeup_fd = -1

        for signum, handler in self._previous_signal_handlers.items():
            signal.signal(signum, handler)
        self._previous_signal_handlers.clear()

        if self._signal_wakeup_reader is not None:
            self._signal_wakeup_reader.close()
            self._signal_wakeup_reader = None
        if self._signal_wakeup_writer is not None:
            self._signal_wakeup_writer.close()
            self._signal_wakeup_writer = None

        if self._netlink_socket is not None:
            self._netlink_socket.close()
            self._netlink_socket = None

    def _open_netlink_socket(self) -> socket.socket:
        """
        Open the single daemon-owned NETLINK_ROUTE event source.

        The socket subscribes only to event classes that can affect the RC3
        reconciliation snapshot or route state. Events are not interpreted as
        policy facts; they only schedule a fresh full reconciliation.
        """
        # linux/rtnetlink.h:
        # RTMGRP_LINK=0x1, RTMGRP_IPV4_IFADDR=0x10,
        # RTMGRP_IPV4_ROUTE=0x40.
        groups = 0x1 | 0x10 | 0x40

        try:
            netlink = socket.socket(
                socket.AF_NETLINK,
                socket.SOCK_RAW,
                socket.NETLINK_ROUTE,
            )
            netlink.setblocking(False)
            netlink.bind((0, groups))
        except OSError as exc:
            try:
                netlink.close()
            except (NameError, OSError):
                pass
            raise KernelError(
                f"failed to open NETLINK_ROUTE listener: {exc}"
            ) from exc

        return netlink

    @staticmethod
    def _drain_netlink_socket(netlink: socket.socket) -> bool:
        """
        Drain one readable Netlink burst and request full reconciliation.

        ENOBUFS means messages were lost; because the daemon never treats
        individual messages as policy facts, the safe response is exactly the
        same: perform a fresh full reconciliation.
        """
        triggered = False

        while True:
            try:
                data = netlink.recv(65535)
            except BlockingIOError:
                break
            except OSError as exc:
                if exc.errno == errno.ENOBUFS:
                    return True
                raise KernelError(
                    f"NETLINK_ROUTE receive failed: {exc}"
                ) from exc

            if not data:
                break
            triggered = True

        return triggered

    def _log_reconcile_outcome(
        self,
        signature: tuple[object, ...],
        *,
        level: int = logging.INFO,
        facts: tuple[DiagnosticFact, ...] = (),
        recovered_from: tuple[DiagnosticFact, ...] = (),
    ) -> None:
        """
        Edge-triggered final pass logging.

        Severity describes CURRENT functional state:
        - INFO: ACTIVE and the pass was clean;
        - WARNING: ACTIVE after a recovered incident, or DEGRADED with
          forwarding confirmed ON;
        - ERROR: ISOLATED, or DEGRADED with forwarding OFF/not confirmed ON.

        Dedupe identity uses stable RuntimeReasonCode values, never free-form
        exception detail.  Detail is render-only text.

        Clean INFO remains purely edge-triggered.  Unchanged WARNING/ERROR is
        repeated only after `failure_reminder_interval` (default 5 minutes).
        """
        dedupe_signature = (
            signature,
            tuple(fact.code for fact in facts),
            tuple(fact.code for fact in recovered_from),
        )
        now = time.monotonic()
        same_signature = (
            dedupe_signature == self._last_reconcile_log_signature
        )

        if same_signature:
            if level < logging.WARNING:
                return
            if (
                self._last_reconcile_log_at is not None
                and now - self._last_reconcile_log_at
                    < self.failure_reminder_interval
            ):
                return
        else:
            self._last_reconcile_log_signature = dedupe_signature

        self._last_reconcile_log_at = now

        message_parts = [f"reconcile outcome: {signature!r}"]

        if facts:
            message_parts.append(
                "pass facts: " + "; ".join(
                    self._format_diagnostic_fact(fact)
                    for fact in facts
                )
            )

        if recovered_from:
            message_parts.append(
                "recovered from: " + "; ".join(
                    self._format_diagnostic_fact(fact)
                    for fact in recovered_from
                )
            )

        LOG.log(level, "; ".join(message_parts))

    @staticmethod
    def _format_diagnostic_fact(fact: DiagnosticFact) -> str:
        base = RUNTIME_REASON_TEXT[fact.code]
        if fact.detail is None:
            return f"{fact.code.name}: {base}"
        return f"{fact.code.name}: {base}: {fact.detail}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


