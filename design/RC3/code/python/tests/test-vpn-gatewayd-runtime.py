#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import vpn_gatewayd as vpng


class InstanceLockSecurityTests(unittest.TestCase):
    def test_creates_secure_runtime_directory_and_lock(self):
        with tempfile.TemporaryDirectory() as parent:
            runtime_dir = Path(parent) / "vpn-gateway"
            lock_path = runtime_dir / "vpn-gatewayd.lock"

            with vpng.InstanceLock(lock_path):
                directory_stat = runtime_dir.stat()
                lock_stat = lock_path.stat()
                self.assertEqual(
                    stat.S_IMODE(directory_stat.st_mode),
                    0o700,
                )
                self.assertEqual(directory_stat.st_uid, os.geteuid())
                self.assertEqual(stat.S_IMODE(lock_stat.st_mode), 0o600)
                self.assertEqual(lock_stat.st_uid, os.geteuid())

    def test_rejects_existing_runtime_directory_wrong_mode(self):
        with tempfile.TemporaryDirectory() as parent:
            runtime_dir = Path(parent) / "vpn-gateway"
            runtime_dir.mkdir(mode=0o755)
            lock_path = runtime_dir / "vpn-gatewayd.lock"

            with self.assertRaises(vpng.InstanceLockError):
                with vpng.InstanceLock(lock_path):
                    self.fail("lock unexpectedly acquired")

            self.assertEqual(
                stat.S_IMODE(runtime_dir.stat().st_mode),
                0o755,
            )

    def test_rejects_runtime_directory_symlink(self):
        with tempfile.TemporaryDirectory() as parent:
            real_dir = Path(parent) / "real"
            real_dir.mkdir(mode=0o700)
            runtime_dir = Path(parent) / "vpn-gateway"
            runtime_dir.symlink_to(real_dir, target_is_directory=True)

            with self.assertRaises(vpng.InstanceLockError):
                with vpng.InstanceLock(runtime_dir / "vpn-gatewayd.lock"):
                    self.fail("lock unexpectedly acquired")

    def test_rejects_existing_lock_wrong_mode_without_fixing_it(self):
        with tempfile.TemporaryDirectory() as parent:
            runtime_dir = Path(parent) / "vpn-gateway"
            runtime_dir.mkdir(mode=0o700)
            lock_path = runtime_dir / "vpn-gatewayd.lock"
            lock_path.write_text("")
            lock_path.chmod(0o644)

            with self.assertRaises(vpng.InstanceLockError):
                with vpng.InstanceLock(lock_path):
                    self.fail("lock unexpectedly acquired")

            self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), 0o644)

    def test_rejects_lock_symlink(self):
        with tempfile.TemporaryDirectory() as parent:
            runtime_dir = Path(parent) / "vpn-gateway"
            runtime_dir.mkdir(mode=0o700)
            target = runtime_dir / "target"
            target.write_text("")
            target.chmod(0o600)
            lock_path = runtime_dir / "vpn-gatewayd.lock"
            lock_path.symlink_to(target)

            with self.assertRaises(vpng.InstanceLockError):
                with vpng.InstanceLock(lock_path):
                    self.fail("lock unexpectedly acquired")


if __name__ == "__main__":
    unittest.main(verbosity=2)
