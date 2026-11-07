#!/usr/bin/env python3
"""
vpn-gatewayd — implementation for architecture RC2.4.

This file is intentionally rebuilt from the architecture document only.
It does not preserve API or structure from earlier skeletons.

Current scope:
- stdlib only;
- one long-lived daemon process;
- managed_vpns runtime projection;
- route-only reconciliation plan;
- fixed firewall/NAT infrastructure with static MASQUERADE;
- STARTING/ACTIVE/DEGRADED/ISOLATED/STOPPING lifecycle;
- stateless marker-based cleanup;
- no config reload;
- no dynamic NAT model;
- no separate per-profile NAT-safety predicate;
- no separate preflight phase.

Implementation details explicitly left open by the architecture remain TODOs here,
especially firewall canonical comparison and the serialized Netlink/event loop.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import logging
import math
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence


# ---------------------------------------------------------------------------
# Architecture: RC2.4
# Implementation: RC2.4
# ---------------------------------------------------------------------------

VERSION = "RC2.4"

DEFAULT_CONFIG_PATH = Path("/etc/vpn-gateway/vpn-gateway.toml")
DEFAULT_LOCK_PATH = Path("/run/vpn-gateway/vpn-gatewayd.lock")

DEFAULT_RECONCILE_INTERVAL = 10.0
MIN_RECONCILE_INTERVAL = 1.0
MAX_RECONCILE_INTERVAL = 60.0
DEFAULT_FAILURE_REMINDER_INTERVAL = 300.0

BLACKHOLE_ROUTE_PROTO = 201
KERNEL_ROUTE_PROTO = 2
VPN_ROUTE_PROTO = 202
BLACKHOLE_METRIC = 65536
PEER_METRIC_STEP = 10
MAX_ROUTE_METRIC = (1 << 32) - 1

VPNG_CHAIN_PREFIX = "VPNG-"

LOG = logging.getLogger("vpn-gatewayd")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GatewayError(Exception):
    """Base class for expected daemon/domain errors."""


class ConfigError(GatewayError):
    """Runtime configuration cannot be projected safely."""


class InstanceLockError(GatewayError):
    """Lifetime lock could not be acquired safely."""


class CleanupError(GatewayError):
    """Marker-based cleanup could not be completed and verified."""


class PlanValidationError(GatewayError):
    """A route plan violates architecture invariants."""


class ReconciliationError(GatewayError):
    """A reconciliation pass violated its completion/result contract."""


class FirewallInspectionError(GatewayError):
    """Expected firewall snapshot parse/normalization/comparison failure."""


class KernelError(GatewayError):
    """Base class for expected kernel/userspace adapter failures."""


# ---------------------------------------------------------------------------
# Closed state sets
# ---------------------------------------------------------------------------


class DaemonState(Enum):
    STARTING = auto()
    ACTIVE = auto()
    DEGRADED = auto()
    ISOLATED = auto()
    STOPPING = auto()


class FirewallSafety(Enum):
    SAFE = auto()
    UNSAFE = auto()
    UNKNOWN = auto()


class RouteType(Enum):
    UNICAST = auto()
    BLACKHOLE = auto()
    UNREACHABLE = auto()
    PROHIBIT = auto()
    THROW = auto()


class ProfileResourceSet(Enum):
    CONFIGURED = auto()
    OWNED = auto()


class ApplyStateResult(Enum):
    SUCCESS = auto()
    FAIL = auto()


class ConfigIssueLevel(Enum):
    ERROR = auto()
    WARNING = auto()
    NOTE = auto()


class RuntimeReasonCode(Enum):
    FIREWALL_INVENTORY_FAILED = auto()
    FIREWALL_INSPECTION_FAILED = auto()
    FIREWALL_DRIFT = auto()
    FIREWALL_REPAIR_FAILED = auto()
    ROUTE_PASS_INCOMPLETE = auto()
    PROFILE_ROUTE_MISMATCH = auto()
    FORWARDING_DISABLE_FAILED = auto()
    FORWARDING_ENABLE_FAILED = auto()
    FORWARDING_QUERY_FAILED = auto()
    FORWARDING_RESTORED = auto()


RUNTIME_REASON_TEXT: Mapping[RuntimeReasonCode, str] = MappingProxyType(
    {
        RuntimeReasonCode.FIREWALL_INVENTORY_FAILED:
            "failed to inventory fixed firewall/NAT state",
        RuntimeReasonCode.FIREWALL_INSPECTION_FAILED:
            "failed to parse/normalize/compare fixed firewall/NAT state",
        RuntimeReasonCode.FIREWALL_DRIFT:
            "fixed firewall/NAT state differs from configured policy",
        RuntimeReasonCode.FIREWALL_REPAIR_FAILED:
            "failed to repair fixed firewall/NAT state",
        RuntimeReasonCode.ROUTE_PASS_INCOMPLETE:
            "route reconciliation pass did not complete",
        RuntimeReasonCode.PROFILE_ROUTE_MISMATCH:
            "verified profile route state differs from desired state",
        RuntimeReasonCode.FORWARDING_DISABLE_FAILED:
            "failed to confirm ip_forward disabled",
        RuntimeReasonCode.FORWARDING_ENABLE_FAILED:
            "failed to confirm ip_forward enabled",
        RuntimeReasonCode.FORWARDING_QUERY_FAILED:
            "failed to query ip_forward state",
        RuntimeReasonCode.FORWARDING_RESTORED:
            "ip_forward was unexpectedly disabled and was restored",
    }
)


# ---------------------------------------------------------------------------
# Immutable value objects
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class RouteSpec:
    destination: IPv4Network
    route_type: RouteType
    via: IPv4Address | None
    interface: str | None
    metric: int | None
    proto: int | None
    onlink: bool


@dataclass(slots=True, frozen=True)
class ReconciliationPlan:
    route_adds: frozenset[RouteSpec]
    route_deletes: frozenset[RouteSpec]
    route_replaces: frozenset[RouteSpec]


@dataclass(slots=True, frozen=True)
class VpnProfileConfig:
    """
    Validated managed profile.

    All fields are already normalized by ConfigLoader:
    - profile ID is canonical spelling from TOML;
    - network/routes are canonical IPv4Network objects;
    - ACL bare addresses are normalized to /32;
    - exact duplicates in set-like inputs are removed;
    - peers preserve configured order.
    """

    profile_id: str
    interface: str
    network: IPv4Network
    local_address: IPv4Address
    peers: tuple[IPv4Address, ...]
    routes: tuple[IPv4Network, ...]
    allowed_sources: tuple[IPv4Network, ...]

    @property
    def chain_input(self) -> str:
        return f"VPNG-{self.profile_id.upper()}-INPUT"

    @property
    def chain_forward(self) -> str:
        return f"VPNG-{self.profile_id.upper()}-FORWARD"

    @property
    def chain_nat(self) -> str:
        return f"VPNG-{self.profile_id.upper()}-NAT"


@dataclass(slots=True, frozen=True)
class GatewayConfig:
    """
    Validated runtime projection.

    `vpns` contains managed profiles only.  The raw TOML catalog and unmanaged
    definitions belong to ConfigLoader/--check-config and are not retained by
    the running daemon.
    """

    reconcile_interval: float
    common_allowed_sources: tuple[IPv4Network, ...]
    vpns: Mapping[str, VpnProfileConfig]


@dataclass(slots=True, frozen=True)
class ConfigIssue:
    level: ConfigIssueLevel
    location: str
    message: str


@dataclass(slots=True, frozen=True)
class ConfigCheckResult:
    issues: tuple[ConfigIssue, ...]

    @property
    def has_errors(self) -> bool:
        return any(issue.level is ConfigIssueLevel.ERROR for issue in self.issues)


@dataclass(slots=True, frozen=True)
class DiagnosticFact:
    """
    Stable machine reason plus optional human detail.

    `code` participates in machine identity/deduplication.
    `detail` is render-only diagnostic text and may vary between passes.
    """

    code: RuntimeReasonCode
    detail: str | None = None


@dataclass(slots=True, frozen=True)
class FirewallCheck:
    """Read-only result of fixed firewall/NAT verification."""

    safety: FirewallSafety
    reason: DiagnosticFact | None

    def __post_init__(self) -> None:
        if self.safety is FirewallSafety.SAFE:
            if self.reason is not None:
                raise ValueError("SAFE FirewallCheck must not carry a reason")
            return

        if self.reason is None:
            raise ValueError(
                "UNSAFE/UNKNOWN FirewallCheck requires a DiagnosticFact"
            )


@dataclass(slots=True, frozen=True)
class ProfileResult:
    """Profile identity is the key of the containing result mapping."""

    result: ApplyStateResult
    reason: DiagnosticFact | None = None

    def __post_init__(self) -> None:
        if self.result is ApplyStateResult.SUCCESS:
            if self.reason is not None:
                raise ValueError("SUCCESS ProfileResult must not carry a reason")
            return

        if self.reason is None:
            raise ValueError("FAIL ProfileResult requires a DiagnosticFact")


@dataclass(slots=True, frozen=True)
class RouteVerifyResult:
    profile_results: Mapping[str, ProfileResult]
    owned_routes_by_profile: Mapping[str, frozenset[RouteSpec]]


# ---------------------------------------------------------------------------
# Configuration loading / offline lint
# ---------------------------------------------------------------------------


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
    ) -> str | None:
        if not isinstance(value, str):
            issues.append(
                ConfigIssue(level, location, "must be a string")
            )
            return None

        if not self._INTERFACE_RE.fullmatch(value):
            issues.append(
                ConfigIssue(
                    level,
                    location,
                    "must match [A-Za-z][A-Za-z0-9_.-]{0,14}",
                )
            )
            return None

        if value.casefold() in self._FORBIDDEN_INTERFACES:
            issues.append(
                ConfigIssue(
                    level,
                    location,
                    f"forbidden interface name: {value!r}",
                )
            )
            return None

        return value

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
                if left.interface != right.interface:
                    continue
                level = conflict_level(left_id, right_id)
                if level is None:
                    continue
                issues.append(
                    ConfigIssue(
                        level,
                        "vpn",
                        f"interface {left.interface!r} is shared by "
                        f"profiles {left_id!r} and {right_id!r}",
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


class VpnProfile:
    """
    Pure profile/domain object.

    No kernel reads.
    No kernel writes.
    No readiness query.
    No Netlink socket.
    """

    def __init__(self, config: VpnProfileConfig) -> None:
        self.config = config
        self._owned_routes: set[RouteSpec] = set()

    def _list_routes(self, source: ProfileResourceSet) -> frozenset[RouteSpec]:
        if source is ProfileResourceSet.CONFIGURED:
            return self._configured_routes()
        if source is ProfileResourceSet.OWNED:
            return frozenset(self._owned_routes)
        raise AssertionError(f"unhandled ProfileResourceSet: {source!r}")

    def _configured_routes(self) -> frozenset[RouteSpec]:
        """
        CONFIGURED is derived only from immutable config.

        For every protected prefix:
        - one BLACKHOLE guard;
        - one UNICAST route per peer.
        """
        routes: set[RouteSpec] = set()

        for destination in self.config.routes:
            routes.add(
                RouteSpec(
                    destination=destination,
                    route_type=RouteType.BLACKHOLE,
                    via=None,
                    interface=None,
                    metric=BLACKHOLE_METRIC,
                    proto=BLACKHOLE_ROUTE_PROTO,
                    onlink=False,
                )
            )

            for index, peer in enumerate(self.config.peers):
                routes.add(
                    RouteSpec(
                        destination=destination,
                        route_type=RouteType.UNICAST,
                        via=peer,
                        interface=self.config.interface,
                        metric=(index + 1) * PEER_METRIC_STEP,
                        proto=VPN_ROUTE_PROTO,
                        onlink=True,
                    )
                )

        return frozenset(routes)

    def update_owned_state(
        self,
        *,
        routes: set[RouteSpec] | frozenset[RouteSpec],
    ) -> None:
        """Atomic defensive replacement after daemon verify."""
        self._owned_routes = set(routes)


# ---------------------------------------------------------------------------
# Kernel/userspace boundary
# ---------------------------------------------------------------------------


class KernelInterface(ABC):
    """
    Physical kernel/userspace boundary.

    It must not know CONFIGURED/OWNED/DESIRED and must not make policy choices.
    Fixed firewall policy is constructed by VpnGatewayDaemon; this adapter only
    inventories/materializes concrete state.
    """

    # ---- Runtime routing -------------------------------------------------

    @abstractmethod
    def list_routes(self) -> frozenset[RouteSpec]:
        """Return normalized main IPv4 routing-table snapshot."""

    @abstractmethod
    def add_route(self, route: RouteSpec) -> None:
        """Materialize the complete RouteSpec without hidden policy defaults."""

    @abstractmethod
    def delete_route(self, route: RouteSpec) -> None:
        """Delete exactly the represented route."""

    @abstractmethod
    def replace_route(self, route: RouteSpec) -> None:
        """
        Materialize `route` with replace semantics.

        Used only for authoritative canonicalization when the exact desired
        RouteSpec already exists in ACTUAL but is not OWNED by this process.
        """

    @abstractmethod
    def list_interface_ipv4(
        self,
    ) -> Mapping[str, frozenset[IPv4Address]]:
        """
        Return every existing interface.

        Existing interface with no IPv4 -> empty frozenset.
        Missing key -> interface does not exist.
        """

    # ---- Forwarding ------------------------------------------------------

    @abstractmethod
    def get_ip_forward(self) -> bool:
        pass

    @abstractmethod
    def set_ip_forward(self, enabled: bool) -> None:
        pass

    # ---- Fixed firewall/NAT ---------------------------------------------

    @abstractmethod
    def iptables_save(self) -> str:
        """Return inventory sufficient to verify daemon-owned fixed policy."""

    @abstractmethod
    def iptables_restore(self, payload: str, *, noflush: bool = True) -> None:
        """Apply an exact payload atomically per table/COMMIT."""

    def close(self) -> None:
        """Release technical resources such as sockets, if any."""


class SubprocessKernelInterface(KernelInterface):
    """
    Debian 13 subprocess adapter.

    Route/address inventory and route mutations use iproute2.
    Forwarding and firewall methods are completed in later implementation
    steps.  All subprocesses use bounded timeouts and a stable locale.

    Policy construction deliberately does not live here.
    """

    def __init__(
        self,
        *,
        command_timeout: float = 10.0,
        iptables_wait_seconds: int = 5,
    ) -> None:
        self.command_timeout = command_timeout
        self.iptables_wait_seconds = iptables_wait_seconds

    def _run(
        self,
        argv: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """
        Run one bounded userspace adapter command with stable locale.

        Human stderr is preserved in KernelError.detail text, but callers map
        failures to stable RuntimeReasonCode values for machine identity.
        """
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"

        try:
            return subprocess.run(
                list(argv),
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=self.command_timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = exc.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            detail = (stderr or "").strip()
            raise KernelError(
                f"command timed out after {self.command_timeout}s: "
                f"{list(argv)!r}; stderr={detail!r}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip()
            raise KernelError(
                f"command failed rc={exc.returncode}: {list(argv)!r}; "
                f"stderr={detail!r}"
            ) from exc
        except OSError as exc:
            raise KernelError(
                f"failed to execute {list(argv)!r}: {exc}"
            ) from exc

    @staticmethod
    def _load_json_array(stdout: str, *, context: str) -> list[object]:
        try:
            payload = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise KernelError(
                f"{context}: command returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(payload, list):
            raise KernelError(
                f"{context}: expected top-level JSON array, "
                f"got {type(payload).__name__}"
            )

        return payload

    @staticmethod
    def _parse_route_destination(value: object) -> IPv4Network:
        if not isinstance(value, str) or not value:
            raise KernelError(
                f"route inventory: invalid destination {value!r}"
            )

        normalized = "0.0.0.0/0" if value == "default" else value
        if "/" not in normalized:
            normalized = f"{normalized}/32"

        try:
            return IPv4Network(normalized, strict=True)
        except ValueError as exc:
            raise KernelError(
                f"route inventory: invalid IPv4 destination {value!r}"
            ) from exc

    @staticmethod
    def _parse_route_type(value: object) -> RouteType:
        if value is None:
            return RouteType.UNICAST

        names = {
            "unicast": RouteType.UNICAST,
            "blackhole": RouteType.BLACKHOLE,
            "unreachable": RouteType.UNREACHABLE,
            "prohibit": RouteType.PROHIBIT,
            "throw": RouteType.THROW,
        }
        numbers = {
            1: RouteType.UNICAST,
            6: RouteType.BLACKHOLE,
            7: RouteType.UNREACHABLE,
            8: RouteType.PROHIBIT,
            9: RouteType.THROW,
        }

        if isinstance(value, str):
            lowered = value.casefold()
            if lowered in names:
                return names[lowered]
            if value.isdecimal():
                value = int(value)

        if isinstance(value, int) and not isinstance(value, bool):
            route_type = numbers.get(value)
            if route_type is not None:
                return route_type

        raise KernelError(
            f"route inventory: unsupported route type {value!r}"
        )

    @staticmethod
    def _parse_route_protocol(value: object) -> int:
        # iproute2 omits RTPROT_BOOT (3) unless detailed output is requested.
        if value is None:
            return 3

        if isinstance(value, str) and value.isdecimal():
            value = int(value)

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 255
        ):
            raise KernelError(
                f"route inventory: invalid numeric protocol {value!r}"
            )

        return value

    @staticmethod
    def _parse_optional_metric(value: object) -> int | None:
        if value is None:
            return None
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= MAX_ROUTE_METRIC
        ):
            raise KernelError(
                f"route inventory: invalid metric {value!r}"
            )
        return value

    @classmethod
    def _parse_route_entry(cls, entry: object) -> RouteSpec:
        if not isinstance(entry, dict):
            raise KernelError(
                f"route inventory: expected object, got "
                f"{type(entry).__name__}"
            )

        # These forms cannot be represented faithfully by the current
        # single-next-hop RouteSpec.  Never silently omit them from ACTUAL.
        for unsupported in ("nexthops", "nhid", "multipath"):
            if unsupported in entry:
                raise KernelError(
                    "route inventory: unsupported multi/nexthop route "
                    f"contains {unsupported!r}: {entry!r}"
                )

        table = entry.get("table")
        if table not in (None, "main", 254, "254"):
            raise KernelError(
                f"route inventory: unexpected non-main table {table!r}"
            )

        gateway_value = entry.get("gateway")
        gateway: IPv4Address | None
        if gateway_value is None:
            gateway = None
        elif isinstance(gateway_value, str):
            try:
                gateway = IPv4Address(gateway_value)
            except ValueError as exc:
                raise KernelError(
                    f"route inventory: invalid IPv4 gateway "
                    f"{gateway_value!r}"
                ) from exc
        else:
            raise KernelError(
                f"route inventory: invalid gateway {gateway_value!r}"
            )

        if "via" in entry:
            raise KernelError(
                "route inventory: cross-family/structured via is not "
                f"representable: {entry['via']!r}"
            )

        interface = entry.get("dev")
        if interface is not None and (
            not isinstance(interface, str) or not interface
        ):
            raise KernelError(
                f"route inventory: invalid interface {interface!r}"
            )

        flags = entry.get("flags", [])
        if not isinstance(flags, list) or not all(
            isinstance(flag, str) for flag in flags
        ):
            raise KernelError(
                f"route inventory: invalid flags {flags!r}"
            )

        return RouteSpec(
            destination=cls._parse_route_destination(entry.get("dst")),
            route_type=cls._parse_route_type(entry.get("type")),
            via=gateway,
            interface=interface,
            metric=cls._parse_optional_metric(entry.get("metric")),
            proto=cls._parse_route_protocol(entry.get("protocol")),
            onlink="onlink" in flags,
        )

    def list_routes(self) -> frozenset[RouteSpec]:
        """
        Return normalized main-table IPv4 routes from iproute2 JSON.

        `-N` forces protocol/scope identifiers to numeric form.  The adapter
        still normalizes the protocol omitted by iproute2 for RTPROT_BOOT.
        Structurally unrepresentable multipath/nexthop routes fail inventory
        instead of being silently omitted from ACTUAL.
        """
        completed = self._run(
            (
                "ip",
                "-j",
                "-N",
                "-4",
                "route",
                "show",
                "table",
                "main",
            )
        )
        payload = self._load_json_array(
            completed.stdout,
            context="route inventory",
        )
        return frozenset(
            self._parse_route_entry(entry)
            for entry in payload
        )

    @staticmethod
    def _route_command_argv(
        action: str,
        route: RouteSpec,
    ) -> tuple[str, ...]:
        type_name = {
            RouteType.UNICAST: "unicast",
            RouteType.BLACKHOLE: "blackhole",
            RouteType.UNREACHABLE: "unreachable",
            RouteType.PROHIBIT: "prohibit",
            RouteType.THROW: "throw",
        }[route.route_type]

        if route.proto is None:
            raise KernelError(
                f"cannot materialize route with proto=None: {route!r}"
            )
        if not 0 <= route.proto <= 255:
            raise KernelError(
                f"cannot materialize route with invalid proto: {route!r}"
            )

        argv = [
            "ip",
            "-4",
            "route",
            action,
            type_name,
            str(route.destination),
            "table",
            "main",
            "proto",
            str(route.proto),
        ]

        if route.metric is not None:
            argv.extend(("metric", str(route.metric)))
        if route.via is not None:
            argv.extend(("via", str(route.via)))
        if route.interface is not None:
            argv.extend(("dev", route.interface))
        if route.onlink:
            argv.append("onlink")

        return tuple(argv)

    def add_route(self, route: RouteSpec) -> None:
        """Materialize one complete RouteSpec in the main IPv4 table."""
        self._run(self._route_command_argv("add", route))

    def delete_route(self, route: RouteSpec) -> None:
        """Delete the represented route from the main IPv4 table."""
        self._run(self._route_command_argv("del", route))

    def replace_route(self, route: RouteSpec) -> None:
        """Canonicalize one complete RouteSpec with `ip route replace`."""
        self._run(self._route_command_argv("replace", route))

    def list_interface_ipv4(
        self,
    ) -> Mapping[str, frozenset[IPv4Address]]:
        """
        Return every interface and its local IPv4 addresses.

        `addr_info[].local` is authoritative for tun/point-to-point interfaces;
        peer/broadcast fields are deliberately ignored.
        """
        completed = self._run(("ip", "-j", "-4", "addr", "show"))
        payload = self._load_json_array(
            completed.stdout,
            context="IPv4 address inventory",
        )

        mutable: dict[str, set[IPv4Address]] = {}
        for entry in payload:
            if not isinstance(entry, dict):
                raise KernelError(
                    "IPv4 address inventory: expected object, got "
                    f"{type(entry).__name__}"
                )

            interface = entry.get("ifname")
            if not isinstance(interface, str) or not interface:
                raise KernelError(
                    "IPv4 address inventory: invalid/missing ifname "
                    f"{interface!r}"
                )

            addresses = mutable.setdefault(interface, set())
            address_info = entry.get("addr_info", [])
            if not isinstance(address_info, list):
                raise KernelError(
                    f"IPv4 address inventory: invalid addr_info for "
                    f"{interface!r}: {address_info!r}"
                )

            for info in address_info:
                if not isinstance(info, dict):
                    raise KernelError(
                        "IPv4 address inventory: invalid address object "
                        f"for {interface!r}: {info!r}"
                    )
                if info.get("family") not in (None, "inet"):
                    continue

                local = info.get("local")
                if not isinstance(local, str) or not local:
                    raise KernelError(
                        "IPv4 address inventory: missing local address "
                        f"for {interface!r}: {info!r}"
                    )
                try:
                    addresses.add(IPv4Address(local))
                except ValueError as exc:
                    raise KernelError(
                        "IPv4 address inventory: invalid local IPv4 "
                        f"{local!r} for {interface!r}"
                    ) from exc

        return MappingProxyType(
            {
                interface: frozenset(addresses)
                for interface, addresses in mutable.items()
            }
        )

    def get_ip_forward(self) -> bool:
        """TODO: read /proc/sys/net/ipv4/ip_forward or bounded sysctl."""
        raise NotImplementedError

    def set_ip_forward(self, enabled: bool) -> None:
        """TODO: write daemon-owned net.ipv4.ip_forward."""
        raise NotImplementedError

    def iptables_save(self) -> str:
        """
        TODO implementation step 5/6.

        Inventory all tables needed to verify the reserved VPNG-* namespace,
        owned jumps and fixed MASQUERADE rules.

        EXP-001 contract: capture iptables-save stdout directly into memory.
        Do not create temporary rules files.
        """
        raise NotImplementedError

    def iptables_restore(self, payload: str, *, noflush: bool = True) -> None:
        """
        TODO implementation step 5/6.

        Use iptables-restore --noflush and bounded lock wait.
        Feed `payload` through stdin from memory; no temporary rules files.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Lifetime process lock
