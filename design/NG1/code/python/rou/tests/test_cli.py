from ipaddress import IPv4Address, IPv4Interface
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.cli import CliError, cmd_down, cmd_show, cmd_up, default_instance_file
from rou.command_backend import CommandResult
from rou.instance_config import InstanceFileConfig
from rou.device_engine import DeviceBindingSnapshot
from rou.domain import ActiveConfig
from rou.environment import EnvironmentSnapshot
from rou.instance_lifecycle import InstanceConfig, InstanceVerification
from rou.planner import PlannerRuntimeState
from rou.state_store import StateLoadResult, StateStoreError


class FakeBackend:
    def __init__(self, active_returncode=3):
        self.calls = []
        self.active_returncode = active_returncode

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append(argv)
        if argv[:3] == ("systemctl", "is-active", "--quiet"):
            return CommandResult(argv, self.active_returncode, "", "")
        return CommandResult(argv, 0, "", "")


def config():
    return InstanceFileConfig(
        instance=InstanceConfig(
            namespace="rou0",
            host_if="rouvpn0",
            inner_if="host0",
            host_address=IPv4Interface("192.0.2.1/30"),
            inner_address=IPv4Interface("192.0.2.2/30"),
        ),
        publication_bind_address=IPv4Address("0.0.0.0"),
        router_config=Path("/etc/router.toml"),
        state_file=Path("/var/lib/vpn-gateway/rou0/state.json"),
    )


class CliTests(unittest.TestCase):
    def test_default_instance_path_is_conventional(self):
        self.assertEqual(
            default_instance_file("rou0"),
            Path("/etc/vpn-gateway/instances/rou0.toml"),
        )

    def test_up_rolls_back_instance_if_service_not_active(self):
        backend = FakeBackend(active_returncode=3)
        events = []

        with (
            patch("rou.cli._load_pair", return_value=(config(), object())),
            patch(
                "rou.cli.ensure_instance",
                side_effect=lambda *_: events.append("ensure"),
            ),
            patch(
                "rou.cli.destroy_instance",
                side_effect=lambda *_: events.append("destroy"),
            ),
        ):
            with self.assertRaisesRegex(CliError, "did not become active"):
                cmd_up(
                    "rou0",
                    Path("/etc/instance.toml"),
                    backend,
                )

        self.assertEqual(events, ["ensure", "destroy"])
        self.assertIn(
            ("systemctl", "disable", "--now", "rouvpn@rou0.service"),
            backend.calls,
        )


    def test_up_is_non_disruptive_when_service_already_active(self):
        backend = FakeBackend(active_returncode=0)

        with (
            patch("rou.cli._load_pair", return_value=(config(), object())),
            patch("rou.cli.ensure_instance") as ensure,
            patch("rou.cli.destroy_instance") as destroy,
        ):
            result = cmd_up(
                "rou0",
                Path("/etc/instance.toml"),
                backend,
            )

        self.assertTrue(result["already_active"])
        ensure.assert_not_called()
        destroy.assert_not_called()
        self.assertFalse(
            any(
                "net.ipv4.ip_forward=0" in argv
                for argv in backend.calls
            )
        )

    def test_down_does_not_require_router_policy_to_parse(self):
        backend = FakeBackend(active_returncode=3)
        destroyed = []

        with (
            patch(
                "rou.cli.load_instance_file_config",
                return_value=config(),
            ),
            patch(
                "rou.cli.load_active_config",
                side_effect=AssertionError("must not load router config"),
            ),
            patch(
                "rou.cli.destroy_instance",
                side_effect=lambda *_: destroyed.append(True),
            ),
        ):
            result = cmd_down(
                "rou0",
                Path("/etc/instance.toml"),
                backend,
            )

        self.assertTrue(result["removed"])
        self.assertEqual(destroyed, [True])

    def test_down_refuses_if_service_is_still_active(self):
        backend = FakeBackend(active_returncode=0)

        with (
            patch(
                "rou.cli.load_instance_file_config",
                return_value=config(),
            ),
            patch("rou.cli.destroy_instance") as destroy,
        ):
            with self.assertRaisesRegex(CliError, "remains active"):
                cmd_down(
                    "rou0",
                    Path("/etc/instance.toml"),
                    backend,
                )

        destroy.assert_not_called()
        self.assertTrue(
            any(
                "net.ipv4.ip_forward=0" in argv
                for argv in backend.calls
            )
        )

    def test_down_refuses_on_indeterminate_systemd_status(self):
        backend = FakeBackend(active_returncode=1)

        with (
            patch(
                "rou.cli.load_instance_file_config",
                return_value=config(),
            ),
            patch("rou.cli.destroy_instance") as destroy,
        ):
            with self.assertRaisesRegex(CliError, "cannot prove"):
                cmd_down(
                    "rou0",
                    Path("/etc/instance.toml"),
                    backend,
                )

        destroy.assert_not_called()


    def test_show_reports_full_policy_verification(self):
        backend = FakeBackend()
        router = ActiveConfig({}, {})
        snapshot = EnvironmentSnapshot(
            interfaces=(),
            routes=(),
            rules=(),
            sysctls=(("net.ipv4.ip_forward", "0"),),
        )
        projection = SimpleNamespace(
            bindings=DeviceBindingSnapshot((), ()),
        )
        status = SimpleNamespace(
            ok=True,
            errors=(),
            projection=projection,
        )

        with (
            patch("rou.cli._load_pair", return_value=(config(), router)),
            patch(
                "rou.cli.verify_instance",
                return_value=InstanceVerification(True, ()),
            ),
            patch(
                "rou.cli.JsonRuntimeStateStore"
            ) as store_cls,
            patch(
                "rou.cli.collect_environment_snapshot",
                return_value=snapshot,
            ),
            patch(
                "rou.cli.inspect_runtime_status",
                return_value=status,
            ) as inspect,
        ):
            store_cls.return_value.load.return_value = StateLoadResult(
                PlannerRuntimeState.empty(),
                0,
            )
            result = cmd_show(
                "rou0",
                Path("/etc/instance.toml"),
                backend,
            )

        self.assertTrue(result["appliance_verified"])
        self.assertTrue(result["state_ok"])
        self.assertTrue(result["policy_verified"])
        self.assertEqual(result["policy_errors"], [])
        inspect.assert_called_once()

    def test_show_does_not_project_policy_from_untrusted_state(self):
        backend = FakeBackend()
        router = ActiveConfig({}, {})

        with (
            patch("rou.cli._load_pair", return_value=(config(), router)),
            patch(
                "rou.cli.verify_instance",
                return_value=InstanceVerification(True, ()),
            ),
            patch("rou.cli.JsonRuntimeStateStore") as store_cls,
            patch("rou.cli.inspect_runtime_status") as inspect,
        ):
            store_cls.return_value.load.side_effect = StateStoreError(
                "state integrity failure"
            )
            result = cmd_show(
                "rou0",
                Path("/etc/instance.toml"),
                backend,
            )

        self.assertFalse(result["state_ok"])
        self.assertFalse(result["policy_verified"])
        self.assertIn("state integrity failure", result["state_error"])
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
