from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile
import unittest

from rou.instance_lock import (
    ControllerInstanceBusyError,
    ControllerInstanceLockError,
    InstanceLockSpec,
    acquire_controller_instance_lock,
)


class ControllerInstanceLockTests(unittest.TestCase):
    def spec(self, root: Path) -> InstanceLockSpec:
        return InstanceLockSpec(
            runtime_directory=root / "runtime",
            expected_owner_uid=os.getuid(),
        )

    def test_acquire_creates_hardened_runtime_dir_and_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))

            lock = acquire_controller_instance_lock(spec)
            try:
                self.assertTrue(lock.acquired)
                directory = spec.runtime_directory.lstat()
                lock_file = spec.lock_path.lstat()
                self.assertTrue(stat.S_ISDIR(directory.st_mode))
                self.assertEqual(stat.S_IMODE(directory.st_mode), 0o700)
                self.assertEqual(directory.st_uid, os.getuid())
                self.assertTrue(stat.S_ISREG(lock_file.st_mode))
                self.assertEqual(stat.S_IMODE(lock_file.st_mode), 0o600)
                self.assertEqual(lock_file.st_uid, os.getuid())
            finally:
                lock.release()

    def test_second_open_fails_immediately_while_first_lock_is_held(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))
            first = acquire_controller_instance_lock(spec)
            try:
                with self.assertRaisesRegex(
                    ControllerInstanceBusyError,
                    "another VPN-GATE controller instance is running",
                ):
                    acquire_controller_instance_lock(spec)
            finally:
                first.release()

    def test_stale_regular_lock_file_does_not_block_reacquire(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))
            first = acquire_controller_instance_lock(spec)
            first.release()

            self.assertTrue(spec.lock_path.exists())
            second = acquire_controller_instance_lock(spec)
            try:
                self.assertTrue(second.acquired)
            finally:
                second.release()

    def test_context_manager_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))
            with acquire_controller_instance_lock(spec) as first:
                self.assertTrue(first.acquired)
            self.assertFalse(first.acquired)

            second = acquire_controller_instance_lock(spec)
            second.release()

    def test_release_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))
            lock = acquire_controller_instance_lock(spec)
            lock.release()
            lock.release()
            self.assertFalse(lock.acquired)

    def test_runtime_directory_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "real"
            target.mkdir(mode=0o700)
            runtime = root / "runtime"
            runtime.symlink_to(target, target_is_directory=True)
            spec = InstanceLockSpec(runtime, os.getuid())

            with self.assertRaisesRegex(
                ControllerInstanceLockError,
                "must not be a symlink",
            ):
                acquire_controller_instance_lock(spec)

    def test_wrong_runtime_directory_mode_is_not_repaired(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))
            spec.runtime_directory.mkdir()
            os.chmod(spec.runtime_directory, 0o755)

            with self.assertRaisesRegex(
                ControllerInstanceLockError,
                "expected 0700",
            ):
                acquire_controller_instance_lock(spec)

            self.assertEqual(
                stat.S_IMODE(spec.runtime_directory.lstat().st_mode),
                0o755,
            )

    def test_wrong_runtime_directory_owner_expectation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            os.chmod(runtime, 0o700)
            spec = InstanceLockSpec(
                runtime_directory=runtime,
                expected_owner_uid=os.getuid() + 1,
            )

            with self.assertRaisesRegex(
                ControllerInstanceLockError,
                "owner UID",
            ):
                acquire_controller_instance_lock(spec)

    def test_lock_file_symlink_is_refused_by_nofollow_open(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))
            spec.runtime_directory.mkdir(mode=0o700)
            os.chmod(spec.runtime_directory, 0o700)
            target = spec.runtime_directory / "target"
            target.write_text("not a lock", encoding="utf-8")
            spec.lock_path.symlink_to(target)

            with self.assertRaisesRegex(
                ControllerInstanceLockError,
                "cannot safely open controller lock",
            ):
                acquire_controller_instance_lock(spec)

    def test_existing_wrong_lock_mode_is_not_repaired(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = self.spec(Path(temp))
            spec.runtime_directory.mkdir(mode=0o700)
            os.chmod(spec.runtime_directory, 0o700)
            spec.lock_path.write_text("", encoding="utf-8")
            os.chmod(spec.lock_path, 0o644)

            with self.assertRaisesRegex(
                ControllerInstanceLockError,
                "expected 0600",
            ):
                acquire_controller_instance_lock(spec)

            self.assertEqual(
                stat.S_IMODE(spec.lock_path.lstat().st_mode),
                0o644,
            )

    def test_relative_runtime_directory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be absolute"):
            InstanceLockSpec(Path("relative"), os.getuid())


if __name__ == "__main__":
    unittest.main()
