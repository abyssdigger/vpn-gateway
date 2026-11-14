from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Protocol

from .linux_network import LinuxNetworkDesired
from .linux_nft import (
    FILTER_TABLE,
    NAT_TABLE,
    NftFilterDesired,
    NftNatDesired,
    NftTableObservation,
    normalize_nft_text,
    parse_nft_rule_comments,
    verify_nft_table,
)
from .linux_observation import (
    LinuxRoutingObservation,
    parse_link_json,
    parse_route_json,
    parse_rule_json,
    verify_linux_routing,
)
from .linux_routing import (
    FIRST_RULE_PRIORITY,
    MAX_RULE_PRIORITY,
    RT_TABLE_COMPAT,
    RT_TABLE_DEFAULT,
    RT_TABLE_LOCAL,
    RT_TABLE_MAIN,
    RT_TABLE_UNSPEC,
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


@dataclass(frozen=True)
class LinuxNetworkObservation:
    routing: LinuxRoutingObservation
    filter: NftTableObservation | None
    nat: NftTableObservation | None


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
) -> LinuxNetworkVerification:
    errors: list[str] = []

    routing = verify_linux_routing(
        desired.routing,
        observed.routing,
        expected_ip_forward=desired.ip_forward_required,
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

    return LinuxNetworkVerification(
        ok=not errors,
        errors=tuple(errors),
    )


class LinuxNetworkDriver:
    """Concrete structural Linux materializer for one dedicated ROU namespace."""

    def __init__(self, runner: LinuxCommandRunner) -> None:
        self._runner = runner

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

        forward_text = self._runner.run(
            ("sysctl", "-n", "net.ipv4.ip_forward")
        ).stdout.strip()
        if forward_text not in {"0", "1"}:
            raise LinuxDriverError(
                "net.ipv4.ip_forward observation is not 0/1: "
                f"{forward_text!r}"
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
            routing=LinuxRoutingObservation(
                interfaces=interfaces,
                routes=routes,
                rules=rules,
                ip_forward=forward_text == "1",
            ),
            filter=nft_filter,
            nat=nft_nat,
        )

    def verify_current(
        self,
        desired: LinuxNetworkDesired,
    ) -> LinuxNetworkVerification:
        return verify_linux_network(
            desired,
            self.observe(desired),
        )

    def materialize_structural(
        self,
        desired: LinuxNetworkDesired,
    ) -> LinuxDriverResult:
        """Full fail-closed rebuild with fresh closed/open verification."""

        try:
            self._set_forwarding(False)
            before = self.observe(desired)

            tagged_tables = {
                item.table_id
                for item in before.routing.routes
                if item.protocol in {201, 202}
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
                self._runner.run(
                    (
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
            closed_verification = self._verify_closed(
                desired,
                closed,
            )
            if not closed_verification.ok:
                raise LinuxDriverError(
                    "closed-state verification failed: "
                    + "; ".join(closed_verification.errors)
                )

            if desired.ip_forward_required:
                self._set_forwarding(True)

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
                self._set_forwarding(False)
            except Exception as close_exc:
                diagnostic += (
                    "; protective forwarding close also failed: "
                    + str(close_exc)
                )
            return LinuxDriverResult(False, diagnostic)

    def _verify_closed(
        self,
        desired: LinuxNetworkDesired,
        observed: LinuxNetworkObservation,
    ) -> LinuxNetworkVerification:
        closed_routing = verify_linux_routing(
            desired.routing,
            observed.routing,
            expected_ip_forward=False,
        )
        errors = list(closed_routing.errors)

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

        return LinuxNetworkVerification(
            not errors,
            tuple(errors),
        )

    def _set_forwarding(self, enabled: bool) -> None:
        self._runner.run(
            (
                "sysctl",
                "-q",
                "-w",
                "net.ipv4.ip_forward="
                + ("1" if enabled else "0"),
            )
        )

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
