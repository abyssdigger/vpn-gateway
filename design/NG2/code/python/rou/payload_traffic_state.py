from __future__ import annotations

from dataclasses import dataclass

from .interface_identity import InterfaceIdentity
from .network_rules import NetworkRulesSpec, NetworkRulesState, StateKnowledge
from .payload_rules_state import Knowledge, PayloadRulesState


@dataclass(frozen=True)
class PayloadProfileTrafficState:
    profile_name: str
    observed_paths: tuple[InterfaceIdentity, ...] | None

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise ValueError("payload profile state name must be non-empty")


@dataclass(frozen=True)
class PayloadTrafficStateInfo:
    rules_state: PayloadRulesState
    profiles: tuple[PayloadProfileTrafficState, ...]

    def __post_init__(self) -> None:
        names = [item.profile_name for item in self.profiles]
        if len(set(names)) != len(names):
            raise ValueError("duplicate profile in payload traffic state")

        if self.rules_state.knowledge is Knowledge.UNKNOWN:
            if any(item.observed_paths is not None for item in self.profiles):
                raise ValueError(
                    "unknown payload-rules knowledge must not claim current profile paths"
                )
        else:
            if any(item.observed_paths is None for item in self.profiles):
                raise ValueError(
                    "known payload-rules knowledge requires explicit profile path state"
                )


def project_payload_traffic_state(
    desired: NetworkRulesSpec,
    observed: NetworkRulesState,
    rules_state: PayloadRulesState,
) -> PayloadTrafficStateInfo:
    """Project rules assessment into the payload-domain InfoEvent payload.

    The function exposes no NetworkRulesSpec/NetworkRulesState object in the returned
    payload. It only carries payload-rules assessment and per-Profile observed paths.
    """

    authoritative = (
        observed.knowledge is StateKnowledge.KNOWN
        and observed.fresh
        and observed.rules is not None
    )

    if rules_state.knowledge is Knowledge.UNKNOWN:
        if authoritative:
            raise ValueError(
                "unknown payload-rules state contradicts authoritative observation"
            )
        return PayloadTrafficStateInfo(
            rules_state=rules_state,
            profiles=tuple(
                PayloadProfileTrafficState(domain.name, None)
                for domain in desired.routing_domains
            ),
        )

    if not authoritative:
        raise ValueError(
            "known payload-rules state requires authoritative network-rules observation"
        )

    actual_by_name = {
        domain.name: domain
        for domain in observed.rules.routing_domains
    }

    return PayloadTrafficStateInfo(
        rules_state=rules_state,
        profiles=tuple(
            PayloadProfileTrafficState(
                domain.name,
                (
                    actual_by_name[domain.name].ordered_paths
                    if domain.name in actual_by_name
                    else ()
                ),
            )
            for domain in desired.routing_domains
        ),
    )
