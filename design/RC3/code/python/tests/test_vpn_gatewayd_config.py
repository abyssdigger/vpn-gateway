#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import vpn_gatewayd as vpng


class NoSecurityLoader(vpng.ConfigLoader):
    def _validate_config_security(self, path: Path) -> None:
        return

    def _validate_opened_config_stat(self, path: Path, file_stat) -> None:
        return


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.loader = NoSecurityLoader()

    def write(self, body: str) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.unlink(tmp.name))
        with tmp:
            tmp.write(textwrap.dedent(body))
        return Path(tmp.name)

    def load(self, body: str):
        return self.loader.load_runtime(self.write(body))

    def check(self, body: str):
        return self.loader.check(self.write(body))

    def test_valid_binding_specific_projection(self):
        cfg = self.load(
            """
            enabled = true
            reconcile_interval = 12.5
            common_allowed_sources = ["10.200.200.8"]

            [profiles.primary]
            routes = ["10.0.0.0/8"]
            allowed_sources = ["10.200.201.0/24"]
            bindings = [
              { interface = "wg0", network = "172.20.126.0/29" },
              { interface = "wg1", network = "172.20.127.0/29" },
              { interface = "oc+", network = "172.20.130.0/29" },
            ]
            """
        )
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.reconcile_interval, 12.5)
        profile = cfg.profiles["primary"]
        self.assertEqual(len(profile.bindings), 3)
        self.assertEqual(
            [spec.exact_rank for spec in profile.bindings],
            [0, 1, None],
        )
        self.assertEqual(profile.dynamic_metric_min, 30)
        self.assertEqual(
            str(profile.bindings[1].network),
            "172.20.127.0/29",
        )

    def test_defaults_are_applied(self):
        cfg = self.load(
            """
            [profiles.primary]
            routes = ["10.0.0.0/8"]
            bindings = [
              { interface = "wg0", network = "172.20.126.0/29" },
            ]
            """
        )
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.reconcile_interval, vpng.DEFAULT_RECONCILE_INTERVAL)
        self.assertEqual(cfg.common_allowed_sources, ())
        self.assertEqual(cfg.profiles["primary"].allowed_sources, ())

    def test_global_disabled_ignores_profile_bodies_and_operational_values(self):
        cfg = self.load(
            """
            enabled = false
            reconcile_interval = "not-a-number"
            common_allowed_sources = "not-an-array"

            [profiles."bad.id"]
            nonsense = [{ future = "schema" }]
            """
        )
        self.assertFalse(cfg.enabled)
        self.assertEqual(dict(cfg.profiles), ())
        self.assertEqual(cfg.common_allowed_sources, ())

    def test_global_disabled_still_rejects_unknown_top_level_key(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                enabled = false
                future_top_level = true
                """
            )

    def test_disabled_profile_body_is_not_parsed_or_linted(self):
        body = """
            [profiles.primary]
            routes = ["10.0.0.0/8"]
            bindings = [
              { interface = "wg0", network = "172.20.126.0/29" },
            ]

            [profiles."bad.id"]
            enabled = false
            unknown_future_key = "anything"
            routes = "wrong-type"
            bindings = "wrong-type"
        """
        cfg = self.load(body)
        self.assertEqual(tuple(cfg.profiles), ("primary",))
        result = self.check(body)
        self.assertFalse(result.has_errors)
        self.assertEqual(result.issues, ())

    def test_enabled_config_requires_enabled_profile(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                enabled = true
                [profiles.future]
                enabled = false
                nonsense = true
                """
            )

    def test_enabled_profile_unknown_key_is_error(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.0/29" },
                ]
                local_address = "172.20.126.2"
                """
            )

    def test_binding_unknown_key_is_error(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.0/29", peer = "x" },
                ]
                """
            )

    def test_old_list_selector_is_rejected(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = ["wg0", "wg1"], network = "172.20.126.0/29" },
                ]
                """
            )

    def test_prefix_between_exacts_does_not_consume_exact_rank(self):
        cfg = self.load(
            """
            [profiles.primary]
            routes = ["10.0.0.0/8"]
            bindings = [
              { interface = "wg0", network = "172.20.126.0/29" },
              { interface = "oc+", network = "172.20.130.0/29" },
              { interface = "wg1", network = "172.20.127.0/29" },
              { interface = "tun+", network = "172.20.140.0/29" },
              { interface = "wg2", network = "172.20.128.0/29" },
            ]
            """
        )
        specs = cfg.profiles["primary"].bindings
        self.assertEqual(
            [spec.exact_rank for spec in specs],
            [0, None, 1, None, 2],
        )
        self.assertEqual(cfg.profiles["primary"].dynamic_metric_min, 40)

    def test_selector_namespace_overlap_is_global_error(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = "vpns+", network = "172.20.130.0/29" },
                ]

                [profiles.backup]
                routes = ["192.168.0.0/16"]
                bindings = [
                  { interface = "vpns9", network = "172.20.131.0/29" },
                ]
                """
            )

    def test_binding_networks_may_overlap(self):
        cfg = self.load(
            """
            [profiles.primary]
            routes = ["10.0.0.0/8"]
            bindings = [
              { interface = "wg0", network = "172.20.126.0/29" },
              { interface = "wg1", network = "172.20.126.0/29" },
            ]
            """
        )
        self.assertEqual(len(cfg.profiles["primary"].bindings), 2)

    def test_protected_route_must_not_overlap_any_binding_network(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["172.20.0.0/16"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.0/29" },
                ]
                """
            )

    def test_protected_routes_cannot_overlap_across_profiles(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.0/29" },
                ]

                [profiles.backup]
                routes = ["10.1.0.0/16"]
                bindings = [
                  { interface = "wg1", network = "172.20.127.0/29" },
                ]
                """
            )

    def test_noncanonical_binding_network_is_rejected(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.1/29" },
                ]
                """
            )

    def test_slash32_binding_network_is_rejected_but_slash31_allowed(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.1/32" },
                ]
                """
            )
        cfg = self.load(
            """
            [profiles.primary]
            routes = ["10.0.0.0/8"]
            bindings = [
              { interface = "wg0", network = "172.20.126.0/31" },
            ]
            """
        )
        self.assertEqual(
            str(cfg.profiles["primary"].bindings[0].network),
            "172.20.126.0/31",
        )

    def test_duplicate_route_is_error(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8", "10.0.0.0/8"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.0/29" },
                ]
                """
            )

    def test_acl_duplicates_normalize_and_check_warns(self):
        body = """
            common_allowed_sources = ["10.1.1.1", "10.1.1.1/32"]
            [profiles.primary]
            routes = ["10.0.0.0/8"]
            bindings = [
              { interface = "wg0", network = "172.20.126.0/29" },
            ]
            allowed_sources = ["10.2.0.0/24", "10.2.0.0/24"]
        """
        cfg = self.load(body)
        self.assertEqual(len(cfg.common_allowed_sources), 1)
        self.assertEqual(len(cfg.profiles["primary"].allowed_sources), 1)
        result = self.check(body)
        self.assertFalse(result.has_errors)
        self.assertEqual(
            sum(i.level is vpng.ConfigIssueLevel.WARNING for i in result.issues),
            2,
        )

    def test_reconcile_interval_range_and_type(self):
        for value in ('"10"', "0.5", "61.0"):
            with self.subTest(value=value):
                with self.assertRaises(vpng.ConfigError):
                    self.load(
                        f"""
                        reconcile_interval = {value}
                        [profiles.primary]
                        routes = ["10.0.0.0/8"]
                        bindings = [
                          {{ interface = "wg0", network = "172.20.126.0/29" }},
                        ]
                        """
                    )

    def test_case_insensitive_enabled_profile_collision_is_error(self):
        with self.assertRaises(vpng.ConfigError):
            self.load(
                """
                [profiles.primary]
                routes = ["10.0.0.0/8"]
                bindings = [
                  { interface = "wg0", network = "172.20.126.0/29" },
                ]

                [profiles.PRIMARY]
                routes = ["192.168.0.0/16"]
                bindings = [
                  { interface = "wg1", network = "172.20.127.0/29" },
                ]
                """
            )

    def test_read_toml_uses_o_nofollow_and_revalidates_opened_object(self):
        loader = vpng.ConfigLoader()
        path = Path("/etc/vpn-gateway/vpn-gateway.toml")
        root_dir = mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        regular = mock.Mock(st_mode=stat.S_IFREG | 0o600, st_uid=0)
        loader._stat_path = mock.Mock(return_value=root_dir)
        loader._lstat_path = mock.Mock(return_value=regular)

        fake_fd = 99
        with mock.patch("vpn_gatewayd.config.os.open", return_value=fake_fd) as opened,              mock.patch("vpn_gatewayd.config.os.fstat", return_value=regular),              mock.patch("vpn_gatewayd.config.os.fdopen", mock.mock_open(read_data=b"enabled=false\n")):
            document = loader._read_toml(path)

        self.assertFalse(document["enabled"])
        flags = opened.call_args.args[1]
        self.assertTrue(flags & os.O_NOFOLLOW)

    def test_opened_config_stat_rejects_owner_or_writable_mode(self):
        loader = vpng.ConfigLoader()
        path = Path("/x")
        with self.assertRaises(vpng.ConfigError):
            loader._validate_opened_config_stat(
                path,
                mock.Mock(st_mode=stat.S_IFREG | 0o600, st_uid=1000),
            )
        with self.assertRaises(vpng.ConfigError):
            loader._validate_opened_config_stat(
                path,
                mock.Mock(st_mode=stat.S_IFREG | 0o620, st_uid=0),
            )


if __name__ == "__main__":
    unittest.main()
