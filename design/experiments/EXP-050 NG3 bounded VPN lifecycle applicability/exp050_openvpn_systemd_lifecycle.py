#!/usr/bin/env python3
"""EXP-050: bounded OpenVPN lifecycle through the EXP-049 systemd onboarding contract."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from rou.controller_startup import ControllerStartupStatus, start_controller_once
from rou.controller_stop import ControllerStopStatus, stop_controller_once
from rou.forwarding_gate import (
    ForwardingGateState,
    converge_forwarding_gate_once,
)
from rou.instance_lock import InstanceLockSpec
from rou.interface_inventory import parse_ip_link_inventory
from rou.linux_forwarding_gate import LinuxForwardingGateBackend
from rou.linux_nft_scaffold import LinuxNftScaffoldBackend, SubprocessNftRunner
from rou.linux_policy_platform import NG3_LINUX_POLICY_PLATFORM
from rou.linux_structural_policy import LinuxStructuralPolicyBackend
from rou.managed_network_domain import (
    ManagedNetworkDomainSpec,
    ensure_managed_network_domain,
    verify_managed_network_domain,
)
from rou.network_policy_activation import activate_network_policy


HERE = Path(__file__).resolve().parent
EXP049_PATH = (
    HERE.parent
    / "EXP-049 NG3 administrator VPN onboarding applicability"
    / "exp049_openvpn_onboarding.py"
)
_spec = importlib.util.spec_from_file_location("exp049_systemd_support", EXP049_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load EXP-049 systemd support")
e49 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = e49
_spec.loader.exec_module(e49)

# Exact EXP-049 mechanism, with separate evidence-unit names only.
e49.DOMAIN_UNIT = "exp050-vpn-gate-domain.service"
e49.CLIENT_UNIT = "exp050-openvpn.service"

FIXED_LOCAL_PORT = 11941
AGGRESSIVE_ROUTE = "203.0.113.250/32"
AGGRESSIVE_MARKER = Path("/run/exp050-aggressive-hook-ran")
AGGRESSIVE_NFT_COMMENT = "exp050-aggressive-hook"


def config_text(*, local_port: int | None = None) -> str:
    text = e49.STRUCTURAL_CONFIG
    if local_port is not None:
        text = text.replace(
            f"remote_port = {e49.OPENVPN_PORT}\n",
            f"remote_port = {e49.OPENVPN_PORT}\nlocal_port = {local_port}\n",
        )
    return text


def changed_client_config(source: Path, target: Path) -> None:
    text = source.read_text(encoding="utf-8")
    text = text.replace(
        "nobind\nroute-noexec\n",
        f"lport {FIXED_LOCAL_PORT}\nroute-noexec\n",
    )
    target.write_text(text, encoding="utf-8")


def aggressive_client_config(source: Path, target: Path, hook: Path) -> None:
    text = source.read_text(encoding="utf-8")
    text += (
        f"\nroute {AGGRESSIVE_ROUTE.split('/')[0]} 255.255.255.255\n"
        f"up {hook}\n"
    )
    target.write_text(text, encoding="utf-8")


def write_aggressive_hook(path: Path) -> None:
    path.write_text(
        """#!/bin/sh
set -e
echo executed > /run/exp050-aggressive-hook-ran
ip rule add priority 16384 lookup main
nft add rule ip vpn_gate stack_output accept comment "exp050-aggressive-hook"
sysctl -w net.ipv4.conf.all.log_martians=1
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def fresh_policy(config: str, domain_spec, runner):
    verification = verify_managed_network_domain(domain_spec, runner)
    assert verification.confirmed, verification.errors
    assert verification.host_boundary is not None
    interfaces = parse_ip_link_inventory(
        runner.run(("ip", "-n", domain_spec.namespace, "-j", "link", "show"))
    )
    prepared = e49.PreparedPolicy(config)
    desired = prepared.build_current(verification.host_boundary, interfaces)
    assert prepared.observed_binding is not None
    assert len(prepared.observed_binding.bindings) == 1
    return prepared, desired


def reconcile_policy(config: str, domain_spec, runner):
    prepared, desired = fresh_policy(config, domain_spec, runner)
    activation = activate_network_policy(
        LinuxForwardingGateBackend(runner, domain_spec.namespace),
        LinuxNftScaffoldBackend(runner, domain_spec.namespace),
        LinuxStructuralPolicyBackend(
            runner=runner,
            namespace=domain_spec.namespace,
            platform=NG3_LINUX_POLICY_PLATFORM,
        ),
        desired.routing,
        desired.nft,
        NG3_LINUX_POLICY_PLATFORM,
    )
    assert activation.ready, (activation.status, activation.diagnostic)
    return prepared, activation


