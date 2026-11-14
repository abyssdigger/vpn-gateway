import unittest

from rou.linux_local_process import (
    LinuxLocalProcessConfig,
    LinuxLocalProcessError,
)


class LinuxLocalProcessConfigTests(unittest.TestCase):
    def test_accepts_explicit_uid_and_nonzero_conntrack_mark(self):
        config = LinuxLocalProcessConfig(uid=65534, ct_mark=0x24)

        self.assertEqual(config.uid, 65534)
        self.assertEqual(config.ct_mark, 0x24)

    def test_rejects_reserved_or_out_of_range_values(self):
        for uid in (-1, 0, (1 << 32) - 1):
            with self.subTest(uid=uid):
                with self.assertRaises(LinuxLocalProcessError):
                    LinuxLocalProcessConfig(uid=uid, ct_mark=1)

        for mark in (0, 1 << 32):
            with self.subTest(mark=mark):
                with self.assertRaises(LinuxLocalProcessError):
                    LinuxLocalProcessConfig(uid=1, ct_mark=mark)

    def test_rejects_bool_as_integer_configuration(self):
        with self.assertRaises(LinuxLocalProcessError):
            LinuxLocalProcessConfig(uid=True, ct_mark=1)
        with self.assertRaises(LinuxLocalProcessError):
            LinuxLocalProcessConfig(uid=1, ct_mark=True)


if __name__ == "__main__":
    unittest.main()
