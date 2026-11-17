"""Bounded Release-1 supported-VPN integration transport configuration."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
import tomllib
from typing import Any

from .local_integration_policy import IntegrationTransportProtocol


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_KEYS = frozenset(
    {
        "device",
        "protocol",
        "remote_ipv4",
        "remote_port",
        "local_port",
    }
)


class IntegrationConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IntegrationTransportConfig:
    integration_id: str
    device_id: str
    protocol: IntegrationTransportProtocol
    remote_address: ipaddress.IPv4Address
    remote_port: int
    local_port: int | None = None


def parse_integration_transport_config(
    text: str,
) -> tuple[IntegrationTransportConfig, ...]:
    """Parse only the [integration.*] slice from the common NG3 TOML file."""
    try:
        raw = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, TypeError) as exc:
        raise IntegrationConfigError(f"invalid TOML: {exc}") from None

    integrations = raw.get("integration", {})
    if not isinstance(integrations, dict):
        raise IntegrationConfigError("integration must be a TOML table")

    result = []
    for integration_id in sorted(integrations):
        if not _ID_RE.fullmatch(integration_id):
            raise IntegrationConfigError(
                f"invalid integration id {integration_id!r}"
            )
        body = integrations[integration_id]
        if not isinstance(body, dict):
            raise IntegrationConfigError(
                f"integration.{integration_id} must be a TOML table"
            )
        unknown = sorted(set(body) - _KEYS)
        if unknown:
            raise IntegrationConfigError(
                f"integration.{integration_id} has unsupported field(s): "
                + ", ".join(unknown)
            )

        device_id = body.get("device")
        if not isinstance(device_id, str) or not _ID_RE.fullmatch(device_id):
            raise IntegrationConfigError(
                f"integration.{integration_id}.device must be a valid Device ID"
            )
        try:
            protocol = IntegrationTransportProtocol(body.get("protocol"))
        except (TypeError, ValueError):
            raise IntegrationConfigError(
                f"integration.{integration_id}.protocol must be tcp or udp"
            ) from None

        remote_raw = body.get("remote_ipv4")
        if not isinstance(remote_raw, str):
            raise IntegrationConfigError(
                f"integration.{integration_id}.remote_ipv4 must be an IPv4 string"
            )
        try:
            remote_address = ipaddress.IPv4Address(remote_raw)
        except ipaddress.AddressValueError:
            raise IntegrationConfigError(
                f"integration.{integration_id}.remote_ipv4 is invalid"
            ) from None

        remote_port = _port(
            body.get("remote_port"),
            f"integration.{integration_id}.remote_port",
        )
        local_port_raw = body.get("local_port")
        local_port = (
            None
            if local_port_raw is None
            else _port(
                local_port_raw,
                f"integration.{integration_id}.local_port",
            )
        )

        result.append(
            IntegrationTransportConfig(
                integration_id=integration_id,
                device_id=device_id,
                protocol=protocol,
                remote_address=remote_address,
                remote_port=remote_port,
                local_port=local_port,
            )
        )

    return tuple(result)


def _port(value: Any, where: str) -> int:
    if type(value) is not int or not 1 <= value <= 65535:
        raise IntegrationConfigError(
            f"{where} must be an integer in [1, 65535]"
        )
    return value
