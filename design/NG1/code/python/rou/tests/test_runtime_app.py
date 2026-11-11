from ipaddress import IPv4Address, IPv4Interface
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rou.command_backend import CommandResult
from rou.domain import ActiveConfig
from rou.instance_config import InstanceFileConfig
from rou.instance_lifecycle import InstanceConfig, InstanceVerification
from rou.runtime import RuntimeLoopResult
from rou.runtime_app import (
    RuntimeAppError,
    RuntimeLock,
    RuntimePaths,
    run_instance_runtime,
)


class FakeBackend:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, input_text=None, check=True):
        self.calls.append(argv)
        return CommandResult(argv, 0, "", "")


class FakeSupervisor:
    instances = []

    def __init__(self, endpoints):
        self.endpoints = tuple(endpoints)
        self.started = False
        self.closed = False
        FakeSupervisor.instances.append(self)

    def start(self):
        self.started = True

    def check_health(self):
        if not self.started or self.closed:
            raise RuntimeError("not healthy")

    def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, *args, **kwargs):
        self.args = args

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def should_stop(self):
        return False


def instance_file_config(state_file: Path) -> InstanceFileConfig:
    return InstanceFileConfig(
        instance=InstanceConfig(
            namespace="rou0",
            host_if="rouvpn0",
            inner_if="host0",
            host_address=IPv4Interface("192.0.2.1/30"),
            inner_address=IPv4Interface("192.0.2.2/30"),
        ),
        publication_bind_address=IPv4Address("127.0.0.1"),
        router_config=Path("/etc/router.toml"),
        state_file=state_file,
    )


class RuntimeAppTests(unittest.TestCase):
    def test_runtime_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "runtime" / "rou0.lock"
            first = RuntimeLock(path)
            second = RuntimeLock(path)
            first.acquire()
            try:
                with self.assertRaisesRegex(RuntimeAppError, "another runtime"):
                    second.acquire()
            finally:
                first.close()

            second.acquire()
            second.close()

    def test_runtime_closes_forwarding_before_instance_verification(self):
        with tempfile.TemporaryDirectory() as td:
            backend = FakeBackend()
            cfg = instance_file_config(Path(td) / "state.json")
            order = []

            def fake_verify(instance, passed_backend):
                order.append("verify")
                self.assertIs(passed_backend, backend)
                self.assertTrue(backend.calls)
                self.assertIn(
                    "net.ipv4.ip_forward=0",
                    backend.calls[-1],
                )
                return InstanceVerification(True, ())

            with (
                patch(
                    "rou.runtime_app.load_instance_file_config",
                    return_value=cfg,
                ),
                patch(
                    "rou.runtime_app.load_active_config",
                    return_value=ActiveConfig({}, {}),
                ),
                patch(
                    "rou.runtime_app.verify_instance",
                    side_effect=fake_verify,
                ),
                patch(
                    "rou.runtime_app.compile_publication_endpoints",
                    return_value=(),
                ),
                patch(
                    "rou.runtime_app.PublicationSupervisor",
                    FakeSupervisor,
                ),
                patch("rou.runtime_app.IpMonitorWakeupSource", FakeContext),
                patch("rou.runtime_app.SignalStop", FakeContext),
                patch(
                    "rou.runtime_app.run_runtime_loop",
                    return_value=RuntimeLoopResult(1, 0, 0, 0),
                ) as loop,
            ):
                result = run_instance_runtime(
                    "rou0",
                    "/etc/instance.toml",
                    host_backend=backend,
                    runtime_paths=RuntimePaths(
                        Path(td) / "runtime" / "rou0.lock"
                    ),
                )

            self.assertEqual(order, ["verify"])
            self.assertEqual(result.reconciliations, 1)
            self.assertTrue(FakeSupervisor.instances[-1].closed)
            loop.assert_called_once()

    def test_unverified_instance_never_starts_publications(self):
        with tempfile.TemporaryDirectory() as td:
            backend = FakeBackend()
            cfg = instance_file_config(Path(td) / "state.json")
            FakeSupervisor.instances.clear()

            with (
                patch(
                    "rou.runtime_app.load_instance_file_config",
                    return_value=cfg,
                ),
                patch(
                    "rou.runtime_app.load_active_config",
                    return_value=ActiveConfig({}, {}),
                ),
                patch(
                    "rou.runtime_app.verify_instance",
                    return_value=InstanceVerification(
                        False,
                        ("host0 missing",),
                    ),
                ),
                patch(
                    "rou.runtime_app.PublicationSupervisor",
                    FakeSupervisor,
                ),
            ):
                with self.assertRaisesRegex(RuntimeAppError, "unverified"):
                    run_instance_runtime(
                        "rou0",
                        "/etc/instance.toml",
                        host_backend=backend,
                        runtime_paths=RuntimePaths(
                            Path(td) / "runtime" / "rou0.lock"
                        ),
                    )

            self.assertEqual(FakeSupervisor.instances, ())


if __name__ == "__main__":
    unittest.main()
