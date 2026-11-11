from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Network

from .domain import ActiveConfig, Direction


class FlowDirection(str, Enum):
    HOST_TO_DEVICE = "host_to_device"
    DEVICE_TO_HOST = "device_to_host"


class Verdict(str, Enum):
    ACCEPT = "accept"
    DROP = "drop"


@dataclass(frozen=True)
class NewFlowRuleIntent:
    profile_name: str
    device_name: str
    remote_prefix: IPv4Network
    direction: FlowDirection
    verdict: Verdict


def _direction_verdict(profile_direction: Direction, direction: FlowDirection) -> Verdict:
    if direction is FlowDirection.HOST_TO_DEVICE:
        allowed = profile_direction in (Direction.OUTBOUND, Direction.BIDIRECTIONAL)
    else:
        allowed = profile_direction in (Direction.INBOUND, Direction.BIDIRECTIONAL)
    return Verdict.ACCEPT if allowed else Verdict.DROP


def compile_new_flow_intents(config: ActiveConfig) -> tuple[NewFlowRuleIntent, ...]:
    """Compile explicit NEW-flow verdicts for every active Profile/Device/prefix pair.

    Omission is never used to represent a denying direction. Rules are sorted
    longest-prefix-first so a broader Profile cannot override a more-specific verdict.
    """

    rules: list[NewFlowRuleIntent] = []

    for profile in config.profiles.values():
        if not profile.enabled:
            continue
        assert profile.direction is not None

        for device_name in profile.device_order:
            device = config.devices.get(device_name)
            if device is None:
                raise ValueError(
                    f"Profile {profile.name!r} references unknown Device {device_name!r}"
                )
            if not device.enabled:
                continue

            for prefix in profile.destinations:
                rules.append(
                    NewFlowRuleIntent(
                        profile_name=profile.name,
                        device_name=device_name,
                        remote_prefix=prefix,
                        direction=FlowDirection.HOST_TO_DEVICE,
                        verdict=_direction_verdict(
                            profile.direction,
                            FlowDirection.HOST_TO_DEVICE,
                        ),
                    )
                )
                rules.append(
                    NewFlowRuleIntent(
                        profile_name=profile.name,
                        device_name=device_name,
                        remote_prefix=prefix,
                        direction=FlowDirection.DEVICE_TO_HOST,
                        verdict=_direction_verdict(
                            profile.direction,
                            FlowDirection.DEVICE_TO_HOST,
                        ),
                    )
                )

    return tuple(
        sorted(
            rules,
            key=lambda rule: (
                rule.direction.value,
                rule.device_name,
                -rule.remote_prefix.prefixlen,
                int(rule.remote_prefix.network_address),
                rule.profile_name,
            ),
        )
    )
