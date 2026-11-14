import unittest

from rou.linux_prerequisites import (
    LinuxNamespacePrerequisites,
    verify_linux_namespace_prerequisites,
)


class LinuxNamespacePrerequisiteTests(unittest.TestCase):
    def test_interface_name_with_dot_uses_unambiguous_slash_sysctl_path(self):
        desired = LinuxNamespacePrerequisites(("host0", "eth0.100"))

        commands = dict(desired.observation_commands)

        self.assertEqual(
            commands["net.ipv4.conf.eth0.100.rp_filter"],
            ("sysctl", "-n", "net/ipv4/conf/eth0.100/rp_filter"),
        )
        self.assertEqual(
            commands["net.ipv6.conf.eth0.100.disable_ipv6"],
            ("sysctl", "-n", "net/ipv6/conf/eth0.100/disable_ipv6"),
        )

    def test_verifier_reports_prerequisite_drift(self):
        desired = LinuxNamespacePrerequisites(("host0",))
        observed = tuple(
            (
                key,
                "1" if key == "net.ipv6.conf.all.forwarding" else expected,
            )
            for key, expected in desired.expected_sysctls
        )

        errors = verify_linux_namespace_prerequisites(desired, observed)

        self.assertEqual(
            errors,
            ("net.ipv6.conf.all.forwarding='1', expected '0'",),
        )


if __name__ == "__main__":
    unittest.main()
