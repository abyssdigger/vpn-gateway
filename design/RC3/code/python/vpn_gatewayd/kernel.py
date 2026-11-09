from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod
from ipaddress import IPv4Address, IPv4Network
from types import MappingProxyType
from typing import Mapping, Sequence

from .constants import IP_FORWARD_PATH, MAX_ROUTE_METRIC
from .errors import KernelError
from .interfaces import InterfaceRecord
from .models import RouteSpec, RouteType

class KernelInterface(ABC):
    """
    Physical kernel/userspace boundary.

    It must not know CONFIGURED/OWNED/DESIRED and must not make policy choices.
    Fixed firewall policy is constructed by VpnGatewayDaemon; this adapter only
    inventories/materializes concrete state.
    """

    # ---- Runtime routing -------------------------------------------------

    @abstractmethod
    def list_routes(self) -> frozenset[RouteSpec]:
        """Return normalized main IPv4 routing-table snapshot."""

    @abstractmethod
    def add_route(self, route: RouteSpec) -> None:
        """Materialize the complete RouteSpec without hidden policy defaults."""

    @abstractmethod
    def delete_route(self, route: RouteSpec) -> None:
        """Delete exactly the represented route."""

    @abstractmethod
    def replace_route(self, route: RouteSpec) -> None:
        """
        Materialize `route` with replace semantics.

        Used only for authoritative canonicalization when the exact desired
        RouteSpec already exists in ACTUAL but is not OWNED by this process.
        """

    def list_interfaces(self) -> tuple[InterfaceRecord, ...]:
        """
        Return the typed interface inventory required by RC3.

        Kept non-abstract during the staged RC2->RC3 migration so legacy test
        doubles remain constructible until daemon integration switches over.
        """
        raise NotImplementedError

    @abstractmethod
    def list_interface_ipv4(
        self,
    ) -> Mapping[str, frozenset[IPv4Address]]:
        """
        Return every existing interface.

        Existing interface with no IPv4 -> empty frozenset.
        Missing key -> interface does not exist.
        """

    # ---- Forwarding ------------------------------------------------------

    @abstractmethod
    def get_ip_forward(self) -> bool:
        pass

    @abstractmethod
    def set_ip_forward(self, enabled: bool) -> None:
        pass

    # ---- Fixed firewall/NAT ---------------------------------------------

    @abstractmethod
    def iptables_save(self) -> str:
        """Return inventory sufficient to verify daemon-owned fixed policy."""

    @abstractmethod
    def iptables_restore(self, payload: str, *, noflush: bool = True) -> None:
        """Apply an exact payload atomically per table/COMMIT."""

    def close(self) -> None:
        """Release technical resources such as sockets, if any."""


