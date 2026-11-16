from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from .command_backend import CommandBackend, NamespaceBackend, SubprocessBackend
from .config import load_active_config
from .environment import collect_environment_snapshot
from .instance_config import (
    InstanceFileConfig,
    load_instance_file_config,
    validate_instance_id,
)
from .instance_lifecycle import (
    contain_instance,
    destroy_instance,
    ensure_instance,
    verify_instance,
)
from .nat_state import ConfigNatProvider
from .runtime_app import run_instance_runtime
from .status import inspect_runtime_status
from .state_store import JsonRuntimeStateStore, StateStoreError


LOG = logging.getLogger(__name__)
DEFAULT_INSTANCE_DIR = Path("/etc/vpn-gateway/instances")
SERVICE_TEMPLATE = "rouvpn@{instance}.service"


class CliError(RuntimeError):
    pass


def default_instance_file(instance_id: str) -> Path:
    validate_instance_id(instance_id)
    return DEFAULT_INSTANCE_DIR / f"{instance_id}.toml"


def _load_pair(
    instance_id: str,
    instance_file: Path,
) -> tuple[InstanceFileConfig, object]:
    validate_instance_id(instance_id)
    instance = load_instance_file_config(instance_file)
    router = load_active_config(instance.router_config)
    return instance, router


def _service_name(instance_id: str) -> str:
    validate_instance_id(instance_id)
    return SERVICE_TEMPLATE.format(instance=instance_id)


def _systemctl(
    backend: CommandBackend,
    *args: str,
    check: bool = True,
):
    return backend.run(("systemctl", *args), check=check)



def cmd_prepare(
    instance_id: str,
    instance_file: Path,
    backend: CommandBackend,
) -> dict[str, object]:
    instance, _router = _load_pair(instance_id, instance_file)
    ensure_instance(instance.instance, backend)
    return {
        "ok": True,
        "instance_id": instance_id,
        "prepared": True,
    }


def cmd_contain(
    instance_id: str,
    instance_file: Path,
    backend: CommandBackend,
) -> dict[str, object]:
    validate_instance_id(instance_id)
    instance = load_instance_file_config(instance_file)
    contain_instance(instance.instance, backend)
    return {
        "ok": True,
        "instance_id": instance_id,
        "contained": True,
    }


def cmd_check(
    instance_id: str,
    instance_file: Path,
) -> dict[str, object]:
    instance, router = _load_pair(instance_id, instance_file)
    return {
        "ok": True,
        "instance_id": instance_id,
        "instance_file": str(instance_file),
        "namespace": instance.instance.namespace,
        "router_config": str(instance.router_config),
        "enabled_profiles": sorted(
            name
            for name, profile in router.profiles.items()
            if profile.enabled
        ),
        "active_devices": sorted(router.active_device_names),
    }


def cmd_up(
    instance_id: str,
    instance_file: Path,
    backend: CommandBackend,
) -> dict[str, object]:
    instance, _router = _load_pair(instance_id, instance_file)
    service = _service_name(instance_id)

    already_active = _systemctl(
        backend,
        "is-active",
        "--quiet",
        service,
        check=False,
    )
    if already_active.returncode == 0:
        _systemctl(backend, "enable", service)
        return {
            "ok": True,
            "instance_id": instance_id,
            "service": service,
            "namespace": instance.instance.namespace,
            "already_active": True,
        }

    ensure_instance(instance.instance, backend)
    try:
        _systemctl(backend, "enable", "--now", service)
        active = _systemctl(
            backend,
            "is-active",
            "--quiet",
            service,
            check=False,
        )
        if active.returncode != 0:
            raise CliError(
                f"{service} did not become active after start"
            )
    except Exception:
        # Failed up must not leave a half-created appliance behind.
        _systemctl(backend, "disable", "--now", service, check=False)
        destroy_instance(instance.instance, backend)
        raise

    return {
        "ok": True,
        "instance_id": instance_id,
        "service": service,
        "namespace": instance.instance.namespace,
    }


def cmd_down(
    instance_id: str,
    instance_file: Path,
    backend: CommandBackend,
) -> dict[str, object]:
    validate_instance_id(instance_id)
    instance = load_instance_file_config(instance_file)
    service = _service_name(instance_id)

    _systemctl(backend, "disable", "--now", service, check=False)
    active = _systemctl(
        backend,
        "is-active",
        "--quiet",
        service,
        check=False,
    )
    if active.returncode == 0:
        # Never tear the namespace out from under a live host-side supervisor.
        NamespaceBackend(instance.instance.namespace, backend).run(
            ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
            check=False,
        )
        raise CliError(
            f"refusing teardown while {service} remains active"
        )
    if active.returncode not in {3, 4}:
        NamespaceBackend(instance.instance.namespace, backend).run(
            ("sysctl", "-q", "-w", "net.ipv4.ip_forward=0"),
            check=False,
        )
        raise CliError(
            f"cannot prove {service} inactive: systemctl is-active "
            f"returned {active.returncode}"
        )

    destroy_instance(instance.instance, backend)
    return {
        "ok": True,
        "instance_id": instance_id,
        "service": service,
        "removed": True,
    }


