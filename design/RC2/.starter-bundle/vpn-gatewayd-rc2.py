#!/usr/bin/env python3
"""
vpn-gatewayd — implementation skeleton for architecture RC2.

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
import fcntl
import logging
import os
import signal
import socket
import subprocess
import sys
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence


# ---------------------------------------------------------------------------
# Architecture: RC2
# Skeleton: RC2
# ---------------------------------------------------------------------------

VERSION = "RC2"

DEFAULT_CONFIG_PATH = Path("/etc/vpn-gateway/vpn-gateway.toml")
DEFAULT_LOCK_PATH = Path("/run/vpn-gateway/vpn-gatewayd.lock")

DEFAULT_RECONCILE_INTERVAL = 10.0
MIN_RECONCILE_INTERVAL = 1.0
MAX_RECONCILE_INTERVAL = 60.0

BLACKHOLE_ROUTE_PROTO = 201
KERNEL_ROUTE_PROTO = 2
VPN_ROUTE_PROTO = 202
BLACKHOLE_METRIC = 65536
PEER_METRIC_STEP = 10

VPNG_CHAIN_PREFIX = "VPNG-"

LOG = logging.getLogger("vpn-gatewayd")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GatewayError(Exception):
    """Base class for expected daemon/domain errors."""


class ConfigError(GatewayError):
    """Runtime configuration cannot be projected safely."""


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

    def load_runtime(self, path: Path) -> GatewayConfig:
        """
        Read selected config path and return managed validated projection.

        Must perform config file/directory security checks.
        Must not touch kernel-state or acquire the daemon runtime lock.
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

    def _read_toml(self, path: Path) -> Mapping[str, object]:
        self._validate_config_security(path)
        try:
            with path.open("rb") as fh:
                document = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"{path}: cannot read TOML: {exc}") from exc

        if not isinstance(document, dict):
            raise ConfigError(f"{path}: TOML root must be a table")
        return document

    def _validate_config_security(self, path: Path) -> None:
        """
        TODO implementation step 1.

        Required checks, in diagnostic order:
        - stat parent directory; ENOENT/not-directory -> ConfigError;
        - stat config file; ENOENT/not-regular-file -> ConfigError;
        - config file owner uid == 0;
        - config file mode has no group/other write;
        - parent directory owner uid == 0;
        - parent directory mode has no group/other write.

        Do not use path.exists()/is_file() as the security primitive: the
        implementation should obtain the stat results it will actually check
        and convert OSError into a precise ConfigError.
        """
        raise NotImplementedError

    def _build_runtime_projection(
        self,
        path: Path,
        document: Mapping[str, object],
    ) -> GatewayConfig:
        """
        TODO implementation step 1.

        Required high-level flow:
        1. validate top-level runtime schema;
        2. normalize managed_vpns as case-insensitive set-like selection;
        3. resolve each selected profile unambiguously;
        4. validate only selected profile bodies fully;
        5. validate managed-set cross-conflicts:
           - unique interfaces;
           - globally non-overlapping protected routes;
           - protected routes do not overlap any managed vpn.network;
        6. return MappingProxyType of managed VpnProfileConfig objects.

        Unmanaged profile bodies are not value/schema validated here.
        """
        raise NotImplementedError

    def _lint_document(
        self,
        path: Path,
        document: Mapping[str, object],
    ) -> ConfigCheckResult:
        """
        TODO implementation step 1.

        Reuse runtime validation for managed profiles, then lint the unmanaged
        catalog and cross-conflicts.  Aggregate independent ERROR/WARNING/NOTE
        issues in one result instead of failing at the first issue.
        """
        raise NotImplementedError


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
    Debian 13 adapter placeholder.

    Route/address inventory will use `ip -j`.
    Firewall inventory/apply will use iptables-save/iptables-restore with
    bounded subprocess timeouts and bounded iptables lock wait.

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
        try:
            return subprocess.run(
                list(argv),
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=self.command_timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise KernelError(f"command failed: {argv!r}: {exc}") from exc

    def list_routes(self) -> frozenset[RouteSpec]:
        """
        TODO implementation step 5.

        Parse `ip -j -4 route show table main`.
        Normalize:
        - "default" -> 0.0.0.0/0;
        - bare host dst -> /32;
        - named proto, especially "kernel", -> numeric ID;
        - onlink flag into RouteSpec.onlink.
        """
        raise NotImplementedError

    def add_route(self, route: RouteSpec) -> None:
        """TODO: exact route materialization from complete RouteSpec."""
        raise NotImplementedError

    def delete_route(self, route: RouteSpec) -> None:
        """TODO: exact route deletion."""
        raise NotImplementedError

    def list_interface_ipv4(
        self,
    ) -> Mapping[str, frozenset[IPv4Address]]:
        """
        TODO implementation step 5.

        Parse `ip -j -4 addr show`.
        For tun/p2p semantics use address_info[].local, not peer-oriented
        address fields.
        """
        raise NotImplementedError

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
        """
        raise NotImplementedError

    def iptables_restore(self, payload: str, *, noflush: bool = True) -> None:
        """
        TODO implementation step 5/6.

        Use iptables-restore --noflush and bounded lock wait.
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
        except OSError:
            os.close(fd)
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
    ) -> None:
        self.config_path = config_path
        self.kernel = kernel
        self.config_loader = config_loader
        self.notifier = notifier or SystemdNotifier()
        self.lock_path = lock_path

        self.state = DaemonState.STARTING
        self.config: GatewayConfig | None = None
        self.profiles: Mapping[str, VpnProfile] = MappingProxyType({})

        self._reported_route_overlaps: dict[str, frozenset[RouteSpec]] = {}
        self._shutdown_requested = False
        self._last_reconcile_log_signature: tuple[object, ...] | None = None

        # Conscious boundary: the architecture requires one daemon-owned
        # Netlink listener.  It is an event source owned by orchestration, not
        # a policy/materialization operation of KernelInterface.  Exact
        # serialized event-loop mechanics remain open.
        self._netlink_socket: socket.socket | None = None

    # ---- Lifecycle -------------------------------------------------------

    def serve(self) -> None:
        """
        Full normal lifecycle.

        A failed startup intentionally does not run an ad-hoc rollback:
        partial marked state remains fail-closed with forwarding off and is
        removed by the next universal cleanup.
        """
        with InstanceLock(self.lock_path):
            self.cleanup()

            # Architectural boundary: config is first read only here, AFTER
            # lock + cleanup.
            config = self.config_loader.load_runtime(self.config_path)
            self._install_config(config)

            self.apply()

            self.state = DaemonState.ACTIVE
            self._install_signal_handlers()
            self.notifier.ready()

            # run() returns only for a requested graceful shutdown.
            self.run()

            self.state = DaemonState.STOPPING
            self.notifier.stopping()
            self.cleanup()

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
        forwarding_enabled, forwarding_enable_error = (
            self._best_effort_enable_forwarding()
        )

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

        if forwarding_enable_error is not None:
            current_facts.append(forwarding_enable_error)

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
        TODO implementation step 4.

        Build exactly one immutable desired snapshot for the current pass:
        BLACKHOLE routes are always desired; UNICAST routes are desired only
        for ready profiles.  Return a MappingProxyType whose values are
        frozensets.  The same snapshot is passed to build/validate/verify and
        is not recomputed inside those phases.
        """
        raise NotImplementedError

    def _build_plan(
        self,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> ReconciliationPlan:
        """TODO implementation step 4: pure plan construction."""
        raise NotImplementedError

    def _validate_plan(
        self,
        plan: ReconciliationPlan,
        *,
        all_kernel_routes: frozenset[RouteSpec],
        desired_routes_by_profile: Mapping[str, frozenset[RouteSpec]],
    ) -> None:
        """
        TODO implementation step 4.

        Required checks include:
        - no RouteSpec in both add/delete;
        - foreign delete only in exact protected authoritative scope;
        - proto kernel (KERNEL_ROUTE_PROTO == 2) never appears in route_deletes;
        - owned non-desired delete has profile ownership justification;
        - every add belongs to current desired_routes_by_profile;
        - no two managed profiles claim the same exact resource.

        Exact protected prefix == connected main-table proto-kernel route must
        therefore fail initial startup plan validation.
        """
        raise NotImplementedError

    def _apply_plan(self, plan: ReconciliationPlan) -> None:
        """
        TODO implementation step 6.

        Apply missing BLACKHOLE route_adds before ordinary route operations.
        NAT operations do not exist in ReconciliationPlan.
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
        TODO implementation step 4.

        Include:
        - exact protected prefixes;
        - competing exact routes;
        - relevant BLACKHOLE guards;
        - more-/less-specific overlaps;
        - exclude default route as an overlap.
        """
        raise NotImplementedError

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
        TODO implementation/research.

        First test canonical iptables-restore -> iptables-save round-trip on the
        target host without counters.  If text is not stable, use only a small
        normalizer/parser for the daemon-owned fixed subset.

        Expected parse/normalization/comparison inability must raise
        FirewallInspectionError so _check_fixed_firewall_nat() maps it to
        UNKNOWN.  Programming errors must not be hidden by a broad catch.
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
        Return (confirmed_enabled, error).

        Like disable, this helper does not emit an intermediate log; the caller
        includes the result in the final reconciliation outcome signature.
        """
        try:
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

        return True, None

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
        def request_shutdown(signum: int, frame: object) -> None:
            del signum, frame
            self._shutdown_requested = True

        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)

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
        """
        dedupe_signature = (
            signature,
            tuple(fact.code for fact in facts),
            tuple(fact.code for fact in recovered_from),
        )
        if dedupe_signature == self._last_reconcile_log_signature:
            return
        self._last_reconcile_log_signature = dedupe_signature

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