# ---------------------------------------------------------------------------


class InstanceLock:
    """Exclusive lifetime flock.  --check-config never constructs this."""

    def __init__(self, path: Path = DEFAULT_LOCK_PATH) -> None:
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> "InstanceLock":
        fd = os.open(
            self.path,
            os.O_RDWR
            | os.O_CREAT
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise InstanceLockError(
                    f"another vpn-gatewayd instance is running "
                    f"(lock busy: {self.path})"
                ) from exc
            raise
        self._fd = fd
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


# ---------------------------------------------------------------------------
# Optional stdlib systemd notification helper
# ---------------------------------------------------------------------------


class SystemdNotifier:
    """
    Minimal optional sd_notify-compatible helper.

    Event-loop scheduling of WATCHDOG=1 remains an implementation task.
    """

    def __init__(self) -> None:
        self._notify_socket = os.environ.get("NOTIFY_SOCKET")

    @property
    def enabled(self) -> bool:
        return bool(self._notify_socket)

    def notify(self, message: str) -> None:
        if not self._notify_socket:
            return

        address: str | bytes
        if self._notify_socket.startswith("@"):
            address = b"\0" + self._notify_socket[1:].encode()
        else:
            address = self._notify_socket

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(address)
            sock.sendall(message.encode())
        except OSError as exc:
            # Notification transport is operational metadata, not gateway
            # policy.  A stale/unavailable NOTIFY_SOCKET must not kill the
            # daemon or watchdog/event loop.
            LOG.warning("sd_notify failed: %s", exc)
        finally:
            sock.close()

    def ready(self) -> None:
        self.notify("READY=1")

    def watchdog(self) -> None:
        self.notify("WATCHDOG=1")

    def stopping(self) -> None:
        self.notify("STOPPING=1")


# ---------------------------------------------------------------------------
# Daemon orchestration
# ---------------------------------------------------------------------------


class VpnGatewayDaemon:
    """
    Sole orchestration owner.

    Normal startup order is deliberately encoded at the top level:
        LOCK -> CLEANUP -> LOAD/VALIDATE -> APPLY -> RUN

    The config is therefore NOT read in __init__.
    """

    def __init__(
        self,
        *,
        config_path: Path,
        kernel: KernelInterface,
        config_loader: ConfigLoader,
        notifier: SystemdNotifier | None = None,
        lock_path: Path = DEFAULT_LOCK_PATH,
        failure_reminder_interval: float = DEFAULT_FAILURE_REMINDER_INTERVAL,
    ) -> None:
        self.config_path = config_path
        self.kernel = kernel
        self.config_loader = config_loader
        self.notifier = notifier or SystemdNotifier()
        self.lock_path = lock_path
        self.failure_reminder_interval = failure_reminder_interval

        self.state = DaemonState.STARTING
        self.config: GatewayConfig | None = None
        self.profiles: Mapping[str, VpnProfile] = MappingProxyType({})

        self._reported_route_overlaps: dict[str, frozenset[RouteSpec]] = {}
        self._shutdown_requested = False
        self._last_reconcile_log_signature: tuple[object, ...] | None = None
        self._last_reconcile_log_at: float | None = None

        self._signal_wakeup_reader: socket.socket | None = None
        self._signal_wakeup_writer: socket.socket | None = None
        self._previous_wakeup_fd = -1
        self._previous_signal_handlers: dict[int, object] = {}

        # Conscious boundary: the architecture requires one daemon-owned
        # Netlink listener.  It is an event source owned by orchestration, not
        # a policy/materialization operation of KernelInterface.  Exact
        # serialized event-loop mechanics remain open.
        self._netlink_socket: socket.socket | None = None

    # ---- Lifecycle -------------------------------------------------------

    def serve(self) -> None:
        """
        Full normal lifecycle with signal-safe STARTING checkpoints.

        A failed startup still does not run an ad-hoc rollback transaction.
        A requested graceful shutdown is different: once the daemon owns the
        lifetime lock, it stops at the nearest completed phase boundary and
        performs universal cleanup if APPLY may have created kernel state.
        """
        self._install_signal_handlers()
        try:
            # Signal before ownership: nothing is ours to clean.
            if self._shutdown_requested:
                self.state = DaemonState.STOPPING
                return

            with InstanceLock(self.lock_path):
                self.cleanup()
                if self._startup_shutdown_checkpoint(
                    kernel_may_be_dirty=False
                ):
                    return

                # Architectural boundary: config is first read only here,
                # AFTER lock + cleanup.
                config = self.config_loader.load_runtime(self.config_path)
                self._install_config(config)
                if self._startup_shutdown_checkpoint(
                    kernel_may_be_dirty=False
                ):
                    return

                self.apply()

                # Critical boundary: APPLY may have enabled ip_forward.
                # Never emit READY=1 or enter RUN if shutdown was requested.
                if self._startup_shutdown_checkpoint(
                    kernel_may_be_dirty=True
                ):
                    return

                self.state = DaemonState.ACTIVE
                self.notifier.ready()

                # run() returns only for a requested graceful shutdown.
                self.run()

                self.state = DaemonState.STOPPING
                self.notifier.stopping()
                self.cleanup()
        finally:
            self._restore_signal_handlers()

    def _startup_shutdown_checkpoint(
        self,
        *,
        kernel_may_be_dirty: bool,
    ) -> bool:
        """Return True when STARTING must terminate gracefully now."""
        if not self._shutdown_requested:
            return False

        self.state = DaemonState.STOPPING
        if kernel_may_be_dirty:
            self.cleanup()
        return True

    def _install_config(self, config: GatewayConfig) -> None:
        self.config = config
        profiles = {
            profile_id: VpnProfile(profile_config)
            for profile_id, profile_config in config.vpns.items()
        }
        self.profiles = MappingProxyType(profiles)
        self._reported_route_overlaps = {
            profile_id: frozenset() for profile_id in profiles
        }

    def cleanup(self) -> None:
        """
        Universal marker-based cleanup, independent of config/persistent state.

        Required order:
        1. ip_forward = 0;
        2. inventory owned resources by markers;
        3. delete proto-202 VPN routes;
        4. remove VPNG-* jumps/chains in managed iptables tables;
        5. remove proto-201/metric-65536 blackholes only after prior cleanup
           succeeded;
        6. verify actual state is clean.

        No whole-table blind flush.
        """
        raise NotImplementedError

    def apply(self) -> None:
        """
        Fail-hard bootstrap.

        Required order:
        1. fresh initial routes/interfaces snapshot;
        2. build + _validate_plan() BEFORE new side effects;
        3. install fixed firewall/NAT infrastructure, including static
           MASQUERADE for EVERY managed profile regardless readiness/peers;
        4. verify fixed firewall/NAT == SAFE;
        5. apply route plan (BLACKHOLE adds first);
        6. verify routes against the same desired snapshot; verify result and
           owned_routes_by_profile must cover every managed profile;
        7. any profile FAIL/incomplete verify is fatal on startup;
        8. set and confirm ip_forward = 1 LAST.
        """
        raise NotImplementedError

    def run(self) -> None:
        """
        Serialized event loop placeholder.

        Must serialize:
        - Netlink events;
        - periodic reconciliation;
        - future IPC;
        - shutdown.

        At most one reconciliation plan executes at a time.
        Netlink bursts are coalesced/debounced.
        WATCHDOG=1 must be scheduled before the watchdog deadline even when no
        external events arrive.

        The selector must include `_signal_wakeup_reader`; SIGTERM/SIGINT wake
        it immediately through signal.set_wakeup_fd instead of waiting for the
        periodic reconciliation timeout.
        """
        raise NotImplementedError

    # ---- Runtime reconciliation ----------------------------------------

    def reconcile(self) -> None:
        """
        Runtime orchestration skeleton.

        Fixed firewall/NAT verification is always first.  Route reconciliation
        starts only after fixed infrastructure is SAFE.
        """
        firewall = self._check_fixed_firewall_nat()
        pass_incidents: list[DiagnosticFact] = []
        isolation_disable_fact: DiagnosticFact | None = None

        if firewall.safety is FirewallSafety.UNKNOWN:
            isolation_disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="firewall/NAT UNKNOWN"
            )
            self.state = DaemonState.ISOLATED

            facts: list[DiagnosticFact] = []
            if firewall.reason is not None:
                facts.append(firewall.reason)
            if isolation_disable_fact is not None:
                facts.append(isolation_disable_fact)

            signature_parts: list[object] = [
                "isolated",
                "firewall-unknown",
            ]
            signature_parts.extend(
                ("reason", fact.code) for fact in facts
            )

            self._log_reconcile_outcome(
                tuple(signature_parts),
                level=logging.ERROR,
                facts=tuple(facts),
            )
            # Blind repair is forbidden for UNKNOWN.
            return

        if firewall.safety is FirewallSafety.UNSAFE:
            if firewall.reason is not None:
                pass_incidents.append(firewall.reason)

            isolation_disable_fact = self._best_effort_disable_forwarding(
                high_severity_context="firewall/NAT UNSAFE"
            )
            if isolation_disable_fact is not None:
                pass_incidents.append(isolation_disable_fact)

            # Even if disabling forwarding failed, restoring filter/NAT is
            # still useful and required.  filter before nat inside repair.
            try:
                self._repair_fixed_firewall_nat()
                repaired = self._check_fixed_firewall_nat()
            except KernelError as exc:
                repaired = FirewallCheck(
                    safety=FirewallSafety.UNKNOWN,
                    reason=DiagnosticFact(
                        code=RuntimeReasonCode.FIREWALL_REPAIR_FAILED,
                        detail=str(exc),
                    ),
                )

            if repaired.safety is not FirewallSafety.SAFE:
                self.state = DaemonState.ISOLATED

                facts = list(pass_incidents)
                if repaired.reason is not None:
                    facts.append(repaired.reason)

                signature_parts = [
                    "isolated",
                    "firewall-repair-failed",
                    repaired.safety,
                ]
                signature_parts.extend(
                    ("reason", fact.code) for fact in facts
                )

                self._log_reconcile_outcome(
                    tuple(signature_parts),
                    level=logging.ERROR,
                    facts=tuple(facts),
                )
                return

            firewall = repaired

        # Fixed firewall/NAT is now SAFE.  A fresh route pass is required
        # before forwarding can be restored after isolation.
        try:
            profile_results = self._require_complete_profile_results(
                self._reconcile_routes_once()
            )
        except (KernelError, PlanValidationError, ReconciliationError) as exc:
            # SAFE firewall + incomplete route pass => DEGRADED.
            #
            # Severity depends on CURRENT forwarding availability:
            # - confirmed ON  -> WARNING (gateway is still forwarding);
            # - OFF/unknown   -> ERROR   (gateway is not confirmed usable).
            self.state = DaemonState.DEGRADED
            forwarding_on, forwarding_query_error = (
                self._query_forwarding_state()
            )

            facts = list(pass_incidents)
            facts.append(
                DiagnosticFact(
                    code=RuntimeReasonCode.ROUTE_PASS_INCOMPLETE,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            if forwarding_query_error is not None:
                facts.append(forwarding_query_error)

            signature_parts: list[object] = [
                "degraded",
                "route-pass-incomplete",
                ("ip-forward", forwarding_on),
            ]
            signature_parts.extend(
                ("reason", fact.code) for fact in facts
            )

            self._log_reconcile_outcome(
                tuple(signature_parts),
                level=(
                    logging.WARNING
                    if forwarding_on
                    else logging.ERROR
                ),
                facts=tuple(facts),
            )
            return

        # A completed SAFE fresh route pass is sufficient to restore global
        # forwarding even if a profile result is FAIL: profile-local route
        # failures remain fail-closed via BLACKHOLE/FORWARD policy.
        forwarding_enabled, forwarding_enable_fact = (
            self._best_effort_enable_forwarding()
        )

        # If we intentionally isolated this same pass because firewall was
        # UNSAFE, restoring ip_forward is part of that recovery and must not
        # create a duplicate FORWARDING_RESTORED incident.
        if (
            forwarding_enabled
            and forwarding_enable_fact is not None
            and forwarding_enable_fact.code
                is RuntimeReasonCode.FORWARDING_RESTORED
        ):
            if not pass_incidents:
                pass_incidents.append(forwarding_enable_fact)
            forwarding_enable_fact = None

        all_success = all(
            result.result is ApplyStateResult.SUCCESS
            for result in profile_results.values()
        )

        if all_success and forwarding_enabled:
            self.state = DaemonState.ACTIVE
        else:
            self.state = DaemonState.DEGRADED

        profile_signature: list[tuple[object, ...]] = []
        current_facts: list[DiagnosticFact] = []
        for profile_id, result in sorted(profile_results.items()):
            item: list[object] = [profile_id, result.result]
            if result.reason is not None:
                item.append(result.reason.code)
                current_facts.append(result.reason)
            profile_signature.append(tuple(item))

        if forwarding_enable_fact is not None:
            current_facts.append(forwarding_enable_fact)

        recovered_from: tuple[DiagnosticFact, ...] = ()
        if self.state is DaemonState.ACTIVE:
            recovered_from = tuple(pass_incidents)
        else:
            # The pass did not fully recover to ACTIVE.  Preserve prior
            # incidents as current-pass diagnostic facts, without claiming
            # "recovered from".
            current_facts[0:0] = pass_incidents

        signature_parts: list[object] = [
            self.state,
            tuple(profile_signature),
            ("ip-forward", forwarding_enabled),
        ]
        signature_parts.extend(
            ("reason", fact.code) for fact in current_facts
        )

        if self.state is DaemonState.ACTIVE:
            level = (
                logging.WARNING
                if recovered_from
                else logging.INFO
            )
        elif forwarding_enabled:
            # DEGRADED but gateway is still forwarding.
            level = logging.WARNING
        else:
            # DEGRADED and forwarding is OFF/not confirmed usable.
            level = logging.ERROR

        self._log_reconcile_outcome(
            tuple(signature_parts),
            level=level,
            facts=tuple(current_facts),
            recovered_from=recovered_from,
        )

    def _reconcile_routes_once(self) -> Mapping[str, ProfileResult]:
        """
        One lifecycle-neutral route reconciliation pass.

        Required flow:
        - fresh route + interface/address snapshots;
        - derive readiness;
        - CONFIGURED + OWNED -> one immutable desired_routes_by_profile;
        - build route-only plan from that same desired snapshot;
        - validate against that same desired snapshot;
        - apply, BLACKHOLE adds first;
        - fresh verify against that same desired snapshot;
        - map result per managed profile;
        - commit each profile OWNED only from verified state.

        This method must not mutate DaemonState.

        Contract:
        - return only after a completed fresh verify;
        - per-profile FAIL is a valid result only after that completed verify;
        - if snapshot/build/apply/verify/commit-contract cannot complete,
          propagate KernelError, PlanValidationError or ReconciliationError;
        - if verify itself raises KernelError, propagate it unchanged;
        - never return a partial/empty result to represent an incomplete pass;
        - returned keys must equal the complete managed profile key set;
        - do not replace previously confirmed OWNED state for a profile unless
          the current pass has verified the replacement.
        """
        raise NotImplementedError

    # ---- Route plan ------------------------------------------------------

    def _derive_desired_routes(
        self,
        *,
        interface_ipv4: Mapping[str, frozenset[IPv4Address]],
    ) -> Mapping[str, frozenset[RouteSpec]]:
        """
        Build one immutable DESIRED snapshot for the current pass.

        BLACKHOLE guards are always desired.
        UNICAST peer routes are desired only while the profile is ready.
        """
        desired: dict[str, frozenset[RouteSpec]] = {}

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            configured = profile._list_routes(
                ProfileResourceSet.CONFIGURED
            )

            if self._profile_is_ready(profile, interface_ipv4):
                selected = configured
            else:
                selected = frozenset(
                    route
                    for route in configured
                    if route.route_type is RouteType.BLACKHOLE
                )

            desired[profile_id] = frozenset(selected)

        return MappingProxyType(desired)

    def _require_complete_desired_snapshot(
        self,
        desired_routes_by_profile: Mapping[
            str,
            frozenset[RouteSpec],
        ],
    ) -> None:
        expected = frozenset(self.profiles)
        actual = frozenset(desired_routes_by_profile)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ReconciliationError(
                "incomplete desired route snapshot: "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )

    def _build_plan(
        self,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> ReconciliationPlan:
        """
        Pure route-plan construction from ACTUAL + DESIRED + OWNED.

        Authoritative scope is exact protected destinations only:
        - desired + actual + owned -> keep;
        - desired + missing actual -> add;
        - desired + actual + not owned -> replace;
        - actual exact + non-desired -> delete;
        - more-/less-specific overlaps -> diagnostics only.
        """
        self._require_complete_desired_snapshot(
            desired_routes_by_profile
        )

        route_adds: set[RouteSpec] = set()
        route_deletes: set[RouteSpec] = set()
        route_replaces: set[RouteSpec] = set()

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            desired = desired_routes_by_profile[profile_id]
            owned = profile._list_routes(ProfileResourceSet.OWNED)
            protected = frozenset(profile.config.routes)

            actual_exact = frozenset(
                route
                for route in all_kernel_routes
                if route.destination in protected
            )

            for route in actual_exact:
                if route in desired:
                    if route not in owned:
                        route_replaces.add(route)
                    continue

                route_deletes.add(route)

            actual_exact_set = set(actual_exact)
            for route in desired:
                if route not in actual_exact_set:
                    route_adds.add(route)

        return ReconciliationPlan(
            route_adds=frozenset(route_adds),
            route_deletes=frozenset(route_deletes),
            route_replaces=frozenset(route_replaces),
        )

    def _validate_plan(
        self,
        plan: ReconciliationPlan,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> None:
        """
        Validate route-plan safety before any side effect.

        `route_replaces` expresses authoritative canonicalization of an exact
        desired RouteSpec that already exists in ACTUAL but is not OWNED.
        This avoids encoding delete+recreate as an illegal add/delete overlap.
        """
        self._require_complete_desired_snapshot(
            desired_routes_by_profile
        )

        operation_sets = {
            "add": plan.route_adds,
            "delete": plan.route_deletes,
            "replace": plan.route_replaces,
        }
        operation_names = tuple(operation_sets)
        for index, left_name in enumerate(operation_names):
            for right_name in operation_names[index + 1:]:
                overlap = (
                    operation_sets[left_name]
                    & operation_sets[right_name]
                )
                if overlap:
                    raise PlanValidationError(
                        f"route plan operations overlap "
                        f"({left_name}/{right_name}): {overlap!r}"
                    )

        desired_owners: dict[RouteSpec, str] = {}
        desired_all: set[RouteSpec] = set()
        protected_destinations: dict[IPv4Network, str] = {}
        configured_by_profile: dict[str, frozenset[RouteSpec]] = {}
        owned_owners: dict[RouteSpec, set[str]] = {}

        for profile_id in sorted(self.profiles, key=str.casefold):
            profile = self.profiles[profile_id]
            configured = profile._list_routes(
                ProfileResourceSet.CONFIGURED
            )
            configured_by_profile[profile_id] = configured

            for destination in profile.config.routes:
                previous = protected_destinations.get(destination)
                if previous is not None and previous != profile_id:
                    raise PlanValidationError(
                        "multiple managed profiles claim exact protected "
                        f"destination {destination}: "
                        f"{previous!r}, {profile_id!r}"
                    )
                protected_destinations[destination] = profile_id

            for route in desired_routes_by_profile[profile_id]:
                previous = desired_owners.get(route)
                if previous is not None and previous != profile_id:
                    raise PlanValidationError(
                        "multiple managed profiles claim exact RouteSpec "
                        f"{route!r}: {previous!r}, {profile_id!r}"
                    )
                desired_owners[route] = profile_id
                desired_all.add(route)

            for route in profile._list_routes(ProfileResourceSet.OWNED):
                owned_owners.setdefault(route, set()).add(profile_id)

        actual = set(all_kernel_routes)

        for route in plan.route_adds:
            if route not in desired_all:
                raise PlanValidationError(
                    f"route add is not in current DESIRED: {route!r}"
                )
            if route in actual:
                raise PlanValidationError(
                    f"route add already exists in ACTUAL; "
                    f"replace/keep required: {route!r}"
                )

        for route in plan.route_replaces:
            if route.proto == KERNEL_ROUTE_PROTO:
                raise PlanValidationError(
                    f"proto kernel route must never be replaced: {route!r}"
                )
            if route not in desired_all:
                raise PlanValidationError(
                    f"route replace is not in current DESIRED: {route!r}"
                )
            if route not in actual:
                raise PlanValidationError(
                    f"route replace is absent from ACTUAL: {route!r}"
                )
            if route in owned_owners:
                raise PlanValidationError(
                    f"already OWNED desired route must be kept, "
                    f"not replaced: {route!r}"
                )

        exact_scope = frozenset(protected_destinations)

        for route in plan.route_deletes:
            if route.proto == KERNEL_ROUTE_PROTO:
                raise PlanValidationError(
                    f"proto kernel route must never be deleted: {route!r}"
                )
            if route not in actual:
                raise PlanValidationError(
                    f"route delete is absent from ACTUAL: {route!r}"
                )

            owners = owned_owners.get(route)
            if owners:
                justified = any(
                    route in configured_by_profile[profile_id]
                    for profile_id in owners
                )
                if not justified:
                    raise PlanValidationError(
                        "owned route delete has no current configured "
                        f"ownership justification: {route!r}"
                    )
                if route in desired_all:
                    raise PlanValidationError(
                        f"OWNED desired route must be kept: {route!r}"
                    )
                continue

            if route.destination not in exact_scope:
                raise PlanValidationError(
                    "foreign route delete is outside authoritative exact "
                    f"protected scope: {route!r}"
                )
            if route in desired_all:
                raise PlanValidationError(
                    "foreign exact desired route must use replace "
                    f"canonicalization, not delete: {route!r}"
                )

    def _apply_plan(self, plan: ReconciliationPlan) -> None:
        """
        TODO implementation step 6.

        Apply missing BLACKHOLE route_adds before ordinary route operations.
        Then delete competing exact routes, perform authoritative replacements,
        and apply remaining adds.  NAT operations do not exist in
        ReconciliationPlan.
        """
        raise NotImplementedError

    def _verify_plan(
        self,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> RouteVerifyResult:
        """
        TODO implementation step 6.

        Verify against the immutable desired snapshot created before plan
        construction.  Must return a result for every managed profile.
        """
        raise NotImplementedError

    def _require_complete_profile_results(
        self,
        results: Mapping[str, ProfileResult],
    ) -> Mapping[str, ProfileResult]:
        """
        Safety guard against vacuous all([]) / partial verify results.

        A completed pass must return exactly the managed profile key set.
        """
        expected = frozenset(self.profiles)
        actual = frozenset(results)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ReconciliationError(
                "incomplete profile results: "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )
        return MappingProxyType(dict(results))

    def _commit_owned(
        self,
        *,
        verified_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> None:
        """
        Commit profile ownership only after a complete verify result.

        Validate the entire managed key set BEFORE mutating any profile so a
        partial verify result cannot partially replace process-local OWNED.
        """
        expected = frozenset(self.profiles)
        actual = frozenset(verified_routes_by_profile)
        if actual != expected:
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            raise ReconciliationError(
                "incomplete verified ownership mapping: "
                f"missing={missing!r}, unexpected={unexpected!r}"
            )

        for profile_id in sorted(expected):
            self.profiles[profile_id].update_owned_state(
                routes=verified_routes_by_profile[profile_id]
            )

    def _routes_for_profile(
        self,
        profile: VpnProfile,
        all_kernel_routes: frozenset[RouteSpec],
    ) -> frozenset[RouteSpec]:
        """
        Return routes related to this profile's protected address space.

        Exact routes and more-/less-specific overlaps are included for
        verification/diagnostics.  The default route is deliberately excluded
        from overlap reporting.
        """
        protected = profile.config.routes
        default = IPv4Network("0.0.0.0/0")

        return frozenset(
            route
            for route in all_kernel_routes
            if (
                route.destination != default
                and any(
                    route.destination.overlaps(destination)
                    for destination in protected
                )
            )
        )

    # ---- Readiness / helpers --------------------------------------------

    def _profile_is_ready(
        self,
        profile: VpnProfile,
        interface_ipv4: Mapping[str, frozenset[IPv4Address]],
    ) -> bool:
        addresses = interface_ipv4.get(profile.config.interface)
        return (
            addresses is not None
            and profile.config.local_address in addresses
        )

    def effective_sources(
        self,
        profile: VpnProfile,
    ) -> tuple[IPv4Network, ...]:
        if self.config is None:
            raise RuntimeError("config not installed")

        merged = set(self.config.common_allowed_sources)
        merged.update(profile.config.allowed_sources)

        return tuple(
            sorted(
                merged,
                key=lambda net: (int(net.network_address), net.prefixlen),
            )
        )

    # ---- Fixed firewall/NAT ---------------------------------------------

    def _check_fixed_firewall_nat(self) -> FirewallCheck:
        """
        Read-only verification.

        Must verify:
        - reserved VPNG-* chains expected for current managed config;
        - fixed INPUT/FORWARD chains and contents;
        - VPNG-INGRESS;
        - VPNG-RESERVED;
        - profile NAT chains;
        - static MASQUERADE for every managed profile, including peers=[];
        - exact owned jump layout/order in INPUT/FORWARD/POSTROUTING.

        Inventory failure => UNKNOWN.
        Readable confirmed drift => UNSAFE.
        Exact match => SAFE.
        """
        try:
            snapshot = self.kernel.iptables_save()
        except KernelError as exc:
            return FirewallCheck(
                safety=FirewallSafety.UNKNOWN,
                reason=DiagnosticFact(
                    code=RuntimeReasonCode.FIREWALL_INVENTORY_FAILED,
                    detail=str(exc),
                ),
            )

        try:
            return self._compare_fixed_firewall_nat(snapshot)
        except FirewallInspectionError as exc:
            return FirewallCheck(
                safety=FirewallSafety.UNKNOWN,
                reason=DiagnosticFact(
                    code=RuntimeReasonCode.FIREWALL_INSPECTION_FAILED,
                    detail=str(exc),
                ),
            )

    def _compare_fixed_firewall_nat(self, snapshot: str) -> FirewallCheck:
        """
        TODO implementation step 5/6.

        EXP-001 PASS established the comparison boundary retained by RC2.2:
        - iptables-save stdout is the canonical inventory representation;
        - strip only comments/blank lines demonstrated as volatile;
        - minimally parse tables, chain declarations, ordered chain contents,
          and exact positions/uniqueness of daemon jumps;
        - compare individual rules as canonical iptables-save strings;
        - do NOT compare restore payload text directly with save output;
        - do NOT build a universal semantic firewall AST/normalizer.

        Expected parse/comparison inability must raise FirewallInspectionError
        so _check_fixed_firewall_nat() maps it to UNKNOWN.  Programming errors
        must not be hidden by a broad catch.
        """
        raise NotImplementedError

    def _build_fixed_firewall_nat_payload(self) -> str:
        """
        TODO implementation step 5/6.

        Policy belongs here, NOT in KernelInterface.

        Build fixed filter/NAT policy from current managed config:
        - profile INPUT chains;
        - VPNG-INGRESS;
        - VPNG-RESERVED;
        - profile FORWARD chains;
        - profile NAT chains;
        - static MASQUERADE on every managed profile.interface;
        - deterministic jumps sorted by case-insensitive profile ID.

        Return the complete restore payload as an in-memory string.  Policy is
        the single source of truth for both materialization and expected
        canonical comparison state.
        """
        raise NotImplementedError

    def _repair_fixed_firewall_nat(self) -> None:
        """
        Repair confirmed UNSAFE fixed policy.

        Cross-table atomicity does not exist:
        - normal case: forwarding has already been disabled;
        - if sysctl disable failed, still restore filter first, then nat;
        - verify again after repair.
        """
        raise NotImplementedError

    def _build_firewall_cleanup_payload(self, snapshot: str) -> str:
        """
        TODO implementation step 7.

        Stateless cleanup by reserved VPNG-* namespace, without current config.
        Must remove only owned jumps/chains, never blind-flush foreign tables.
        """
        raise NotImplementedError

    # ---- ip_forward ------------------------------------------------------

    def _best_effort_disable_forwarding(
        self,
        *,
        high_severity_context: str,
    ) -> DiagnosticFact | None:
        """
        Return None only when forwarding is confirmed disabled.

        A non-None DiagnosticFact records an incident in the current reconciliation
        pass.  The helper deliberately does not log by itself: final state
        decides whether the pass outcome is ERROR or a recovered WARNING.
        """
        try:
            if not self.kernel.get_ip_forward():
                return None

            self.kernel.set_ip_forward(False)
            if self.kernel.get_ip_forward():
                return DiagnosticFact(
                    code=RuntimeReasonCode.FORWARDING_DISABLE_FAILED,
                    detail=(
                        f"{high_severity_context}: ip_forward remains enabled "
                        "after successful write"
                    ),
                )
        except KernelError as exc:
            return DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_DISABLE_FAILED,
                detail=f"{high_severity_context}: {exc}",
            )

        return None

    def _best_effort_enable_forwarding(
        self,
    ) -> tuple[bool, DiagnosticFact | None]:
        """
        Return (confirmed_enabled, fact).

        Read before write.  If forwarding was already ON, return (True, None).
        If an unexpected OFF is successfully restored, return a recovered
        FORWARDING_RESTORED fact.  Failure returns FORWARDING_ENABLE_FAILED.
        The caller decides whether a restored fact is independent or merely
        duplicates an earlier firewall-isolation incident in the same pass.
        """
        try:
            if self.kernel.get_ip_forward():
                return True, None

            self.kernel.set_ip_forward(True)
            enabled = self.kernel.get_ip_forward()
        except KernelError as exc:
            return False, DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_ENABLE_FAILED,
                detail=str(exc),
            )

        if not enabled:
            return (
                False,
                DiagnosticFact(
                    code=RuntimeReasonCode.FORWARDING_ENABLE_FAILED,
                    detail="ip_forward remains disabled after successful write",
                ),
            )

        return (
            True,
            DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_RESTORED,
                detail="ip_forward was OFF before the enable step",
            ),
        )

    def _query_forwarding_state(
        self,
    ) -> tuple[bool, DiagnosticFact | None]:
        """
        Return (confirmed_on, error) without emitting an intermediate log.

        Query failure is conservatively treated as not confirmed ON.  The
        caller includes the error in the final reconciliation signature, so
        severity remains a property of the final current-state diagnosis.
        """
        try:
            return self.kernel.get_ip_forward(), None
        except KernelError as exc:
            return False, DiagnosticFact(
                code=RuntimeReasonCode.FORWARDING_QUERY_FAILED,
                detail=str(exc),
            )

    # ---- Events / signals / logging -------------------------------------

    def _install_signal_handlers(self) -> None:
        """
        Install handlers before startup phases and create selector wakeup fd.

        Handlers perform no cleanup/kernel work; they only set a flag.
        """
        if self._signal_wakeup_reader is not None:
            return

        reader, writer = socket.socketpair()
        reader.setblocking(False)
        writer.setblocking(False)

        self._signal_wakeup_reader = reader
        self._signal_wakeup_writer = writer
        self._previous_wakeup_fd = signal.set_wakeup_fd(
            writer.fileno(),
            warn_on_full_buffer=False,
        )

        def request_shutdown(signum: int, frame: object) -> None:
            del signum, frame
            self._shutdown_requested = True

        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            self._previous_signal_handlers[signum] = signal.getsignal(signum)

        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def _restore_signal_handlers(self) -> None:
        """Restore process-global signal state; useful for tests/embedding."""
        try:
            signal.set_wakeup_fd(self._previous_wakeup_fd)
        finally:
            self._previous_wakeup_fd = -1

        for signum, handler in self._previous_signal_handlers.items():
            signal.signal(signum, handler)
        self._previous_signal_handlers.clear()

        if self._signal_wakeup_reader is not None:
            self._signal_wakeup_reader.close()
            self._signal_wakeup_reader = None
        if self._signal_wakeup_writer is not None:
            self._signal_wakeup_writer.close()
            self._signal_wakeup_writer = None

    def _open_netlink_socket(self) -> socket.socket:
        """
        TODO implementation step 8.

        One daemon-owned AF_NETLINK/NETLINK_ROUTE socket subscribed to link and
        IPv4 address changes.  This listener intentionally remains outside
        KernelInterface because it feeds orchestration events and materializes
        no policy.  ENOBUFS must trigger a full resync.
        """
        raise NotImplementedError

    def _log_reconcile_outcome(
        self,
        signature: tuple[object, ...],
        *,
        level: int = logging.INFO,
        facts: tuple[DiagnosticFact, ...] = (),
        recovered_from: tuple[DiagnosticFact, ...] = (),
    ) -> None:
        """
        Edge-triggered final pass logging.

        Severity describes CURRENT functional state:
        - INFO: ACTIVE and the pass was clean;
        - WARNING: ACTIVE after a recovered incident, or DEGRADED with
          forwarding confirmed ON;
        - ERROR: ISOLATED, or DEGRADED with forwarding OFF/not confirmed ON.

        Dedupe identity uses stable RuntimeReasonCode values, never free-form
        exception detail.  Detail is render-only text.

        Clean INFO remains purely edge-triggered.  Unchanged WARNING/ERROR is
        repeated only after `failure_reminder_interval` (default 5 minutes).
        """
        dedupe_signature = (
            signature,
            tuple(fact.code for fact in facts),
            tuple(fact.code for fact in recovered_from),
        )
        now = time.monotonic()
        same_signature = (
            dedupe_signature == self._last_reconcile_log_signature
        )

        if same_signature:
            if level < logging.WARNING:
                return
            if (
                self._last_reconcile_log_at is not None
                and now - self._last_reconcile_log_at
                    < self.failure_reminder_interval
            ):
                return
        else:
            self._last_reconcile_log_signature = dedupe_signature

        self._last_reconcile_log_at = now

        message_parts = [f"reconcile outcome: {signature!r}"]

        if facts:
            message_parts.append(
                "pass facts: " + "; ".join(
                    self._format_diagnostic_fact(fact)
                    for fact in facts
                )
            )

        if recovered_from:
            message_parts.append(
                "recovered from: " + "; ".join(
                    self._format_diagnostic_fact(fact)
                    for fact in recovered_from
                )
            )

        LOG.log(level, "; ".join(message_parts))

    @staticmethod
    def _format_diagnostic_fact(fact: DiagnosticFact) -> str:
        base = RUNTIME_REASON_TEXT[fact.code]
        if fact.detail is None:
            return f"{fact.code.name}: {base}"
        return f"{fact.code.name}: {base}: {fact.detail}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vpn-gatewayd")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"config path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate/lint config without runtime lock or kernel side effects",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _print_config_issues(result: ConfigCheckResult) -> None:
    order = {
        ConfigIssueLevel.ERROR: 0,
        ConfigIssueLevel.WARNING: 1,
        ConfigIssueLevel.NOTE: 2,
    }
    for issue in sorted(
        result.issues,
        key=lambda item: (order[item.level], item.location, item.message),
    ):
        print(
            f"{issue.level.name}: {issue.location}: {issue.message}",
            file=sys.stderr,
        )


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()
    args = _build_arg_parser().parse_args(argv)

    loader = ConfigLoader()

    if args.check_config:
        try:
            result = loader.check(args.config)
        except ConfigError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        _print_config_issues(result)
        return 1 if result.has_errors else 0

    # Deliberately do not load config here.  Normal lifecycle requires:
    # LOCK -> CLEANUP -> LOAD + VALIDATE -> APPLY -> RUN.
    kernel = SubprocessKernelInterface()
    daemon = VpnGatewayDaemon(
        config_path=args.config,
        kernel=kernel,
        config_loader=loader,
    )

    try:
        daemon.serve()
    except NotImplementedError as exc:
        LOG.error("skeleton method is not implemented: %s", exc)
        return 2
    except (GatewayError, OSError) as exc:
        LOG.error("%s", exc)
        return 1
    finally:
        kernel.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
