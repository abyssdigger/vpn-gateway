from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Interface, IPv4Network
import json
import re

from .command_backend import CommandBackend, NamespaceBackend
from .device_engine import DeviceBindingSnapshot
from .domain import ActiveConfig
from .environment import collect_environment_snapshot
from .firewall_kernel import apply_filter_state, observe_filter_state
from .firewall_state import compile_filter_state
from .namespace_prereq import verify_namespace_prerequisites


_IFNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class InstanceConfigError(ValueError):
    pass


class InstanceLifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstanceConfig:
    namespace: str
    host_if: str
    inner_if: str
    host_address: IPv4Interface
    inner_address: IPv4Interface

    def __post_init__(self) -> None:
        if not _NAMESPACE_RE.fullmatch(self.namespace):
            raise InstanceConfigError(
                f"invalid namespace name {self.namespace!r}"
            )
        for field_name, value in (
            ("host_if", self.host_if),
            ("inner_if", self.inner_if),
        ):
            if not _IFNAME_RE.fullmatch(value):
                raise InstanceConfigError(
                    f"{field_name} is not a valid Linux interface name: {value!r}"
                )
        if self.inner_if != "host0":
            raise InstanceConfigError(
                "current production model requires inner_if='host0'"
            )
        if self.host_if == self.inner_if:
            raise InstanceConfigError("host_if and inner_if must differ")
        if self.host_address.ip == self.inner_address.ip:
            raise InstanceConfigError("host and inner addresses must differ")
        if self.host_address.network != self.inner_address.network:
            raise InstanceConfigError(
                "host and inner addresses must belong to the same IPv4 network"
            )
        if self.host_address.network.prefixlen <= 30 and self.host_address.ip in {
            self.host_address.network.network_address,
            self.host_address.network.broadcast_address,
        }:
            raise InstanceConfigError("host address is not usable in its subnet")
        if self.inner_address.network.prefixlen <= 30 and self.inner_address.ip in {
            self.inner_address.network.network_address,
            self.inner_address.network.broadcast_address,
        }:
            raise InstanceConfigError("inner address is not usable in its subnet")

    @property
    def link_network(self) -> IPv4Network:
        return self.host_address.network


@dataclass(frozen=True)
class InstanceVerification:
    ok: bool
    errors: tuple[str, ...]


def _namespace_names(host: CommandBackend) -> tuple[str, ...]:
    result = host.run(("ip", "netns", "list"))
    names: list[str] = []
    for line in result.stdout.splitlines():
        first = line.strip().split(maxsplit=1)
        if first:
            names.append(first[0])
    return tuple(names)


def _json_array(text: str, what: str) -> list[dict]:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InstanceLifecycleError(
            f"invalid {what} JSON: {exc}"
        ) from None
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise InstanceLifecycleError(f"{what} JSON must be an array of objects")
    return raw


def _missing_link_error(stderr: str) -> bool:
    lowered = stderr.lower()
    return (
        "does not exist" in lowered
        or "cannot find device" in lowered
        or "device not found" in lowered
    )


def _host_link_detail(
    host: CommandBackend,
    ifname: str,
) -> dict | None:
    result = host.run(
        ("ip", "-j", "-d", "link", "show", "dev", ifname),
        check=False,
    )
    if result.returncode != 0:
        if _missing_link_error(result.stderr):
            return None
        raise InstanceLifecycleError(
            f"cannot inspect host interface {ifname!r}: {result.stderr.strip()}"
        )
    raw = _json_array(result.stdout, f"host interface {ifname!r}")
    if len(raw) != 1:
        raise InstanceLifecycleError(
            f"host interface {ifname!r} snapshot is ambiguous"
        )
    return raw[0]


def _host_link_exists(host: CommandBackend, ifname: str) -> bool:
    return _host_link_detail(host, ifname) is not None


def _namespace_link_detail(
    ns: NamespaceBackend,
    ifname: str,
) -> dict | None:
    result = ns.run(
        ("ip", "-j", "-d", "link", "show", "dev", ifname),
        check=False,
    )
    if result.returncode != 0:
        if _missing_link_error(result.stderr):
            return None
        raise InstanceLifecycleError(
            f"cannot inspect inner interface {ifname!r}: {result.stderr.strip()}"
        )
    raw = _json_array(result.stdout, f"inner interface {ifname!r}")
    if len(raw) != 1:
        raise InstanceLifecycleError(
            f"inner interface {ifname!r} snapshot is ambiguous"
        )
    return raw[0]


def _namespace_link_snapshot(
    ns: NamespaceBackend,
    ifname: str,
) -> list[dict]:
    result = ns.run(
        ("ip", "-j", "-4", "addr", "show", "dev", ifname),
        check=False,
    )
    if result.returncode != 0:
        return []
    return _json_array(result.stdout, f"address snapshot for {ifname!r}")