def service_pid() -> int:
    return e49.systemd_main_pid(e49.CLIENT_UNIT)


def cgroup_empty_or_absent(unit: str) -> bool:
    group = e49.systemctl(
        "show", "--property=ControlGroup", "--value", unit, check=False
    ).stdout.strip()
    if not group or group == "/":
        return True
    path = Path("/sys/fs/cgroup") / group.lstrip("/")
    procs = path / "cgroup.procs"
    if not procs.exists():
        return True
    return not procs.read_text(encoding="utf-8").strip()


def wait_service_ready() -> int:
    e49.wait_until(
        "systemd OpenVPN vpn0",
        lambda: e49.interface_exists(e49.MANAGED, e49.VPN_IF),
        timeout=20.0,
    )
    assert e49.systemd_unit_active(e49.CLIENT_UNIT)
    pid = e49.prove_systemd_namespace_attachment()
    e49.wait_until(
        "OpenVPN tunnel payload",
        lambda: e49.ping(e49.MANAGED, e49.VPN_SERVER_ADDR, count=1),
        timeout=20.0,
    )
    return pid


def prove_payload() -> None:
    e49.command(
        (
            "ip", "route", "replace", f"{e49.VPN_SERVER_ADDR}/32",
            "via", str(e49.INNER_ADDR.ip), "dev", e49.HOST_BOUNDARY,
        )
    )
    assert e49.host_ping(e49.VPN_SERVER_ADDR)


def socket_uses_fixed_port() -> bool:
    output = e49.ns_command(
        e49.MANAGED, "ss", "-H", "-u", "-n", "-p", check=False
    ).stdout
    return f":{FIXED_LOCAL_PORT}" in output


def no_aggressive_state() -> tuple[bool, dict]:
    route = e49.command(
        ("ip", "-n", e49.MANAGED, "route", "show", AGGRESSIVE_ROUTE),
        check=False,
    ).stdout.strip()
    rule = e49.command(
        ("ip", "-n", e49.MANAGED, "rule", "show", "priority", "16384"),
        check=False,
    ).stdout.strip()
    ruleset = e49.ns_command(
        e49.MANAGED, "nft", "list", "ruleset", check=False
    ).stdout
    marker = AGGRESSIVE_MARKER.exists()
    detail = {
        "route": route,
        "rule": rule,
        "marker": marker,
        "nft_marker": AGGRESSIVE_NFT_COMMENT in ruleset,
    }
    return not route and not rule and not marker and not detail["nft_marker"], detail


def clean_units() -> None:
    e49.systemctl("stop", e49.CLIENT_UNIT, check=False)
    e49.systemctl("stop", e49.DOMAIN_UNIT, check=False)
    e49.systemctl("reset-failed", e49.CLIENT_UNIT, e49.DOMAIN_UNIT, check=False)


