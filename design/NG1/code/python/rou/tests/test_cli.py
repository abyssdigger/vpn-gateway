from ipaddress import IPv4Address, IPv4Interface
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.cli import CliError, cmd_down, cmd_up, default_instance_file
from rou.command_backend import CommandResult
from rou.instance_config import InstanceFileConfig
from rou.instance_lifecycle import InstanceConfig


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
        state_file=Path("/var/lib/rou0/state.json"),
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
                "rou.cli.create_instance",
                side_effect=lambda *_: events.append("create"),
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

        self.assertEqual(events, ["create", "destroy"])
        self.assertIn(
            ("systemctl", "stop", "rouvpn@rou0.service"),
            backend.calls,
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


if __name__ == "__main__":
    unittest.main()