class SubprocessKernelInterface(KernelInterface):
    """
    Debian 13 subprocess adapter.

    Route/address inventory and route mutations use iproute2.
    Forwarding and firewall methods are completed in later implementation
    steps.  All subprocesses use bounded timeouts and a stable locale.

    Policy construction deliberately does not live here.
    """

    def __init__(
        self,
        *,
        command_timeout: float = 10.0,
        iptables_wait_seconds: int = 5,
    ) -> None:
        self.command_timeout = command_timeout
        self.iptables_wait_seconds = iptables_wait_seconds

    def _run(
        self,
        argv: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """
        Run one bounded userspace adapter command with stable locale.

        Human stderr is preserved in KernelError.detail text, but callers map
        failures to stable RuntimeReasonCode values for machine identity.
        """
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"

        try:
            return subprocess.run(
                list(argv),
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=self.command_timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = exc.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            detail = (stderr or "").strip()
            raise KernelError(
                f"command timed out after {self.command_timeout}s: "
                f"{list(argv)!r}; stderr={detail!r}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip()
            raise KernelError(
                f"command failed rc={exc.returncode}: {list(argv)!r}; "
                f"stderr={detail!r}"
            ) from exc
        except OSError as exc:
            raise KernelError(
                f"failed to execute {list(argv)!r}: {exc}"
            ) from exc

    @staticmethod
    def _load_json_array(stdout: str, *, context: str) -> list[object]:
        try:
            payload = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise KernelError(
                f"{context}: command returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(payload, list):
            raise KernelError(
                f"{context}: expected top-level JSON array, "
                f"got {type(payload).__name__}"
            )

        return payload

    @staticmethod
    def _parse_route_destination(value: object) -> IPv4Network:
        if not isinstance(value, str) or not value:
            raise KernelError(
                f"route inventory: invalid destination {value!r}"
            )

        normalized = "0.0.0.0/0" if value == "default" else value
        if "/" not in normalized:
            normalized = f"{normalized}/32"

        try:
            return IPv4Network(normalized, strict=True)
        except ValueError as exc:
            raise KernelError(
                f"route inventory: invalid IPv4 destination {value!r}"
            ) from exc

    @staticmethod
    def _parse_route_type(value: object) -> RouteType:
        if value is None:
            return RouteType.UNICAST

        names = {
            "unicast": RouteType.UNICAST,
            "blackhole": RouteType.BLACKHOLE,
            "unreachable": RouteType.UNREACHABLE,
            "prohibit": RouteType.PROHIBIT,
            "throw": RouteType.THROW,
        }
        numbers = {
            1: RouteType.UNICAST,
            6: RouteType.BLACKHOLE,
            7: RouteType.UNREACHABLE,
            8: RouteType.PROHIBIT,
            9: RouteType.THROW,
        }

        if isinstance(value, str):
            lowered = value.casefold()
            if lowered in names:
                return names[lowered]
            if value.isdecimal():
                value = int(value)

        if isinstance(value, int) and not isinstance(value, bool):
            route_type = numbers.get(value)
            if route_type is not None:
                return route_type

        raise KernelError(
            f"route inventory: unsupported route type {value!r}"
        )

    @staticmethod
    def _parse_route_protocol(value: object) -> int:
        # iproute2 omits RTPROT_BOOT (3) unless detailed output is requested.
        if value is None:
            return 3

        if isinstance(value, str) and value.isdecimal():
            value = int(value)

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 255
        ):
            raise KernelError(
                f"route inventory: invalid numeric protocol {value!r}"
            )

        return value

    @staticmethod
    def _parse_optional_metric(value: object) -> int | None:
        if value is None:
            return None
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= MAX_ROUTE_METRIC
        ):
            raise KernelError(
                f"route inventory: invalid metric {value!r}"
            )
        return value

    @classmethod
    def _parse_route_entry(cls, entry: object) -> RouteSpec:
        if not isinstance(entry, dict):
            raise KernelError(
                f"route inventory: expected object, got "
                f"{type(entry).__name__}"
            )

        # These forms cannot be represented faithfully by the current
        # single-next-hop RouteSpec.  Never silently omit them from ACTUAL.
        for unsupported in ("nexthops", "nhid", "multipath"):
            if unsupported in entry:
                raise KernelError(
                    "route inventory: unsupported multi/nexthop route "
                    f"contains {unsupported!r}: {entry!r}"
                )

        table = entry.get("table")
        if table not in (None, "main", 254, "254"):
            raise KernelError(
                f"route inventory: unexpected non-main table {table!r}"
            )

        gateway_value = entry.get("gateway")
        gateway: IPv4Address | None
        if gateway_value is None:
            gateway = None
        elif isinstance(gateway_value, str):
            try:
                gateway = IPv4Address(gateway_value)
            except ValueError as exc:
                raise KernelError(
                    f"route inventory: invalid IPv4 gateway "
                    f"{gateway_value!r}"
                ) from exc
        else:
            raise KernelError(
                f"route inventory: invalid gateway {gateway_value!r}"
            )

        if "via" in entry:
            raise KernelError(
                "route inventory: cross-family/structured via is not "
                f"representable: {entry['via']!r}"
            )

        interface = entry.get("dev")
        if interface is not None and (
            not isinstance(interface, str) or not interface
        ):
            raise KernelError(
                f"route inventory: invalid interface {interface!r}"
            )

        flags = entry.get("flags", [])
        if not isinstance(flags, list) or not all(
            isinstance(flag, str) for flag in flags
        ):
            raise KernelError(
                f"route inventory: invalid flags {flags!r}"
            )

        return RouteSpec(
            destination=cls._parse_route_destination(entry.get("dst")),
            route_type=cls._parse_route_type(entry.get("type")),
            via=gateway,
            interface=interface,
            metric=cls._parse_optional_metric(entry.get("metric")),
            proto=cls._parse_route_protocol(entry.get("protocol")),
            onlink="onlink" in flags,
        )

    def list_routes(self) -> frozenset[RouteSpec]:
        """
        Return normalized main-table IPv4 routes from iproute2 JSON.

        `-N` forces protocol/scope identifiers to numeric form.  The adapter
        still normalizes the protocol omitted by iproute2 for RTPROT_BOOT.
        Structurally unrepresentable multipath/nexthop routes fail inventory
        instead of being silently omitted from ACTUAL.
        """
        completed = self._run(
            (
                "ip",
                "-j",
                "-N",
                "-4",
                "route",
                "show",
                "table",
                "main",
            )
        )
        payload = self._load_json_array(
            completed.stdout,
            context="route inventory",
        )
        return frozenset(
            self._parse_route_entry(entry)
            for entry in payload
        )

    @staticmethod
    def _route_command_argv(
        action: str,
        route: RouteSpec,
    ) -> tuple[str, ...]:
        type_name = {
            RouteType.UNICAST: "unicast",
            RouteType.BLACKHOLE: "blackhole",
            RouteType.UNREACHABLE: "unreachable",
            RouteType.PROHIBIT: "prohibit",
            RouteType.THROW: "throw",
        }[route.route_type]

        if route.proto is None:
            raise KernelError(
                f"cannot materialize route with proto=None: {route!r}"
            )
        if not 0 <= route.proto <= 255:
            raise KernelError(
                f"cannot materialize route with invalid proto: {route!r}"
            )

        argv = [
            "ip",
            "-4",
            "route",
            action,
            type_name,
            str(route.destination),
            "table",
            "main",
            "proto",
            str(route.proto),
        ]

        if route.metric is not None:
            argv.extend(("metric", str(route.metric)))
        if route.via is not None:
            argv.extend(("via", str(route.via)))
        if route.interface is not None:
            argv.extend(("dev", route.interface))
        if route.onlink:
            argv.append("onlink")

        return tuple(argv)

    def add_route(self, route: RouteSpec) -> None:
        """Materialize one complete RouteSpec in the main IPv4 table."""
        self._run(self._route_command_argv("add", route))

    def delete_route(self, route: RouteSpec) -> None:
        """Delete the represented route from the main IPv4 table."""
        self._run(self._route_command_argv("del", route))

    def replace_route(self, route: RouteSpec) -> None:
        """Canonicalize one complete RouteSpec with `ip route replace`."""
        self._run(self._route_command_argv("replace", route))

    def list_interfaces(self) -> tuple[InterfaceRecord, ...]:
        """
        Return a typed snapshot of every interface and its local IPv4 addresses.

        The command is intentionally not filtered with `-4`: addressless and
        IPv6-only interfaces must remain visible to selector resolution.
        Duplicate records for one name may be merged only when their ifindex is
        identical; conflicting ifindex values are an invalid inventory.
        """
        completed = self._run(("ip", "-j", "addr", "show"))
        payload = self._load_json_array(
            completed.stdout,
            context="interface inventory",
        )

        mutable: dict[str, tuple[int, set[IPv4Address]]] = {}
        for entry in payload:
            if not isinstance(entry, dict):
                raise KernelError(
                    "interface inventory: expected object, got "
                    f"{type(entry).__name__}"
                )

            name = entry.get("ifname")
            if not isinstance(name, str) or not name:
                raise KernelError(
                    "interface inventory: invalid/missing ifname "
                    f"{name!r}"
                )

            ifindex = entry.get("ifindex")
            if (
                not isinstance(ifindex, int)
                or isinstance(ifindex, bool)
                or ifindex <= 0
            ):
                raise KernelError(
                    f"interface inventory: invalid/missing ifindex "
                    f"for {name!r}: {ifindex!r}"
                )

            existing = mutable.get(name)
            if existing is None:
                addresses: set[IPv4Address] = set()
                mutable[name] = (ifindex, addresses)
            else:
                existing_ifindex, addresses = existing
                if existing_ifindex != ifindex:
                    raise KernelError(
                        "interface inventory: duplicate ifname with "
                        f"conflicting ifindex: {name!r} has "
                        f"{existing_ifindex} and {ifindex}"
                    )

            address_info = entry.get("addr_info", [])
            if not isinstance(address_info, list):
                raise KernelError(
                    f"interface inventory: invalid addr_info for "
                    f"{name!r}: {address_info!r}"
                )

            for info in address_info:
                if not isinstance(info, dict):
                    raise KernelError(
                        "interface inventory: invalid address object "
                        f"for {name!r}: {info!r}"
                    )
                if info.get("family") != "inet":
                    continue

                local = info.get("local")
                if not isinstance(local, str) or not local:
                    raise KernelError(
                        "interface inventory: missing local IPv4 "
                        f"for {name!r}: {info!r}"
                    )
                try:
                    addresses.add(IPv4Address(local))
                except ValueError as exc:
                    raise KernelError(
                        "interface inventory: invalid local IPv4 "
                        f"{local!r} for {name!r}"
                    ) from exc

        return tuple(
            InterfaceRecord(
                name=name,
                ifindex=ifindex,
                ipv4=frozenset(addresses),
            )
            for name, (ifindex, addresses) in sorted(mutable.items())
        )

    def list_interface_ipv4(
        self,
    ) -> Mapping[str, frozenset[IPv4Address]]:
        """
        Return every interface and its local IPv4 addresses.

        The command is intentionally not filtered with `-4`: Debian 13
        iproute2 omits addressless interfaces from `ip -j -4 addr show`.
        Reading all families preserves interface existence; only
        `addr_info[].family == "inet"` contributes addresses.

        `addr_info[].local` is authoritative for tun/point-to-point interfaces;
        peer/address/broadcast fields are deliberately ignored.
        """
        completed = self._run(("ip", "-j", "addr", "show"))
        payload = self._load_json_array(
            completed.stdout,
            context="IPv4 address inventory",
        )

        mutable: dict[str, set[IPv4Address]] = {}
        for entry in payload:
            if not isinstance(entry, dict):
                raise KernelError(
                    "IPv4 address inventory: expected object, got "
                    f"{type(entry).__name__}"
                )

            interface = entry.get("ifname")
            if not isinstance(interface, str) or not interface:
                raise KernelError(
                    "IPv4 address inventory: invalid/missing ifname "
                    f"{interface!r}"
                )

            addresses = mutable.setdefault(interface, set())
            address_info = entry.get("addr_info", [])
            if not isinstance(address_info, list):
                raise KernelError(
                    f"IPv4 address inventory: invalid addr_info for "
                    f"{interface!r}: {address_info!r}"
                )

            for info in address_info:
                if not isinstance(info, dict):
                    raise KernelError(
                        "IPv4 address inventory: invalid address object "
                        f"for {interface!r}: {info!r}"
                    )
                if info.get("family") not in (None, "inet"):
                    continue

                local = info.get("local")
                if not isinstance(local, str) or not local:
                    raise KernelError(
                        "IPv4 address inventory: missing local address "
                        f"for {interface!r}: {info!r}"
                    )
                try:
                    addresses.add(IPv4Address(local))
                except ValueError as exc:
                    raise KernelError(
                        "IPv4 address inventory: invalid local IPv4 "
                        f"{local!r} for {interface!r}"
                    ) from exc

        return MappingProxyType(
            {
                interface: frozenset(addresses)
                for interface, addresses in mutable.items()
            }
        )

    def get_ip_forward(self) -> bool:
        """Read daemon-owned IPv4 forwarding state from procfs."""
        try:
            value = IP_FORWARD_PATH.read_text(encoding="ascii").strip()
        except OSError as exc:
            raise KernelError(
                f"failed to read {IP_FORWARD_PATH}: {exc}"
            ) from exc

        if value == "0":
            return False
        if value == "1":
            return True
        raise KernelError(
            f"unexpected {IP_FORWARD_PATH} value: {value!r}"
        )

    def set_ip_forward(self, enabled: bool) -> None:
        """Set daemon-owned IPv4 forwarding state through procfs."""
        try:
            IP_FORWARD_PATH.write_text(
                "1\n" if enabled else "0\n",
                encoding="ascii",
            )
        except OSError as exc:
            raise KernelError(
                f"failed to write {IP_FORWARD_PATH}: {exc}"
            ) from exc

    def iptables_save(self) -> str:
        """Return canonical filter+nat inventory from iptables-save."""
        # Debian 13 iptables-save (iptables-nft 1.8.11) has no -w/--wait
        # option.  Only iptables-restore uses the bounded xtables wait below.
        filter_save = self._run(
            ("iptables-save", "-t", "filter")
        ).stdout
        nat_save = self._run(
            ("iptables-save", "-t", "nat")
        ).stdout
        return filter_save.rstrip("\n") + "\n" + nat_save.rstrip("\n") + "\n"

    def iptables_restore(self, payload: str, *, noflush: bool = True) -> None:
        """Apply an in-memory restore payload with bounded xtables wait."""
        argv = [
            "iptables-restore",
            "-w",
            str(self.iptables_wait_seconds),
        ]
        if noflush:
            argv.append("--noflush")
        self._run(tuple(argv), input_text=payload)


# ---------------------------------------------------------------------------
# Lifetime process lock
# ---------------------------------------------------------------------------


