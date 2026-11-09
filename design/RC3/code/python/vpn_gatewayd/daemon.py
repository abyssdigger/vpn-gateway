from __future__ import annotations

import logging
import select
import signal
import socket
import time
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .config import ConfigLoader
from .constants import (
    BLACKHOLE_METRIC,
    BLACKHOLE_ROUTE_PROTO,
    DEFAULT_FAILURE_REMINDER_INTERVAL,
    DEFAULT_LOCK_PATH,
    KERNEL_ROUTE_PROTO,
    LOG,
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
from .kernel import KernelInterface
from .models import (
    ApplyStateResult,
    DaemonState,
    DiagnosticFact,
    FirewallCheck,
    FirewallSafety,
    GatewayConfig,
    ProfileResourceSet,
    ProfileResult,
    RUNTIME_REASON_TEXT,
    ReconciliationPlan,
    RouteSpec,
    RouteType,
    RouteVerifyResult,
    RuntimeReasonCode,
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

        self._reported_route_overlaps: dict[str, frozenset[RouteSpec]] = {}
        self._shutdown_requested = False
        self._last_reconcile_log_signature: tuple[object, ...] | None = None
        self._last_reconcile_log_at: float | None = None

        self._signal_wakeup_reader: socket.socket | None = None
        self._signal_wakeup_writer: socket.socket | None = None
        self._previous_wakeup_fd = -1
        self._previous_signal_handlers: dict[int, object] = {}

        # Conscious boundary: the architecture requires one daemon-owned
        # Netlink listener.  It is an event source owned by orchestration, not
        # a policy/materialization operation of KernelInterface.  Exact
        # serialized event-loop mechanics remain open.
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

                self.state = DaemonState.ACTIVE
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
        self._reported_route_overlaps = {
            profile_id: frozenset() for profile_id in profiles
        }

    def cleanup(self) -> None:
        """Universal marker-based cleanup used before startup and on stop."""
        try:
            self.kernel.set_ip_forward(False)
            if self.kernel.get_ip_forward():
                raise CleanupError("ip_forward remains enabled after disable")

            routes = self.kernel.list_routes()
            for route in sorted(
                (route for route in routes if route.proto == VPN_ROUTE_PROTO),
                key=self._route_sort_key,
            ):
                self.kernel.delete_route(route)

            snapshot = self.kernel.iptables_save()
            cleanup_payload = self._build_firewall_cleanup_payload(snapshot)
            if cleanup_payload:
                self.kernel.iptables_restore(cleanup_payload, noflush=True)

            routes = self.kernel.list_routes()
            blackholes = sorted(
                (
                    route
                    for route in routes
                    if (
                        route.route_type is RouteType.BLACKHOLE
                        and route.proto == BLACKHOLE_ROUTE_PROTO
                        and route.metric == BLACKHOLE_METRIC
                    )
                ),
                key=self._route_sort_key,
            )
            for route in blackholes:
                self.kernel.delete_route(route)

            remaining_routes = self.kernel.list_routes()
            if any(route.proto == VPN_ROUTE_PROTO for route in remaining_routes):
                raise CleanupError("proto-202 VPN routes remain after cleanup")
            if any(
                route.route_type is RouteType.BLACKHOLE
                and route.proto == BLACKHOLE_ROUTE_PROTO
                and route.metric == BLACKHOLE_METRIC
                for route in remaining_routes
            ):
                raise CleanupError("owned blackhole routes remain after cleanup")

            remaining_fw = self._parse_iptables_save(
                self.kernel.iptables_save()
            )
            self._require_no_vpng_firewall_resources(remaining_fw)
        except (KernelError, FirewallInspectionError) as exc:
            raise CleanupError(str(exc)) from exc

    def apply(self) -> None:
        """Apply one fail-hard happy-path bootstrap transaction boundary."""
        if self.config is None:
            raise RuntimeError("config not installed")

        initial_routes = self.kernel.list_routes()
        interface_ipv4 = self.kernel.list_interface_ipv4()
        desired = self._derive_desired_routes(interface_ipv4=interface_ipv4)
        plan = self._build_plan(
            all_kernel_routes=initial_routes,
            desired_routes_by_profile=desired,
        )
        self._validate_plan(
            plan,
            all_kernel_routes=initial_routes,
            desired_routes_by_profile=desired,
        )

        self.kernel.iptables_restore(
            self._build_fixed_firewall_nat_payload(),
            noflush=True,
        )
        firewall = self._check_fixed_firewall_nat()
        if firewall.safety is not FirewallSafety.SAFE:
            detail = firewall.reason.detail if firewall.reason else None
            raise ReconciliationError(
                f"fixed firewall/NAT verification failed: "
                f"{firewall.safety.name}: {detail or 'no detail'}"
            )

        self._apply_plan(plan)
        verified = self._verify_plan(
            all_kernel_routes=self.kernel.list_routes(),
            desired_routes_by_profile=desired,
        )
        results = self._require_complete_profile_results(
            verified.profile_results
        )
        failed = [
            profile_id
            for profile_id, result in results.items()
            if result.result is not ApplyStateResult.SUCCESS
        ]
        if failed:
            raise ReconciliationError(
                f"initial route verification failed for profiles: {failed!r}"
            )

        self._commit_owned(
            verified_routes_by_profile=verified.owned_routes_by_profile
        )

        self.kernel.set_ip_forward(True)
        if not self.kernel.get_ip_forward():
            raise KernelError("ip_forward remains disabled after enable")

    def run(self) -> None:
        """Happy-path runtime: remain alive until SIGTERM/SIGINT wakes us."""
        reader = self._signal_wakeup_reader
        if reader is None:
            raise RuntimeError("signal wakeup reader is not installed")

        while not self._shutdown_requested:
            try:
                readable, _, _ = select.select([reader], [], [])
            except InterruptedError:
                continue
            if reader not in readable:
                continue

            while True:
                try:
                    data = reader.recv(4096)
                except BlockingIOError:
                    break
                if not data:
                    break

        # Runtime reconciliation/Netlink/watchdog are intentionally deferred
        # until the happy-path bootstrap has been exercised on the target host.

    # ---- Runtime reconciliation ----------------------------------------

    def reconcile(self) -> None:
        """
        Runtime orchestration skeleton.

        Fixed firewall/NAT verification is always first.  Route reconciliation
        starts only after fixed infrastructure is SAFE.
        """
        firewall = self._check_fixed_firewall_nat()
        pass_incidents: list[DiagnosticFact] = []
        isolation_disable_fact: DiagnosticFact | None = None

        if firewall.safety is FirewallSafety.UNKNOWN:
            isolation_disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="firewall/NAT UNKNOWN"
            )
            self.state = DaemonState.ISOLATED

            facts: list[DiagnosticFact] = []
            if firewall.reason is not None:
                facts.append(firewall.reason)
            if isolation_disable_fact is not None:
                facts.append(isolation_disable_fact)

            signature_parts: list[object] = [
                "isolated",
                "firewall-unknown",
            ]
            signature_parts.extend(
                ("reason", fact.code) for fact in facts
            )

            self._log_reconcile_outcome(
                tuple(signature_parts),
                level=logging.ERROR,
                facts=tuple(facts),
            )
            # Blind repair is forbidden for UNKNOWN.
            return

        if firewall.safety is FirewallSafety.UNSAFE:
            if firewall.reason is not None:
                pass_incidents.append(firewall.reason)

            isolation_disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="firewall/NAT UNSAFE"
            )
            if isolation_disable_fact is not None:
                pass_incidents.append(isolation_disable_fact)

            # Even if disabling forwarding failed, restoring filter/NAT is
            # still useful and required.  filter before nat inside repair.
            try:
                self._repair_fixed_firewall_nat()
                repaired = self._check_fixed_firewall_nat()
            except KernelError as exc:
                repaired = FirewallCheck(
                    safety=FirewallSafety.UNKNOWN,
                    reason=DiagnosticFact(
                        code=RuntimeReasonCode.FIREWALL_REPAIR_FAILED,
                        detail=str(exc),
                    ),
                )

            if repaired.safety is not FirewallSafety.SAFE:
                self.state = DaemonState.ISOLATED

                facts = list(pass_incidents)
                if repaired.reason is not None:
                    facts.append(repaired.reason)

                signature_parts = [
                    "isolated",
                    "firewall-repair-failed",
                    repaired.safety,
                ]
                signature_parts.extend(
                    ("reason", fact.code) for fact in facts
                )

                self._log_reconcile_outcome(
                    tuple(signature_parts),
                    level=logging.ERROR,
                    facts=tuple(facts),
                )
                return

            firewall = repaired

        # Fixed firewall/NAT is now SAFE.  A fresh route pass is required
        # before forwarding can be restored after isolation.
        try:
            profile_results = self._require_complete_profile_results(
                self._reconcile_routes_once()
            )
        except (KernelError, PlanValidationError, ReconciliationError) as exc:
            # SAFE firewall + incomplete route pass => DEGRADED.
            #
            # Severity depends on CURRENT forwarding availability:
            # - confirmed ON  -> WARNING (gateway is still forwarding);
            # - OFF/unknown   -> ERROR   (gateway is not confirmed usable).
            self.state = DaemonState.DEGRADED
            forwarding_on, forwarding_query_error = (
                self._query_forwarding_state()
            )

            facts = list(pass_incidents)
            facts.append(
                DiagnosticFact(
                    code=RuntimeReasonCode.ROUTE_PASS_INCOMPLETE,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            if forwarding_query_error is not None:
                facts.append(forwarding_query_error)

            signature_parts: list[object] = [
                "degraded",
                "route-pass-incomplete",
                ("ip-forward", forwarding_on),
            ]
            signature_parts.extend(
                ("reason", fact.code) for fact in facts
            )

            self._log_reconcile_outcome(
                tuple(signature_parts),
                level=(
                    logging.WARNING
                    if forwarding_on
                    else logging.ERROR
                ),
                facts=tuple(facts),
            )
            return

        # A completed SAFE fresh route pass is sufficient to restore global
        # forwarding even if a profile result is FAIL: profile-local route
        # failures remain fail-closed via BLACKHOLE/FORWARD policy.
        forwarding_enabled, forwarding_enable_fact = (
            self._best_effort_enable_forwarding()
        )

        # If we intentionally isolated this same pass because firewall was
        # UNSAFE, restoring ip_forward is part of that recovery and must not
        # create a duplicate FORWARDING_RESTORED incident.
        if (
            forwarding_enabled
            and forwarding_enable_fact is not None
            and forwarding_enable_fact.code
                is RuntimeReasonCode.FORWARDING_RESTORED
        ):
            if not pass_incidents:
                pass_incidents.append(forwarding_enable_fact)
            forwarding_enable_fact = None

        all_success = all(
            result.result is ApplyStateResult.SUCCESS
            for result in profile_results.values()
        )

        if all_success and forwarding_enabled:
            self.state = DaemonState.ACTIVE
        else:
            self.state = DaemonState.DEGRADED

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
            # The pass did not fully recover to ACTIVE.  Preserve prior
            # incidents as current-pass diagnostic facts, without claiming
            # "recovered from".
            current_facts[0:0] = pass_incidents

        signature_parts: list[object] = [
            self.state,
            tuple(profile_signature),
            ("ip-forward", forwarding_enabled),
        ]
        signature_parts.extend(
            ("reason", fact.code) for fact in current_facts
        )

        if self.state is DaemonState.ACTIVE:
            level = (
                logging.WARNING
                if recovered_from
                else logging.INFO
            )
        elif forwarding_enabled:
            # DEGRADED but gateway is still forwarding.
            level = logging.WARNING
        else:
            # DEGRADED and forwarding is OFF/not confirmed usable.
            level = logging.ERROR

        self._log_reconcile_outcome(
            tuple(signature_parts),
            level=level,
            facts=tuple(current_facts),
            recovered_from=recovered_from,
        )

    def _reconcile_routes_once(self) -> Mapping[str, ProfileResult]:
        """
        One lifecycle-neutral route reconciliation pass.

        Required flow:
        - fresh route + interface/address snapshots;
        - derive readiness;
        - CONFIGURED + OWNED -> one immutable desired_routes_by_profile;
        - build route-only plan from that same desired snapshot;
        - validate against that same desired snapshot;
        - apply, BLACKHOLE adds first;
        - fresh verify against that same desired snapshot;
        - map result per managed profile;
        - commit each profile OWNED only from verified state.

        This method must not mutate DaemonState.

        Contract:
        - return only after a completed fresh verify;
        - per-profile FAIL is a valid result only after that completed verify;
        - if snapshot/build/apply/verify/commit-contract cannot complete,
          propagate KernelError, PlanValidationError or ReconciliationError;
        - if verify itself raises KernelError, propagate it unchanged;
        - never return a partial/empty result to represent an incomplete pass;
        - returned keys must equal the complete managed profile key set;
        - do not replace previously confirmed OWNED state for a profile unless
          the current pass has verified the replacement.
        """
        raise NotImplementedError

    # ---- Route plan ------------------------------------------------------

    def _derive_desired_routes(
        self,
        *,
        interface_ipv4: Mapping[str, frozenset[IPv4Address]],
    ) -> Mapping[str, frozenset[RouteSpec]]:
        """
        Build one immutable DESIRED snapshot for the current pass.

        BLACKHOLE guards are always desired.
        UNICAST peer routes are desired only while the profile is ready.
        """
        desired: dict[str, frozenset[RouteSpec]] = {}

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            configured = profile._list_routes(
                ProfileResourceSet.CONFIGURED
            )

            if self._profile_is_ready(profile, interface_ipv4):
                selected = configured
            else:
                selected = frozenset(
                    route
                    for route in configured
                    if route.route_type is RouteType.BLACKHOLE
                )

            desired[profile_id] = frozenset(selected)

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
            owned = profile._list_routes(ProfileResourceSet.OWNED)
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
        configured_by_profile: dict[str, frozenset[RouteSpec]] = {}
        owned_owners: dict[RouteSpec, set[str]] = {}

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            configured = profile._list_routes(
                ProfileResourceSet.CONFIGURED
            )
            configured_by_profile[profile_id] = configured

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

            for route in profile._list_routes(ProfileResourceSet.OWNED):
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
                    route in configured_by_profile[profile_id]
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
        """Verify exact protected-prefix state against the same DESIRED snapshot."""
        self._require_complete_desired_snapshot(desired_routes_by_profile)

        profile_results: dict[str, ProfileResult] = {}
        owned_routes: dict[str, frozenset[RouteSpec]] = {}

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            desired = desired_routes_by_profile[profile_id]
            protected = frozenset(profile.config.routes)
            actual_exact = frozenset(
                route
                for route in all_kernel_routes
                if route.destination in protected
            )

            if actual_exact == desired:
                profile_results[profile_id] = ProfileResult(
                    result=ApplyStateResult.SUCCESS
                )
                owned_routes[profile_id] = desired
            else:
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
                owned_routes[profile_id] = profile._list_routes(
                    ProfileResourceSet.OWNED
                )

        return RouteVerifyResult(
            profile_results=MappingProxyType(profile_results),
            owned_routes_by_profile=MappingProxyType(owned_routes),
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
    ) -> None:
        """
        Commit profile ownership only after a complete verify result.

        Validate the entire managed key set BEFORE mutating any profile so a
        partial verify result cannot partially replace process-local OWNED.
        """
        expected = frozenset(self.profiles)
        actual = frozenset(verified_routes_by_profile)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ReconciliationError(
                "incomplete verified ownership mapping: "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )

        for profile_id in sorted(expected):
            self.profiles[profile_id].update_owned_state(
                routes=verified_routes_by_profile[profile_id]
            )

    def _routes_for_profile(
        self,
        profile: VpnProfile,
        all_kernel_routes: frozenset[RouteSpec],
    ) -> frozenset[RouteSpec]:
        """
        Return routes related to this profile's protected address space.

        Exact routes and more-/less-specific overlaps are included for
        verification/diagnostics.  The default route is deliberately excluded
        from overlap reporting.
        """
        protected = profile.config.routes
        default = IPv4Network("0.0.0.0/0")

        return frozenset(
            route
            for route in all_kernel_routes
            if (
                route.destination != default
                and any(
                    route.destination.overlaps(destination)
                    for destination in protected
                )
            )
        )

    # ---- Readiness / helpers --------------------------------------------

    def _profile_is_ready(
        self,
        profile: VpnProfile,
        interface_ipv4: Mapping[str, frozenset[IPv4Address]],
    ) -> bool:
        addresses = interface_ipv4.get(str(profile.config.interface))
        return (
            addresses is not None
            and profile.config.local_address in addresses
        )

    def effective_sources(
        self,
        profile: VpnProfile,
    ) -> tuple[IPv4Network, ...]:
        if self.config is None:
            raise RuntimeError("config not installed")

        merged = set(self.config.common_allowed_sources)
        merged.update(profile.config.allowed_sources)

        return tuple(
            sorted(
                merged,
                key=lambda net: (int(net.network_address), net.prefixlen),
            )
        )

    # ---- Fixed firewall/NAT ---------------------------------------------

    def _check_fixed_firewall_nat(self) -> FirewallCheck:
        """
        Read-only verification.

        Must verify:
        - reserved VPNG-* chains expected for current managed config;
        - fixed INPUT/FORWARD chains and contents;
        - VPNG-INGRESS;
        - VPNG-RESERVED;
        - profile NAT chains;
        - static MASQUERADE for every managed profile, including peers=[];
        - exact owned jump layout/order in INPUT/FORWARD/POSTROUTING.

        Inventory failure => UNKNOWN.
        Readable confirmed drift => UNSAFE.
        Exact match => SAFE.
        """
        try:
            snapshot = self.kernel.iptables_save()
        except KernelError as exc:
            return FirewallCheck(
                safety=FirewallSafety.UNKNOWN,
                reason=DiagnosticFact(
                    code=RuntimeReasonCode.FIREWALL_INVENTORY_FAILED,
                    detail=str(exc),
                ),
            )

        try:
            return self._compare_fixed_firewall_nat(snapshot)
        except FirewallInspectionError as exc:
            return FirewallCheck(
                safety=FirewallSafety.UNKNOWN,
                reason=DiagnosticFact(
                    code=RuntimeReasonCode.FIREWALL_INSPECTION_FAILED,
                    detail=str(exc),
                ),
            )

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
        tokens = rule.split()
        try:
            index = tokens.index("-j")
        except ValueError:
            return None
        if index + 1 >= len(tokens):
            return None
        return tokens[index + 1]

    def _fixed_firewall_model(
        self,
    ) -> tuple[
        Mapping[str, tuple[str, ...]],
        Mapping[str, Mapping[str, tuple[str, ...]]],
    ]:
        if self.config is None:
            raise RuntimeError("config not installed")

        profile_ids = tuple(sorted(self.profiles, key=str.casefold))
        input_jumps = tuple(
            f"-A INPUT -j {self.profiles[profile_id].config.chain_input}"
            for profile_id in profile_ids
        )
        forward_jumps = (
            "-A FORWARD -j VPNG-INGRESS",
            "-A FORWARD -j VPNG-RESERVED",
            *(
                f"-A FORWARD -j {self.profiles[profile_id].config.chain_forward}"
                for profile_id in profile_ids
            ),
        )
        nat_jumps = tuple(
            f"-A POSTROUTING -j {self.profiles[profile_id].config.chain_nat}"
            for profile_id in profile_ids
        )

        filter_rules: dict[str, tuple[str, ...]] = {}
        ingress: list[str] = []
        for profile_id in profile_ids:
            cfg = self.profiles[profile_id].config
            ingress.extend((
                f"-A VPNG-INGRESS -i {str(cfg.interface)} -m conntrack --ctstate INVALID -j DROP",
                f"-A VPNG-INGRESS -i {str(cfg.interface)} -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT",
                f"-A VPNG-INGRESS -i {str(cfg.interface)} -j REJECT --reject-with icmp-host-prohibited",
            ))
        ingress.append("-A VPNG-INGRESS -j RETURN")
        filter_rules["VPNG-INGRESS"] = tuple(ingress)

        reserved = [
            f"-A VPNG-RESERVED -d {self.profiles[profile_id].config.network} "
            "-j REJECT --reject-with icmp-host-prohibited"
            for profile_id in profile_ids
        ]
        reserved.append("-A VPNG-RESERVED -j RETURN")
        filter_rules["VPNG-RESERVED"] = tuple(reserved)

        nat_rules: dict[str, tuple[str, ...]] = {}
        for profile_id in profile_ids:
            profile = self.profiles[profile_id]
            cfg = profile.config
            input_rules = (
                f"-A {cfg.chain_input} -i {str(cfg.interface)} -m conntrack --ctstate INVALID -j DROP",
                f"-A {cfg.chain_input} -i {str(cfg.interface)} -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT",
                f"-A {cfg.chain_input} -s {cfg.network} -d {cfg.local_address}/32 -i {str(cfg.interface)} -m conntrack --ctstate NEW -j ACCEPT",
                f"-A {cfg.chain_input} -i {str(cfg.interface)} -j REJECT --reject-with icmp-host-prohibited",
                f"-A {cfg.chain_input} -j RETURN",
            )
            filter_rules[cfg.chain_input] = input_rules

            forward_rules: list[str] = []
            sources = self.effective_sources(profile)
            for destination in cfg.routes:
                forward_rules.append(
                    f"-A {cfg.chain_forward} -d {destination} -o {str(cfg.interface)} "
                    "-m conntrack --ctstate INVALID -j DROP"
                )
                for source in sources:
                    forward_rules.append(
                        f"-A {cfg.chain_forward} -s {source} -d {destination} "
                        f"-o {str(cfg.interface)} -j ACCEPT"
                    )
                forward_rules.append(
                    f"-A {cfg.chain_forward} -d {destination} "
                    "-j REJECT --reject-with icmp-host-prohibited"
                )
            forward_rules.append(f"-A {cfg.chain_forward} -j RETURN")
            filter_rules[cfg.chain_forward] = tuple(forward_rules)

            nat_rules[cfg.chain_nat] = (
                f"-A {cfg.chain_nat} -o {str(cfg.interface)} -m addrtype ! --src-type LOCAL -j MASQUERADE",
                f"-A {cfg.chain_nat} -j RETURN",
            )

        jumps = MappingProxyType({
            "INPUT": input_jumps,
            "FORWARD": tuple(forward_jumps),
            "POSTROUTING": nat_jumps,
        })
        chain_rules = MappingProxyType({
            "filter": MappingProxyType(filter_rules),
            "nat": MappingProxyType(nat_rules),
        })
        return jumps, chain_rules

    def _compare_fixed_firewall_nat(self, snapshot: str) -> FirewallCheck:
        """Compare only daemon-owned namespace and built-in jump prefixes."""
        parsed = self._parse_iptables_save(snapshot)
        jumps, expected = self._fixed_firewall_model()

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

            expected_chains = set(expected[table_name])
            actual_owned = {
                chain for chain in chains if chain.startswith(VPNG_CHAIN_PREFIX)
            }
            if actual_owned != expected_chains:
                return FirewallCheck(
                    safety=FirewallSafety.UNSAFE,
                    reason=DiagnosticFact(
                        RuntimeReasonCode.FIREWALL_DRIFT,
                        f"{table_name} VPNG chains expected={sorted(expected_chains)!r} "
                        f"actual={sorted(actual_owned)!r}",
                    ),
                )

            for chain, expected_rules in expected[table_name].items():
                actual_rules = tuple(rules.get(chain, ()))
                if actual_rules != expected_rules:
                    return FirewallCheck(
                        safety=FirewallSafety.UNSAFE,
                        reason=DiagnosticFact(
                            RuntimeReasonCode.FIREWALL_DRIFT,
                            f"{table_name}/{chain} rules differ",
                        ),
                    )

        filter_rules = parsed["filter"]["rules"]
        nat_rules = parsed["nat"]["rules"]
        assert isinstance(filter_rules, dict)
        assert isinstance(nat_rules, dict)

        for chain, expected_prefix in (
            ("INPUT", jumps["INPUT"]),
            ("FORWARD", jumps["FORWARD"]),
        ):
            actual = tuple(filter_rules.get(chain, ()))
            if actual[:len(expected_prefix)] != expected_prefix:
                return FirewallCheck(
                    FirewallSafety.UNSAFE,
                    DiagnosticFact(
                        RuntimeReasonCode.FIREWALL_DRIFT,
                        f"filter/{chain} VPNG jump prefix differs",
                    ),
                )
            if any(
                (self._jump_target(rule) or "").startswith(VPNG_CHAIN_PREFIX)
                for rule in actual[len(expected_prefix):]
            ):
                return FirewallCheck(
                    FirewallSafety.UNSAFE,
                    DiagnosticFact(
                        RuntimeReasonCode.FIREWALL_DRIFT,
                        f"filter/{chain} has extra VPNG jump",
                    ),
                )

        postrouting = tuple(nat_rules.get("POSTROUTING", ()))
        expected_postrouting = jumps["POSTROUTING"]
        if postrouting[:len(expected_postrouting)] != expected_postrouting:
            return FirewallCheck(
                FirewallSafety.UNSAFE,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_DRIFT,
                    "nat/POSTROUTING VPNG jump prefix differs",
                ),
            )
        if any(
            (self._jump_target(rule) or "").startswith(VPNG_CHAIN_PREFIX)
            for rule in postrouting[len(expected_postrouting):]
        ):
            return FirewallCheck(
                FirewallSafety.UNSAFE,
                DiagnosticFact(
                    RuntimeReasonCode.FIREWALL_DRIFT,
                    "nat/POSTROUTING has extra VPNG jump",
                ),
            )

        return FirewallCheck(FirewallSafety.SAFE, None)

    def _build_fixed_firewall_nat_payload(self) -> str:
        """Build deterministic filter+nat bootstrap payload without foreign flush."""
        jumps, chain_rules = self._fixed_firewall_model()
        lines: list[str] = ["*filter"]
        for chain in sorted(chain_rules["filter"]):
            lines.append(f":{chain} - [0:0]")

        for position, rule in enumerate(jumps["INPUT"], start=1):
            lines.append(rule.replace("-A INPUT", f"-I INPUT {position}", 1))
        for position, rule in enumerate(jumps["FORWARD"], start=1):
            lines.append(
                rule.replace("-A FORWARD", f"-I FORWARD {position}", 1)
            )
        for chain in sorted(chain_rules["filter"]):
            lines.extend(chain_rules["filter"][chain])
        lines.append("COMMIT")

        lines.append("*nat")
        for chain in sorted(chain_rules["nat"]):
            lines.append(f":{chain} - [0:0]")
        for position, rule in enumerate(jumps["POSTROUTING"], start=1):
            lines.append(
                rule.replace(
                    "-A POSTROUTING",
                    f"-I POSTROUTING {position}",
                    1,
                )
            )
        for chain in sorted(chain_rules["nat"]):
            lines.extend(chain_rules["nat"][chain])
        lines.append("COMMIT")
        return "\n".join(lines) + "\n"

    def _repair_fixed_firewall_nat(self) -> None:
        """
        Repair confirmed UNSAFE fixed policy.

        Cross-table atomicity does not exist:
        - normal case: forwarding has already been disabled;
        - if sysctl disable failed, still restore filter first, then nat;
        - verify again after repair.
        """
        raise NotImplementedError

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

    def _open_netlink_socket(self) -> socket.socket:
        """
        TODO implementation step 8.

        One daemon-owned AF_NETLINK/NETLINK_ROUTE socket subscribed to link and
        IPv4 address changes.  This listener intentionally remains outside
        KernelInterface because it feeds orchestration events and materializes
        no policy.  ENOBUFS must trigger a full resync.
        """
        raise NotImplementedError

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


