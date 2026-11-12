from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface, ip_address, ip_interface
from pathlib import Path
import re
import tomllib
from typing import Any

from .instance_lifecycle import InstanceConfig, InstanceConfigError


class InstanceFileConfigError(ValueError):
    pass


_INSTANCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TOP_LEVEL_KEYS = frozenset({"schema_version", "instance"})
_INSTANCE_KEYS = frozenset(
    {
        "namespace",
        "host_interface",
        "host_address",
        "inner_address",
        "publication_bind_address",
        "router_config",
        "state_file",
    }
)


@dataclass(frozen=True)
class InstanceFileConfig:
    instance: InstanceConfig
    publication_bind_address: IPv4Address
    router_config: Path
    state_file: Path


def validate_instance_id(instance_id: str) -> str:
    if not _INSTANCE_ID_RE.fullmatch(instance_id):
        raise InstanceFileConfigError(
            f"invalid instance id {instance_id!r}; "
            "expected [a-z0-9][a-z0-9-]*"
        )
    return instance_id


def _absolute_path(
    value: Any,
    where: str,
    *,
    required_root: Path | None = None,
) -> Path:
    if not isinstance(value, str) or not value:
        raise InstanceFileConfigError(
            f"{where} must be a non-empty absolute path string"
        )
    path = Path(value)
    if not path.is_absolute():
        raise InstanceFileConfigError(f"{where} must be absolute")
    if required_root is not None:
        try:
            path.relative_to(required_root)
        except ValueError:
            raise InstanceFileConfigError(
                f"{where} must be below {required_root}"
            ) from None
    return path


def _ipv4_interface(value: Any, where: str) -> IPv4Interface:
    if not isinstance(value, str):
        raise InstanceFileConfigError(f"{where} must be a string")
    try:
        parsed = ip_interface(value)
    except ValueError as exc:
        raise InstanceFileConfigError(
            f"{where} is not a valid IPv4 interface address: {exc}"
        ) from None
    if not isinstance(parsed, IPv4Interface):
        raise InstanceFileConfigError(f"{where} must be IPv4")
    return parsed


def _ipv4_address(value: Any, where: str) -> IPv4Address:
    if not isinstance(value, str):
        raise InstanceFileConfigError(f"{where} must be a string")
    try:
        parsed = ip_address(value)
    except ValueError as exc:
        raise InstanceFileConfigError(
            f"{where} is not a valid IPv4 address: {exc}"
        ) from None
    if not isinstance(parsed, IPv4Address):
        raise InstanceFileConfigError(f"{where} must be IPv4")
    return parsed


def parse_instance_file_config(text: str) -> InstanceFileConfig:
    try:
        root = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise InstanceFileConfigError(f"invalid TOML: {exc}") from None

    unknown = sorted(set(root) - _TOP_LEVEL_KEYS)
    if unknown:
        raise InstanceFileConfigError(
            f"unsupported top-level field(s): {', '.join(unknown)}"
        )

    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        raise InstanceFileConfigError("schema_version = 1 is required")

    body = root.get("instance")
    if not isinstance(body, dict):
        raise InstanceFileConfigError("instance must be a TOML table")

    unknown_instance = sorted(set(body) - _INSTANCE_KEYS)
    if unknown_instance:
        raise InstanceFileConfigError(
            "instance has unsupported field(s): "
            + ", ".join(unknown_instance)
        )

    required = _INSTANCE_KEYS
    missing = sorted(required - set(body))
    if missing:
        raise InstanceFileConfigError(
            "instance is missing required field(s): "
            + ", ".join(missing)
        )

    namespace = body["namespace"]
    host_if = body["host_interface"]
    if not isinstance(namespace, str):
        raise InstanceFileConfigError("instance.namespace must be a string")
    if not isinstance(host_if, str):
        raise InstanceFileConfigError(
            "instance.host_interface must be a string"
        )

    try:
        instance = InstanceConfig(
            namespace=namespace,
            host_if=host_if,
            inner_if="host0",
            host_address=_ipv4_interface(
                body["host_address"],
                "instance.host_address",
            ),
            inner_address=_ipv4_interface(
                body["inner_address"],
                "instance.inner_address",
            ),
        )
    except InstanceConfigError as exc:
        raise InstanceFileConfigError(str(exc)) from None

    router_config = _absolute_path(
        body["router_config"],
        "instance.router_config",
    )
    state_file = _absolute_path(
        body["state_file"],
        "instance.state_file",
        required_root=Path("/var/lib/vpn-gateway"),
    )
    if router_config == state_file:
        raise InstanceFileConfigError(
            "router_config and state_file must be different paths"
        )

    return InstanceFileConfig(
        instance=instance,
        publication_bind_address=_ipv4_address(
            body["publication_bind_address"],
            "instance.publication_bind_address",
        ),
        router_config=router_config,
        state_file=state_file,
    )


def load_instance_file_config(path: str | Path) -> InstanceFileConfig:
    return parse_instance_file_config(
        Path(path).read_text(encoding="utf-8")
    )
