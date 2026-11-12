from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rou.instance_config import (
    InstanceFileConfigError,
    parse_instance_file_config,
    validate_instance_id,
)


VALID = """
schema_version = 1

[instance]
namespace = "vpn-gate-rou0"
host_interface = "rouvpn0"
host_address = "192.0.2.1/30"
inner_address = "192.0.2.2/30"
publication_bind_address = "0.0.0.0"
router_config = "/etc/vpn-gateway/routers/rou0.toml"
state_file = "/var/lib/vpn-gateway/rou0/state.json"
"""


class InstanceFileConfigTests(unittest.TestCase):
    def test_valid_config(self):
        cfg = parse_instance_file_config(VALID)
        self.assertEqual(cfg.instance.namespace, "vpn-gate-rou0")
        self.assertEqual(cfg.instance.inner_if, "host0")
        self.assertEqual(str(cfg.publication_bind_address), "0.0.0.0")
        self.assertEqual(
            cfg.router_config,
            Path("/etc/vpn-gateway/routers/rou0.toml"),
        )

    def test_slash31_link_is_valid(self):
        cfg = parse_instance_file_config(
            VALID.replace("192.0.2.1/30", "192.0.2.0/31")
            .replace("192.0.2.2/30", "192.0.2.1/31")
        )
        self.assertEqual(cfg.instance.link_network.prefixlen, 31)

    def test_missing_or_unknown_schema_version_rejected(self):
        with self.assertRaisesRegex(InstanceFileConfigError, "schema_version"):
            parse_instance_file_config(
                VALID.replace("schema_version = 1\n", "")
            )
        with self.assertRaisesRegex(InstanceFileConfigError, "schema_version"):
            parse_instance_file_config(
                VALID.replace("schema_version = 1", "schema_version = 2")
            )

    def test_paths_must_be_absolute_and_distinct(self):
        with self.assertRaisesRegex(InstanceFileConfigError, "must be absolute"):
            parse_instance_file_config(
                VALID.replace(
                    "/etc/vpn-gateway/routers/rou0.toml",
                    "router.toml",
                )
            )
        with self.assertRaisesRegex(InstanceFileConfigError, "different paths"):
            parse_instance_file_config(
                VALID.replace(
                    "/etc/vpn-gateway/routers/rou0.toml",
                    "/var/lib/vpn-gateway/rou0/state.json",
                )
            )


    def test_state_file_must_stay_under_hardened_state_root(self):
        with self.assertRaisesRegex(
            InstanceFileConfigError,
            "must be below /var/lib/vpn-gateway",
        ):
            parse_instance_file_config(
                VALID.replace(
                    "/var/lib/vpn-gateway/rou0/state.json",
                    "/srv/rou0/state.json",
                )
            )

    def test_ipv6_publication_bind_rejected(self):
        with self.assertRaisesRegex(InstanceFileConfigError, "must be IPv4"):
            parse_instance_file_config(
                VALID.replace("0.0.0.0", "2001:db8::1")
            )

    def test_unknown_field_rejected(self):
        with self.assertRaisesRegex(InstanceFileConfigError, "unsupported"):
            parse_instance_file_config(
                VALID + "\n[other]\nvalue=1\n"
            )

    def test_instance_id_uses_safe_opaque_grammar(self):
        self.assertEqual(validate_instance_id("rou0"), "rou0")
        self.assertEqual(validate_instance_id("1-test"), "1-test")
        for bad in ("Rou0", "rou_0", "rou.0", "../rou0", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(InstanceFileConfigError):
                    validate_instance_id(bad)


if __name__ == "__main__":
    unittest.main()
