from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
import json
from typing import Callable, Mapping, Sequence

from .device_engine import EnvironmentInterface, InterfaceIdentity


class EnvironmentParseError(ValueError):
    pass


class EnvironmentCollectError(RuntimeError):
    pass


@dataclass(frozen=True)
class InterfaceIPv4Address:
    identity: InterfaceIdentity
    address: IPv4Address
    prefixlen: int


@dataclass(frozen=True)
class RouteNexthop:
    ifname: str
    weight: int = 1


@dataclass(frozen=True)
class KernelRoute:
    table: int
    destination: IPv4Network
    route_type: str
    protocol: str | int | None
    metric: int | None
    ifname: str | None
    nexthops: tuple[RouteNexthop, ...]


@dataclass(frozen=True)
class KernelRule:
    priority: int
    table: int | None
    action: str
    source: IPv4Network | None = None
    destination: IPv4Network | None = None
    iif: str | None = None


@dataclass(frozen=True)
class EnvironmentSnapshot:
    interfaces: tuple[EnvironmentInterface, ...]
    ipv4_addresses: tuple[InterfaceIPv4Address, ...] = ()
    routes: tuple[KernelRoute, ...] = ()
    rules: tuple[KernelRule, ...] = ()
    sysctls: tuple[tuple[str, str], ...] = ()

    @property
    def sysctl_map(self) -> Mapping[str, str]:
        return dict(self.sysctls)


def _load_json_array(text: str, what: str) -> list:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EnvironmentParseError(f"invalid {what} JSON: {exc}") from None
    if not isinstance(raw, list):
        raise EnvironmentParseError(f"{what} JSON root must be an array")
    return raw


def parse_ip_link_json(text: str) -> EnvironmentSnapshot:
    """Parse ordered `ip -j link show` output into the interface part of a snapshot."""

    raw = _load_json_array(text, "ip-link")
    out: list[EnvironmentInterface] = []
    seen_names: set[str] = set()
    seen_indexes: set[int] = set()

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise EnvironmentParseError(f"interface[{position}] must be an object")

        ifname = item.get("ifname")
        ifindex = item.get("ifindex")

        if not isinstance(ifname, str) or not ifname:
            raise EnvironmentParseError(
                f"interface[{position}].ifname must be a non-empty string"
            )
        if len(ifname.encode("utf-8")) > 15:
            raise EnvironmentParseError(
                f"interface[{position}].ifname exceeds Linux IFNAMSIZ-1"
            )
        if type(ifindex) is not int or ifindex <= 0:
            raise EnvironmentParseError(
                f"interface[{position}].ifindex must be a positive integer"
            )
        if ifname in seen_names:
            raise EnvironmentParseError(
                f"duplicate interface name {ifname!r} in one snapshot"
            )
        if ifindex in seen_indexes:
            raise EnvironmentParseError(
                f"duplicate ifindex {ifindex} in one snapshot"
            )

        seen_names.add(ifname)
        seen_indexes.add(ifindex)
        out.append(EnvironmentInterface(InterfaceIdentity(ifname, ifindex)))

    return EnvironmentSnapshot(tuple(out))


def parse_ip_addr_json(
    text: str,
    interfaces: Sequence[EnvironmentInterface],
) -> tuple[InterfaceIPv4Address, ...]:
    """Parse `ip -j -4 addr show` and bind addresses to observed interface identity."""

    raw = _load_json_array(text, "ip-addr")
    by_name = {item.identity.ifname: item.identity for item in interfaces}
    out: list[InterfaceIPv4Address] = []

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise EnvironmentParseError(f"address-interface[{position}] must be an object")
        ifname = item.get("ifname")
        if ifname not in by_name:
            raise EnvironmentParseError(
                f"address-interface[{position}] references unobserved interface {ifname!r}"
            )
        ifindex = item.get("ifindex")
        if ifindex is not None and ifindex != by_name[ifname].ifindex:
            raise EnvironmentParseError(
                f"address-interface[{position}] identity mismatch for {ifname!r}: "
                f"link ifindex={by_name[ifname].ifindex}, addr ifindex={ifindex!r}"
            )
        addr_info = item.get("addr_info", [])
        if not isinstance(addr_info, list):
            raise EnvironmentParseError(
                f"address-interface[{position}].addr_info must be an array"
            )

        for addr_position, addr in enumerate(addr_info):
            if not isinstance(addr, dict):
                raise EnvironmentParseError(
                    f"address-interface[{position}].addr_info[{addr_position}] must be an object"
                )
            if addr.get("family") != "inet":
                continue
            local = addr.get("local")
            prefixlen = addr.get("prefixlen")
            try:
                parsed = IPv4Address(local)
            except Exception:
                raise EnvironmentParseError(
                    f"invalid IPv4 address {local!r} on {ifname!r}"
                ) from None
            if type(prefixlen) is not int or not 0 <= prefixlen <= 32:
                raise EnvironmentParseError(
                    f"invalid IPv4 prefixlen {prefixlen!r} on {ifname!r}"
                )
            out.append(
                InterfaceIPv4Address(
                    identity=by_name[ifname],
                    address=parsed,
                    prefixlen=prefixlen,
                )
            )

    return tuple(out)


