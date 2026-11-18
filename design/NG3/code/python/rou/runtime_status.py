"""Current-only RuntimeStatusAgent contract and alpha JSON presentation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable

from .binding import PathBinding
from .payload_profile import PayloadProfileRequest
from .release1_config import Release1Config


class RuntimeReadiness(str, Enum):
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ConfiguredDeviceStatus:
    device_id: str
    enabled: bool
    expected_interfaces: tuple[str, ...]
    use_outbound_nat: bool | None
    vpn_client_transports: tuple[str, ...]
    server_publications: tuple[str, ...]
    firewall_rules: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class ConfiguredProfileStatus:
    profile_id: str
    enabled: bool
    direction: str | None
    destinations: tuple[str, ...]
    device_order: tuple[str, ...]
    availability_check: str | None


@dataclass(frozen=True, slots=True)
class ConfiguredIntentStatus:
    devices: tuple[ConfiguredDeviceStatus, ...]
    profiles: tuple[ConfiguredProfileStatus, ...]


@dataclass(frozen=True, slots=True)
class EffectivePathStatus:
    device_id: str
    selector_index: int
    slot_index: int
    ifname: str
    ifindex: int


@dataclass(frozen=True, slots=True)
class EffectiveProfileStatus:
    profile_id: str
    ordered_paths: tuple[EffectivePathStatus, ...]


@dataclass(frozen=True, slots=True)
class AvailabilityProfileStatus:
    profile_id: str
    state: str


@dataclass(frozen=True, slots=True)
class RuntimeStatusSnapshot:
    configured_intent: ConfiguredIntentStatus
    confirmed_effective_state: tuple[EffectiveProfileStatus, ...] | None
    availability_state: tuple[AvailabilityProfileStatus, ...]
    readiness: RuntimeReadiness
    blocking_problems: tuple[str, ...]
    unknown_or_unconfirmed_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["readiness"] = self.readiness.value
        return value


class RuntimeStatusAgent:
    """Retain only the latest current status projection; never own represented policy."""

    def __init__(self, configured_intent: ConfiguredIntentStatus) -> None:
        if not isinstance(configured_intent, ConfiguredIntentStatus):
            raise ValueError("configured_intent must be ConfiguredIntentStatus")
        self._configured = configured_intent
        self._effective: tuple[EffectiveProfileStatus, ...] | None = None
        self._availability = tuple(
            AvailabilityProfileStatus(
                profile.profile_id,
                (
                    "disabled"
                    if profile.availability_check is None
                    else "unconfirmed"
                ),
            )
            for profile in configured_intent.profiles
            if profile.enabled
        )
        self._readiness = RuntimeReadiness.STARTING
        self._problems: tuple[str, ...] = ()
        self._unknown: tuple[str, ...] = ("confirmed_effective_state",)

    def confirm_effective(
        self,
        profiles: Iterable[PayloadProfileRequest],
        bindings: Iterable[PathBinding],
        *,
        readiness: RuntimeReadiness = RuntimeReadiness.READY,
    ) -> None:
        if readiness not in {RuntimeReadiness.READY, RuntimeReadiness.DEGRADED}:
            raise ValueError("confirmed effective state requires READY or DEGRADED readiness")
        self._effective = build_effective_profile_status(profiles, bindings)
        self._readiness = readiness
        self._problems = ()
        self._unknown = tuple(
            field
            for field in ()
        )

    def mark_unconfirmed(
        self,
        *,
        readiness: RuntimeReadiness,
        problem: str,
        unknown_fields: Iterable[str] = ("confirmed_effective_state",),
    ) -> None:
        if readiness not in {
            RuntimeReadiness.STARTING,
            RuntimeReadiness.DEGRADED,
            RuntimeReadiness.FAILED,
        }:
            raise ValueError("unconfirmed state requires STARTING, DEGRADED or FAILED readiness")
        if not isinstance(problem, str) or not problem:
            raise ValueError("problem must be non-empty text")
        fields = tuple(sorted(set(unknown_fields)))
        if any(not isinstance(item, str) or not item for item in fields):
            raise ValueError("unknown fields must be non-empty text")
        self._effective = None
        self._readiness = readiness
        self._problems = (problem,)
        self._unknown = fields

    def mark_stopping(self) -> None:
        self._readiness = RuntimeReadiness.STOPPING

    def mark_stopped(self) -> None:
        self._readiness = RuntimeReadiness.STOPPED
        self._effective = None
        self._unknown = ("confirmed_effective_state",)

    def snapshot(self) -> RuntimeStatusSnapshot:
        return RuntimeStatusSnapshot(
            configured_intent=self._configured,
            confirmed_effective_state=self._effective,
            availability_state=self._availability,
            readiness=self._readiness,
            blocking_problems=self._problems,
            unknown_or_unconfirmed_fields=self._unknown,
        )


def build_configured_intent_status(config: Release1Config) -> ConfiguredIntentStatus:
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config")

    devices = []
    for device_id in sorted(config.structural.devices):
        structural = config.structural.devices[device_id]
        semantic = config.devices[device_id]
        devices.append(
            ConfiguredDeviceStatus(
                device_id=device_id,
                enabled=structural.enabled,
                expected_interfaces=tuple(
                    (
                        selector.value
                        if selector.quota == 1
                        else f"{selector.value}/{selector.quota}"
                    )
                    for selector in structural.expected_interfaces
                ),
                use_outbound_nat=semantic.use_outbound_nat,
                vpn_client_transports=tuple(
                    _render_client_transport(item)
                    for item in semantic.allow_vpn_client
                ),
                server_publications=tuple(
                    _render_publication(item)
                    for item in semantic.publish_vpn_server
                ),
                firewall_rules=(
                    None
                    if semantic.firewall is None
                    else tuple(_render_firewall_rule(item) for item in semantic.firewall)
                ),
            )
        )

    profiles = []
    for profile_id in sorted(config.structural.profiles):
        structural = config.structural.profiles[profile_id]
        semantic = config.profiles[profile_id]
        profiles.append(
            ConfiguredProfileStatus(
                profile_id=profile_id,
                enabled=structural.enabled,
                direction=(
                    None
                    if structural.direction is None
                    else _render_direction(
                        structural.direction.value,
                        semantic.ordinary_gateway_nat,
                        semantic.route_return,
                    )
                ),
                destinations=tuple(
                    item.with_prefixlen for item in structural.destinations
                ),
                device_order=structural.device_order,
                availability_check=(
                    None
                    if semantic.availability_check is None
                    else (
                        semantic.availability_check.mechanism
                        if semantic.availability_check.target is None
                        else (
                            f"{semantic.availability_check.mechanism}/"
                            f"{semantic.availability_check.target}"
                        )
                    )
                ),
            )
        )

    return ConfiguredIntentStatus(tuple(devices), tuple(profiles))


def build_effective_profile_status(
    profiles: Iterable[PayloadProfileRequest],
    bindings: Iterable[PathBinding],
) -> tuple[EffectiveProfileStatus, ...]:
    current_profiles = tuple(sorted(profiles, key=lambda item: item.profile_id))
    current_bindings = tuple(bindings)
    endpoint_by_path = {item.path_id: item.endpoint for item in current_bindings}
    if len(endpoint_by_path) != len(current_bindings):
        raise ValueError("duplicate current path binding")

    result = []
    for profile in current_profiles:
        paths = []
        for path_id in profile.ordered_paths:
            endpoint = endpoint_by_path.get(path_id)
            if endpoint is None:
                raise ValueError(
                    f"effective Profile {profile.profile_id!r} references unbound path {path_id!r}"
                )
            paths.append(
                EffectivePathStatus(
                    device_id=path_id.device_id,
                    selector_index=path_id.selector_index,
                    slot_index=path_id.slot_index,
                    ifname=endpoint.ifname,
                    ifindex=endpoint.ifindex,
                )
            )
        result.append(EffectiveProfileStatus(profile.profile_id, tuple(paths)))
    return tuple(result)


def write_runtime_status_json(path: Path, snapshot: RuntimeStatusSnapshot) -> None:
    if isinstance(path, str):
        path = Path(path)
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("status path must be absolute")
    if not isinstance(snapshot, RuntimeStatusSnapshot):
        raise ValueError("snapshot must be RuntimeStatusSnapshot")

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        snapshot.to_dict(),
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    ) + "\n"

    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=parent,
        text=True,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _render_direction(base: str, gateway_nat: bool, route_return: bool) -> str:
    suffixes = []
    if gateway_nat:
        suffixes.append("snat")
    if route_return:
        suffixes.append("route-return")
    return base + "".join(f"+{item}" for item in suffixes)


def _render_client_transport(item) -> str:
    local = "" if item.local_port is None else f":{item.local_port}"
    return f"{item.protocol}{local}>{item.remote_address}:{item.remote_port}"


def _render_publication(item) -> str:
    selector = (
        ""
        if item.host_selector.kind == "any"
        else f"/{item.host_selector.value}"
    )
    host = ",".join(
        str(span.first) if span.first == span.last else f"{span.first}-{span.last}"
        for span in item.host_ports.spans
    )
    internal = ",".join(
        str(span.first) if span.first == span.last else f"{span.first}-{span.last}"
        for span in item.internal_ports.spans
    )
    return f"{item.protocol}{selector}:{host}>{internal}"


def _render_firewall_rule(item) -> str:
    parts = [item.direction, item.action]
    if item.protocol is not None:
        parts.append(item.protocol)
    if item.source_ipv4_cidr is not None:
        source = item.source_ipv4_cidr.with_prefixlen
        if item.source_ports is not None:
            source += ":" + _render_port_bundle(item.source_ports)
        parts.extend(("from", source))
    if item.destination_ipv4_cidr is not None:
        destination = item.destination_ipv4_cidr.with_prefixlen
        if item.destination_ports is not None:
            destination += ":" + _render_port_bundle(item.destination_ports)
        parts.extend(("to", destination))
    value = " ".join(parts)
    return value if item.comment is None else f"{value} # {item.comment}"


def _render_port_bundle(bundle) -> str:
    return ",".join(
        str(span.first) if span.first == span.last else f"{span.first}-{span.last}"
        for span in bundle.spans
    )
