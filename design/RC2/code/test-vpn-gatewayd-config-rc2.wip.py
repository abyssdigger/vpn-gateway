#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).with_name("vpn-gatewayd-rc2.wip.py")

spec = importlib.util.spec_from_file_location("vpn_gatewayd_rc221", MODULE_PATH)
assert spec is not None and spec.loader is not None
vpng = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = vpng
spec.loader.exec_module(vpng)


VALID_PRIMARY = """
[vpn.primary]
interface = "vpns0"
network = "172.20.130.0/29"
local_address = "172.20.130.1"
peers = ["172.20.130.6"]
routes = ["10.0.0.0/8"]
allowed_sources = ["10.200.201.0/24"]
"""


class NoSecurityLoader(vpng.ConfigLoader):
    def _validate_config_security(self, path: Path) -> None:
        del path


class ConfigTestCase(unittest.TestCase):
    def write_config(self, body: str) -> tuple[tempfile.TemporaryDirectory, Path]:
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "vpn-gateway.toml"
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return td, path

    def issues(self, result, level):
        return [issue for issue in result.issues if issue.level is level]

    def test_valid_runtime_projection(self):
        td, path = self.write_config(
            """
            reconcile_interval = 10.0
            managed_vpns = ["primary", "backup"]
            common_allowed_sources = ["10.200.200.8", "10.200.200.9/32"]

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.0.0.0/8"]
            allowed_sources = ["10.200.201.0/24"]

            [vpn.backup]
            interface = "wg0"
            network = "172.20.126.0/29"
            local_address = "172.20.126.1"
            peers = ["172.20.126.2", "172.20.126.3"]
            routes = ["100.64.0.0/10", "192.168.0.0/16"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        cfg = NoSecurityLoader().load_runtime(path)

        self.assertEqual(cfg.reconcile_interval, 10.0)
        self.assertEqual(tuple(cfg.vpns), ("backup", "primary"))
        self.assertEqual(
            tuple(map(str, cfg.common_allowed_sources)),
            ("10.200.200.8/32", "10.200.200.9/32"),
        )
        self.assertEqual(cfg.vpns["primary"].interface, "vpns0")
        self.assertEqual(
            tuple(map(str, cfg.vpns["backup"].routes)),
            ("100.64.0.0/10", "192.168.0.0/16"),
        )

    def test_malformed_unmanaged_definition_does_not_block_runtime(self):
        td, path = self.write_config(
            """
            reconcile_interval = 10.0
            managed_vpns = ["primary"]
            common_allowed_sources = []
            """
            + VALID_PRIMARY
            + """
            [vpn."bad.id"]
            network = "definitely-not-an-ip"
            surprise = true
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        cfg = loader.load_runtime(path)
        self.assertEqual(tuple(cfg.vpns), ("primary",))

        result = loader.check(path)
        warnings = self.issues(result, vpng.ConfigIssueLevel.WARNING)
        self.assertTrue(warnings)
        self.assertFalse(result.has_errors)
        self.assertTrue(
            any("profile ID must match" in issue.message for issue in warnings)
        )

    def test_managed_empty_peers_is_note_not_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = []
            routes = ["10.0.0.0/8"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        cfg = loader.load_runtime(path)
        self.assertEqual(cfg.vpns["primary"].peers, ())

        result = loader.check(path)
        self.assertFalse(result.has_errors)
        notes = self.issues(result, vpng.ConfigIssueLevel.NOTE)
        self.assertEqual(len(notes), 1)
        self.assertIn("no UNICAST VPN routes", notes[0].message)

    def test_managed_route_transport_overlap_is_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary", "backup"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["172.20.126.0/29"]
            allowed_sources = []

            [vpn.backup]
            interface = "wg0"
            network = "172.20.126.0/29"
            local_address = "172.20.126.1"
            peers = ["172.20.126.2"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path)

        result = loader.check(path)
        self.assertTrue(result.has_errors)
        self.assertTrue(
            any(
                "overlaps VPN transport network" in issue.message
                for issue in self.issues(result, vpng.ConfigIssueLevel.ERROR)
            )
        )

    def test_conflict_with_unmanaged_profile_is_warning_only(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []
            """
            + VALID_PRIMARY
            + """
            [vpn.backup]
            interface = "wg0"
            network = "10.20.0.0/16"
            local_address = "10.20.0.1"
            peers = ["10.20.0.2"]
            routes = ["192.168.0.0/16"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        cfg = loader.load_runtime(path)
        self.assertEqual(tuple(cfg.vpns), ("primary",))

        result = loader.check(path)
        self.assertFalse(result.has_errors)
        warnings = self.issues(result, vpng.ConfigIssueLevel.WARNING)
        self.assertTrue(
            any(
                "overlaps VPN transport network" in issue.message
                for issue in warnings
            )
        )

    def test_set_like_duplicates_normalize_and_lint(self):
        td, path = self.write_config(
            """
            managed_vpns = ["PRIMARY", "primary"]
            common_allowed_sources = [
                "10.200.200.8",
                "10.200.200.8/32",
            ]

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.0.0.0/8", "10.0.0.0/8"]
            allowed_sources = [
                "10.200.201.1",
                "10.200.201.1/32",
            ]
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        cfg = loader.load_runtime(path)

        self.assertEqual(tuple(cfg.vpns), ("primary",))
        self.assertEqual(len(cfg.common_allowed_sources), 1)
        self.assertEqual(len(cfg.vpns["primary"].routes), 1)
        self.assertEqual(len(cfg.vpns["primary"].allowed_sources), 1)

        result = loader.check(path)
        self.assertFalse(result.has_errors)
        warnings = self.issues(result, vpng.ConfigIssueLevel.WARNING)
        self.assertGreaterEqual(len(warnings), 4)

    def test_selected_case_insensitive_ambiguity_is_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []

            [vpn.PRIMARY]
            interface = "wg0"
            network = "172.20.126.0/29"
            local_address = "172.20.126.1"
            peers = ["172.20.126.2"]
            routes = ["192.168.0.0/16"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path)
        self.assertTrue(loader.check(path).has_errors)

    def test_unmanaged_case_ambiguity_is_warning(self):
        td, path = self.write_config(
            """
            managed_vpns = ["other"]
            common_allowed_sources = []

            [vpn.other]
            interface = "tun0"
            network = "172.20.140.0/29"
            local_address = "172.20.140.1"
            peers = ["172.20.140.2"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["192.168.0.0/16"]
            allowed_sources = []

            [vpn.PRIMARY]
            interface = "wg0"
            network = "172.20.126.0/29"
            local_address = "172.20.126.1"
            peers = ["172.20.126.2"]
            routes = ["100.64.0.0/10"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        cfg = loader.load_runtime(path)
        self.assertEqual(tuple(cfg.vpns), ("other",))

        result = loader.check(path)
        self.assertFalse(result.has_errors)
        self.assertTrue(
            any(
                "case-insensitive ambiguous unmanaged" in issue.message
                for issue in self.issues(
                    result, vpng.ConfigIssueLevel.WARNING
                )
            )
        )

    def test_duplicate_peers_managed_error_unmanaged_warning(self):
        td1, path1 = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6", "172.20.130.6"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []
            """
        )
        self.addCleanup(td1.cleanup)
        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path1)

        td2, path2 = self.write_config(
            """
            managed_vpns = ["other"]
            common_allowed_sources = []

            [vpn.other]
            interface = "tun0"
            network = "172.20.140.0/29"
            local_address = "172.20.140.1"
            peers = ["172.20.140.2"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6", "172.20.130.6"]
            routes = ["192.168.0.0/16"]
            allowed_sources = []
            """
        )
        self.addCleanup(td2.cleanup)

        result = loader.check(path2)
        self.assertFalse(result.has_errors)
        self.assertTrue(
            any(
                "duplicate peer" in issue.message
                for issue in self.issues(
                    result, vpng.ConfigIssueLevel.WARNING
                )
            )
        )

    def test_noncanonical_cidr_is_rejected(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = ["10.200.200.8/24"]

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.1/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.1.2.3/8"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path)

        result = loader.check(path)
        self.assertTrue(result.has_errors)

    def test_reconcile_interval_must_be_toml_float(self):
        td, path = self.write_config(
            """
            reconcile_interval = 10
            managed_vpns = ["primary"]
            common_allowed_sources = []
            """
            + VALID_PRIMARY
        )
        self.addCleanup(td.cleanup)

        with self.assertRaises(vpng.ConfigError):
            NoSecurityLoader().load_runtime(path)

    def test_managed_interface_conflict_is_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary", "backup"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "tun0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []

            [vpn.backup]
            interface = "tun0"
            network = "172.20.126.0/29"
            local_address = "172.20.126.1"
            peers = ["172.20.126.2"]
            routes = ["192.168.0.0/16"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path)
        self.assertTrue(loader.check(path).has_errors)

    def test_same_profile_route_nesting_is_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.0.0.0/8", "10.20.0.0/16"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path)

    def test_exact_route_ownership_conflict_is_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary", "backup"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []

            [vpn.backup]
            interface = "wg0"
            network = "172.20.126.0/29"
            local_address = "172.20.126.1"
            peers = ["172.20.126.2"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        result = NoSecurityLoader().check(path)
        self.assertTrue(result.has_errors)
        self.assertTrue(
            any(
                "exact ownership conflict" in issue.message
                for issue in self.issues(
                    result, vpng.ConfigIssueLevel.ERROR
                )
            )
        )

    def test_slash31_and_endpoint_addresses_are_valid(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "tun0"
            network = "172.20.130.0/31"
            local_address = "172.20.130.0"
            peers = ["172.20.130.1"]
            routes = ["10.0.0.1/32"]
            allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        cfg = NoSecurityLoader().load_runtime(path)
        self.assertEqual(str(cfg.vpns["primary"].network), "172.20.130.0/31")
        self.assertEqual(str(cfg.vpns["primary"].local_address), "172.20.130.0")
        self.assertEqual(str(cfg.vpns["primary"].peers[0]), "172.20.130.1")

    def test_unknown_top_level_key_is_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []
            surprise = true
            """
            + VALID_PRIMARY
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path)
        self.assertTrue(loader.check(path).has_errors)

    def test_unknown_managed_profile_key_is_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []

            [vpn.primary]
            interface = "vpns0"
            network = "172.20.130.0/29"
            local_address = "172.20.130.1"
            peers = ["172.20.130.6"]
            routes = ["10.0.0.0/8"]
            allowed_sources = []
            surprise = true
            """
        )
        self.addCleanup(td.cleanup)

        loader = NoSecurityLoader()
        with self.assertRaises(vpng.ConfigError):
            loader.load_runtime(path)


    def test_read_toml_uses_o_nofollow_and_fstat_on_opened_object(self):
        class ProbeLoader(vpng.ConfigLoader):
            def __init__(self):
                self.opened_stat_seen = False

            def _validate_config_security(self, path: Path) -> None:
                del path

            def _validate_opened_config_stat(self, path, file_stat):
                del path, file_stat
                self.opened_stat_seen = True

        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        loader = ProbeLoader()
        real_open = vpng.os.open
        flags_seen = []

        def recording_open(target, flags, *args, **kwargs):
            flags_seen.append(flags)
            return real_open(target, flags, *args, **kwargs)

        with mock.patch.object(vpng.os, "open", side_effect=recording_open):
            document = loader._read_toml(path)

        self.assertIn("managed_vpns", document)
        self.assertEqual(len(flags_seen), 1)
        self.assertTrue(flags_seen[0] & vpng.os.O_NOFOLLOW)
        self.assertTrue(flags_seen[0] & vpng.os.O_CLOEXEC)
        self.assertTrue(loader.opened_stat_seen)

    def test_opened_config_stat_revalidates_type_owner_and_mode(self):
        loader = vpng.ConfigLoader()
        path = Path("/etc/vpn-gateway/vpn-gateway.toml")

        loader._validate_opened_config_stat(
            path,
            SimpleNamespace(
                st_mode=stat.S_IFREG | 0o640,
                st_uid=0,
            ),
        )

        bad_stats = (
            SimpleNamespace(st_mode=stat.S_IFIFO | 0o600, st_uid=0),
            SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=1000),
            SimpleNamespace(st_mode=stat.S_IFREG | 0o660, st_uid=0),
        )
        for file_stat in bad_stats:
            with self.subTest(file_stat=file_stat):
                with self.assertRaises(vpng.ConfigError):
                    loader._validate_opened_config_stat(path, file_stat)


    def test_read_toml_rejects_symlink_even_if_precheck_is_bypassed(self):
        class NoPrecheckLoader(vpng.ConfigLoader):
            def _validate_config_security(self, path: Path) -> None:
                del path

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "real.toml"
            target.write_text(
                'managed_vpns = ["primary"]\ncommon_allowed_sources = []\n',
                encoding="utf-8",
            )
            link = root / "vpn-gateway.toml"
            link.symlink_to(target)

            with self.assertRaises(vpng.ConfigError):
                NoPrecheckLoader()._read_toml(link)


    def test_missing_vpn_table_reports_explicit_error(self):
        td, path = self.write_config(
            """
            managed_vpns = ["primary"]
            common_allowed_sources = []
            """
        )
        self.addCleanup(td.cleanup)

        result = NoSecurityLoader().check(path)
        self.assertTrue(result.has_errors)
        self.assertTrue(
            any(
                issue.location == "vpn"
                and issue.message == "required [vpn] table is missing"
                for issue in self.issues(
                    result, vpng.ConfigIssueLevel.ERROR
                )
            )
        )

    def test_security_contract_without_root(self):
        class FakeStatLoader(vpng.ConfigLoader):
            def __init__(self, mapping):
                self.mapping = mapping

            def _lookup(self, path: Path):
                value = self.mapping.get(str(path))
                if isinstance(value, BaseException):
                    raise value
                return value

            def _stat_path(self, path: Path):
                return self._lookup(path)

            def _lstat_path(self, path: Path):
                return self._lookup(path)

        path = Path("/etc/vpn-gateway/vpn-gateway.toml")
        parent = path.parent

        good_parent = SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o750,
            st_uid=0,
        )
        good_file = SimpleNamespace(
            st_mode=stat.S_IFREG | 0o640,
            st_uid=0,
        )

        FakeStatLoader(
            {str(parent): good_parent, str(path): good_file}
        )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): SimpleNamespace(
                        st_mode=stat.S_IFDIR | 0o770,
                        st_uid=0,
                    ),
                    str(path): good_file,
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): good_parent,
                    str(path): SimpleNamespace(
                        st_mode=stat.S_IFREG | 0o660,
                        st_uid=0,
                    ),
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): good_parent,
                    str(path): SimpleNamespace(
                        st_mode=stat.S_IFREG | 0o640,
                        st_uid=1000,
                    ),
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): good_parent,
                    str(path): SimpleNamespace(
                        st_mode=stat.S_IFLNK | 0o777,
                        st_uid=0,
                    ),
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): SimpleNamespace(
                        st_mode=stat.S_IFDIR | 0o750,
                        st_uid=1000,
                    ),
                    str(path): good_file,
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): SimpleNamespace(
                        st_mode=stat.S_IFREG | 0o640,
                        st_uid=0,
                    ),
                    str(path): good_file,
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): good_parent,
                    str(path): SimpleNamespace(
                        st_mode=stat.S_IFIFO | 0o600,
                        st_uid=0,
                    ),
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): FileNotFoundError(2, "No such file or directory"),
                    str(path): good_file,
                }
            )._validate_config_security(path)

        with self.assertRaises(vpng.ConfigError):
            FakeStatLoader(
                {
                    str(parent): good_parent,
                    str(path): FileNotFoundError(2, "No such file or directory"),
                }
            )._validate_config_security(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
