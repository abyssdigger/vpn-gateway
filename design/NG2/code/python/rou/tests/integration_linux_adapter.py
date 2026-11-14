from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.interface_identity import InterfaceIdentity
from rou.linux_driver import (
    CommandResult,
    LinuxNetworkExecutor,
    NetworkNamespaceLinuxRunner,
)
from rou.runtime_bootstrap import bootstrap_linux_network_rules_adapter
from rou.network_rules import (
    DispatchRuleSpec,
    FlowInitiationAllowSpec,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    SourceNatSpec,
    SourceNatTarget,
    StateKnowledge,
    TerminalDisposition,
    TrafficAllowSpec,
    TrafficPredicate,
    TrafficSelector,
)
from ipaddress import IPv4Network


NS = "vpng2-adapter-ci"
DEST = IPv4Network("198.51.100.0/24")
DEST2 = IPv4Network("203.0.113.0/24")
DEST3 = IPv4Network("192.0.2.0/24")


def host(*argv: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        argv,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


class RecordingHostRunner:
    def __init__(self):
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append(argv)
        completed = host(
            *argv,
            check=False,
            input_text=input_text,
        )
        result = CommandResult(
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"host command failed rc={result.returncode}: "
                f"{argv!r}: {result.stderr.strip()}"
            )
        return result


def cleanup():
    host("ip", "netns", "del", NS, check=False)


def make_namespace():
    cleanup()
    host("ip", "netns", "add", NS)
    host("ip", "-n", NS, "link", "set", "lo", "up")
    for name in ("host0", "vpns00", "vpns01"):
        host("ip", "-n", NS, "link", "add", name, "type", "dummy")
        host("ip", "-n", NS, "link", "set", name, "up")


def identity(name: str) -> InterfaceIdentity:
    raw = host(
        "ip", "-n", NS, "-j", "link", "show", "dev", name
    ).stdout
    item = json.loads(raw)[0]
    return InterfaceIdentity(item["ifname"], item["ifindex"])


def spec(
    path_identity: InterfaceIdentity,
    destination_network: IPv4Network = DEST,
) -> NetworkRulesSpec:
    local = NetworkEndpoint.local_network()
    path = NetworkEndpoint.interface_path(path_identity)
    destination = TrafficPredicate.match(
        TrafficSelector(destination=destination_network)
    )
    return NetworkRulesSpec(
        routing_domains=(
            RoutingDomainSpec(
                "corp",
                (destination_network,),
                (path_identity,),
                TerminalDisposition.DROP,
            ),
        ),
        dispatch_rules=(
            DispatchRuleSpec(
                destination_network,
                "corp",
                source=local,
            ),
        ),
        traffic_allows=(
            TrafficAllowSpec(local, path, destination),
            TrafficAllowSpec(
                path,
                local,
                TrafficPredicate.match(
                    TrafficSelector(source=destination_network)
                ),
            ),
        ),
        flow_initiation_allows=(
            FlowInitiationAllowSpec(local, path, destination),
        ),
        source_nat=(
            SourceNatSpec(
                source=local,
                egress=path,
                predicate=destination,
                target=SourceNatTarget.EGRESS_ADDRESS,
            ),
        ),
    )


def priority_spec(
    ordered_paths: tuple[InterfaceIdentity, ...],
) -> NetworkRulesSpec:
    local = NetworkEndpoint.local_network()
    destination = TrafficPredicate.match(
        TrafficSelector(destination=DEST3)
    )
    policy_paths = tuple(
        sorted(
            ordered_paths,
            key=lambda identity: (
                identity.ifname,
                identity.ifindex,
            ),
        )
    )
    traffic = []
    flows = []
    for identity in policy_paths:
        path = NetworkEndpoint.interface_path(identity)
        traffic.append(
            TrafficAllowSpec(local, path, destination)
        )
        flows.append(
            FlowInitiationAllowSpec(local, path, destination)
        )

    return NetworkRulesSpec(
        routing_domains=(
            RoutingDomainSpec(
                "priority-test",
                (DEST3,),
                ordered_paths,
                TerminalDisposition.DROP,
                priority_prefix_length=len(ordered_paths),
            ),
        ),
        dispatch_rules=(
            DispatchRuleSpec(
                DEST3,
                "priority-test",
                source=local,
            ),
        ),
        traffic_allows=tuple(traffic),
        flow_initiation_allows=tuple(flows),
    )


def routing_only_spec(
    path_identity: InterfaceIdentity,
    destination_network: IPv4Network,
) -> NetworkRulesSpec:
    local = NetworkEndpoint.local_network()
    return NetworkRulesSpec(
        routing_domains=(
            RoutingDomainSpec(
                "default",
                (destination_network,),
                (path_identity,),
                TerminalDisposition.DROP,
            ),
        ),
        dispatch_rules=(
            DispatchRuleSpec(
                destination_network,
                "default",
                source=local,
            ),
        ),
    )


def tagged_routes():
    return json.loads(
        host(
            "ip",
            "netns",
            "exec",
            NS,
            "ip",
            "-j",
            "-4",
            "route",
            "show",
            "table",
            "all",
        ).stdout
    )


def owned_rules():
    return json.loads(
        host(
            "ip",
            "netns",
            "exec",
            NS,
            "ip",
            "-j",
            "-4",
            "rule",
            "show",
        ).stdout
    )


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    make_namespace()
    host_runner = RecordingHostRunner()
    runner = NetworkNamespaceLinuxRunner(host_runner, NS)
    driver = LinuxNetworkExecutor(runner)

    # Simulate process restart with stale physical policy and forwarding still open.
    host(
        "ip", "netns", "exec", NS,
        "sysctl", "-q", "-w", "net.ipv4.ip_forward=1",
    )
    host(
        "ip", "netns", "exec", NS,
        "sysctl", "-q", "-w", "net/ipv6/conf/all/forwarding=1",
    )
    host(
        "ip", "netns", "exec", NS,
        "sysctl", "-q", "-w", "net/ipv6/conf/default/forwarding=1",
    )
    host(
        "ip", "netns", "exec", NS,
        "nft", "add", "table", "inet", "stale_before_bootstrap",
    )

    bootstrapped = bootstrap_linux_network_rules_adapter(
        driver,
        local_interface="host0",
    )
    if not bootstrapped.success or bootstrapped.adapter is None:
        raise RuntimeError(
            "runtime bootstrap failed: "
            f"{bootstrapped.diagnostic}"
        )
    adapter = bootstrapped.adapter

    forward = host(
        "ip", "netns", "exec", NS,
        "sysctl", "-n", "net.ipv4.ip_forward",
    ).stdout.strip()
    if forward != "0":
        raise RuntimeError(
            f"bootstrap exposed Adapter with ip_forward={forward!r}"
        )
    for key in (
        "net.ipv6.conf.all.forwarding",
        "net.ipv6.conf.default.forwarding",
    ):
        value = host(
            "ip", "netns", "exec", NS,
            "sysctl", "-n", key,
        ).stdout.strip()
        if value != "0":
            raise RuntimeError(
                f"bootstrap exposed Adapter with {key}={value!r}"
            )
    nft_tables = host(
        "ip", "netns", "exec", NS, "nft", "list", "tables"
    ).stdout
    if "stale_before_bootstrap" not in nft_tables:
        raise RuntimeError(
            "bootstrap unexpectedly mutated stale policy before owner reconcile"
        )
    print("PASS BOOT: stale restart state is dual-stack closed before Adapter publication")

    owner = object()
    owner2 = object()

    try:
        old = identity("vpns00")
        wanted = spec(old)
        applied = adapter.apply(owner, wanted)
        if not applied.success:
            raise RuntimeError(f"initial apply failed: {applied.diagnostic}")

        state = adapter.get_last_state(owner)
        if (
            state.knowledge is not StateKnowledge.KNOWN
            or not state.fresh
            or state.rules != wanted
        ):
            raise RuntimeError(f"initial Adapter state is not fresh KNOWN: {state}")

        forward = host(
            "ip", "netns", "exec", NS,
            "sysctl", "-n", "net.ipv4.ip_forward"
        ).stdout.strip()
        if forward != "1":
            raise RuntimeError(f"ip_forward after apply is {forward!r}")

        nft_tables = host(
            "ip", "netns", "exec", NS, "nft", "list", "tables"
        ).stdout
        if "vpng2_filter" not in nft_tables or "vpng2_nat" not in nft_tables:
            raise RuntimeError("owned nft tables are missing")
        if "stale_before_bootstrap" in nft_tables:
            raise RuntimeError(
                "first Adapter reconcile did not remove stale nft policy"
            )

        expected_sysctls = {
            "net.ipv4.conf.all.rp_filter": "0",
            "net.ipv4.conf.default.rp_filter": "0",
            "net.ipv4.conf.host0.rp_filter": "0",
            "net.ipv4.conf.vpns00.rp_filter": "0",
            "net.ipv6.conf.all.forwarding": "0",
            "net.ipv6.conf.default.forwarding": "0",
            "net.ipv6.conf.default.disable_ipv6": "1",
            "net.ipv6.conf.host0.disable_ipv6": "1",
            "net.ipv6.conf.vpns00.disable_ipv6": "1",
        }
        for key, expected in expected_sysctls.items():
            actual = host(
                "ip", "netns", "exec", NS,
                "sysctl", "-n", key,
            ).stdout.strip()
            if actual != expected:
                raise RuntimeError(
                    f"namespace prerequisite {key}={actual!r}, expected {expected!r}"
                )
        print("PASS A0: IPv4-only namespace prerequisites verify live")

        rules = owned_rules()
        terminal = [
            item for item in rules
            if item.get("priority") == 2
            and item.get("action") == "unreachable"
            and item.get("iif") == "host0"
        ]
        if not terminal:
            raise RuntimeError("terminal host0 RPDB fail-close is missing")

        if not adapter.renew_state(owner).success:
            raise RuntimeError("fresh exact renew failed after initial apply")
        print(f"PASS A: exact apply/verify ifindex={old.ifindex}")

        wanted2 = spec(old, DEST2)
        second_applied = adapter.apply(owner2, wanted2)
        if not second_applied.success:
            raise RuntimeError(
                f"second owner apply failed: {second_applied.diagnostic}"
            )
        if adapter.get_last_state(owner2).rules != wanted2:
            raise RuntimeError("second owner did not receive exact fresh state")
        print("PASS A2: second owner shares generation with owner-scoped domain")

        # A pure path-priority permutation must use the narrow route-only path.
        priority_owner = object()
        alternate = identity("vpns01")
        priority_initial = priority_spec((old, alternate))
        priority_applied = adapter.apply(priority_owner, priority_initial)
        if not priority_applied.success:
            raise RuntimeError(
                "priority-test initial apply failed: "
                f"{priority_applied.diagnostic}"
            )

        priority_reordered = priority_spec((alternate, old))
        host_runner.calls.clear()
        priority_changed = adapter.apply(
            priority_owner,
            priority_reordered,
        )
        if not priority_changed.success:
            raise RuntimeError(
                "priority-test reorder failed: "
                f"{priority_changed.diagnostic}"
            )

        inner_calls = [
            argv[4:]
            for argv in host_runner.calls
            if argv[:4] == ("ip", "netns", "exec", NS)
        ]
        forwarding_writes = [
            argv
            for argv in inner_calls
            if argv[:3] == ("sysctl", "-q", "-w")
            and argv[-1].startswith("net.ipv4.ip_forward=")
        ]
        if forwarding_writes:
            raise RuntimeError(
                "route-priority fast path touched forwarding barrier: "
                f"{forwarding_writes}; diagnostic={priority_changed.diagnostic!r}"
            )

        route_adds = [
            argv
            for argv in inner_calls
            if argv[:3] == ("ip", "route", "add")
        ]
        route_deletes = [
            argv
            for argv in inner_calls
            if argv[:3] == ("ip", "route", "del")
        ]
        if len(route_adds) != 3 or len(route_deletes) != 3:
            raise RuntimeError(
                "route-priority fast path did not perform three "
                "duplicate/delete moves: "
                f"adds={route_adds} deletes={route_deletes}"
            )

        nft_mutations = [
            argv
            for argv in inner_calls
            if (
                argv[:3] == ("nft", "-f", "-")
                or argv[:3] == ("nft", "delete", "table")
            )
        ]
        if nft_mutations:
            raise RuntimeError(
                "route-priority fast path mutated nft policy: "
                f"{nft_mutations}"
            )

        priority_routes = {
            item.get("metric"): item.get("dev")
            for item in tagged_routes()
            if item.get("protocol") in (202, "202")
            and item.get("dst") == DEST3.with_prefixlen
        }
        if priority_routes != {
            10: "vpns01",
            20: "vpns00",
        }:
            raise RuntimeError(
                "route-priority fast path produced wrong metric order: "
                f"{priority_routes}"
            )
        if adapter.get_last_state(priority_owner).rules != priority_reordered:
            raise RuntimeError(
                "route-priority fast path did not commit reordered owner state"
            )
        print(
            "PASS A3: pure path reorder used verified route-only fast path "
            "without forwarding or nft mutation"
        )

        if not adapter.cleanup(priority_owner).success:
            raise RuntimeError("priority-test owner cleanup failed")

        # Same-name/new-ifindex must invalidate the old generation.
        host("ip", "-n", NS, "link", "del", "vpns00")
        host("ip", "-n", NS, "link", "add", "vpns00", "type", "dummy")
        host("ip", "-n", NS, "link", "set", "vpns00", "up")
        new = identity("vpns00")
        if new.ifindex == old.ifindex:
            raise RuntimeError("same-name replacement reused old ifindex")

        renewed = adapter.renew_state(owner)
        if renewed.success:
            raise RuntimeError("same-name/new-ifindex was not detected as drift")
        if adapter.get_last_state(owner).knowledge is not StateKnowledge.UNKNOWN:
            raise RuntimeError("generation drift did not make state UNKNOWN")
        print(
            "PASS B: same-name/new-ifindex detected "
            f"old={old.ifindex} new={new.ifindex}"
        )

        wanted = spec(new)
        repaired = adapter.apply(owner, wanted)
        if not repaired.success:
            raise RuntimeError(
                f"fresh-generation apply failed: {repaired.diagnostic}"
            )

        projected_second = adapter.get_last_state(owner2)
        if (
            projected_second.knowledge is not StateKnowledge.KNOWN
            or projected_second.rules is None
            or projected_second.rules.routing_domains[0].ordered_paths
        ):
            raise RuntimeError(
                "stale second owner was not projected to KNOWN zero-path state: "
                f"{projected_second}"
            )

        wanted2 = spec(new, DEST2)
        second_repaired = adapter.apply(owner2, wanted2)
        if not second_repaired.success:
            raise RuntimeError(
                "second owner fresh-generation apply failed: "
                f"{second_repaired.diagnostic}"
            )
        if adapter.get_last_state(owner).rules != wanted:
            raise RuntimeError("second owner update disturbed first owner")
        print(
            "PASS C: sequential multi-owner generation update converged "
            "without deadlock"
        )

        # Remove the normal route and prove renew detects it, then structural apply repairs.
        route = next(
            item for item in tagged_routes()
            if item.get("protocol") in (202, "202")
            and item.get("dst") == DEST.with_prefixlen
        )
        table = str(route["table"])
        host(
            "ip", "netns", "exec", NS,
            "ip", "route", "del", "table", table,
            DEST.with_prefixlen, "dev", "vpns00",
            "metric", "10",
        )
        host(
            "ip", "netns", "exec", NS,
            "nft", "add", "table", "inet", "foreign_ci",
        )
        host(
            "ip", "netns", "exec", NS,
            "sysctl", "-q", "-w", "net/ipv4/conf/vpns00/rp_filter=1",
        )
        if adapter.renew_state(owner).success:
            raise RuntimeError(
                "route/foreign-nft drift was not detected"
            )

        host_runner.calls.clear()
        repaired = adapter.apply(owner, wanted)
        if not repaired.success:
            raise RuntimeError(f"route drift repair failed: {repaired.diagnostic}")
        forwarding_writes = [
            argv[-1]
            for argv in host_runner.calls
            if argv[:7]
            == (
                "ip",
                "netns",
                "exec",
                NS,
                "sysctl",
                "-q",
                "-w",
            )
        ]
        if not forwarding_writes or forwarding_writes[0] != "net.ipv4.ip_forward=0":
            raise RuntimeError(
                f"repair did not close barrier first: {forwarding_writes}"
            )
        if forwarding_writes[-1] != "net.ipv4.ip_forward=1":
            raise RuntimeError(
                f"repair did not reopen after verification: {forwarding_writes}"
            )
        nft_tables = host(
            "ip", "netns", "exec", NS, "nft", "list", "tables"
        ).stdout
        if "foreign_ci" in nft_tables:
            raise RuntimeError("structural repair left foreign nft table")
        rp_filter = host(
            "ip", "netns", "exec", NS,
            "sysctl", "-n", "net/ipv4/conf/vpns00/rp_filter",
        ).stdout.strip()
        if rp_filter != "0":
            raise RuntimeError(
                f"structural repair left vpns00 rp_filter={rp_filter!r}"
            )
        print(
            "PASS D: route + foreign-nft + sysctl drift repaired behind "
            "forwarding barrier"
        )

        default_owner = object()
        default_spec = routing_only_spec(
            new,
            IPv4Network("0.0.0.0/0"),
        )
        default_applied = adapter.apply(default_owner, default_spec)
        if not default_applied.success:
            raise RuntimeError(
                f"default-route owner apply failed: {default_applied.diagnostic}"
            )
        if not adapter.renew_state(default_owner).success:
            raise RuntimeError("default-route owner exact renew failed")

        by_table = {}
        for item in tagged_routes():
            if item.get("dst") not in (None, "default"):
                continue
            by_table.setdefault(str(item.get("table")), []).append(item)
        if not any(
            any(route.get("protocol") in (202, "202") for route in routes)
            and any(route.get("protocol") in (201, "201") for route in routes)
            for routes in by_table.values()
        ):
            raise RuntimeError(
                "no routing table contains both unicast default and terminal "
                "blackhole default"
            )
        print("PASS D2: /0 dispatch and dual default routes verify in live kernel")

        if not adapter.cleanup(default_owner).success:
            raise RuntimeError("default-route owner cleanup failed")

        cleaned = adapter.cleanup(owner)
        if not cleaned.success:
            raise RuntimeError(f"first owner cleanup failed: {cleaned.diagnostic}")

        forward = host(
            "ip", "netns", "exec", NS,
            "sysctl", "-n", "net.ipv4.ip_forward"
        ).stdout.strip()
        if forward != "1":
            raise RuntimeError(
                "first owner cleanup did not preserve surviving owner forwarding"
            )
        if adapter.get_last_state(owner2).rules != wanted2:
            raise RuntimeError("first owner cleanup disturbed surviving owner")

        cleaned2 = adapter.cleanup(owner2)
        if not cleaned2.success:
            raise RuntimeError(f"second owner cleanup failed: {cleaned2.diagnostic}")

        forward = host(
            "ip", "netns", "exec", NS,
            "sysctl", "-n", "net.ipv4.ip_forward"
        ).stdout.strip()
        if forward != "0":
            raise RuntimeError(f"final cleanup left ip_forward={forward}")

        nft_tables = host(
            "ip", "netns", "exec", NS, "nft", "list", "tables"
        ).stdout
        if "vpng2_filter" in nft_tables or "vpng2_nat" in nft_tables:
            raise RuntimeError("final cleanup left owned nft table")

        stale_routes = [
            item for item in tagged_routes()
            if item.get("protocol") in (201, 202, "201", "202")
        ]
        if stale_routes:
            raise RuntimeError(f"cleanup left tagged routes: {stale_routes}")

        stale_rules = [
            item for item in owned_rules()
            if 1 <= item.get("priority", -1) <= 32765
        ]
        if stale_rules:
            raise RuntimeError(f"cleanup left owned RPDB rules: {stale_rules}")

        print(
            "PASS E: per-owner cleanup preserved survivor, final cleanup "
            "removed owned state"
        )
        print("NG2_LINUX_ADAPTER_INTEGRATION=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