def run_lifecycle_cycle(
    cycle: int,
    *,
    root: Path,
    server_config: Path,
    safe_client: Path,
    changed_client: Path,
    aggressive_client: Path,
    hook: Path,
    runner,
    domain_spec,
    lock_spec,
) -> None:
    server_proc = None
    server_log = None
    startup = None
    current_config = config_text()

    print(f"EXP050_CYCLE_{cycle}_BEGIN")
    e49.setup_server_namespace()
    try:
        ensured = ensure_managed_network_domain(domain_spec, runner)
        assert ensured.confirmed

        e49.write_systemd_units(safe_client)
        clean_units()
        e49.systemctl("start", e49.DOMAIN_UNIT)
        assert e49.systemd_unit_active(e49.DOMAIN_UNIT)

        server_proc, server_log = e49.spawn_openvpn(
            e49.SERVER_NS,
            server_config,
            root / f"exp050-server-{cycle}.log",
        )
        e49.wait_until(
            "OpenVPN server TUN",
            lambda: e49.interface_exists(e49.SERVER_NS, e49.SERVER_TUN),
        )
        assert e49.ping(e49.MANAGED, e49.SERVER_UNDERLAY, count=1)

        # 1. Start using the exact systemd onboarding mechanism that passed EXP-049.
        e49.systemctl("start", e49.CLIENT_UNIT)
        first_pid = wait_service_ready()
        first_prepared, _ = fresh_policy(current_config, domain_spec, runner)

        holder = {}
        def load_policy():
            prepared = e49.PreparedPolicy(current_config)
            holder["prepared"] = prepared
            return prepared

        startup = start_controller_once(
            lock_spec,
            domain_spec,
            runner,
            NG3_LINUX_POLICY_PLATFORM,
            load_policy,
        )
        assert startup.status is ControllerStartupStatus.READY, (
            startup.status,
            startup.diagnostic,
        )
        assert startup.session is not None
        prove_payload()
        first_endpoint = first_prepared.observed_binding.bindings[0].endpoint
        print(
            f"EXP050_CYCLE_{cycle}_START=PASS:"
            f"pid={first_pid}:endpoint={first_endpoint!r}"
        )

        # 3. Restart with the same VPN-specific configuration.
        e49.systemctl("restart", e49.CLIENT_UNIT)
        second_pid = wait_service_ready()
        assert second_pid != first_pid
        assert not Path(f"/proc/{first_pid}").exists()
        same_prepared, _ = reconcile_policy(current_config, domain_spec, runner)
        prove_payload()
        same_endpoint = same_prepared.observed_binding.bindings[0].endpoint
        print(
            f"EXP050_CYCLE_{cycle}_RESTART_SAME_CONFIG=PASS:"
            f"old_pid={first_pid}:new_pid={second_pid}:endpoint={same_endpoint!r}"
        )

        # 4. Stop completely, change a material VPN-specific setting, and restart.
        e49.systemctl("stop", e49.CLIENT_UNIT)
        e49.wait_until(
            "same-config service stop",
            lambda: not e49.systemd_unit_active(e49.CLIENT_UNIT),
            timeout=10.0,
        )
        assert not Path(f"/proc/{second_pid}").exists()
        assert not e49.interface_exists(e49.MANAGED, e49.VPN_IF)

        e49.write_systemd_units(changed_client)
        current_config = config_text(local_port=FIXED_LOCAL_PORT)
        e49.systemctl("start", e49.CLIENT_UNIT)
        changed_pid = wait_service_ready()
        assert changed_pid != second_pid
        e49.wait_until(
            "changed OpenVPN fixed source port",
            socket_uses_fixed_port,
            timeout=10.0,
        )
        changed_prepared, _ = reconcile_policy(current_config, domain_spec, runner)
        prove_payload()
        changed_endpoint = changed_prepared.observed_binding.bindings[0].endpoint
        print(
            f"EXP050_CYCLE_{cycle}_RESTART_CHANGED_CONFIG=PASS:"
            f"pid={changed_pid}:local_port={FIXED_LOCAL_PORT}:"
            f"endpoint={changed_endpoint!r}"
        )

        # 5. Aggressive configuration under the supported policy-neutral contract.
        #
        # route-noexec remains enabled, and external user scripts are NOT elevated
        # with script-security 2. The config contains both a route directive and
        # an up hook which, if executed, would touch reserved RPDB/nft/sysctl.
        e49.systemctl("stop", e49.CLIENT_UNIT)
        e49.wait_until(
            "changed-config service stop",
            lambda: not e49.systemd_unit_active(e49.CLIENT_UNIT),
            timeout=10.0,
        )
        AGGRESSIVE_MARKER.unlink(missing_ok=True)
        e49.write_systemd_units(aggressive_client)
        start = e49.systemctl("start", e49.CLIENT_UNIT, check=False)
        time.sleep(1.0)
        safe, detail = no_aggressive_state()
        journal = e49.systemd_client_log()
        assert safe, detail
        assert "script-security" in journal.lower() or start.returncode != 0
        print(
            f"EXP050_CYCLE_{cycle}_AGGRESSIVE_SUPPORTED_CONTRACT=PASS:"
            + json.dumps(detail, sort_keys=True)
        )
        print(
            f"EXP050_CYCLE_{cycle}_AGGRESSIVE_DIAGNOSTIC="
            + json.dumps(journal[-4000:])
        )
        e49.systemctl("stop", e49.CLIENT_UNIT, check=False)

        # Restore a valid supported generation for the bounded domain stop.
        e49.write_systemd_units(changed_client)
        e49.systemctl("start", e49.CLIENT_UNIT)
        stop_pid = wait_service_ready()
        reconcile_policy(current_config, domain_spec, runner)
        prove_payload()

        # 2. Candidate bounded stop: close forwarding, stop domain anchor, rely on
        # BindsTo/After to stop the VPN cgroup, then destroy the owned domain.
        closed = converge_forwarding_gate_once(
            LinuxForwardingGateBackend(runner, e49.MANAGED),
            ForwardingGateState.DISABLED,
        )
        assert closed.confirmed
        e49.systemctl("stop", e49.DOMAIN_UNIT)
        e49.wait_until(
            "BindsTo-propagated VPN stop",
            lambda: not e49.systemd_unit_active(e49.CLIENT_UNIT),
            timeout=10.0,
        )
        assert not Path(f"/proc/{stop_pid}").exists()
        assert cgroup_empty_or_absent(e49.CLIENT_UNIT)
        assert not e49.interface_exists(e49.MANAGED, e49.VPN_IF)
        print(
            f"EXP050_CYCLE_{cycle}_SYSTEMD_BOUNDED_VPN_STOP=PASS:"
            f"old_pid={stop_pid}:cgroup_empty=true"
        )

        stopped = stop_controller_once(startup.session, domain_spec, runner)
        assert stopped.status is ControllerStopStatus.STOPPED, stopped
        startup = None

        namespaces = e49.command(("ip", "netns", "list"), check=False).stdout
        host_link = e49.command(
            ("ip", "link", "show", "dev", e49.HOST_BOUNDARY),
            check=False,
        )
        assert e49.MANAGED not in namespaces
        assert host_link.returncode != 0
        assert not Path(f"/proc/{stop_pid}").exists()
        assert cgroup_empty_or_absent(e49.CLIENT_UNIT)
        print(f"EXP050_CYCLE_{cycle}_MANAGED_DOMAIN_ABSENCE=PASS")
        print(f"EXP050_CYCLE_{cycle}_RESULT=PASS")

    finally:
        e49.systemctl("stop", e49.CLIENT_UNIT, check=False)
        e49.systemctl("stop", e49.DOMAIN_UNIT, check=False)
        if startup is not None and startup.session is not None:
            try:
                stop_controller_once(startup.session, domain_spec, runner)
            except Exception as exc:
                print(f"EXP050_CYCLE_{cycle}_STOP_FALLBACK={type(exc).__name__}:{exc}")
        e49.cleanup_managed(domain_spec, runner)
        e49.terminate_process(server_proc, server_log)
        e49.teardown_server_namespace()
        AGGRESSIVE_MARKER.unlink(missing_ok=True)


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("EXP-050 must run as root under systemd")

    version = e49.command(("openvpn", "--version")).stdout.splitlines()[0]
    print("EXP050_OPENVPN=" + json.dumps(version))
    print("EXP050_PREREQUISITE=EXP049_SYSTEMD_PASS")

    root = Path(tempfile.mkdtemp(prefix="exp050-openvpn-"))
    runner = SubprocessNftRunner()
    domain_spec = ManagedNetworkDomainSpec(
        namespace=e49.MANAGED,
        host_interface=e49.HOST_BOUNDARY,
        inner_interface=e49.INNER_BOUNDARY,
        host_address=e49.HOST_ADDR,
        inner_address=e49.INNER_ADDR,
    )
    lock_spec = InstanceLockSpec(
        runtime_directory=root / "runtime",
        expected_owner_uid=os.getuid(),
    )

    original_forward = e49.command(
        ("sysctl", "-n", "net.ipv4.ip_forward")
    ).stdout.strip()

    try:
        e49.cleanup_managed(domain_spec, runner)
        e49.teardown_server_namespace()
        clean_units()
        e49.command(("sysctl", "-w", "net.ipv4.ip_forward=1"))

        e49.generate_pki(root)
        server_config, safe_client = e49.write_openvpn_configs(root)
        changed_client = root / "client-changed.conf"
        aggressive_client = root / "client-aggressive.conf"
        hook = root / "aggressive-hook.sh"
        changed_client_config(safe_client, changed_client)
        write_aggressive_hook(hook)
        aggressive_client_config(changed_client, aggressive_client, hook)

        for cycle in (1, 2):
            run_lifecycle_cycle(
                cycle,
                root=root,
                server_config=server_config,
                safe_client=safe_client,
                changed_client=changed_client,
                aggressive_client=aggressive_client,
                hook=hook,
                runner=runner,
                domain_spec=domain_spec,
                lock_spec=lock_spec,
            )

        print("EXP050_RESULT=PASS")
        return 0
    finally:
        clean_units()
        e49.cleanup_managed(domain_spec, runner)
        e49.teardown_server_namespace()
        e49.command(
            ("sysctl", "-w", f"net.ipv4.ip_forward={original_forward}"),
            check=False,
        )


if __name__ == "__main__":
    sys.exit(main())
