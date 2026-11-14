from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network

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

    def __post_init__(self) -> None:
        if not self.probe_id:
            raise ValueError("probe_id must be non-empty")


@dataclass(frozen=True)
class AvailabilityProbeSetRequest:
    probes: tuple[AvailabilityProbeRequest, ...]

    def __post_init__(self) -> None:
        ids = [item.probe_id for item in self.probes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate probe_id")


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

        for probe in request.probes:
            if probe.mechanism is not ProbeMechanism.ICMP:
                raise ValueError(
                    f"unsupported probe mechanism {probe.mechanism!r}"
                )

            target = IPv4Network(f"{probe.target}/32")
            path = NetworkEndpoint.interface_path(probe.path)

            routing_domains.append(
                RoutingDomainSpec(
                    name=probe.probe_id,
                    destinations=(target,),
                    ordered_paths=(probe.path,),
                    terminal_disposition=TerminalDisposition.DROP,
                )
            )
            dispatch_rules.append(
                DispatchRuleSpec(
                    destination=target,
                    routing_domain=probe.probe_id,
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
