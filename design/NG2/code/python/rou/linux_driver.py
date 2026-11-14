from __future__ import annotations

from dataclasses import dataclass, replace
import subprocess
from typing import Protocol

from .interface_identity import InterfaceIdentity
from .linux_network import (
    LinuxNetworkDesired,
    linux_network_route_priority_only_change,
)
from .linux_route_priority import plan_route_slot_moves
from .linux_nft import (
    FILTER_TABLE,
    NAT_TABLE,
    NftFilterDesired,
    NftNatDesired,
    NftTableIdentity,
    NftTableObservation,
    normalize_nft_text,
    parse_nft_rule_comments,
    parse_nft_tables,
    verify_nft_table,
)
from .linux_observation import (
    LinuxRoutingObservation,
    parse_link_json,
    parse_route_json,
    parse_rule_json,
    verify_linux_routing,
)
from .linux_prerequisites import verify_linux_namespace_prerequisites
from .linux_routing import (
    FIRST_PATH_METRIC,
    FIRST_RULE_PRIORITY,
    MAX_RULE_PRIORITY,
    PATH_METRIC_STEP,
    RT_TABLE_COMPAT,
    RT_TABLE_DEFAULT,
    RT_TABLE_LOCAL,
    RT_TABLE_MAIN,
    RT_TABLE_UNSPEC,
    TERMINAL_METRIC,
    TERMINAL_ROUTE_PROTOCOL,
    UNICAST_ROUTE_PROTOCOL,
    LinuxRouteKind,
)


