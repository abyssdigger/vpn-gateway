from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .device_engine import (
    DeviceBindingState,
    ExpectedBindingState,
    InterfaceIdentity,
)
from .domain import ActiveConfig
from .metrics import compile_profile_metric_layout
from .planner import PlannerRuntimeState
from .traffic_state import TrafficRuntimeState


STATE_VERSION = 1


class StateStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class StateLoadResult:
    state: PlannerRuntimeState
    dropped_entries: int


def _identity_to_json(identity: InterfaceIdentity) -> dict[str, object]:
    return {
        "ifname": identity.ifname,
        "ifindex": identity.ifindex,
    }


def _parse_identity(raw: Any, where: str) -> InterfaceIdentity:
    if not isinstance(raw, dict):
        raise StateStoreError(f"{where} must be an object")
    ifname = raw.get("ifname")
    ifindex = raw.get("ifindex")
    if not isinstance(ifname, str) or not ifname:
        raise StateStoreError(f"{where}.ifname must be a non-empty string")
    if type(ifindex) is not int or ifindex <= 0:
        raise StateStoreError(f"{where}.ifindex must be a positive integer")
    return InterfaceIdentity(ifname, ifindex)


def _serialize(state: PlannerRuntimeState) -> dict[str, object]:
    expectations = []
    for (device_name, expected_index), value in sorted(
        state.devices.expectations.items()
    ):
        expectations.append(
            {
                "device": device_name,
                "expected_index": expected_index,
                "candidate_order": [
                    _identity_to_json(identity)
                    for identity in value.candidate_order
                ],
            }
        )

    metrics = []
    for (profile_name, identity), metric in sorted(
        state.traffic.normal_metrics.items(),
        key=lambda item: (
            item[0][0],
            item[0][1].ifname,
            item[0][1].ifindex,
        ),
    ):
        metrics.append(
            {
                "profile": profile_name,
                "identity": _identity_to_json(identity),
                "metric": metric,
            }
        )

    return {
        "version": STATE_VERSION,
        "device_expectations": expectations,
        "traffic_metrics": metrics,
    }


def _load_payload(
    raw: Any,
    config: ActiveConfig,
) -> StateLoadResult:
    if not isinstance(raw, dict):
        raise StateStoreError("state root must be an object")
    if raw.get("version") != STATE_VERSION:
        raise StateStoreError(
            f"unsupported state version {raw.get('version')!r}"
        )

    raw_expectations = raw.get("device_expectations")
    raw_metrics = raw.get("traffic_metrics")
    if not isinstance(raw_expectations, list):
        raise StateStoreError("device_expectations must be an array")
    if not isinstance(raw_metrics, list):
        raise StateStoreError("traffic_metrics must be an array")

    dropped = 0
    expectations: dict[tuple[str, int], ExpectedBindingState] = {}
    identity_owner: dict[InterfaceIdentity, tuple[str, int]] = {}

    active_devices = config.active_device_names

    for position, item in enumerate(raw_expectations):
        where = f"device_expectations[{position}]"
        if not isinstance(item, dict):
            raise StateStoreError(f"{where} must be an object")
        device_name = item.get("device")
        expected_index = item.get("expected_index")
        candidates = item.get("candidate_order")
        if not isinstance(device_name, str) or not device_name:
            raise StateStoreError(f"{where}.device must be a non-empty string")
        if type(expected_index) is not int or expected_index < 0:
            raise StateStoreError(f"{where}.expected_index must be non-negative")
        if not isinstance(candidates, list):
            raise StateStoreError(f"{where}.candidate_order must be an array")

        device = config.devices.get(device_name)
        if (
            device is None
            or device_name not in active_devices
            or expected_index >= len(device.expected_interfaces)
        ):
            dropped += 1
            continue

        expected = device.expected_interfaces[expected_index]
        parsed_candidates: list[InterfaceIdentity] = []
        local_seen: set[InterfaceIdentity] = set()
        incompatible = False

        for candidate_position, raw_identity in enumerate(candidates):
            identity = _parse_identity(
                raw_identity,
                f"{where}.candidate_order[{candidate_position}]",
            )
            if identity in local_seen:
                raise StateStoreError(
                    f"{where} contains duplicate identity {identity!r}"
                )
            local_seen.add(identity)
            if not expected.match.matches(identity.ifname):
                incompatible = True
                continue
            owner = identity_owner.get(identity)
            if owner is not None and owner != (device_name, expected_index):
                raise StateStoreError(
                    f"identity {identity!r} appears in multiple expectations"
                )
            identity_owner[identity] = (device_name, expected_index)
            parsed_candidates.append(identity)

        if incompatible:
            dropped += 1

        key = (device_name, expected_index)
        if key in expectations:
            raise StateStoreError(f"duplicate expectation state for {key!r}")
        expectations[key] = ExpectedBindingState(
            device_name,
            expected_index,
            tuple(parsed_candidates),
        )

    device_state = DeviceBindingState(expectations)
    metric_ranges: dict[tuple[str, str, int], tuple[int, int]] = {}
    for profile in config.profiles.values():
        if not profile.enabled:
            continue
        for item in compile_profile_metric_layout(config, profile):
            metric_ranges[(profile.name, item.device_name, item.expected_index)] = (
                item.start,
                item.end,
            )

    normal_metrics: dict[tuple[str, InterfaceIdentity], int] = {}
    for position, item in enumerate(raw_metrics):
        where = f"traffic_metrics[{position}]"
        if not isinstance(item, dict):
            raise StateStoreError(f"{where} must be an object")
        profile_name = item.get("profile")
        metric = item.get("metric")
        if not isinstance(profile_name, str) or not profile_name:
            raise StateStoreError(f"{where}.profile must be a non-empty string")
        if type(metric) is not int or metric <= 0:
            raise StateStoreError(f"{where}.metric must be a positive integer")
        identity = _parse_identity(item.get("identity"), f"{where}.identity")

        owner = identity_owner.get(identity)
        profile = config.profiles.get(profile_name)
        if owner is None or profile is None or not profile.enabled:
            dropped += 1
            continue

        device_name, expected_index = owner
        metric_range = metric_ranges.get(
            (profile_name, device_name, expected_index)
        )
        if metric_range is None or not (
            metric_range[0] <= metric <= metric_range[1]
        ):
            dropped += 1
            continue

        key = (profile_name, identity)
        if key in normal_metrics:
            raise StateStoreError(f"duplicate traffic metric state for {key!r}")
        normal_metrics[key] = metric

    return StateLoadResult(
        state=PlannerRuntimeState(
            devices=device_state,
            traffic=TrafficRuntimeState(normal_metrics),
        ),
        dropped_entries=dropped,
    )


class JsonRuntimeStateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, config: ActiveConfig) -> StateLoadResult:
        if not self.path.exists():
            return StateLoadResult(PlannerRuntimeState.empty(), 0)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateStoreError(f"cannot load runtime state: {exc}") from exc
        return _load_payload(raw, config)

    def save(self, state: PlannerRuntimeState) -> None:
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        payload = json.dumps(
            _serialize(state),
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"

        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                temp_path = handle.name
                os.fchmod(handle.fileno(), 0o600)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_path, self.path)
            temp_path = None

            dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as exc:
            raise StateStoreError(f"cannot save runtime state: {exc}") from exc
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
