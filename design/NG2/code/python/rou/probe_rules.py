from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from ipaddress import IPv4Address, IPv4Network

from .availability_routing import AvailabilityWindowPolicy
from .interface_identity import InterfaceIdentity
from .network_rules import (
    DispatchRuleSpec,
    FlowInitiationAllowSpec,
    IcmpType,
    NetworkEndpoint,
    NetworkRulesSpec,
    RoutingDomainSpec,
    TerminalDisposition,
    TrafficAllowSpec,
    TrafficPredicate,
    TrafficProtocol,
    TrafficSelector,
)


LOCAL_PROCESS = NetworkEndpoint.local_process()


class ProbeMechanism(str, Enum):
    ICMP = "icmp"


@dataclass(frozen=True)
class AvailabilityProbeRequest:
    probe_id: str
    path: InterfaceIdentity
    target: IPv4Address
    mechanism: ProbeMechanism = ProbeMechanism.ICMP
    enabled: bool = True
    policy: AvailabilityWindowPolicy = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.probe_id:
            raise ValueError("probe_id must be non-empty")
        if not isinstance(self.path, InterfaceIdentity):
            raise ValueError("probe path must be an InterfaceIdentity")
        if not isinstance(self.target, IPv4Address):
            raise ValueError("probe target must be an IPv4Address")
        if not isinstance(self.mechanism, ProbeMechanism):
            raise ValueError("probe mechanism must be a ProbeMechanism")
        if type(self.enabled) is not bool:
            raise ValueError("probe enabled must be boolean")
        if not isinstance(self.policy, AvailabilityWindowPolicy):
            raise ValueError(
                "probe policy must be AvailabilityWindowPolicy"
            )


@dataclass(frozen=True)
class AvailabilityProbeSetRequest:
    probes: tuple[AvailabilityProbeRequest, ...]

    def __post_init__(self) -> None:
        ids = [item.probe_id for item in self.probes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate probe_id")


def availability_probe_sets_semantically_equal(
    left: AvailabilityProbeSetRequest,
    right: AvailabilityProbeSetRequest,
) -> bool:
    """Compare logical probe-set snapshots independent of tuple ordering."""

    if not isinstance(left, AvailabilityProbeSetRequest):
        raise ValueError("left probe set must be AvailabilityProbeSetRequest")
    if not isinstance(right, AvailabilityProbeSetRequest):
        raise ValueError("right probe set must be AvailabilityProbeSetRequest")

    return {
        item.probe_id: item
        for item in left.probes
    } == {
        item.probe_id: item
        for item in right.probes
    }


class ProbeRulesCalculator:
    """Translate explicit active-probe intent into common NetworkRules semantics."""

    def calculate(
        self,
        request: AvailabilityProbeSetRequest,
    ) -> NetworkRulesSpec:
        routing_domains: list[RoutingDomainSpec] = []
        dispatch_rules: list[DispatchRuleSpec] = []
        traffic_allows: list[TrafficAllowSpec] = []
        flow_allows: list[FlowInitiationAllowSpec] = []

        planes = {
            (
                probe.mechanism,
                probe.path,
                probe.target,
            )
            for probe in request.probes
        }

        for mechanism, identity, target_address in sorted(
            planes,
            key=lambda item: (
                item[0].value,
                item[1].ifname,
                item[1].ifindex,
                int(item[2]),
            ),
        ):
            if mechanism is not ProbeMechanism.ICMP:
                raise ValueError(
                    f"unsupported probe mechanism {mechanism!r}"
                )

            target = IPv4Network(f"{target_address}/32")
            path = NetworkEndpoint.interface_path(identity)
            domain_name = (
                f"probe:{mechanism.value}:"
                f"{identity.ifname}:{identity.ifindex}:"
                f"{target_address}"
            )

            routing_domains.append(
                RoutingDomainSpec(
                    name=domain_name,
                    destinations=(target,),
                    ordered_paths=(identity,),
                    terminal_disposition=TerminalDisposition.DROP,
                )
            )
            dispatch_rules.append(
                DispatchRuleSpec(
                    destination=target,
                    routing_domain=domain_name,
                    source=LOCAL_PROCESS,
                    bound_output=path,
                    protocol=TrafficProtocol.ICMP,
                )
            )

            request_predicate = TrafficPredicate.match(
                TrafficSelector(
                    destination=target,
                    protocol=TrafficProtocol.ICMP,
                    icmp_types=(IcmpType.ECHO_REQUEST,),
                )
            )
            reply_predicate = TrafficPredicate.match(
                TrafficSelector(
                    source=target,
                    protocol=TrafficProtocol.ICMP,
                    icmp_types=(IcmpType.ECHO_REPLY,),
                )
            )

            traffic_allows.extend(
                (
                    TrafficAllowSpec(
                        LOCAL_PROCESS,
                        path,
                        request_predicate,
                    ),
                    TrafficAllowSpec(
                        path,
                        LOCAL_PROCESS,
                        reply_predicate,
                    ),
                )
            )
            flow_allows.append(
                FlowInitiationAllowSpec(
                    LOCAL_PROCESS,
                    path,
                    request_predicate,
                )
            )

        return NetworkRulesSpec(
            routing_domains=tuple(routing_domains),
            dispatch_rules=tuple(dispatch_rules),
            traffic_allows=tuple(traffic_allows),
            flow_initiation_allows=tuple(flow_allows),
        )