def verify_instance(
    config: InstanceConfig,
    host: CommandBackend,
    *,
    forwarding: bool | None = False,
) -> InstanceVerification:
    errors: list[str] = []

    namespaces = _namespace_names(host)
    if config.namespace not in namespaces:
        errors.append(f"namespace {config.namespace!r} is missing")
        return InstanceVerification(False, tuple(errors))

    host_detail = _host_link_detail(host, config.host_if)
    if host_detail is None:
        errors.append(f"host interface {config.host_if!r} is missing")
    else:
        if host_detail.get("linkinfo", {}).get("info_kind") != "veth":
            errors.append(f"host interface {config.host_if!r} is not a veth")
        if "UP" not in host_detail.get("flags", []):
            errors.append(f"host interface {config.host_if!r} is not UP")

    ns = NamespaceBackend(config.namespace, host)
    inner_detail = _namespace_link_detail(ns, config.inner_if)
    if inner_detail is None:
        errors.append(f"inner interface {config.inner_if!r} is missing")
    else:
        if inner_detail.get("linkinfo", {}).get("info_kind") != "veth":
            errors.append(f"inner interface {config.inner_if!r} is not a veth")
        if "UP" not in inner_detail.get("flags", []):
            errors.append(f"inner interface {config.inner_if!r} is not UP")

    inner = _namespace_link_snapshot(ns, config.inner_if)
    if len(inner) != 1:
        errors.append(f"inner interface {config.inner_if!r} address snapshot is invalid")
    else:
        addresses = {
            (item.get("local"), item.get("prefixlen"))
            for item in inner[0].get("addr_info", [])
            if item.get("family") == "inet"
        }
        if (
            str(config.inner_address.ip),
            config.inner_address.network.prefixlen,
        ) not in addresses:
            errors.append(
                f"inner IPv4 interface {config.inner_address.with_prefixlen} is missing"
            )

    host_result = host.run(
        ("ip", "-j", "-4", "addr", "show", "dev", config.host_if),
        check=False,
    )
    if host_result.returncode == 0:
        try:
            host_raw = json.loads(host_result.stdout)
        except json.JSONDecodeError as exc:
            raise InstanceLifecycleError(
                f"invalid host link JSON for {config.host_if!r}: {exc}"
            ) from None
        if len(host_raw) != 1:
            errors.append(f"host interface {config.host_if!r} snapshot is ambiguous")
        else:
            addresses = {
                (item.get("local"), item.get("prefixlen"))
                for item in host_raw[0].get("addr_info", [])
                if item.get("family") == "inet"
            }
            if (
                str(config.host_address.ip),
                config.host_address.network.prefixlen,
            ) not in addresses:
                errors.append(
                    f"host IPv4 interface {config.host_address.with_prefixlen} is missing"
                )

    main = ns.run(
        ("ip", "-j", "-4", "route", "show", "table", "main"),
        check=False,
    )
    if main.returncode != 0:
        errors.append("cannot observe namespace main routing table")
    else:
        try:
            routes = json.loads(main.stdout)
        except json.JSONDecodeError as exc:
            raise InstanceLifecycleError(
                f"invalid namespace main-route JSON: {exc}"
            ) from None
        default_ok = any(
            route.get("dst", "default") == "default"
            and route.get("gateway") == str(config.host_address.ip)
            and route.get("dev") == config.inner_if
            for route in routes
            if isinstance(route, dict)
        )
        if not default_ok:
            errors.append("namespace underlay default route is missing")


    try:
        filter_text = observe_filter_state(ns)
    except Exception as exc:
        errors.append(f"cannot observe namespace filter table: {exc}")
    else:
        required_policies = {
            ":INPUT DROP [0:0]",
            ":FORWARD DROP [0:0]",
            ":OUTPUT DROP [0:0]",
        }
        filter_lines = set(filter_text.splitlines())
        missing_policies = sorted(required_policies - filter_lines)
        if missing_policies:
            errors.append(
                "namespace filter default policies are not fail-closed: "
                + ", ".join(missing_policies)
            )

    try:
        snapshot = collect_environment_snapshot(
            config.namespace,
            lambda argv: host.run(argv).stdout,
        )
    except Exception as exc:
        errors.append(f"cannot collect namespace prerequisite snapshot: {exc}")
    else:
        expected_forwarding = forwarding
        if expected_forwarding is None:
            observed_forwarding = snapshot.sysctl_map.get(
                "net.ipv4.ip_forward"
            )
            if observed_forwarding not in {"0", "1"}:
                errors.append(
                    "namespace IPv4 forwarding state is not observable"
                )
                expected_forwarding = False
            else:
                expected_forwarding = observed_forwarding == "1"

        prereq = verify_namespace_prerequisites(
            snapshot,
            DeviceBindingSnapshot((), ()),
            forwarding=expected_forwarding,
        )
        errors.extend(prereq.errors)

    return InstanceVerification(not errors, tuple(errors))


