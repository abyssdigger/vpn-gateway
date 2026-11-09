from __future__ import annotations

import math
import os
import re
import stat
import tomllib
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from .constants import (
    DEFAULT_RECONCILE_INTERVAL,
    MAX_RECONCILE_INTERVAL,
    MAX_ROUTE_METRIC,
    MIN_RECONCILE_INTERVAL,
    PEER_METRIC_STEP,
)
from .errors import ConfigError
from .interfaces import InterfaceSelector
from .models import (
    ConfigCheckResult,
    ConfigIssue,
    ConfigIssueLevel,
    GatewayConfig,
    VpnProfileConfig,
)

class ConfigLoader:
    """
    Builds the managed runtime projection and performs offline catalog lint.

    Architectural split:
    - normal startup: validate top-level selection + managed definitions only;
    - --check-config: additionally lint unmanaged definitions/cross-conflicts.

    Ordinary startup must not fail because an unmanaged profile body contains
    malformed values.  The selected profile must, however, be resolvable
    unambiguously.
    """

    _TOP_LEVEL_KEYS = frozenset(
        {
            "reconcile_interval",
            "managed_vpns",
            "common_allowed_sources",
            "vpn",
        }
    )
    _PROFILE_KEYS = frozenset(
        {
            "interface",
            "network",
            "local_address",
            "peers",
            "routes",
            "allowed_sources",
        }
    )
    _PROFILE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,14}$")
    _INTERFACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,14}$")
    _FORBIDDEN_INTERFACES = frozenset({"lo", "any", "default", "all"})

    def load_runtime(self, path: Path) -> GatewayConfig:
        """
        Read selected config path and return managed validated projection.

        Performs config file/directory security checks.
        Does not touch kernel-state or acquire the daemon runtime lock.
        """
        document = self._read_toml(path)
        return self._build_runtime_projection(path, document)

    def check(self, path: Path) -> ConfigCheckResult:
        """
        Full offline lint.

        ERROR:
            anything that would make the managed runtime projection invalid.
        WARNING:
            malformed/unusable unmanaged definitions or future activation
            conflicts; harmless duplicate set-like inputs.
        NOTE:
            valid but operationally notable managed state, currently including
            managed peers=[].

        No runtime lock.  No cleanup.  No kernel side effects.
        """
        document = self._read_toml(path)
        return self._lint_document(path, document)

    # ---- File / TOML boundary ------------------------------------------

    def _stat_path(self, path: Path) -> os.stat_result:
        """Small test seam; normal implementation is a following stat()."""
        return path.stat()

    def _lstat_path(self, path: Path) -> os.stat_result:
        """Small test seam for the config file's final path component."""
        return path.lstat()

    def _read_toml(self, path: Path) -> Mapping[str, object]:
        self._validate_config_security(path)

        fd: int | None = None
        try:
            fd = os.open(
                path,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            opened_stat = os.fstat(fd)
            self._validate_opened_config_stat(path, opened_stat)

            # fdopen() takes ownership of fd on success.
            with os.fdopen(fd, "rb") as fh:
                fd = None
                document = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"{path}: cannot read TOML: {exc}") from exc
        finally:
            if fd is not None:
                os.close(fd)

        if not isinstance(document, dict):
            raise ConfigError(f"{path}: TOML root must be a table")
        return document

    def _validate_opened_config_stat(
        self,
        path: Path,
        file_stat: os.stat_result,
    ) -> None:
        """
        Revalidate the object actually opened after O_NOFOLLOW.

        The pre-open lstat provides deterministic diagnostics for an obvious
        symlink/special file.  O_NOFOLLOW closes the final-component race, and
        fstat makes owner/mode/type checks apply to the opened object itself.
        """
        if not stat.S_ISREG(file_stat.st_mode):
            raise ConfigError(
                f"{path}: opened config object is not a regular file"
            )

        if file_stat.st_uid != 0:
            raise ConfigError(
                f"{path}: opened config file must be owned by root "
                f"(uid 0), got uid {file_stat.st_uid}"
            )

        if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ConfigError(
                f"{path}: opened config file must not be writable "
                "by group/other"
            )

    def _validate_config_security(self, path: Path) -> None:
        """
        Validate the selected config path before reading it.

        Diagnostic order is intentional:
        1. parent exists and is a directory;
        2. config exists and is a regular file;
        3. owner uid;
        4. group/other write bits.

        The final config path component must itself be a regular file, not a
        symlink.  Otherwise a protected /etc/vpn-gateway entry could redirect
        the read to a target whose containing directory has different
        replacement permissions.
        """
        parent = path.parent

        try:
            parent_stat = self._stat_path(parent)
        except OSError as exc:
            raise ConfigError(
                f"{path}: cannot stat parent directory {parent}: {exc}"
            ) from exc

        if not stat.S_ISDIR(parent_stat.st_mode):
            raise ConfigError(
                f"{path}: parent path is not a directory: {parent}"
            )

        try:
            file_stat = self._lstat_path(path)
        except OSError as exc:
            raise ConfigError(f"{path}: cannot lstat config file: {exc}") from exc

        if not stat.S_ISREG(file_stat.st_mode):
            raise ConfigError(
                f"{path}: config path must be a regular file, not a symlink "
                "or other special file"
            )

        if file_stat.st_uid != 0:
            raise ConfigError(
                f"{path}: config file must be owned by root "
                f"(uid 0), got uid {file_stat.st_uid}"
            )

        if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ConfigError(
                f"{path}: config file must not be writable by group/other"
            )

        if parent_stat.st_uid != 0:
            raise ConfigError(
                f"{path}: parent directory {parent} must be owned by root "
                f"(uid 0), got uid {parent_stat.st_uid}"
            )

        if parent_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ConfigError(
                f"{path}: parent directory {parent} must not be writable "
                "by group/other"
            )

    # ---- Runtime projection --------------------------------------------

    def _build_runtime_projection(
        self,
        path: Path,
        document: Mapping[str, object],
    ) -> GatewayConfig:
        """
        Validate only the runtime-selected projection.

        Unmanaged profile bodies are deliberately not value/schema validated.
        Catalog names are inspected only as needed to resolve managed_vpns.
        """
        issues: list[ConfigIssue] = []

        reconcile_interval = self._parse_reconcile_interval(
            document,
            issues=issues,
            level=ConfigIssueLevel.ERROR,
        )
        common_sources = self._parse_top_level_acl(
            document,
            key="common_allowed_sources",
            issues=issues,
            invalid_level=ConfigIssueLevel.ERROR,
            duplicate_level=None,
        )
        selected_refs = self._parse_managed_vpns(
            document,
            issues=issues,
            duplicate_level=None,
        )
        catalog = self._parse_catalog(
            document,
            issues=issues,
            level=ConfigIssueLevel.ERROR,
        )
        self._check_unknown_top_level_keys(
            document,
            issues=issues,
            level=ConfigIssueLevel.ERROR,
        )

        resolved_ids = self._resolve_managed_ids(
            selected_refs,
            catalog,
            issues=issues,
            ambiguity_level=ConfigIssueLevel.ERROR,
            missing_level=ConfigIssueLevel.ERROR,
        )

        managed: dict[str, VpnProfileConfig] = {}
        for profile_id in resolved_ids:
            body = catalog[profile_id]
            parsed = self._parse_profile(
                profile_id,
                body,
                issues=issues,
                invalid_level=ConfigIssueLevel.ERROR,
                duplicate_level=None,
            )
            if parsed is not None:
                managed[profile_id] = parsed

        self._check_cross_conflicts(
            managed,
            managed_ids=frozenset(managed),
            issues=issues,
            include_unmanaged=False,
        )

        errors = [
            issue for issue in issues
            if issue.level is ConfigIssueLevel.ERROR
        ]
        if errors:
            rendered = "; ".join(
                f"{issue.location}: {issue.message}" for issue in errors
            )
            raise ConfigError(f"{path}: invalid runtime config: {rendered}")

        assert reconcile_interval is not None
        assert common_sources is not None
        assert managed

        ordered = {
            profile_id: managed[profile_id]
            for profile_id in sorted(managed, key=str.casefold)
        }
        return GatewayConfig(
            reconcile_interval=reconcile_interval,
            common_allowed_sources=common_sources,
            vpns=MappingProxyType(ordered),
        )

    # ---- Offline lint ---------------------------------------------------

    def _lint_document(
        self,
        path: Path,
        document: Mapping[str, object],
    ) -> ConfigCheckResult:
        """
        Full catalog lint with managed/unmanaged severity separation.

        This intentionally does not call _build_runtime_projection(): doing so
        would stop at runtime-invalid selection and would lose independent
        catalog diagnostics.
        """
        del path
        issues: list[ConfigIssue] = []

        self._check_unknown_top_level_keys(
            document,
            issues=issues,
            level=ConfigIssueLevel.ERROR,
        )
        self._parse_reconcile_interval(
            document,
            issues=issues,
            level=ConfigIssueLevel.ERROR,
        )
        self._parse_top_level_acl(
            document,
            key="common_allowed_sources",
            issues=issues,
            invalid_level=ConfigIssueLevel.ERROR,
            duplicate_level=ConfigIssueLevel.WARNING,
        )
        selected_refs = self._parse_managed_vpns(
            document,
            issues=issues,
            duplicate_level=ConfigIssueLevel.WARNING,
        )
        catalog = self._parse_catalog(
            document,
            issues=issues,
            level=ConfigIssueLevel.ERROR,
        )

        groups = self._catalog_casefold_groups(catalog)

        managed_ids = frozenset(
            self._resolve_managed_ids(
                selected_refs,
                catalog,
                issues=issues,
                ambiguity_level=ConfigIssueLevel.ERROR,
                missing_level=ConfigIssueLevel.ERROR,
            )
        )

        selected_keys = {
            ref.casefold()
            for ref in selected_refs
        }
        for folded, profile_ids in sorted(groups.items()):
            if len(profile_ids) <= 1 or folded in selected_keys:
                continue
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.WARNING,
                    "vpn",
                    "case-insensitive ambiguous unmanaged profile definitions: "
                    + ", ".join(repr(item) for item in profile_ids),
                )
            )

        parsed_profiles: dict[str, VpnProfileConfig] = {}
        for profile_id in sorted(catalog, key=str.casefold):
            managed = profile_id in managed_ids
            invalid_level = (
                ConfigIssueLevel.ERROR
                if managed
                else ConfigIssueLevel.WARNING
            )
            parsed = self._parse_profile(
                profile_id,
                catalog[profile_id],
                issues=issues,
                invalid_level=invalid_level,
                duplicate_level=ConfigIssueLevel.WARNING,
            )
            if parsed is None:
                continue

            parsed_profiles[profile_id] = parsed
            if managed and not parsed.peers:
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.NOTE,
                        f"vpn.{profile_id}.peers",
                        "empty peers list: no UNICAST VPN routes will be "
                        "created; protected routes remain blackholed",
                    )
                )

        self._check_cross_conflicts(
            parsed_profiles,
            managed_ids=managed_ids,
            issues=issues,
            include_unmanaged=True,
        )

        return ConfigCheckResult(tuple(issues))

    # ---- Top-level schema helpers --------------------------------------

    def _check_unknown_top_level_keys(
        self,
        document: Mapping[str, object],
        *,
        issues: list[ConfigIssue],
        level: ConfigIssueLevel,
    ) -> None:
        for key in sorted(set(document) - self._TOP_LEVEL_KEYS):
            issues.append(
                ConfigIssue(
                    level,
                    str(key),
                    "unknown top-level key/section",
                )
            )

    def _parse_reconcile_interval(
        self,
        document: Mapping[str, object],
        *,
        issues: list[ConfigIssue],
        level: ConfigIssueLevel,
    ) -> float | None:
        if "reconcile_interval" not in document:
            return DEFAULT_RECONCILE_INTERVAL

        value = document["reconcile_interval"]
        if type(value) is not float:
            issues.append(
                ConfigIssue(
                    level,
                    "reconcile_interval",
                    "must be a TOML float",
                )
            )
            return None

        if (
            not math.isfinite(value)
            or value < MIN_RECONCILE_INTERVAL
            or value > MAX_RECONCILE_INTERVAL
        ):
            issues.append(
                ConfigIssue(
                    level,
                    "reconcile_interval",
                    f"must be finite and in "
                    f"[{MIN_RECONCILE_INTERVAL}, {MAX_RECONCILE_INTERVAL}]",
                )
            )
            return None

        return value

    def _parse_managed_vpns(
        self,
        document: Mapping[str, object],
        *,
        issues: list[ConfigIssue],
        duplicate_level: ConfigIssueLevel | None,
    ) -> tuple[str, ...]:
        location = "managed_vpns"
        if "managed_vpns" not in document:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "required key is missing",
                )
            )
            return ()

        value = document["managed_vpns"]
        if not isinstance(value, list):
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must be an array of strings",
                )
            )
            return ()

        if not value:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must select at least one profile",
                )
            )
            return ()

        normalized: list[str] = []
        seen: dict[str, int] = {}

        for index, item in enumerate(value):
            item_location = f"{location}[{index}]"
            if not isinstance(item, str):
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        item_location,
                        "must be a string",
                    )
                )
                continue

            folded = item.casefold()
            if folded in seen:
                if duplicate_level is not None:
                    issues.append(
                        ConfigIssue(
                            duplicate_level,
                            item_location,
                            "duplicate managed_vpns selection; "
                            f"same profile as index {seen[folded]}",
                        )
                    )
                continue

            seen[folded] = index
            normalized.append(item)

        if not normalized and value:
            # All entries were type-invalid.  Their element errors are more
            # useful than a second "empty selection" error.
            return ()

        return tuple(normalized)

    def _parse_catalog(
        self,
        document: Mapping[str, object],
        *,
        issues: list[ConfigIssue],
        level: ConfigIssueLevel,
    ) -> Mapping[str, object]:
        if "vpn" not in document:
            issues.append(
                ConfigIssue(
                    level,
                    "vpn",
                    "required [vpn] table is missing",
                )
            )
            return {}

        value = document["vpn"]
        if not isinstance(value, dict):
            issues.append(
                ConfigIssue(
                    level,
                    "vpn",
                    "must be a TOML table containing profile definitions",
                )
            )
            return {}
        return value

    def _parse_top_level_acl(
        self,
        document: Mapping[str, object],
        *,
        key: str,
        issues: list[ConfigIssue],
        invalid_level: ConfigIssueLevel,
        duplicate_level: ConfigIssueLevel | None,
    ) -> tuple[IPv4Network, ...] | None:
        if key not in document:
            issues.append(
                ConfigIssue(
                    invalid_level,
                    key,
                    "required key is missing",
                )
            )
            return None

        return self._parse_acl_list(
            document[key],
            location=key,
            issues=issues,
            invalid_level=invalid_level,
            duplicate_level=duplicate_level,
        )

    # ---- Selection resolution ------------------------------------------

    @staticmethod
    def _catalog_casefold_groups(
        catalog: Mapping[str, object],
    ) -> Mapping[str, tuple[str, ...]]:
        groups: dict[str, list[str]] = {}
        for profile_id in catalog:
            groups.setdefault(profile_id.casefold(), []).append(profile_id)
        return {
            folded: tuple(sorted(profile_ids, key=str.casefold))
            for folded, profile_ids in groups.items()
        }

    def _resolve_managed_ids(
        self,
        selected_refs: Sequence[str],
        catalog: Mapping[str, object],
        *,
        issues: list[ConfigIssue],
        ambiguity_level: ConfigIssueLevel,
        missing_level: ConfigIssueLevel,
    ) -> tuple[str, ...]:
        groups = self._catalog_casefold_groups(catalog)
        resolved: list[str] = []

        for ref in selected_refs:
            matches = groups.get(ref.casefold(), ())
            if not matches:
                issues.append(
                    ConfigIssue(
                        missing_level,
                        "managed_vpns",
                        f"selected profile {ref!r} has no [vpn.<profile>] "
                        "definition",
                    )
                )
                continue

            if len(matches) != 1:
                issues.append(
                    ConfigIssue(
                        ambiguity_level,
                        "managed_vpns",
                        f"selected profile {ref!r} resolves ambiguously to: "
                        + ", ".join(repr(item) for item in matches),
                    )
                )
                continue

            resolved.append(matches[0])

        return tuple(sorted(set(resolved), key=str.casefold))

    # ---- Profile parsing ------------------------------------------------

    def _parse_profile(
        self,
        profile_id: str,
        body: object,
        *,
        issues: list[ConfigIssue],
        invalid_level: ConfigIssueLevel,
        duplicate_level: ConfigIssueLevel | None,
    ) -> VpnProfileConfig | None:
        base = f"vpn.{profile_id}"
        valid = True

        if not self._PROFILE_ID_RE.fullmatch(profile_id):
            issues.append(
                ConfigIssue(
                    invalid_level,
                    base,
                    "profile ID must match "
                    "[A-Za-z][A-Za-z0-9_-]{0,14}",
                )
            )
            valid = False

        if not isinstance(body, dict):
            issues.append(
                ConfigIssue(
                    invalid_level,
                    base,
                    "profile definition must be a TOML table",
                )
            )
            return None

        unknown = sorted(set(body) - self._PROFILE_KEYS)
        for key in unknown:
            issues.append(
                ConfigIssue(
                    invalid_level,
                    f"{base}.{key}",
                    "unknown profile key/section",
                )
            )
            valid = False

        missing = sorted(self._PROFILE_KEYS - set(body))
        for key in missing:
            issues.append(
                ConfigIssue(
                    invalid_level,
                    f"{base}.{key}",
                    "required key is missing",
                )
            )
            valid = False

        interface = (
            self._parse_interface(
                body["interface"],
                location=f"{base}.interface",
                issues=issues,
                level=invalid_level,
            )
            if "interface" in body
            else None
        )
        network = (
            self._parse_network(
                body["network"],
                location=f"{base}.network",
                issues=issues,
                level=invalid_level,
                forbid_32=True,
                forbid_default=False,
            )
            if "network" in body
            else None
        )
        local_address = (
            self._parse_ipv4_address(
                body["local_address"],
                location=f"{base}.local_address",
                issues=issues,
                level=invalid_level,
            )
            if "local_address" in body
            else None
        )
        peers = (
            self._parse_peers(
                body["peers"],
                location=f"{base}.peers",
                issues=issues,
                invalid_level=invalid_level,
            )
            if "peers" in body
            else None
        )
        routes = (
            self._parse_routes(
                body["routes"],
                location=f"{base}.routes",
                issues=issues,
                invalid_level=invalid_level,
                duplicate_level=duplicate_level,
            )
            if "routes" in body
            else None
        )
        allowed_sources = (
            self._parse_acl_list(
                body["allowed_sources"],
                location=f"{base}.allowed_sources",
                issues=issues,
                invalid_level=invalid_level,
                duplicate_level=duplicate_level,
            )
            if "allowed_sources" in body
            else None
        )

        if any(
            value is None
            for value in (
                interface,
                network,
                local_address,
                peers,
                routes,
                allowed_sources,
            )
        ):
            valid = False

        if network is not None and local_address is not None:
            if local_address not in network:
                issues.append(
                    ConfigIssue(
                        invalid_level,
                        f"{base}.local_address",
                        f"{local_address} is outside VPN network {network}",
                    )
                )
                valid = False

        if peers is not None:
            if len(peers) * PEER_METRIC_STEP > MAX_ROUTE_METRIC:
                issues.append(
                    ConfigIssue(
                        invalid_level,
                        f"{base}.peers",
                        "peer count makes route metric exceed unsigned "
                        "32-bit range",
                    )
                )
                valid = False

            if network is not None:
                for index, peer in enumerate(peers):
                    if peer not in network:
                        issues.append(
                            ConfigIssue(
                                invalid_level,
                                f"{base}.peers[{index}]",
                                f"{peer} is outside VPN network {network}",
                            )
                        )
                        valid = False
            if local_address is not None:
                for index, peer in enumerate(peers):
                    if peer == local_address:
                        issues.append(
                            ConfigIssue(
                                invalid_level,
                                f"{base}.peers[{index}]",
                                "peer must not equal local_address",
                            )
                        )
                        valid = False

        if not valid:
            return None

        assert interface is not None
        assert network is not None
        assert local_address is not None
        assert peers is not None
        assert routes is not None
        assert allowed_sources is not None

        return VpnProfileConfig(
            profile_id=profile_id,
            interface=interface,
            network=network,
            local_address=local_address,
            peers=peers,
            routes=routes,
            allowed_sources=allowed_sources,
        )

    def _parse_interface(
        self,
        value: object,
        *,
        location: str,
        issues: list[ConfigIssue],
        level: ConfigIssueLevel,
    ) -> InterfaceSelector | None:
        if not isinstance(value, str):
            issues.append(
                ConfigIssue(level, location, "must be a string")
            )
            return None

        try:
            return InterfaceSelector.parse(value)
        except ValueError as exc:
            issues.append(
                ConfigIssue(
                    level,
                    location,
                    f"invalid interface selector: {exc}",
                )
            )
            return None

    def _parse_ipv4_address(
        self,
        value: object,
        *,
        location: str,
        issues: list[ConfigIssue],
        level: ConfigIssueLevel,
    ) -> IPv4Address | None:
        if not isinstance(value, str):
            issues.append(
                ConfigIssue(level, location, "must be an IPv4 address string")
            )
            return None

        try:
            return IPv4Address(value)
        except ValueError as exc:
            issues.append(
                ConfigIssue(level, location, f"invalid IPv4 address: {exc}")
            )
            return None

    def _parse_network(
        self,
        value: object,
        *,
        location: str,
        issues: list[ConfigIssue],
        level: ConfigIssueLevel,
        forbid_32: bool,
        forbid_default: bool,
    ) -> IPv4Network | None:
        if not isinstance(value, str):
            issues.append(
                ConfigIssue(level, location, "must be an IPv4 CIDR string")
            )
            return None

        if "/" not in value:
            issues.append(
                ConfigIssue(level, location, "must use explicit CIDR notation")
            )
            return None

        try:
            network = IPv4Network(value, strict=True)
        except ValueError as exc:
            issues.append(
                ConfigIssue(
                    level,
                    location,
                    f"invalid or non-canonical IPv4 CIDR: {exc}",
                )
            )
            return None

        if forbid_32 and network.prefixlen == 32:
            issues.append(
                ConfigIssue(level, location, "/32 VPN network is forbidden")
            )
            return None

        if forbid_default and network.prefixlen == 0:
            issues.append(
                ConfigIssue(level, location, "0.0.0.0/0 route is forbidden")
            )
            return None

        return network

    def _parse_string_array(
        self,
        value: object,
        *,
        location: str,
        issues: list[ConfigIssue],
        level: ConfigIssueLevel,
    ) -> list[str] | None:
        if not isinstance(value, list):
            issues.append(
                ConfigIssue(level, location, "must be an array of strings")
            )
            return None

        parsed: list[str] = []
        valid = True
        for index, item in enumerate(value):
            if not isinstance(item, str):
                issues.append(
                    ConfigIssue(
                        level,
                        f"{location}[{index}]",
                        "must be a string",
                    )
                )
                valid = False
                continue
            parsed.append(item)

        return parsed if valid else None

    def _parse_peers(
        self,
        value: object,
        *,
        location: str,
        issues: list[ConfigIssue],
        invalid_level: ConfigIssueLevel,
    ) -> tuple[IPv4Address, ...] | None:
        raw = self._parse_string_array(
            value,
            location=location,
            issues=issues,
            level=invalid_level,
        )
        if raw is None:
            return None

        peers: list[IPv4Address] = []
        seen: dict[IPv4Address, int] = {}
        valid = True

        for index, item in enumerate(raw):
            try:
                peer = IPv4Address(item)
            except ValueError as exc:
                issues.append(
                    ConfigIssue(
                        invalid_level,
                        f"{location}[{index}]",
                        f"invalid IPv4 address: {exc}",
                    )
                )
                valid = False
                continue

            if peer in seen:
                issues.append(
                    ConfigIssue(
                        invalid_level,
                        f"{location}[{index}]",
                        f"duplicate peer; same address as index {seen[peer]}",
                    )
                )
                valid = False
                continue

            seen[peer] = index
            peers.append(peer)

        return tuple(peers) if valid else None

    def _parse_routes(
        self,
        value: object,
        *,
        location: str,
        issues: list[ConfigIssue],
        invalid_level: ConfigIssueLevel,
        duplicate_level: ConfigIssueLevel | None,
    ) -> tuple[IPv4Network, ...] | None:
        raw = self._parse_string_array(
            value,
            location=location,
            issues=issues,
            level=invalid_level,
        )
        if raw is None:
            return None

        if not raw:
            issues.append(
                ConfigIssue(
                    invalid_level,
                    location,
                    "must contain at least one protected route",
                )
            )
            return None

        routes: list[IPv4Network] = []
        seen: dict[IPv4Network, int] = {}
        valid = True

        for index, item in enumerate(raw):
            route = self._parse_network(
                item,
                location=f"{location}[{index}]",
                issues=issues,
                level=invalid_level,
                forbid_32=False,
                forbid_default=True,
            )
            if route is None:
                valid = False
                continue

            if route in seen:
                if duplicate_level is not None:
                    issues.append(
                        ConfigIssue(
                            duplicate_level,
                            f"{location}[{index}]",
                            f"duplicate protected route; same as index "
                            f"{seen[route]}",
                        )
                    )
                continue

            seen[route] = index
            routes.append(route)

        for left_index, left in enumerate(routes):
            for right in routes[left_index + 1:]:
                if left.overlaps(right):
                    issues.append(
                        ConfigIssue(
                            invalid_level,
                            location,
                            f"protected routes overlap: {left} and {right}",
                        )
                    )
                    valid = False

        if not valid:
            return None

        return tuple(
            sorted(
                routes,
                key=lambda net: (int(net.network_address), net.prefixlen),
            )
        )

    def _parse_acl_list(
        self,
        value: object,
        *,
        location: str,
        issues: list[ConfigIssue],
        invalid_level: ConfigIssueLevel,
        duplicate_level: ConfigIssueLevel | None,
    ) -> tuple[IPv4Network, ...] | None:
        raw = self._parse_string_array(
            value,
            location=location,
            issues=issues,
            level=invalid_level,
        )
        if raw is None:
            return None

        networks: list[IPv4Network] = []
        seen: dict[IPv4Network, int] = {}
        valid = True

        for index, item in enumerate(raw):
            item_location = f"{location}[{index}]"
            try:
                if "/" in item:
                    network = IPv4Network(item, strict=True)
                else:
                    address = IPv4Address(item)
                    network = IPv4Network(f"{address}/32", strict=True)
            except ValueError as exc:
                issues.append(
                    ConfigIssue(
                        invalid_level,
                        item_location,
                        f"invalid or non-canonical IPv4 ACL entry: {exc}",
                    )
                )
                valid = False
                continue

            if network in seen:
                if duplicate_level is not None:
                    issues.append(
                        ConfigIssue(
                            duplicate_level,
                            item_location,
                            f"duplicate ACL entry after normalization; "
                            f"same as index {seen[network]}",
                        )
                    )
                continue

            seen[network] = index
            networks.append(network)

        if not valid:
            return None

        return tuple(
            sorted(
                networks,
                key=lambda net: (int(net.network_address), net.prefixlen),
            )
        )

    # ---- Cross-profile semantics ---------------------------------------

    def _check_cross_conflicts(
        self,
        profiles: Mapping[str, VpnProfileConfig],
        *,
        managed_ids: frozenset[str],
        issues: list[ConfigIssue],
        include_unmanaged: bool,
    ) -> None:
        profile_ids = sorted(profiles, key=str.casefold)

        def conflict_level(*owners: str) -> ConfigIssueLevel | None:
            if all(owner in managed_ids for owner in owners):
                return ConfigIssueLevel.ERROR
            if include_unmanaged:
                return ConfigIssueLevel.WARNING
            return None

        # Interfaces are exclusive only within a simultaneously managed set.
        for left_index, left_id in enumerate(profile_ids):
            left = profiles[left_id]
            for right_id in profile_ids[left_index + 1:]:
                right = profiles[right_id]
                if not left.interface.overlaps(right.interface):
                    continue
                level = conflict_level(left_id, right_id)
                if level is None:
                    continue
                issues.append(
                    ConfigIssue(
                        level,
                        "vpn",
                        f"interface selectors {str(left.interface)!r} and "
                        f"{str(right.interface)!r} overlap for profiles "
                        f"{left_id!r} and {right_id!r}",
                    )
                )

        # Protected route space is globally exclusive.
        for left_index, left_id in enumerate(profile_ids):
            left = profiles[left_id]
            for right_id in profile_ids[left_index + 1:]:
                right = profiles[right_id]
                level = conflict_level(left_id, right_id)
                if level is None:
                    continue
                for left_route in left.routes:
                    for right_route in right.routes:
                        if not left_route.overlaps(right_route):
                            continue
                        relation = (
                            "exact ownership conflict"
                            if left_route == right_route
                            else "overlap"
                        )
                        issues.append(
                            ConfigIssue(
                                level,
                                "vpn",
                                f"protected route {relation} between "
                                f"{left_id!r}:{left_route} and "
                                f"{right_id!r}:{right_route}",
                            )
                        )

        # Every route must be disjoint from every VPN transport network.
        for route_owner in profile_ids:
            route_profile = profiles[route_owner]
            for network_owner in profile_ids:
                network_profile = profiles[network_owner]
                level = conflict_level(route_owner, network_owner)
                if level is None:
                    continue
                for route in route_profile.routes:
                    if not route.overlaps(network_profile.network):
                        continue
                    issues.append(
                        ConfigIssue(
                            level,
                            "vpn",
                            f"protected route {route_owner!r}:{route} "
                            f"overlaps VPN transport network "
                            f"{network_owner!r}:{network_profile.network}",
                        )
                    )


# ---------------------------------------------------------------------------
# Runtime profile object
# ---------------------------------------------------------------------------


