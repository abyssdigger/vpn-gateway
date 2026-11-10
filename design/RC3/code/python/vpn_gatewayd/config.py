from __future__ import annotations

import math
import os
import re
import stat
import tomllib
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .constants import (
    BLACKHOLE_METRIC,
    DEFAULT_RECONCILE_INTERVAL,
    FIRST_UNICAST_METRIC,
    MAX_RECONCILE_INTERVAL,
    MIN_RECONCILE_INTERVAL,
    ROUTE_METRIC_STEP,
)
from .errors import ConfigError
from .interfaces import BindingSpec, InterfaceSelector, InterfaceSelectorKind
from .models import (
    ConfigCheckResult,
    ConfigIssue,
    ConfigIssueLevel,
    GatewayConfig,
    VpnProfileConfig,
)


class ConfigLoader:
    """Security-aware staged parser for the RC3 enabled projection."""

    _TOP_LEVEL_KEYS = frozenset(
        {
            "enabled",
            "reconcile_interval",
            "common_allowed_sources",
            "profiles",
        }
    )
    _PROFILE_KEYS = frozenset(
        {"enabled", "routes", "bindings", "allowed_sources"}
    )
    _BINDING_KEYS = frozenset({"interface", "network"})
    _PROFILE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,14}$")

    def load_runtime(self, path: Path) -> GatewayConfig:
        document = self._read_toml(path)
        issues: list[ConfigIssue] = []
        config = self._project(document, issues=issues, warn_duplicates=False)
        errors = [i for i in issues if i.level is ConfigIssueLevel.ERROR]
        if errors or config is None:
            rendered = "; ".join(
                f"{issue.location}: {issue.message}" for issue in errors
            )
            raise ConfigError(f"{path}: invalid runtime config: {rendered}")
        return config

    def check(self, path: Path) -> ConfigCheckResult:
        document = self._read_toml(path)
        issues: list[ConfigIssue] = []
        self._project(document, issues=issues, warn_duplicates=True)
        return ConfigCheckResult(tuple(issues))

    # ---- File / TOML boundary ------------------------------------------

    def _stat_path(self, path: Path) -> os.stat_result:
        return path.stat()

    def _lstat_path(self, path: Path) -> os.stat_result:
        return path.lstat()

    def _read_toml(self, path: Path) -> Mapping[str, object]:
        self._validate_config_security(path)

        fd: int | None = None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            opened_stat = os.fstat(fd)
            self._validate_opened_config_stat(path, opened_stat)
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
                f"{path}: opened config file must not be writable by group/other"
            )

    def _validate_config_security(self, path: Path) -> None:
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

    # ---- Staged projection ---------------------------------------------

    def _project(
        self,
        document: Mapping[str, object],
        *,
        issues: list[ConfigIssue],
        warn_duplicates: bool,
    ) -> GatewayConfig | None:
        self._check_unknown_keys(
            document,
            self._TOP_LEVEL_KEYS,
            "",
            issues,
        )
        enabled = self._parse_bool(
            document.get("enabled", True),
            "enabled",
            issues,
        )
        if enabled is None:
            return None

        # Intentional global off switch: profile bodies and operational body
        # values are not parsed once the envelope says disabled.
        if not enabled:
            return GatewayConfig(
                enabled=False,
                reconcile_interval=DEFAULT_RECONCILE_INTERVAL,
                common_allowed_sources=(),
                profiles=MappingProxyType({}),
            )

        reconcile_interval = self._parse_reconcile_interval(document, issues)
        common_sources = self._parse_acl_list(
            document.get("common_allowed_sources", []),
            "common_allowed_sources",
            issues,
            warn_duplicates=warn_duplicates,
        )

        raw_profiles = document.get("profiles")
        if not isinstance(raw_profiles, dict):
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    "profiles",
                    "required top-level profiles table is missing or invalid",
                )
            )
            return None

        enabled_bodies: list[tuple[str, Mapping[str, object]]] = []
        for profile_id, raw_body in raw_profiles.items():
            location = f"profiles.{profile_id}"
            if not isinstance(raw_body, dict):
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        location,
                        "profile definition must be a TOML table",
                    )
                )
                continue
            profile_enabled = self._parse_bool(
                raw_body.get("enabled", True),
                f"{location}.enabled",
                issues,
            )
            if profile_enabled is None:
                continue
            if not profile_enabled:
                continue
            enabled_bodies.append((str(profile_id), raw_body))

        if not enabled_bodies:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    "profiles",
                    "enabled config requires at least one enabled profile",
                )
            )

        folded: dict[str, str] = {}
        profiles: dict[str, VpnProfileConfig] = {}
        for profile_id, body in enabled_bodies:
            location = f"profiles.{profile_id}"
            if not self._PROFILE_ID_RE.fullmatch(profile_id):
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        location,
                        "profile ID must match "
                        "[A-Za-z][A-Za-z0-9_-]{0,14}",
                    )
                )
                continue
            key = profile_id.casefold()
            previous = folded.get(key)
            if previous is not None:
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        location,
                        "profile ID collides case-insensitively with "
                        f"{previous!r}",
                    )
                )
                continue
            folded[key] = profile_id
            parsed = self._parse_enabled_profile(
                profile_id,
                body,
                issues=issues,
                warn_duplicates=warn_duplicates,
            )
            if parsed is not None:
                profiles[profile_id] = parsed

        self._check_cross_conflicts(profiles, issues)

        if reconcile_interval is None or common_sources is None:
            return None
        if any(i.level is ConfigIssueLevel.ERROR for i in issues):
            return None

        ordered = {
            profile_id: profiles[profile_id]
            for profile_id in sorted(profiles, key=str.casefold)
        }
        return GatewayConfig(
            enabled=True,
            reconcile_interval=reconcile_interval,
            common_allowed_sources=common_sources,
            profiles=MappingProxyType(ordered),
        )

    # ---- Scalar/schema helpers -----------------------------------------

    def _check_unknown_keys(
        self,
        body: Mapping[str, object],
        allowed: frozenset[str],
        base: str,
        issues: list[ConfigIssue],
    ) -> bool:
        valid = True
        for key in sorted(set(body) - allowed):
            location = f"{base}.{key}" if base else str(key)
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "unknown key/section",
                )
            )
            valid = False
        return valid

    def _parse_bool(
        self,
        value: object,
        location: str,
        issues: list[ConfigIssue],
    ) -> bool | None:
        if type(value) is not bool:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must be boolean",
                )
            )
            return None
        return value

    def _parse_reconcile_interval(
        self,
        document: Mapping[str, object],
        issues: list[ConfigIssue],
    ) -> float | None:
        value = document.get(
            "reconcile_interval",
            DEFAULT_RECONCILE_INTERVAL,
        )
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    "reconcile_interval",
                    "must be a finite number",
                )
            )
            return None
        result = float(value)
        if not math.isfinite(result):
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    "reconcile_interval",
                    "must be finite",
                )
            )
            return None
        if not MIN_RECONCILE_INTERVAL <= result <= MAX_RECONCILE_INTERVAL:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    "reconcile_interval",
                    f"must be in [{MIN_RECONCILE_INTERVAL}, "
                    f"{MAX_RECONCILE_INTERVAL}]",
                )
            )
            return None
        return result

    # ---- Enabled profile parsing ---------------------------------------

    def _parse_enabled_profile(
        self,
        profile_id: str,
        body: Mapping[str, object],
        *,
        issues: list[ConfigIssue],
        warn_duplicates: bool,
    ) -> VpnProfileConfig | None:
        base = f"profiles.{profile_id}"
        valid = self._check_unknown_keys(
            body,
            self._PROFILE_KEYS,
            base,
            issues,
        )

        for key in ("routes", "bindings"):
            if key not in body:
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        f"{base}.{key}",
                        "required key is missing",
                    )
                )
                valid = False

        routes = (
            self._parse_routes(
                body["routes"],
                f"{base}.routes",
                issues,
            )
            if "routes" in body
            else None
        )
        bindings = (
            self._parse_bindings(
                body["bindings"],
                f"{base}.bindings",
                issues,
            )
            if "bindings" in body
            else None
        )
        allowed = self._parse_acl_list(
            body.get("allowed_sources", []),
            f"{base}.allowed_sources",
            issues,
            warn_duplicates=warn_duplicates,
        )
        if routes is None or bindings is None or allowed is None:
            valid = False
        if not valid:
            return None

        return VpnProfileConfig(
            profile_id=profile_id,
            routes=routes,
            bindings=bindings,
            allowed_sources=allowed,
        )

    def _parse_bindings(
        self,
        value: object,
        location: str,
        issues: list[ConfigIssue],
    ) -> tuple[BindingSpec, ...] | None:
        if not isinstance(value, list):
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must be an array of inline BindingSpec tables",
                )
            )
            return None
        if not value:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must contain at least one BindingSpec",
                )
            )
            return None

        result: list[BindingSpec] = []
        exact_rank = 0
        valid = True
        for index, raw in enumerate(value):
            base = f"{location}[{index}]"
            if not isinstance(raw, dict):
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        base,
                        "BindingSpec must be an inline table",
                    )
                )
                valid = False
                continue
            if not self._check_unknown_keys(
                raw,
                self._BINDING_KEYS,
                base,
                issues,
            ):
                valid = False
            for key in self._BINDING_KEYS:
                if key not in raw:
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.ERROR,
                            f"{base}.{key}",
                            "required key is missing",
                        )
                    )
                    valid = False

            selector: InterfaceSelector | None = None
            network: IPv4Network | None = None
            if "interface" in raw:
                try:
                    selector = InterfaceSelector.parse(raw["interface"])
                except (TypeError, ValueError) as exc:
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.ERROR,
                            f"{base}.interface",
                            f"invalid interface selector: {exc}",
                        )
                    )
                    valid = False
            if "network" in raw:
                network = self._parse_network(
                    raw["network"],
                    f"{base}.network",
                    issues,
                    forbid_32=True,
                    forbid_default=False,
                )
                if network is None:
                    valid = False

            if selector is None or network is None:
                continue
            rank = (
                exact_rank
                if selector.kind is InterfaceSelectorKind.EXACT
                else None
            )
            result.append(
                BindingSpec(
                    interface=selector,
                    network=network,
                    config_index=index,
                    exact_rank=rank,
                )
            )
            if rank is not None:
                exact_rank += 1

        if not valid:
            return None

        last_exact_metric = (
            FIRST_UNICAST_METRIC
            + (exact_rank - 1) * ROUTE_METRIC_STEP
            if exact_rank
            else None
        )
        if last_exact_metric is not None and last_exact_metric >= BLACKHOLE_METRIC:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "exact BindingSpec metrics reach or exceed BLACKHOLE_METRIC",
                )
            )
            return None

        has_prefix = any(
            spec.interface.kind is InterfaceSelectorKind.PREFIX
            for spec in result
        )
        dynamic_min = FIRST_UNICAST_METRIC + exact_rank * ROUTE_METRIC_STEP
        if has_prefix and dynamic_min >= BLACKHOLE_METRIC:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "no metric slot remains for prefix BindingSpec allocator",
                )
            )
            return None

        return tuple(result)

    def _parse_network(
        self,
        value: object,
        location: str,
        issues: list[ConfigIssue],
        *,
        forbid_32: bool,
        forbid_default: bool,
    ) -> IPv4Network | None:
        if not isinstance(value, str):
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must be an IPv4 CIDR string",
                )
            )
            return None
        if "/" not in value:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must use explicit CIDR notation",
                )
            )
            return None
        try:
            network = IPv4Network(value, strict=True)
        except ValueError as exc:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    f"invalid or non-canonical IPv4 CIDR: {exc}",
                )
            )
            return None
        if forbid_32 and network.prefixlen == 32:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "/32 VPN network is forbidden",
                )
            )
            return None
        if forbid_default and network.prefixlen == 0:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "0.0.0.0/0 route is forbidden",
                )
            )
            return None
        return network

    def _parse_routes(
        self,
        value: object,
        location: str,
        issues: list[ConfigIssue],
    ) -> tuple[IPv4Network, ...] | None:
        raw = self._parse_string_array(value, location, issues)
        if raw is None:
            return None
        if not raw:
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
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
                f"{location}[{index}]",
                issues,
                forbid_32=False,
                forbid_default=True,
            )
            if route is None:
                valid = False
                continue
            if route in seen:
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        f"{location}[{index}]",
                        f"duplicate protected route; same as index {seen[route]}",
                    )
                )
                valid = False
                continue
            seen[route] = index
            routes.append(route)

        for i, left in enumerate(routes):
            for right in routes[i + 1:]:
                if left.overlaps(right):
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.ERROR,
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
        location: str,
        issues: list[ConfigIssue],
        *,
        warn_duplicates: bool,
    ) -> tuple[IPv4Network, ...] | None:
        raw = self._parse_string_array(value, location, issues)
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
                        ConfigIssueLevel.ERROR,
                        item_location,
                        f"invalid or non-canonical IPv4 ACL entry: {exc}",
                    )
                )
                valid = False
                continue
            if network in seen:
                if warn_duplicates:
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.WARNING,
                            item_location,
                            "duplicate ACL entry after normalization; "
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

    def _parse_string_array(
        self,
        value: object,
        location: str,
        issues: list[ConfigIssue],
    ) -> list[str] | None:
        if not isinstance(value, list):
            issues.append(
                ConfigIssue(
                    ConfigIssueLevel.ERROR,
                    location,
                    "must be an array of strings",
                )
            )
            return None
        parsed: list[str] = []
        valid = True
        for index, item in enumerate(value):
            if not isinstance(item, str):
                issues.append(
                    ConfigIssue(
                        ConfigIssueLevel.ERROR,
                        f"{location}[{index}]",
                        "must be a string",
                    )
                )
                valid = False
            else:
                parsed.append(item)
        return parsed if valid else None

    # ---- Cross-profile semantics ---------------------------------------

    def _check_cross_conflicts(
        self,
        profiles: Mapping[str, VpnProfileConfig],
        issues: list[ConfigIssue],
    ) -> None:
        ordered_profiles = [
            profiles[key] for key in sorted(profiles, key=str.casefold)
        ]

        selectors: list[tuple[str, int, InterfaceSelector]] = []
        binding_networks: list[tuple[str, int, IPv4Network]] = []
        protected: list[tuple[str, IPv4Network]] = []

        for profile in ordered_profiles:
            for spec in profile.bindings:
                selectors.append(
                    (profile.profile_id, spec.config_index, spec.interface)
                )
                binding_networks.append(
                    (profile.profile_id, spec.config_index, spec.network)
                )
            for route in profile.routes:
                protected.append((profile.profile_id, route))

        for i, (left_profile, left_index, left) in enumerate(selectors):
            for right_profile, right_index, right in selectors[i + 1:]:
                if left.overlaps(right):
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.ERROR,
                            "profiles",
                            "BindingSpec selector namespaces overlap: "
                            f"{left_profile}[{left_index}]={left!s} and "
                            f"{right_profile}[{right_index}]={right!s}",
                        )
                    )

        for i, (left_profile, left) in enumerate(protected):
            for right_profile, right in protected[i + 1:]:
                if left == right:
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.ERROR,
                            "profiles",
                            "protected route is owned by multiple profiles: "
                            f"{left} ({left_profile}, {right_profile})",
                        )
                    )
                elif left.overlaps(right):
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.ERROR,
                            "profiles",
                            "protected routes overlap across profiles: "
                            f"{left_profile}:{left} and "
                            f"{right_profile}:{right}",
                        )
                    )

        for profile_id, route in protected:
            for net_profile, index, network in binding_networks:
                if route.overlaps(network):
                    issues.append(
                        ConfigIssue(
                            ConfigIssueLevel.ERROR,
                            "profiles",
                            "protected route overlaps enabled BindingSpec.network: "
                            f"{profile_id}:{route} and "
                            f"{net_profile}[{index}]:{network}",
                        )
                    )
