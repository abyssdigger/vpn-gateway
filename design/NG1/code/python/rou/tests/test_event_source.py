import io
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.event_source import EventSourceError, IpMonitorWakeupSource


class FakeProcess:
    def __init__(self):
        read_fd, write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self.stderr = io.BytesIO()
        self.write_fd = write_fd
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0
        try:
            os.close(self.write_fd)
        except OSError:
            pass

    def kill(self):
        self.killed = True
        self.returncode = -9
        try:
            os.close(self.write_fd)
        except OSError:
            pass

    def wait(self, timeout=None):
        return self.returncode

    def emit(self, payload=b"event\n"):
        os.write(self.write_fd, payload)

    def exit(self, returncode=1, stderr=b"failed"):
        if stderr:
            try:
                os.write(self.write_fd, stderr)
            except OSError:
                pass
        self.returncode = returncode
        try:
            os.close(self.write_fd)
        except OSError:
            pass


class CapturingFactory:
    def __init__(self, process):
        self.process = process
        self.argv = None
        self.kwargs = None

    def __call__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        return self.process


class EventSourceTests(unittest.TestCase):
    def test_monitor_command_covers_relevant_rtnetlink_objects(self):
        process = FakeProcess()
        factory = CapturingFactory(process)
        source = IpMonitorWakeupSource("rou0", popen_factory=factory)
        try:
            self.assertFalse(source.wait(0))
            self.assertEqual(
                factory.argv,
                (
                    "ip", "netns", "exec", "rou0",
                    "ip", "monitor", "link", "address", "route", "rule",
                ),
            )
        finally:
            source.close()

    def test_any_monitor_bytes_wake_without_parsing(self):
        process = FakeProcess()
        source = IpMonitorWakeupSource(
            "rou0",
            popen_factory=CapturingFactory(process),
        )
        try:
            source.wait(0)
            process.emit(b"opaque rtnetlink rendering\n")
            self.assertTrue(source.wait(0.1))
        finally:
            source.close()

    def test_timeout_is_not_an_event(self):
        process = FakeProcess()
        source = IpMonitorWakeupSource(
            "rou0",
            popen_factory=CapturingFactory(process),
        )
        try:
            self.assertFalse(source.wait(0))
        finally:
            source.close()

    def test_monitor_exit_is_fatal_to_source(self):
        process = FakeProcess()
        source = IpMonitorWakeupSource(
            "rou0",
            popen_factory=CapturingFactory(process),
        )
        try:
            source.wait(0)
            process.exit(17, b"netns disappeared")
            with self.assertRaisesRegex(
                EventSourceError,
                "17.*netns disappeared",
            ):
                source.wait(0.1)
        finally:
            source.close()

    def test_close_terminates_running_monitor(self):
        process = FakeProcess()
        source = IpMonitorWakeupSource(
            "rou0",
            popen_factory=CapturingFactory(process),
        )
        source.wait(0)
        source.close()
        self.assertTrue(process.terminated)


if __name__ == "__main__":
    unittest.main()