def _parse_table(value: object, what: str) -> int:
    if type(value) is int and value >= 0:
        return value
    aliases = {"local": 255, "main": 254, "default": 253, "unspec": 0}
    if isinstance(value, str):
        if value in aliases:
            return aliases[value]
        if value.isdecimal():
            return int(value)
    raise EnvironmentParseError(f"{what} has unsupported table {value!r}")


def _parse_protocol(value: object, what: str) -> str | int | None:
    if value is None:
        return None
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value:
        if value.isdecimal():
            return int(value)
        return value
    raise EnvironmentParseError(f"{what} has unsupported protocol {value!r}")


def _parse_network(value: object, *, default: str, what: str) -> IPv4Network:
    if value in (None, "default", "all"):
        value = default
    if not isinstance(value, str):
        raise EnvironmentParseError(f"{what} must be an IPv4 prefix")
    try:
        return IPv4Network(value, strict=True)
    except Exception:
        raise EnvironmentParseError(f"{what} is not a strict IPv4 prefix: {value!r}") from None


def parse_ip_route_json(text: str) -> tuple[KernelRoute, ...]:
    """Parse `ip -j -4 route show table all` into semantic route observations."""

    raw = _load_json_array(text, "ip-route")
    out: list[KernelRoute] = []

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise EnvironmentParseError(f"route[{position}] must be an object")

        table = _parse_table(item.get("table", "main"), f"route[{position}]")
        destination = _parse_network(
            item.get("dst"),
            default="0.0.0.0/0",
            what=f"route[{position}].dst",
        )
        route_type = item.get("type", "unicast")
        if not isinstance(route_type, str) or not route_type:
            raise EnvironmentParseError(f"route[{position}].type must be a string")

        metric = item.get("metric")
        if metric is not None and (type(metric) is not int or metric < 0):
            raise EnvironmentParseError(f"route[{position}].metric must be non-negative")

        ifname = item.get("dev")
        if ifname is not None and (not isinstance(ifname, str) or not ifname):
            raise EnvironmentParseError(f"route[{position}].dev must be a string")

        multipath = item.get("multipath", [])
        if not isinstance(multipath, list):
            raise EnvironmentParseError(f"route[{position}].multipath must be an array")
        nexthops: list[RouteNexthop] = []
        for nh_position, nh in enumerate(multipath):
            if not isinstance(nh, dict):
                raise EnvironmentParseError(
                    f"route[{position}].multipath[{nh_position}] must be an object"
                )
            dev = nh.get("dev")
            weight = nh.get("weight", 1)
            if not isinstance(dev, str) or not dev:
                raise EnvironmentParseError(
                    f"route[{position}].multipath[{nh_position}].dev must be a string"
                )
            if type(weight) is not int or weight <= 0:
                raise EnvironmentParseError(
                    f"route[{position}].multipath[{nh_position}].weight must be positive"
                )
            nexthops.append(RouteNexthop(dev, weight))

        out.append(
            KernelRoute(
                table=table,
                destination=destination,
                route_type=route_type,
                protocol=_parse_protocol(
                    item.get("protocol"),
                    f"route[{position}].protocol",
                ),
                metric=metric,
                ifname=ifname,
                nexthops=tuple(nexthops),
            )
        )

    return tuple(out)