class LinuxDriverError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class LinuxCommandRunner(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        ...


class SubprocessLinuxRunner:
    def run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        completed = subprocess.run(
            argv,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        result = CommandResult(
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )
        if check and result.returncode != 0:
            raise LinuxDriverError(
                f"command failed rc={result.returncode}: {argv!r}: "
                f"{result.stderr.strip()}"
            )
        return result


class NetworkNamespaceLinuxRunner:
    """Run Linux network commands inside one pre-existing named namespace."""

    def __init__(
        self,
        host_runner: LinuxCommandRunner,
        namespace: str,
    ) -> None:
        if not namespace:
            raise ValueError("network namespace name must be non-empty")
        self._host_runner = host_runner
        self._namespace = namespace

    def run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        return self._host_runner.run(
            ("ip", "netns", "exec", self._namespace, *argv),
            input_text=input_text,
            check=check,
        )


@dataclass(frozen=True)
class LinuxNetworkObservation:
    prerequisites: tuple[tuple[str, str], ...]
    routing: LinuxRoutingObservation
    filter: NftTableObservation | None
    nat: NftTableObservation | None
    nft_tables: tuple[NftTableIdentity, ...]


@dataclass(frozen=True)
class LinuxNetworkVerification:
    ok: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class LinuxDriverResult:
    success: bool
    diagnostic: str | None = None


_RESERVED_TABLE_IDS = frozenset(
    {
        RT_TABLE_UNSPEC,
        RT_TABLE_COMPAT,
        RT_TABLE_DEFAULT,
        RT_TABLE_MAIN,
        RT_TABLE_LOCAL,
    }
)


def verify_linux_network(
    desired: LinuxNetworkDesired,
    observed: LinuxNetworkObservation,
    *,
    expected_ip_forward: bool | None = None,
) -> LinuxNetworkVerification:
    errors: list[str] = []

    if expected_ip_forward is None:
        expected_ip_forward = desired.ip_forward_required

    errors.extend(
        verify_linux_namespace_prerequisites(
            desired.prerequisites,
            observed.prerequisites,
        )
    )

    routing = verify_linux_routing(
        desired.routing,
        observed.routing,
        expected_ip_forward=expected_ip_forward,
    )
    errors.extend(routing.errors)

    if desired.filter is None:
        if observed.filter is not None:
            errors.append("owned nft filter table should be absent")
    else:
        errors.extend(
            verify_nft_table(
                desired.filter,
                observed.filter,
            ).errors
        )

    if desired.nat is None:
        if observed.nat is not None:
            errors.append("owned nft NAT table should be absent")
    else:
        errors.extend(
            verify_nft_table(
                desired.nat,
                observed.nat,
            ).errors
        )

    expected_tables = set()
    if desired.filter is not None:
        expected_tables.add(
            NftTableIdentity(desired.filter.family, desired.filter.table)
        )
    if desired.nat is not None:
        expected_tables.add(
            NftTableIdentity(desired.nat.family, desired.nat.table)
        )
    actual_tables = set(observed.nft_tables)
    if actual_tables != expected_tables:
        errors.append(
            "nft table inventory differs: expected "
            f"{sorted(expected_tables)!r}, observed {sorted(actual_tables)!r}"
        )

    return LinuxNetworkVerification(
        ok=not errors,
        errors=tuple(errors),
    )


class LinuxNetworkExecutor:
    """Converge and verify structural Linux network state for one ROU namespace."""

    def __init__(self, runner: LinuxCommandRunner) -> None:
        self._runner = runner

    def observe_interfaces(self) -> tuple[InterfaceIdentity, ...]:
        first_links = self._runner.run(
            ("ip", "-j", "link", "show")
        ).stdout
        interfaces = parse_link_json(first_links)
        final_links = self._runner.run(
            ("ip", "-j", "link", "show")
        ).stdout
        final_interfaces = parse_link_json(final_links)
        if final_interfaces != interfaces:
            raise LinuxDriverError(
                "interface inventory changed during interface observation"
            )
        return interfaces

    def observe(
        self,
        desired: LinuxNetworkDesired,
    ) -> LinuxNetworkObservation:
        first_links = self._runner.run(
            ("ip", "-j", "link", "show")
        ).stdout
        interfaces = parse_link_json(first_links)

        routes = parse_route_json(
            self._runner.run(
                (
                    "ip",
                    "-j",
                    "-4",
                    "route",
                    "show",
                    "table",
                    "all",
                )
            ).stdout
        )
        rules = parse_rule_json(
            self._runner.run(
                ("ip", "-j", "-4", "rule", "show")
            ).stdout
        )

        forwarding = self._observe_forwarding()
        prerequisites = tuple(
            (
                key,
                self._runner.run(command).stdout.strip(),
            )
            for key, command in desired.prerequisites.observation_commands
        )

        nft_tables = parse_nft_tables(
            self._runner.run(
                ("nft", "-j", "list", "tables")
            ).stdout
        )
        nft_filter = self._observe_nft_table(
            desired.filter,
            fallback_table=FILTER_TABLE,
        )
        nft_nat = self._observe_nft_table(
            desired.nat,
            fallback_table=NAT_TABLE,
        )

        final_links = self._runner.run(
            ("ip", "-j", "link", "show")
        ).stdout
        final_interfaces = parse_link_json(final_links)
        if final_interfaces != interfaces:
            raise LinuxDriverError(
                "interface inventory changed during network observation"
            )

        return LinuxNetworkObservation(
            prerequisites=prerequisites,
            routing=LinuxRoutingObservation(
                interfaces=interfaces,
                routes=routes,
                rules=rules,
                ip_forward=forwarding,
            ),
            filter=nft_filter,
            nat=nft_nat,
            nft_tables=nft_tables,
        )

    def verify_current(
        self,
        desired: LinuxNetworkDesired,
    ) -> LinuxNetworkVerification:
        return verify_linux_network(
            desired,
            self.observe(desired),
        )

    def close_forwarding_verified(self) -> LinuxDriverResult:
        """Protectively close IPv4/IPv6 forwarding and freshly verify the result."""

        try:
            self._close_forwarding()
            if self._observe_forwarding():
                raise LinuxDriverError(
                    "protective forwarding close verification observed "
                    "net.ipv4.ip_forward=1"
                )
            for key in (
                "net/ipv6/conf/all/forwarding",
                "net/ipv6/conf/default/forwarding",
            ):
                value = self._runner.run(("sysctl", "-n", key)).stdout.strip()
                if value != "0":
                    raise LinuxDriverError(
                        "protective forwarding close verification observed "
                        f"{key.replace('/', '.')}={value!r}"
                    )
            return LinuxDriverResult(True)
        except Exception as exc:
            return LinuxDriverResult(
                False,
                f"cannot prove protective forwarding close: {exc}",
            )

    def materialize_route_priority(
        self,
        current: LinuxNetworkDesired,
        desired: LinuxNetworkDesired,
    ) -> LinuxDriverResult:
        """Apply a verified fixed-metric path permutation without closing forwarding.

        Any failed precondition, mutation or final verification falls back immediately to
        the structural fail-closed materializer.
        """

        try:
            if not linux_network_route_priority_only_change(current, desired):
                raise LinuxDriverError(
                    "requested fast path is not a pure route-priority permutation"
                )

            before = self.observe(current)
            precondition = verify_linux_network(current, before)
            if not precondition.ok:
                raise LinuxDriverError(
                    "route-priority precondition verification failed: "
                    + "; ".join(precondition.errors)
                )

            current_groups = self._route_priority_groups(current)
            desired_groups = self._route_priority_groups(desired)

            for group in sorted(
                desired_groups,
                key=lambda item: (
                    item[1],
                    -item[2].prefixlen,
                    int(item[2].network_address),
                    item[3],
                    item[0],
                ),
            ):
                current_routes = current_groups[group]
                desired_routes = desired_groups[group]
                path_count = len(desired_routes)
                metrics = tuple(
                    FIRST_PATH_METRIC + index * PATH_METRIC_STEP
                    for index in range(path_count + 1)
                )
                if metrics[-1] >= TERMINAL_METRIC:
                    raise LinuxDriverError(
                        "route-priority working slot reaches terminal metric"
                    )

                current_by_metric = {
                    route.metric: route.path
                    for route in current_routes
                }
                desired_by_metric = {
                    route.metric: route.path
                    for route in desired_routes
                }
                current_slots = tuple(
                    current_by_metric.get(metric)
                    for metric in metrics
                )
                desired_slots = tuple(
                    desired_by_metric.get(metric)
                    for metric in metrics
                )

                moves = plan_route_slot_moves(
                    current_slots,
                    desired_slots,
                )
                template = desired_routes[0]
                for move in moves:
                    assert move.path is not None
                    source = replace(
                        template,
                        path=move.path,
                        metric=metrics[move.source_slot],
                    )
                    duplicate = replace(
                        template,
                        path=move.path,
                        metric=metrics[move.target_slot],
                    )

                    # Make before break: the complete eligible path set remains
                    # materialized throughout the transition. Only the moving
                    # path is duplicated between these two commands.
                    self._runner.run(self._route_add_argv(duplicate))
                    self._runner.run(self._route_delete_argv(source))

            final = self.observe(desired)
            verification = verify_linux_network(desired, final)
            if not verification.ok:
                raise LinuxDriverError(
                    "route-priority final verification failed: "
                    + "; ".join(verification.errors)
                )

            return LinuxDriverResult(True)

        except Exception as exc:
            fast_diagnostic = str(exc)
            fallback = self.materialize_structural(desired)
            if fallback.success:
                return LinuxDriverResult(
                    True,
                    "route-priority fast path fell back to structural rebuild: "
                    + fast_diagnostic,
                )
            return LinuxDriverResult(
                False,
                "route-priority fast path failed: "
                + fast_diagnostic
                + "; structural fallback failed: "
                + str(fallback.diagnostic),
            )

    def materialize_structural(
        self,
        desired: LinuxNetworkDesired,
    ) -> LinuxDriverResult:
        """Full fail-closed rebuild with fresh closed/open verification."""

        try:
            self._close_forwarding()
            for command in desired.prerequisites.apply_commands:
                self._runner.run(command)
            before = self.observe(desired)

            tagged_tables = {
                item.table_id
                for item in before.routing.routes
                if item.protocol
                in {TERMINAL_ROUTE_PROTOCOL, UNICAST_ROUTE_PROTOCOL}
            }
            tables_to_flush = (
                set(desired.routing.verification_tables)
                | tagged_tables
            )
            if tables_to_flush & _RESERVED_TABLE_IDS:
                raise LinuxDriverError(
                    "owned route protocol appears in reserved routing table"
                )

            for rule in before.routing.rules:
                if (
                    FIRST_RULE_PRIORITY
                    <= rule.priority
                    <= MAX_RULE_PRIORITY
                ):
                    self._runner.run(
                        (
                            "ip",
                            "rule",
                            "del",
                            "priority",
                            str(rule.priority),
                        )
                    )

            for table_id in sorted(tables_to_flush):
                self._flush_table(table_id)

            for route in desired.routing.routes:
                self._runner.run(self._route_add_argv(route))

            for rule in desired.routing.dispatch_rules:
                if rule.source_ifname is not None:
                    argv = (
                        "ip",
                        "rule",
                        "add",
                        "priority",
                        str(rule.priority),
                        "iif",
                        rule.source_ifname,
                        "to",
                        rule.destination.with_prefixlen,
                        "lookup",
                        str(rule.table_id),
                    )
                else:
                    assert rule.local_process_uid is not None
                    assert rule.protocol is not None
                    assert rule.bound_output is not None
                    uid = str(rule.local_process_uid)
                    argv = (
                        "ip",
                        "rule",
                        "add",
                        "priority",
                        str(rule.priority),
                        "uidrange",
                        f"{uid}-{uid}",
                        "ipproto",
                        rule.protocol.value,
                        "to",
                        rule.destination.with_prefixlen,
                        "oif",
                        rule.bound_output.ifname,
                        "lookup",
                        str(rule.table_id),
                    )
                self._runner.run(argv)

            terminal_rule = desired.routing.terminal_rule
            if terminal_rule is not None:
                self._runner.run(
                    (
                        "ip",
                        "rule",
                        "add",
                        "priority",
                        str(terminal_rule.priority),
                        "iif",
                        terminal_rule.source_ifname,
                        "type",
                        "unreachable",
                    )
                )

            expected_nft = set()
            if desired.filter is not None:
                expected_nft.add(
                    NftTableIdentity(
                        desired.filter.family,
                        desired.filter.table,
                    )
                )
            if desired.nat is not None:
                expected_nft.add(
                    NftTableIdentity(
                        desired.nat.family,
                        desired.nat.table,
                    )
                )
            for table in before.nft_tables:
                if table not in expected_nft:
                    self._runner.run(
                        (
                            "nft",
                            "delete",
                            "table",
                            table.family,
                            table.name,
                        )
                    )

            self._replace_nft_table(
                desired.nat,
                fallback_table=NAT_TABLE,
            )
            self._replace_nft_table(
                desired.filter,
                fallback_table=FILTER_TABLE,
            )

            closed = self.observe(desired)
            closed_verification = verify_linux_network(
                desired,
                closed,
                expected_ip_forward=False,
            )
            if not closed_verification.ok:
                raise LinuxDriverError(
                    "closed-state verification failed: "
                    + "; ".join(closed_verification.errors)
                )

            if desired.ip_forward_required:
                self._set_ipv4_forwarding(True)

            final = self.observe(desired)
            verification = verify_linux_network(
                desired,
                final,
            )
            if not verification.ok:
                raise LinuxDriverError(
                    "final verification failed: "
                    + "; ".join(verification.errors)
                )

            return LinuxDriverResult(True)

        except Exception as exc:
            diagnostic = str(exc)
            try:
                self._close_forwarding()
            except Exception as close_exc:
                diagnostic += (
                    "; protective forwarding close also failed: "
                    + str(close_exc)
                )
            return LinuxDriverResult(False, diagnostic)

    def _set_ipv4_forwarding(self, enabled: bool) -> None:
        self._runner.run(
            (
                "sysctl",
                "-q",
                "-w",
                "net.ipv4.ip_forward="
                + ("1" if enabled else "0"),
            )
        )

    def _close_forwarding(self) -> None:
        self._set_ipv4_forwarding(False)
        self._runner.run(
            (
                "sysctl",
                "-q",
                "-w",
                "net/ipv6/conf/all/forwarding=0",
            )
        )
        self._runner.run(
            (
                "sysctl",
                "-q",
                "-w",
                "net/ipv6/conf/default/forwarding=0",
            )
        )

    def _observe_forwarding(self) -> bool:
        forward_text = self._runner.run(
            ("sysctl", "-n", "net.ipv4.ip_forward")
        ).stdout.strip()
        if forward_text not in {"0", "1"}:
            raise LinuxDriverError(
                "net.ipv4.ip_forward observation is not 0/1: "
                f"{forward_text!r}"
            )
        return forward_text == "1"

    def _flush_table(self, table_id: int) -> None:
        result = self._runner.run(
            (
                "ip",
                "route",
                "flush",
                "table",
                str(table_id),
            ),
            check=False,
        )
        if result.returncode == 0:
            return
        if "fib table does not exist" in result.stderr.lower():
            return
        raise LinuxDriverError(
            f"cannot flush routing table {table_id}: "
            f"rc={result.returncode} stderr={result.stderr.strip()!r}"
        )

    def _route_add_argv(self, route) -> tuple[str, ...]:
        base = (
            "ip",
            "route",
            "add",
            "table",
            str(route.table_id),
        )

        if route.kind is LinuxRouteKind.BLACKHOLE:
            return (
                *base,
                "blackhole",
                route.destination.with_prefixlen,
                "proto",
                str(route.protocol),
                "metric",
                str(route.metric),
            )

        assert route.path is not None
        return (
            *base,
            route.destination.with_prefixlen,
            "dev",
            route.path.ifname,
            "proto",
            str(route.protocol),
            "metric",
            str(route.metric),
        )

    @staticmethod
    def _route_priority_groups(
        desired: LinuxNetworkDesired,
    ) -> dict[tuple, tuple]:
        grouped: dict[tuple, list] = {}
        for route in desired.routing.routes:
            if route.kind is not LinuxRouteKind.UNICAST:
                continue
            group = (
                route.domain,
                route.table_id,
                route.destination,
                route.protocol,
            )
            grouped.setdefault(group, []).append(route)
        return {
            group: tuple(
                sorted(routes, key=lambda route: route.metric)
            )
            for group, routes in grouped.items()
        }

    def _route_delete_argv(self, route) -> tuple[str, ...]:
        if route.kind is not LinuxRouteKind.UNICAST or route.path is None:
            raise LinuxDriverError(
                "route-priority deletion requires a unicast path route"
            )
        return (
            "ip",
            "route",
            "del",
            "table",
            str(route.table_id),
            route.destination.with_prefixlen,
            "dev",
            route.path.ifname,
            "proto",
            str(route.protocol),
            "metric",
            str(route.metric),
        )

    def _nft_probe(
        self,
        table: str,
    ) -> CommandResult:
        return self._runner.run(
            ("nft", "-j", "-n", "list", "table", "ip", table),
            check=False,
        )

    def _observe_nft_table(
        self,
        desired: NftFilterDesired | NftNatDesired | None,
        *,
        fallback_table: str,
    ) -> NftTableObservation | None:
        table = fallback_table if desired is None else desired.table
        probe = self._nft_probe(table)
        if probe.returncode != 0:
            stderr = probe.stderr.lower()
            if (
                "no such file or directory" in stderr
                or "does not exist" in stderr
            ):
                return None
            raise LinuxDriverError(
                f"cannot observe nft table ip {table}: "
                f"rc={probe.returncode} stderr={probe.stderr.strip()!r}"
            )

        comments = parse_nft_rule_comments(probe.stdout)
        text = self._runner.run(
            ("nft", "-n", "list", "table", "ip", table)
        ).stdout
        identities = (
            ()
            if desired is None
            else desired.interface_identities
        )
        return NftTableObservation(
            canonical=normalize_nft_text(text, identities),
            comments=comments,
        )

    def _replace_nft_table(
        self,
        desired: NftFilterDesired | NftNatDesired | None,
        *,
        fallback_table: str,
    ) -> None:
        table = fallback_table if desired is None else desired.table
        probe = self._nft_probe(table)
        exists = probe.returncode == 0

        if not exists:
            stderr = probe.stderr.lower()
            if not (
                "no such file or directory" in stderr
                or "does not exist" in stderr
            ):
                raise LinuxDriverError(
                    f"cannot inspect nft table ip {table}: "
                    f"rc={probe.returncode} "
                    f"stderr={probe.stderr.strip()!r}"
                )

        if desired is None:
            if exists:
                self._runner.run(
                    ("nft", "delete", "table", "ip", table)
                )
            return

        script = desired.definition
        if exists:
            script = (
                f"delete table ip {table}\n"
                + desired.definition
            )

        self._runner.run(
            ("nft", "-f", "-"),
            input_text=script,
        )