def create_instance(
    config: InstanceConfig,
    host: CommandBackend,
) -> None:
    """Create a fresh ROU namespace/veth appliance in fail-closed state."""

    if config.namespace in _namespace_names(host):
        raise InstanceLifecycleError(
            f"refusing to reuse existing namespace {config.namespace!r}"
        )
    if _host_link_exists(host, config.host_if):
        raise InstanceLifecycleError(
            f"refusing to reuse existing host interface {config.host_if!r}"
        )

    created_namespace = False
    try:
        host.run(("ip", "netns", "add", config.namespace))
        created_namespace = True

        host.run(
            (
                "ip", "link", "add", config.host_if,
                "type", "veth", "peer", "name", config.inner_if,
            )
        )
        host.run(
            ("ip", "link", "set", config.inner_if, "netns", config.namespace)
        )
        host.run(
            (
                "ip", "addr", "add", config.host_address.with_prefixlen,
                "dev", config.host_if,
            )
        )
        host.run(("ip", "link", "set", config.host_if, "up"))

        ns = NamespaceBackend(config.namespace, host)
        ns.run(("ip", "link", "set", "lo", "up"))
        ns.run(
            (
                "ip", "addr", "add", config.inner_address.with_prefixlen,
                "dev", config.inner_if,
            )
        )
        ns.run(("ip", "link", "set", config.inner_if, "up"))
        ns.run(
            (
                "ip", "route", "replace", "default",
                "via", str(config.host_address.ip),
                "dev", config.inner_if,
            )
        )

        ns.run(("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"))
        ns.run(("sysctl", "-q", "-w", "net/ipv4/conf/all/rp_filter=0"))
        ns.run(("sysctl", "-q", "-w", "net/ipv4/conf/default/rp_filter=0"))
        ns.run(
            (
                "sysctl", "-q", "-w",
                f"net/ipv4/conf/{config.inner_if}/rp_filter=0",
            )
        )
        ns.run(("sysctl", "-q", "-w", "net/ipv6/conf/all/forwarding=0"))
        ns.run(("sysctl", "-q", "-w", "net/ipv6/conf/default/forwarding=0"))
        ns.run(("sysctl", "-q", "-w", "net/ipv6/conf/default/disable_ipv6=1"))
        ns.run(
            (
                "sysctl", "-q", "-w",
                f"net/ipv6/conf/{config.inner_if}/disable_ipv6=1",
            )
        )


        bootstrap_filter = compile_filter_state(
            ActiveConfig({}, {}),
            DeviceBindingSnapshot((), ()),
        )
        apply_filter_state(bootstrap_filter, ns)

        verified = verify_instance(config, host)
        if not verified.ok:
            raise InstanceLifecycleError(
                "created instance failed verification: "
                + "; ".join(verified.errors)
            )
    except Exception:
        if created_namespace:
            host.run(
                ("ip", "netns", "del", config.namespace),
                check=False,
            )
        host.run(
            ("ip", "link", "del", config.host_if),
            check=False,
        )
        raise



def ensure_instance(
    config: InstanceConfig,
    host: CommandBackend,
) -> None:
    """Ensure the owned instance exists in verified fail-closed form.

    This is intended for systemd ExecStartPre and boot recovery:

    - fully absent namespace+host-veth -> create a fresh instance;
    - fully present -> close forwarding, then verify exact owned structure/prerequisites;
    - partially present -> structural error; never guess/adopt/repair ownership.
    """

    namespaces = _namespace_names(host)
    namespace_exists = config.namespace in namespaces
    host_link_exists = _host_link_exists(host, config.host_if)

    if not namespace_exists and not host_link_exists:
        create_instance(config, host)
        return

    if namespace_exists != host_link_exists:
        raise InstanceLifecycleError(
            "instance infrastructure is partially present; "
            f"namespace_exists={namespace_exists} "
            f"host_link_exists={host_link_exists}"
        )

    ns = NamespaceBackend(config.namespace, host)
    ns.run(
        ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
        check=False,
    )
    verified = verify_instance(config, host, forwarding=False)
    if not verified.ok:
        raise InstanceLifecycleError(
            "existing instance failed fail-closed verification: "
            + "; ".join(verified.errors)
        )


def contain_instance(
    config: InstanceConfig,
    host: CommandBackend,
) -> None:
    """Best-effort containment used by service stop/crash hooks."""

    if config.namespace not in _namespace_names(host):
        return
    NamespaceBackend(config.namespace, host).run(
        ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
        check=False,
    )


def destroy_instance(
    config: InstanceConfig,
    host: CommandBackend,
) -> None:
    """Fail-close and remove ROU namespace/veth resources owned by the instance."""

    namespaces = _namespace_names(host)
    if config.namespace in namespaces:
        ns = NamespaceBackend(config.namespace, host)
        ns.run(
            ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
            check=False,
        )
        host.run(
            ("ip", "netns", "del", config.namespace),
            check=False,
        )

    host.run(
        ("ip", "link", "del", config.host_if),
        check=False,
    )

    if config.namespace in _namespace_names(host):
        raise InstanceLifecycleError(
            f"namespace {config.namespace!r} still exists after teardown"
        )
    if _host_link_exists(host, config.host_if):
        raise InstanceLifecycleError(
            f"host interface {config.host_if!r} still exists after teardown"
        )