def cmd_show(
    instance_id: str,
    instance_file: Path,
    backend: CommandBackend,
) -> dict[str, object]:
    instance, router = _load_pair(instance_id, instance_file)
    verification = verify_instance(
        instance.instance,
        backend,
        forwarding=None,
    )

    result: dict[str, object] = {
        "instance_id": instance_id,
        "instance_file": str(instance_file),
        "namespace": instance.instance.namespace,
        "host_interface": instance.instance.host_if,
        "appliance_verified": verification.ok,
        "appliance_errors": list(verification.errors),
        "active_devices": sorted(router.active_device_names),
        "enabled_profiles": sorted(
            name
            for name, profile in router.profiles.items()
            if profile.enabled
        ),
    }

    try:
        loaded = JsonRuntimeStateStore(instance.state_file).load(router)
    except StateStoreError as exc:
        result.update(
            {
                "state_ok": False,
                "state_error": str(exc),
                "policy_verified": False,
                "policy_errors": [
                    "runtime state is not trustworthy; policy projection skipped"
                ],
            }
        )
        return result

    result.update(
        {
            "state_ok": True,
            "dropped_state_entries": loaded.dropped_entries,
            "remembered_metric_count": len(
                loaded.state.traffic.normal_metrics
            ),
            "remembered_expectation_count": len(
                loaded.state.devices.expectations
            ),
        }
    )

    if not verification.ok:
        result.update(
            {
                "policy_verified": False,
                "policy_errors": [
                    "instance/appliance verification failed; policy projection skipped"
                ],
            }
        )
        return result

    snapshot = collect_environment_snapshot(
        instance.instance.namespace,
        lambda argv: backend.run(argv).stdout,
    )
    ns = NamespaceBackend(instance.instance.namespace, backend)
    status = inspect_runtime_status(
        router,
        instance.instance.namespace,
        loaded.state,
        snapshot,
        ns,
        ConfigNatProvider(),
        local_publication_address=instance.instance.inner_address.ip,
    )

    result.update(
        {
            "policy_verified": status.ok,
            "policy_errors": list(status.errors),
            "interfaces": [
                {
                    "ifname": item.identity.ifname,
                    "ifindex": item.identity.ifindex,
                }
                for item in snapshot.interfaces
            ],
            "bound_interfaces": [
                {
                    "device": item.device_name,
                    "expected_index": item.expected_index,
                    "ifname": item.identity.ifname,
                    "ifindex": item.identity.ifindex,
                    "availability": item.availability.value,
                }
                for item in status.projection.bindings.bound
            ],
            "over_quota_interfaces": [
                {
                    "device": item.device_name,
                    "expected_index": item.expected_index,
                    "ifname": item.identity.ifname,
                    "ifindex": item.identity.ifindex,
                }
                for item in status.projection.bindings.over_quota
            ],
            "route_count": len(snapshot.routes),
            "rule_count": len(snapshot.rules),
            "ip_forward": snapshot.sysctl_map.get(
                "net.ipv4.ip_forward"
            ),
        }
    )
    return result

def cmd_run(
    instance_id: str,
    instance_file: Path,
) -> dict[str, object]:
    result = run_instance_runtime(instance_id, instance_file)
    return {
        "ok": True,
        "instance_id": instance_id,
        "reconciliations": result.reconciliations,
        "planner_failures": result.planner_failures,
        "event_wakeups": result.event_wakeups,
        "audit_wakeups": result.audit_wakeups,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rou")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    parser.add_argument(
        "--instance-file",
        type=Path,
        help="override /etc/vpn-gateway/instances/<id>.toml",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "prepare", "contain", "up", "down", "show", "run"):
        sub = subparsers.add_parser(name)
        sub.add_argument("instance_id")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    backend: CommandBackend | None = None,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        instance_file = (
            args.instance_file
            if args.instance_file is not None
            else default_instance_file(args.instance_id)
        )
        if (
            backend is None
            and args.command in {"prepare", "contain", "up", "down", "show", "run"}
            and os.geteuid() != 0
        ):
            raise CliError(
                f"rou {args.command} requires root privileges; use sudo"
            )

        host = backend or SubprocessBackend()

        if args.command == "check":
            output = cmd_check(args.instance_id, instance_file)
        elif args.command == "prepare":
            output = cmd_prepare(args.instance_id, instance_file, host)
        elif args.command == "contain":
            output = cmd_contain(args.instance_id, instance_file, host)
        elif args.command == "up":
            output = cmd_up(args.instance_id, instance_file, host)
        elif args.command == "down":
            output = cmd_down(args.instance_id, instance_file, host)
        elif args.command == "show":
            output = cmd_show(args.instance_id, instance_file, host)
        elif args.command == "run":
            output = cmd_run(args.instance_id, instance_file)
        else:
            raise CliError(f"unsupported command {args.command!r}")

        print(json.dumps(output, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        LOG.warning("interrupted")
        return 130
    except Exception as exc:
        LOG.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
