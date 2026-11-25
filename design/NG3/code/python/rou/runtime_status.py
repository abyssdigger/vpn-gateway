"""Current-only RuntimeStatusAgent contract and alpha status presentation.\n\nArchitecture: A.008, A.009\n"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable

from .binding import LogicalPathId, PathBinding
from .managed_device_manager import ManagedDeviceRealization
from .managed_device_demand import ManagedDeviceDemandProjection, ProfileManagedDeviceDemand
from .network_policy_layout import ProbePolicyOwner
from .payload_profile import PayloadProfileRequest
from .release1_config import CurrentConfig, Release1Config, WarmPaths, render_helper_routing_interfaces
from .wireguard_peer_manager import WireGuardPeerRealization


_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:[.][0-9A-Za-z-]+)*)?"
    r"(?:[+][0-9A-Za-z-]+(?:[.][0-9A-Za-z-]+)*)?$"
)


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
    availability_check: str | None
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
    warm_paths: WarmPaths | None = None


@dataclass(frozen=True, slots=True)
class ConfiguredIntentStatus:
    helper_routing_interfaces: str
    helper_routing_policy: str
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
    problem_paths: tuple[LogicalPathId, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeStatusSnapshot:
    version: str
    configured_intent: ConfiguredIntentStatus
    confirmed_effective_state: tuple[EffectiveProfileStatus, ...] | None
    managed_device_realizations: tuple[ManagedDeviceRealization, ...]
    wireguard_peer_realizations: tuple[WireGuardPeerRealization, ...]
    availability_state: tuple[AvailabilityProfileStatus, ...]
    readiness: RuntimeReadiness
    blocking_problems: tuple[str, ...]
    unknown_or_unconfirmed_fields: tuple[str, ...]
    # Last demand calculated from fresh structural presence, not a payload verdict.
    managed_profile_demands: tuple[ProfileManagedDeviceDemand, ...] | None = None

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["readiness"] = self.readiness.value
        return value


class RuntimeStatusAgent:
    """Retain only the latest current status projection; never own represented policy."""

    def __init__(
        self,
        configured_intent: ConfiguredIntentStatus,
        *,
        version: str = "development",
    ) -> None:
        if not isinstance(configured_intent, ConfiguredIntentStatus):
            raise ValueError("configured_intent must be ConfiguredIntentStatus")
        if not isinstance(version, str) or not version:
            raise ValueError("version must be non-empty text")
        self._version = version
        self._configured = configured_intent
        self._effective: tuple[EffectiveProfileStatus, ...] | None = None
        self._managed_devices: tuple[ManagedDeviceRealization, ...] = ()
        self._managed_demands: tuple[ProfileManagedDeviceDemand, ...] | None = None
        self._wireguard_peers: tuple[WireGuardPeerRealization, ...] = ()
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
        self._unknown = ()

    def confirm_managed_devices(
        self,
        realizations: Iterable[ManagedDeviceRealization],
    ) -> None:
        current = tuple(realizations)
        if any(not isinstance(item, ManagedDeviceRealization) for item in current):
            raise ValueError(
                "realizations must contain ManagedDeviceRealization"
            )
        ids = [item.device_id for item in current]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate managed Device realization")
        self._managed_devices = tuple(
            sorted(current, key=lambda item: item.device_id)
        )

    def confirm_managed_demand(
        self, projection: ManagedDeviceDemandProjection | None
    ) -> None:
        if projection is not None and not isinstance(projection, ManagedDeviceDemandProjection):
            raise ValueError("projection must be ManagedDeviceDemandProjection or None")
        self._managed_demands = None if projection is None else projection.profiles

    def confirm_wireguard_peers(
        self,
        realizations: Iterable[WireGuardPeerRealization],
    ) -> None:
        current = tuple(realizations)
        if any(not isinstance(item, WireGuardPeerRealization) for item in current):
            raise ValueError(
                "realizations must contain WireGuardPeerRealization"
            )
        ids = [item.device_id for item in current]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate WireGuard peer realization")
        self._wireguard_peers = tuple(
            sorted(current, key=lambda item: item.device_id)
        )

    def confirm_availability(
        self,
        problem_owners: Iterable[ProbePolicyOwner],
    ) -> None:
        owners = tuple(problem_owners)
        if any(not isinstance(owner, ProbePolicyOwner) for owner in owners):
            raise ValueError("problem_owners must contain ProbePolicyOwner")
        problem_profiles = {owner.profile_id for owner in owners}
        problem_paths: dict[str, list[LogicalPathId]] = {}
        for owner in owners:
            problem_paths.setdefault(owner.profile_id, []).append(owner.path_id)
        enabled_profiles = {
            profile.profile_id: profile
            for profile in self._configured.profiles
            if profile.enabled
        }
        unknown = problem_profiles - set(enabled_profiles)
        if unknown:
            raise ValueError(
                f"availability problem owner references unknown enabled Profile: {sorted(unknown)!r}"
            )
        invalid = {
            profile_id
            for profile_id in problem_profiles
            if enabled_profiles[profile_id].availability_check is None
        }
        if invalid:
            raise ValueError(
                f"availability problem owner references disabled availability Profile: {sorted(invalid)!r}"
            )
        self._availability = tuple(
            AvailabilityProfileStatus(
                profile.profile_id,
                (
                    "disabled"
                    if profile.availability_check is None
                    else (
                        "problem"
                        if profile.profile_id in problem_profiles
                        else "monitoring"
                    )
                ),
                tuple(sorted(problem_paths.get(profile.profile_id, ()))),
            )
            for profile in self._configured.profiles
            if profile.enabled
        )

    def mark_degraded(
        self,
        *,
        problem: str,
        unknown_fields: Iterable[str] = (),
    ) -> None:
        """Report a local owner problem without invalidating unrelated projections."""
        if not isinstance(problem, str) or not problem:
            raise ValueError("problem must be non-empty text")
        fields = tuple(sorted(set(unknown_fields)))
        if any(not isinstance(item, str) or not item for item in fields):
            raise ValueError("unknown fields must be non-empty text")
        self._readiness = RuntimeReadiness.DEGRADED
        self._problems = (problem,)
        self._unknown = fields

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
        self._availability = tuple(
            AvailabilityProfileStatus(
                profile.profile_id,
                (
                    "disabled"
                    if profile.availability_check is None
                    else "unconfirmed"
                ),
            )
            for profile in self._configured.profiles
            if profile.enabled
        )
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
            version=self._version,
            configured_intent=self._configured,
            confirmed_effective_state=self._effective,
            managed_device_realizations=self._managed_devices,
            wireguard_peer_realizations=self._wireguard_peers,
            availability_state=self._availability,
            readiness=self._readiness,
            blocking_problems=self._problems,
            unknown_or_unconfirmed_fields=self._unknown,
            managed_profile_demands=self._managed_demands,
        )


def read_release_version(path: Path) -> str:
    """Read and validate the canonical release VERSION value."""
    if isinstance(path, str):
        path = Path(path)
    if not isinstance(path, Path):
        raise ValueError("version path must be pathlib.Path or text")
    version = path.read_text(encoding="ascii").strip()
    if not _SEMVER_PATTERN.fullmatch(version):
        raise ValueError(f"invalid Semantic Versioning release value: {version!r}")
    return version


def build_configured_intent_status(
    config: Release1Config | CurrentConfig,
) -> ConfiguredIntentStatus:
    current = config if isinstance(config, CurrentConfig) else None
    if current is not None:
        config = current.base
    if not isinstance(config, Release1Config):
        raise ValueError("config must be Release1Config or CurrentConfig")

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
                        (
                            selector.value
                            + ("*" if selector.kind.value == "prefix" else "")
                            + ("" if selector.quota == 1 else f"/{selector.quota}")
                        )
                    )
                    for selector in structural.expected_interfaces
                ),
                availability_check=(
                    None
                    if semantic.availability_check is None
                    else _render_availability_check(semantic.availability_check)
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
                        semantic.effective_snat_address,
                        config.default_snat_address,
                    )
                ),
                destinations=tuple(
                    item.with_prefixlen for item in structural.destinations
                ),
                device_order=structural.device_order,
                warm_paths=(
                    current.warm_paths.get(profile_id, "all")
                    if current is not None and structural.enabled else None
                ),
                availability_check=(
                    "default"
                    if semantic.availability_uses_device_default
                    else (
                        None
                        if semantic.availability_check is None
                        else _render_availability_check(
                            semantic.availability_check
                        )
                    )
                ),
            )
        )

    return ConfiguredIntentStatus(
        render_helper_routing_interfaces(config.helper_routing_interfaces),
        config.helper_routing_policy.value,
        tuple(devices),
        tuple(profiles),
    )


def _render_availability_check(value) -> str:
    return f"{value.mechanism}/{value.target}"


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


def render_runtime_status_text(snapshot: RuntimeStatusSnapshot) -> str:
    """Render the normative compact Devices/Profiles current-state view."""
    if not isinstance(snapshot, RuntimeStatusSnapshot):
        raise ValueError("snapshot must be RuntimeStatusSnapshot")

    devices = {item.device_id: item for item in snapshot.configured_intent.devices}
    profiles = {item.profile_id: item for item in snapshot.configured_intent.profiles}
    availability = {item.profile_id: item for item in snapshot.availability_state}

    effective = snapshot.confirmed_effective_state
    effective_by_profile = (
        None
        if effective is None
        else {item.profile_id: item for item in effective}
    )

    lines = [f"VPN-GATE {snapshot.version}", "Devices"]
    if effective is None:
        for device in snapshot.configured_intent.devices:
            state = "disabled" if not device.enabled else "unknown"
            lines.append(f"    {device.device_id}: {state}")
    else:
        paths_by_device: dict[str, dict[LogicalPathId, str]] = {}
        for profile in effective:
            for path in profile.ordered_paths:
                path_id = LogicalPathId(
                    path.device_id,
                    path.selector_index,
                    path.slot_index,
                )
                paths_by_device.setdefault(path.device_id, {})[path_id] = path.ifname
        for device in snapshot.configured_intent.devices:
            if not device.enabled:
                value = "disabled"
            else:
                current = paths_by_device.get(device.device_id, {})
                value = (
                    ", ".join(current[path_id] for path_id in sorted(current))
                    if current
                    else "not discovered"
                )
            lines.append(f"    {device.device_id}: {value}")

    lines.append("Profiles")
    for profile in snapshot.configured_intent.profiles:
        if not profile.enabled:
            lines.append(f"    {profile.profile_id}: disabled")
            continue
        if effective_by_profile is None or profile.profile_id not in effective_by_profile:
            lines.append(f"    {profile.profile_id}: unknown")
            continue

        lines.append(f"    {profile.profile_id}")
        current = effective_by_profile[profile.profile_id]
        availability_state = availability.get(profile.profile_id)
        for index, path in enumerate(current.ordered_paths, start=1):
            path_id = LogicalPathId(
                path.device_id,
                path.selector_index,
                path.slot_index,
            )
            check = _status_availability_check(profile, path.device_id, devices)
            state = _status_path_availability(
                availability_state,
                path_id,
                check,
            )
            lines.append(f"        {index:02d}. {path.ifname} {state}")

    return "\n".join(lines)


def _status_availability_check(
    profile: ConfiguredProfileStatus,
    device_id: str,
    devices: dict[str, ConfiguredDeviceStatus],
) -> str | None:
    if profile.availability_check is None:
        return None
    if profile.availability_check != "default":
        return profile.availability_check
    device = devices.get(device_id)
    if device is None or device.availability_check is None:
        raise ValueError(
            f"Profile {profile.profile_id!r} default availability has no Device check for {device_id!r}"
        )
    return device.availability_check


def _status_path_availability(
    status: AvailabilityProfileStatus | None,
    path_id: LogicalPathId,
    check: str | None,
) -> str:
    if check is None:
        return "unchecked"
    if status is None or status.state == "unconfirmed":
        return f"unknown ({check})"
    if status.state == "disabled":
        raise ValueError("availability status is disabled while a check is configured")
    if status.state == "monitoring":
        return f"available ({check})"
    if status.state == "problem":
        if path_id in status.problem_paths:
            return f"not available ({check})"
        return f"available ({check})"
    raise ValueError(f"unknown availability status: {status.state!r}")


class RuntimeStatusFilePublisher:
    """Publish one current status generation only when its semantic snapshot changes."""

    def __init__(self, json_path: Path, text_path: Path) -> None:
        self._json_path = json_path
        self._text_path = text_path
        self._last_published: RuntimeStatusSnapshot | None = None

    def publish(self, snapshot: RuntimeStatusSnapshot) -> bool:
        if not isinstance(snapshot, RuntimeStatusSnapshot):
            raise ValueError("snapshot must be RuntimeStatusSnapshot")
        if snapshot == self._last_published:
            return False
        write_runtime_status_json(self._json_path, snapshot)
        write_runtime_status_text(self._text_path, snapshot)
        self._last_published = snapshot
        return True


def write_runtime_status_text(path: Path, snapshot: RuntimeStatusSnapshot) -> None:
    if not isinstance(snapshot, RuntimeStatusSnapshot):
        raise ValueError("snapshot must be RuntimeStatusSnapshot")
    _write_atomic_status(path, render_runtime_status_text(snapshot) + "\n")


def write_runtime_status_json(path: Path, snapshot: RuntimeStatusSnapshot) -> None:
    if not isinstance(snapshot, RuntimeStatusSnapshot):
        raise ValueError("snapshot must be RuntimeStatusSnapshot")
    payload = json.dumps(
        snapshot.to_dict(),
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    ) + "\n"
    _write_atomic_status(path, payload)


def _write_atomic_status(path: Path, payload: str) -> None:
    if isinstance(path, str):
        path = Path(path)
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("status path must be absolute")
    parent = path.parent
    if not parent.is_dir():
        raise ValueError("status parent directory must already exist")

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


def _render_direction(base: str, effective_snat_address, default_snat_address) -> str:
    if effective_snat_address is None:
        return base
    if (
        default_snat_address is not None
        and effective_snat_address == default_snat_address
    ):
        return base + "+snat"
    return base + f"+snat>{effective_snat_address}"


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