def parse_ip_rule_json(text: str) -> tuple[KernelRule, ...]:
    """Parse `ip -j -4 rule show` into semantic RPDB observations."""

    raw = _load_json_array(text, "ip-rule")
    out: list[KernelRule] = []

    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise EnvironmentParseError(f"rule[{position}] must be an object")
        priority = item.get("priority", item.get("pref"))
        if type(priority) is not int or priority < 0:
            raise EnvironmentParseError(f"rule[{position}].priority must be non-negative")

        action = item.get("action", "to_tbl")
        if not isinstance(action, str) or not action:
            raise EnvironmentParseError(f"rule[{position}].action must be a string")

        table_value = item.get("table")
        table = None if table_value is None else _parse_table(table_value, f"rule[{position}]")

        source = item.get("src")
        destination = item.get("dst")
        out.append(
            KernelRule(
                priority=priority,
                table=table,
                action=action,
                source=(
                    None
                    if source in (None, "all")
                    else _parse_network(source, default="0.0.0.0/0", what=f"rule[{position}].src")
                ),
                destination=(
                    None
                    if destination in (None, "all")
                    else _parse_network(destination, default="0.0.0.0/0", what=f"rule[{position}].dst")
                ),
                iif=item.get("iif"),
            )
        )

    return tuple(out)


CommandRunner = Callable[[tuple[str, ...]], str]


def _ns_command(namespace: str, args: tuple[str, ...]) -> tuple[str, ...]:
    if not namespace:
        raise EnvironmentCollectError("namespace must be a non-empty string")
    return ("ip", "netns", "exec", namespace, *args)


def collect_environment_snapshot(
    namespace: str,
    run: CommandRunner,
) -> EnvironmentSnapshot:
    """Collect one production EnvironmentSnapshot through an injected command runner.

    Every command is executed in the same ROU namespace. The caller is responsible for
    serialization against namespace teardown; individual command failure aborts collection
    and no partial snapshot is returned.
    """

    try:
        link_text = run(_ns_command(namespace, ("ip", "-j", "link", "show")))
        link_snapshot = parse_ip_link_json(link_text)
        addr_text = run(_ns_command(namespace, ("ip", "-j", "-4", "addr", "show")))
        route_text = run(
            _ns_command(namespace, ("ip", "-j", "-4", "route", "show", "table", "all"))
        )
        rule_text = run(_ns_command(namespace, ("ip", "-j", "-4", "rule", "show")))
        global_sysctl_keys = (
            "net.ipv4.ip_forward",
            "net.ipv4.conf.all.rp_filter",
            "net.ipv4.conf.default.rp_filter",
            "net.ipv6.conf.all.forwarding",
            "net.ipv6.conf.default.forwarding",
        )
        sysctls: list[tuple[str, str]] = [
            (
                key,
                run(_ns_command(namespace, ("sysctl", "-n", key))).strip(),
            )
            for key in global_sysctl_keys
        ]
        for interface in link_snapshot.interfaces:
            ifname = interface.identity.ifname
            for key, proc_path in (
                (
                    f"net.ipv4.conf.{ifname}.rp_filter",
                    f"/proc/sys/net/ipv4/conf/{ifname}/rp_filter",
                ),
                (
                    f"net.ipv6.conf.{ifname}.disable_ipv6",
                    f"/proc/sys/net/ipv6/conf/{ifname}/disable_ipv6",
                ),
            ):
                sysctls.append(
                    (
                        key,
                        run(_ns_command(namespace, ("cat", proc_path))).strip(),
                    )
                )

        final_link_text = run(_ns_command(namespace, ("ip", "-j", "link", "show")))
        final_link_snapshot = parse_ip_link_json(final_link_text)
        if final_link_snapshot.interfaces != link_snapshot.interfaces:
            raise EnvironmentCollectError(
                "environment changed during collection: interface identity/order is unstable"
            )
    except EnvironmentParseError:
        raise
    except Exception as exc:
        raise EnvironmentCollectError(f"environment collection failed: {exc}") from exc

    return EnvironmentSnapshot(
        interfaces=link_snapshot.interfaces,
        ipv4_addresses=parse_ip_addr_json(addr_text, link_snapshot.interfaces),
        routes=parse_ip_route_json(route_text),
        rules=parse_ip_rule_json(rule_text),
        sysctls=tuple(sysctls),
    )
