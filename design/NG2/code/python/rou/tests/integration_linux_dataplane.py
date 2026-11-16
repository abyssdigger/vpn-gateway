from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ipaddress import IPv4Network

from rou.interface_identity import InterfaceIdentity
from rou.linux_adapter import LinuxNetworkRulesAdapter
from rou.linux_driver import CommandResult, LinuxNetworkDriver
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


ROU = "vpng2-dp-rou"
SRC = "vpng2-dp-src"
DST = "vpng2-dp-dst"

LOCAL_NET = IPv4Network("192.0.2.0/30")
REMOTE_NET = IPv4Network("198.51.100.0/30")


def run(*argv: str, check: bool = True, input_text: str | None = None):
    return subprocess.run(
        argv,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def cleanup():
    for namespace in (SRC, DST, ROU):
        run("ip", "netns", "del", namespace, check=False)


class RouRunner:
    def run(self, argv, *, input_text=None, check=True):
        completed = run(
            "ip", "netns", "exec", ROU, *argv,
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
                f"ROU command failed rc={result.returncode}: {argv!r}: "
                f"{result.stderr.strip()}"
            )
        return result


def setup():
    cleanup()
    for namespace in (ROU, SRC, DST):
        run("ip", "netns", "add", namespace)
        run("ip", "-n", namespace, "link", "set", "lo", "up")

    run(
        "ip", "-n", SRC, "link", "add", "src0", "type", "veth",
        "peer", "name", "host0", "netns", ROU,
    )
    run(
        "ip", "-n", DST, "link", "add", "dst0", "type", "veth",
        "peer", "name", "vpns00", "netns", ROU,
    )

    run("ip", "-n", SRC, "addr", "add", "192.0.2.1/30", "dev", "src0")
    run("ip", "-n", ROU, "addr", "add", "192.0.2.2/30", "dev", "host0")
    run("ip", "-n", ROU, "addr", "add", "198.51.100.1/30", "dev", "vpns00")
    run("ip", "-n", DST, "addr", "add", "198.51.100.2/30", "dev", "dst0")

    for namespace, interface in (
        (SRC, "src0"),
        (ROU, "host0"),
        (ROU, "vpns00"),
        (DST, "dst0"),
    ):
        run("ip", "-n", namespace, "link", "set", interface, "up")

    run(
        "ip", "-n", SRC, "route", "add", REMOTE_NET.with_prefixlen,
        "via", "192.0.2.2",
    )
    run(
        "ip", "-n", DST, "route", "add", LOCAL_NET.with_prefixlen,
        "via", "198.51.100.1",
    )


def vpn_identity() -> InterfaceIdentity:
    raw = run(
        "ip", "-n", ROU, "-j", "link", "show", "dev", "vpns00"
    ).stdout
    item = json.loads(raw)[0]
    return InterfaceIdentity(item["ifname"], item["ifindex"])


def policy(
    identity: InterfaceIdentity,
    *,
    allow_remote_new: bool,
    masquerade: bool = False,
) -> NetworkRulesSpec:
    local = NetworkEndpoint.local_network()
    path = NetworkEndpoint.interface_path(identity)

    to_remote = TrafficPredicate.match(
        TrafficSelector(destination=REMOTE_NET)
    )
    from_remote = TrafficPredicate.match(
        TrafficSelector(source=REMOTE_NET)
    )

    flow_rules = [
        FlowInitiationAllowSpec(local, path, to_remote),
    ]
    if allow_remote_new:
        flow_rules.append(
            FlowInitiationAllowSpec(path, local, from_remote)
        )

    source_nat = (
        (
            SourceNatSpec(
                source=local,
                egress=path,
                predicate=to_remote,
                target=SourceNatTarget.EGRESS_ADDRESS,
            ),
        )
        if masquerade
        else ()
    )

    return NetworkRulesSpec(
        routing_domains=(
            RoutingDomainSpec(
                "corp",
                (REMOTE_NET,),
                (identity,),
                TerminalDisposition.DROP,
            ),
        ),
        dispatch_rules=(
            DispatchRuleSpec(
                REMOTE_NET,
                "corp",
                source=local,
            ),
        ),
        traffic_allows=(
            TrafficAllowSpec(local, path, to_remote),
            TrafficAllowSpec(path, local, from_remote),
        ),
        flow_initiation_allows=tuple(flow_rules),
        source_nat=source_nat,
    )


def ping(namespace: str, target: str) -> bool:
    completed = run(
        "ip", "netns", "exec", namespace,
        "ping", "-c", "1", "-W", "1", target,
        check=False,
    )
    return completed.returncode == 0


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    setup()
    owner = object()
    adapter = LinuxNetworkRulesAdapter(
        LinuxNetworkDriver(RouRunner()),
        local_interface="host0",
    )

    try:
        identity = vpn_identity()

        outbound = policy(identity, allow_remote_new=False)
        result = adapter.apply(owner, outbound)
        if not result.success:
            raise RuntimeError(f"outbound apply failed: {result.diagnostic}")
        if adapter.get_last_state(owner).knowledge is not StateKnowledge.KNOWN:
            raise RuntimeError("outbound state is not KNOWN")

        if not ping(SRC, "198.51.100.2"):
            raise RuntimeError(
                "local-initiated ping failed through OUTBOUND policy"
            )
        print("PASS A: local-initiated NEW and return ESTABLISHED traffic pass")

        # Flush conntrack in the ROU namespace if conntrack is present. A new ICMP echo
        # tuple is distinct anyway; this is only defensive against runner reuse.
        run(
            "ip", "netns", "exec", ROU,
            "conntrack", "-F",
            check=False,
        )
        if ping(DST, "192.0.2.1"):
            raise RuntimeError(
                "remote-initiated NEW escaped OUTBOUND flow policy"
            )
        print("PASS B: remote-initiated NEW is blocked")

        bidirectional = policy(identity, allow_remote_new=True)
        result = adapter.apply(owner, bidirectional)
        if not result.success:
            raise RuntimeError(
                f"bidirectional apply failed: {result.diagnostic}"
            )

        if not ping(DST, "192.0.2.1"):
            raise RuntimeError(
                "remote-initiated NEW did not pass after reverse flow allow"
            )
        print("PASS C: reverse flow-initiation allow enables remote NEW")

        # Remove the remote return route. Without source NAT the remote peer cannot
        # route 192.0.2.0/30; MASQUERADE must make the local-initiated flow work anyway.
        run(
            "ip", "-n", DST, "route", "del", LOCAL_NET.with_prefixlen,
            "via", "198.51.100.1",
        )
        nat_policy = policy(
            identity,
            allow_remote_new=False,
            masquerade=True,
        )
        result = adapter.apply(owner, nat_policy)
        if not result.success:
            raise RuntimeError(f"NAT apply failed: {result.diagnostic}")
        run(
            "ip", "netns", "exec", ROU,
            "conntrack", "-F",
            check=False,
        )
        if not ping(SRC, "198.51.100.2"):
            raise RuntimeError(
                "MASQUERADE did not preserve local-initiated flow "
                "without remote return route"
            )
        print("PASS D: semantic EGRESS_ADDRESS NAT works on live dataplane")

        result = adapter.cleanup(owner)
        if not result.success:
            raise RuntimeError(f"cleanup failed: {result.diagnostic}")

        if ping(SRC, "198.51.100.2"):
            raise RuntimeError("payload forwarding survived Adapter cleanup")
        print("PASS E: cleanup closes payload forwarding")

        print("NG2_LINUX_DATAPLANE_INTEGRATION=PASS")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
