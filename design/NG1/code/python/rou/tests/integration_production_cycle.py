from __future__ import annotations

from ipaddress import IPv4Interface, IPv4Network
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.command_backend import CommandBackend, CommandResult, SubprocessBackend
from rou.device_engine import ExpectedInterface, InterfaceMatch, MatchKind
from rou.domain import ActiveConfig, Device, Direction, NatMode, Profile
from rou.instance_lifecycle import InstanceConfig, destroy_instance, ensure_instance
from rou.planner import PlannerRuntimeState, reconcile_once
from rou.state_store import JsonRuntimeStateStore


NS = "vpn-gate-ng1-e2e"
HOST_IF = "roue2e0"
VPN_IF = "vpns00"
STATE_DIR = Path("/run/vpn-gateway-ng1-e2e")
STATE_FILE = STATE_DIR / "state.json"

INSTANCE = InstanceConfig(
    namespace=NS,
    host_if=HOST_IF,
    inner_if="host0",
    host_address=IPv4Interface("192.0.2.1/30"),
    inner_address=IPv4Interface("192.0.2.2/30"),
)

CONFIG = ActiveConfig(
    devices={
        "oc": Device(
            "oc",
            True,
            (
                ExpectedInterface(
                    InterfaceMatch(MatchKind.PREFIX, "vpns"),
                    1,
                ),
            ),
            nat=NatMode.NONE,
        ),
    },
    profiles={
        "corp": Profile(
            "corp",
            True,
            Direction.OUTBOUND,
            (IPv4Network("198.51.100.0/24"),),
            ("oc",),
        ),
    },
)


class RecordingBackend:
    def __init__(self):
        self.host = SubprocessBackend()
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        argv: tuple[str, ...],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        self.calls.append(argv)
        return self.host.run(
            argv,
            input_text=input_text,
            check=check,
        )

    def reset(self) -> None:
        self.calls.clear()

    def forwarding_writes(self) -> list[str]:
        return [
            arg
            for argv in self.calls
            for arg in argv
            if arg.startswith("net.ipv4.ip_forward=")
        ]


def ns(backend: CommandBackend, *argv: str, check: bool = True) -> CommandResult:
    return backend.run(
        ("ip", "netns", "exec", NS, *argv),
        check=check,
    )


def make_vpn_interface(backend: CommandBackend) -> int:
    ns(backend, "ip", "link", "add", VPN_IF, "type", "dummy")
    ns(backend, "ip", "link", "set", VPN_IF, "up")
    return int(
        ns(
            backend,
            "cat",
            f"/sys/class/net/{VPN_IF}/ifindex",
        ).stdout.strip()
    )


def delete_vpn_interface(backend: CommandBackend) -> None:
    ns(
        backend,
        "ip",
        "link",
        "del",
        VPN_IF,
        check=False,
    )


def nft_tables(backend: CommandBackend) -> str:
    return ns(backend, "nft", "list", "tables").stdout


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("integration test must run as root")

    backend = RecordingBackend()
    shutil.rmtree(STATE_DIR, ignore_errors=True)
    STATE_DIR.mkdir(mode=0o700, parents=True)
    store = JsonRuntimeStateStore(STATE_FILE)

    try:
        destroy_instance(INSTANCE, backend)
        ensure_instance(INSTANCE, backend)

        old_ifindex = make_vpn_interface(backend)
        backend.reset()

        first = reconcile_once(
            CONFIG,
            NS,
            PlannerRuntimeState.empty(),
            backend,
            persist_verified_state=store.save,
        )
        if not first.changed_kernel:
            raise RuntimeError("initial reconcile did not materialize kernel state")
        if backend.forwarding_writes()[-1:] != ["net.ipv4.ip_forward=1"]:
            raise RuntimeError(
                f"initial structural reconcile did not end open: "
                f"{backend.forwarding_writes()}"
            )
        if "vpng_filter" not in nft_tables(backend) or "vpng_nat" not in nft_tables(backend):
            raise RuntimeError("production nft tables were not installed")
        print(f"PASS A: initial production reconcile ifindex={old_ifindex}")

        # Replace the bound interface generation without an intermediate reconciliation.
        delete_vpn_interface(backend)
        new_ifindex = make_vpn_interface(backend)
        if new_ifindex == old_ifindex:
            raise RuntimeError("same-name replacement reused old ifindex")

        backend.reset()
        replaced = reconcile_once(
            CONFIG,
            NS,
            first.state,
            backend,
            persist_verified_state=store.save,
        )
        if "net.ipv4.ip_forward=0" in backend.forwarding_writes():
            raise RuntimeError(
                "same-name/new-ifindex lifecycle unexpectedly used global barrier"
            )
        if not replaced.needs_immediate_reconcile:
            raise RuntimeError(
                "replacement did not request delayed metric-slot promotion pass"
            )
        print(
            "PASS B: same-name/new-ifindex replacement stayed incremental "
            f"old={old_ifindex} new={new_ifindex}"
        )

        backend.reset()
        promoted = reconcile_once(
            CONFIG,
            NS,
            replaced.state,
            backend,
            persist_verified_state=store.save,
        )
        if "net.ipv4.ip_forward=0" in backend.forwarding_writes():
            raise RuntimeError("metric promotion unexpectedly used global barrier")
        if promoted.needs_immediate_reconcile:
            raise RuntimeError("metric promotion did not converge")
        print("PASS C: verified removal commit released metric for later promotion")

        delete_vpn_interface(backend)
        backend.reset()
        removed = reconcile_once(
            CONFIG,
            NS,
            promoted.state,
            backend,
            persist_verified_state=store.save,
        )
        if "net.ipv4.ip_forward=0" in backend.forwarding_writes():
            raise RuntimeError("ordinary member disappearance used global barrier")
        print("PASS D: ordinary member disappearance stayed incremental")

        # Foreign nft state is structural and must be repaired behind the global barrier.
        ns(backend, "nft", "add", "table", "ip", "foreign_ci")
        backend.reset()
        repaired = reconcile_once(
            CONFIG,
            NS,
            removed.state,
            backend,
            persist_verified_state=store.save,
        )
        writes = backend.forwarding_writes()
        if "net.ipv4.ip_forward=0" not in writes:
            raise RuntimeError("foreign nft drift did not close global barrier")
        if writes[-1:] != ["net.ipv4.ip_forward=1"]:
            raise RuntimeError(f"structural repair did not reopen cleanly: {writes}")
        if "foreign_ci" in nft_tables(backend):
            raise RuntimeError("foreign nft table survived structural repair")
        print("PASS E: foreign nft drift used barrier and was removed")

        loaded = store.load(CONFIG)
        if loaded.state != repaired.state:
            raise RuntimeError("durable runtime state differs from verified Planner state")
        print("PASS F: durable runtime state matches final verified state")

        print("NG1_PRODUCTION_CYCLE=PASS")
        return 0
    finally:
        try:
            destroy_instance(INSTANCE, backend)
        finally:
            shutil.rmtree(STATE_DIR, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
