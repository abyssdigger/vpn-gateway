"""Linux nft Driver for Device-firewall observation and mutation primitives."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from .device_firewall_desired import (
    DeviceFirewallChainSpec,
    DeviceFirewallRuleSpec,
)
from .device_firewall_structure import (
    DEVICE_FIREWALL_CHILD_COMMENT,
    DEVICE_FIREWALL_FALLTHROUGH_COMMENT,
    DEVICE_FIREWALL_JUMP_COMMENT,
    DEVICE_FIREWALL_RULE_COMMENT,
    DeviceFirewallRuleAction,
)
from .interface_identity import InterfaceIdentity
from .interface_inventory import parse_ip_link_inventory
from .ip_port import is_ip_port
from .linux_nft_scaffold import NftScriptRunner
from .nft_namespace_inventory import (
    NftNamespaceObservation,
    parse_nft_namespace_ruleset,
)


@dataclass(frozen=True, slots=True)
class DeviceFirewallPhysicalSnapshot:
    """Stable link-generation bracket plus the corresponding nft observation."""

    observation: NftNamespaceObservation
    interfaces: tuple[InterfaceIdentity, ...]


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(slots=True)
class LinuxDeviceFirewallDriver:
    """Observe and mutate the owned Device-firewall nft representation."""

    runner: NftScriptRunner
    namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise ValueError("namespace must be a non-empty string")

    def _cmd(self, *args: str) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.namespace, *args)

    def _links(self):
        return parse_ip_link_inventory(
            self.runner.run(self._cmd("ip", "-j", "link", "show"))
        )

    def observe_device_firewall_snapshot(
        self,
    ) -> DeviceFirewallPhysicalSnapshot:
        """Fresh-observe nft state inside one stable interface-generation bracket."""

        before = self._links()
        nft = parse_nft_namespace_ruleset(
            self.runner.run(
                self._cmd("nft", "-j", "list", "ruleset")
            )
        )
        after = self._links()
        if before != after:
            raise RuntimeError(
                "interface identity inventory drift during nft observation"
            )
        return DeviceFirewallPhysicalSnapshot(nft, before)

    def delete_device_jump(self, handle: int) -> None:
        if type(handle) is not int or handle < 0:
            raise ValueError("handle must be a non-negative integer")
        self.runner.run(
            self._cmd(
                "nft",
                "delete",
                "rule",
                "ip",
                "vpn_gate",
                "payload_forward",
                "handle",
                str(handle),
            )
        )

    def delete_device_child_chain(self, name: str) -> None:
        _validate_identifier(name)
        script = (
            f"flush chain ip vpn_gate {name}\n"
            f"delete chain ip vpn_gate {name}\n"
        )
        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            script,
        )

    def create_device_chain(
        self,
        spec: DeviceFirewallChainSpec,
    ) -> None:
        """Create one compiled child chain and insert its dispatch before Profile rules."""

        if not isinstance(spec, DeviceFirewallChainSpec):
            raise ValueError("spec must be DeviceFirewallChainSpec")
        _validate_identifier(spec.child_chain_name)

        lines = [
            (
                f"add chain ip vpn_gate {spec.child_chain_name} "
                f'{{ comment "{DEVICE_FIREWALL_CHILD_COMMENT}"; }}'
            )
        ]
        for rule in spec.rules:
            predicate = _render_predicate(rule)
            action = _render_action(rule)
            comment = (
                DEVICE_FIREWALL_FALLTHROUGH_COMMENT
                if rule.terminal_fallthrough
                else DEVICE_FIREWALL_RULE_COMMENT
            )
            parts = [
                "add rule ip vpn_gate",
                spec.child_chain_name,
            ]
            if predicate:
                parts.append(predicate)
            parts.extend(
                (
                    action,
                    f'comment "{comment}"',
                )
            )
            lines.append(" ".join(parts))

        # EXP-044: insertion, not append, is required so Device policy is
        # evaluated before existing Profile NEW/RETURN accept rules.
        lines.append(
            " ".join(
                (
                    "insert rule ip vpn_gate payload_forward",
                    f"meta iif {spec.ingress.ifindex}",
                    f"meta oif {spec.egress.ifindex}",
                    f"jump {spec.child_chain_name}",
                    f'comment "{DEVICE_FIREWALL_JUMP_COMMENT}"',
                )
            )
        )

        self.runner.run_script(
            self._cmd("nft", "-f", "-"),
            "\n".join(lines) + "\n",
        )


def _validate_identifier(value: str) -> None:
    if (
        not isinstance(value, str)
        or not _SAFE_IDENTIFIER.fullmatch(value)
    ):
        raise ValueError("unsafe nft child-chain identifier")


def _render_predicate(rule: DeviceFirewallRuleSpec) -> str:
    parts: list[str] = []
    for raw in rule.match_expr_json:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("invalid desired Device firewall match JSON") from None
        if not isinstance(value, dict) or set(value) != {"match"}:
            raise ValueError("unsupported desired Device firewall expression")
        match = value["match"]
        if (
            not isinstance(match, dict)
            or set(match) != {"op", "left", "right"}
            or match["op"] != "=="
        ):
            raise ValueError("unsupported desired Device firewall match")

        left = match["left"]
        right = match["right"]
        if left == {"meta": {"key": "l4proto"}}:
            if right not in {"tcp", "udp", "icmp"}:
                raise ValueError("unsupported lower l4 protocol")
            parts.extend(("meta", "l4proto", right))
            continue

        if not isinstance(left, dict) or set(left) != {"payload"}:
            raise ValueError("unsupported lower Device firewall match left side")
        payload = left["payload"]
        if (
            not isinstance(payload, dict)
            or set(payload) != {"protocol", "field"}
        ):
            raise ValueError("unsupported lower payload selector")

        protocol = payload["protocol"]
        field = payload["field"]
        if protocol == "ip" and field in {"saddr", "daddr"}:
            parts.extend(("ip", field, _render_ip_operand(right)))
            continue
        if protocol in {"tcp", "udp"} and field in {"sport", "dport"}:
            parts.extend((protocol, field, _render_port_operand(right)))
            continue
        raise ValueError("unsupported lower Device firewall payload selector")

    return " ".join(parts)


def _render_port_operand(value: object) -> str:
    if type(value) is int:
        if not is_ip_port(value):
            raise ValueError("invalid lower Device firewall port")
        return str(value)

    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("invalid lower Device firewall port operand")

    if set(value) == {"range"}:
        first, last = _port_range(value["range"])
        return f"{first}-{last}"

    if set(value) == {"set"}:
        items = value["set"]
        if not isinstance(items, list) or not items:
            raise ValueError("invalid lower Device firewall port set")
        rendered: list[str] = []
        intervals: list[tuple[int, int]] = []
        for item in items:
            if type(item) is int:
                first = last = item
                if not is_ip_port(item):
                    raise ValueError("invalid lower Device firewall port set item")
                rendered.append(str(item))
            elif isinstance(item, dict) and set(item) == {"range"}:
                first, last = _port_range(item["range"])
                rendered.append(f"{first}-{last}")
            else:
                raise ValueError("invalid lower Device firewall port set item")
            for prior_first, prior_last in intervals:
                if first <= prior_last and prior_first <= last:
                    raise ValueError("overlapping lower Device firewall port set")
            intervals.append((first, last))
        return "{ " + ", ".join(rendered) + " }"

    raise ValueError("invalid lower Device firewall port operand")


def _port_range(value: object) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or type(value[0]) is not int
        or type(value[1]) is not int
        or not is_ip_port(value[0])
        or not is_ip_port(value[1])
        or value[0] > value[1]
    ):
        raise ValueError("invalid lower Device firewall port range")
    return value[0], value[1]


def _render_ip_operand(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or set(value) != {"prefix"}:
        raise ValueError("unsupported lower IPv4 operand")
    prefix = value["prefix"]
    if (
        not isinstance(prefix, dict)
        or set(prefix) != {"addr", "len"}
        or not isinstance(prefix["addr"], str)
        or type(prefix["len"]) is not int
    ):
        raise ValueError("invalid lower IPv4 prefix")
    return f"{prefix['addr']}/{prefix['len']}"


def _render_action(rule: DeviceFirewallRuleSpec) -> str:
    if rule.action is DeviceFirewallRuleAction.RETURN:
        if rule.action_json != '{"return":null}':
            raise ValueError("unexpected RETURN action JSON")
        return "return"
    if rule.action is DeviceFirewallRuleAction.DROP:
        if rule.action_json != '{"drop":null}':
            raise ValueError("unexpected DROP action JSON")
        return "drop"
    if rule.action is DeviceFirewallRuleAction.REJECT:
        if rule.action_json == '{"reject":{"type":"tcp reset"}}':
            return "reject with tcp reset"
        if (
            rule.action_json
            == '{"reject":{"expr":"port-unreachable","type":"icmp"}}'
        ):
            return "reject"
        raise ValueError("unsupported REJECT action JSON")
    raise ValueError("unsupported Device firewall action")
