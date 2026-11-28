"""Linux D.001 realization for explicitly managed WireGuard base instances.

Architecture: D.001 ManagedVPNAdapter.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Protocol, Sequence

from .interface_identity import InterfaceIdentity
from .release1_config import ManagedWireGuardConfig


_OWNER_PREFIX = "vpn-gate:managed-vpn:"
_NONE_PRESHARED_KEYS = frozenset({"", "(none)", "off"})


class ManagedWireGuardError(RuntimeError):
    """Managed WireGuard base state could not be safely observed or converged."""


class ManagedWireGuardState(str, Enum):
    ABSENT = "absent"
    PRESENT = "present"


@dataclass(frozen=True, slots=True)
class ManagedWireGuardObservation:
    device_id: str
    state: ManagedWireGuardState
    interface: InterfaceIdentity | None = None
    confirmed_generation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("device_id must be non-empty text")
        if self.state is ManagedWireGuardState.ABSENT:
            if self.interface is not None or self.confirmed_generation is not None:
                raise ValueError("absent observation cannot carry present state")
        elif self.interface is None:
            raise ValueError("present observation requires interface identity")


class ManagedWireGuardCommandRunner(Protocol):
    def run(self, argv: Sequence[str]) -> str:
        """Run one argv-only command or raise; return stdout."""

    def run_script(self, argv: Sequence[str], script: str) -> str:
        """Run one stdin-fed command or raise; return stdout."""


class SubprocessManagedWireGuardRunner:
    def run(self, argv: Sequence[str]) -> str:
        completed = subprocess.run(
            tuple(argv),
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout

    def run_script(self, argv: Sequence[str], script: str) -> str:
        completed = subprocess.run(
            tuple(argv),
            input=script,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout


@dataclass(frozen=True, slots=True)
class _PreparedPeer:
    public_key: str
    endpoint: str
    probe_prefix: str
    preshared_key: str | None
    preshared_digest: str | None


@dataclass(frozen=True, slots=True)
class _PreparedBase:
    device_id: str
    marker: str
    config: ManagedWireGuardConfig
    private_key: str
    interface_public_key: str
    peers: tuple[_PreparedPeer, ...]
    generation: str


@dataclass(slots=True)
class LinuxManagedWireGuardAdapter:
    """Direct D.001 Adapter for one managed Linux network namespace."""

    runner: ManagedWireGuardCommandRunner
    network_namespace: str

    def __post_init__(self) -> None:
        if not isinstance(self.network_namespace, str) or not self.network_namespace:
            raise ValueError("network_namespace must be non-empty text")

    def desired_generation(
        self,
        device_id: str,
        desired: ManagedWireGuardConfig,
    ) -> str:
        """Validate current secret inputs and return the desired base-generation token."""
        return self._prepare(device_id, desired).generation

    def observe(self, device_id: str) -> ManagedWireGuardObservation:
        marker = _owner_marker(device_id)
        row = self._owned_link(marker)
        if row is None:
            return ManagedWireGuardObservation(
                device_id=device_id,
                state=ManagedWireGuardState.ABSENT,
            )
        return ManagedWireGuardObservation(
            device_id=device_id,
            state=ManagedWireGuardState.PRESENT,
            interface=_identity(row),
        )

    def converge_present(
        self,
        device_id: str,
        desired: ManagedWireGuardConfig,
    ) -> ManagedWireGuardObservation:
        prepared = self._prepare(device_id, desired)

        owned = self._owned_link(prepared.marker)
        if owned is not None:
            if self._matches_prepared(owned, prepared):
                return self._confirmed_observation(owned, prepared)
            self._delete_owned(owned, prepared.marker)
            if self._owned_link(prepared.marker) is not None:
                raise ManagedWireGuardError(
                    "old managed WireGuard generation remains after delete"
                )

        foreign = self._link_by_name(desired.interface)
        if foreign is not None:
            raise ManagedWireGuardError(
                f"interface {desired.interface!r} already exists without the "
                "expected managed-WireGuard ownership"
            )

        created_identity: InterfaceIdentity | None = None
        try:
            self._run(
                (
                    "ip",
                    "-n",
                    self.network_namespace,
                    "link",
                    "add",
                    desired.interface,
                    "type",
                    "wireguard",
                ),
                "managed WireGuard create",
            )
            created = self._link_by_name(desired.interface)
            if created is None or _link_kind(created) != "wireguard":
                raise ManagedWireGuardError(
                    "new WireGuard interface cannot be freshly identified"
                )
            created_identity = _identity(created)

            self._run(
                (
                    "ip",
                    "-n",
                    self.network_namespace,
                    "link",
                    "set",
                    "dev",
                    desired.interface,
                    "alias",
                    prepared.marker,
                ),
                "managed WireGuard ownership-marker apply",
            )
            self._run_script(
                self._ns_command("wg", "setconf", desired.interface, "/dev/stdin"),
                _render_setconf(prepared),
                "managed WireGuard base configuration apply",
            )
            self._run(
                (
                    "ip",
                    "-n",
                    self.network_namespace,
                    "addr",
                    "add",
                    str(desired.address),
                    "dev",
                    desired.interface,
                ),
                "managed WireGuard address apply",
            )
            self._run(
                (
                    "ip",
                    "-n",
                    self.network_namespace,
                    "link",
                    "set",
                    desired.interface,
                    "up",
                ),
                "managed WireGuard link activation",
            )

            confirmed = self._owned_link(prepared.marker)
            if confirmed is None or not self._matches_prepared(confirmed, prepared):
                raise ManagedWireGuardError(
                    "new managed WireGuard generation failed exact fresh verification"
                )
            return self._confirmed_observation(confirmed, prepared)
        except Exception as exc:
            if created_identity is not None:
                self._cleanup_created(created_identity, prepared.marker)
            if isinstance(exc, ManagedWireGuardError):
                raise
            raise ManagedWireGuardError(
                "managed WireGuard creation failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def converge_absent(self, device_id: str) -> ManagedWireGuardObservation:
        marker = _owner_marker(device_id)
        owned = self._owned_link(marker)
        if owned is None:
            return ManagedWireGuardObservation(
                device_id=device_id,
                state=ManagedWireGuardState.ABSENT,
            )
        self._delete_owned(owned, marker)
        if self._owned_link(marker) is not None:
            raise ManagedWireGuardError(
                "managed WireGuard interface remains after delete"
            )
        return ManagedWireGuardObservation(
            device_id=device_id,
            state=ManagedWireGuardState.ABSENT,
        )

    def confirm_present(
        self,
        device_id: str,
        desired_base: ManagedWireGuardConfig,
    ) -> ManagedWireGuardObservation:
        """Confirm the exact current managed base without converging it."""
        prepared = self._prepare(device_id, desired_base)
        first = self._exact_owned_link(prepared)
        if first is None:
            raise ManagedWireGuardError("managed WireGuard base is absent")
        if not self._matches_prepared(first, prepared):
            raise ManagedWireGuardError("managed WireGuard base does not match")
        current = self._recheck_exact_base(prepared, _identity(first))
        return self._confirmed_observation(current, prepared)

    def retire_exact(
        self,
        device_id: str,
        expected_identity: InterfaceIdentity,
        expected_generation: str,
        desired_base: ManagedWireGuardConfig,
    ) -> ManagedWireGuardObservation:
        """Delete only the reverified identity and base generation, at most once.

        This is not an atomic kernel compare-delete against external mutation.
        """
        if not isinstance(expected_identity, InterfaceIdentity):
            raise ValueError("expected_identity must be InterfaceIdentity")
        if not isinstance(expected_generation, str) or not expected_generation:
            raise ValueError("expected_generation must be non-empty text")
        prepared = self._prepare(device_id, desired_base)
        if expected_generation != prepared.generation:
            raise ManagedWireGuardError("managed WireGuard base generation changed")
        if expected_identity.ifname != prepared.config.interface:
            raise ManagedWireGuardError("expected interface name differs from desired base")

        first = self._exact_owned_link(prepared, expected_identity)
        if first is not None:
            if not self._matches_prepared(first, prepared):
                raise ManagedWireGuardError("managed WireGuard base does not match")
            current = self._recheck_exact_base(prepared, expected_identity)
            try:
                self._delete_owned(current, prepared.marker)
            except ValueError as exc:
                # An invalid identity in the final by-name observation is
                # an observation failure, not a caller argument error.
                raise ManagedWireGuardError(
                    "invalid managed WireGuard identity before delete"
                ) from exc
            if self._exact_owned_link(prepared, expected_identity) is not None:
                raise ManagedWireGuardError(
                    "managed WireGuard exact instance remains after delete"
                )

        return ManagedWireGuardObservation(
            device_id=device_id,
            state=ManagedWireGuardState.ABSENT,
        )

    def _recheck_exact_base(
        self,
        prepared: _PreparedBase,
        identity: InterfaceIdentity,
    ) -> dict[str, object]:
        current = self._exact_owned_link(prepared, identity)
        if current is None or not self._matches_prepared(current, prepared):
            raise ManagedWireGuardError(
                "managed WireGuard base changed during exact verification"
            )
        return current

    def _exact_owned_link(
        self,
        prepared: _PreparedBase,
        expected: InterfaceIdentity | None = None,
    ) -> dict[str, object] | None:
        """Validate the whole inventory before any relation/absence decision."""
        inventory: list[tuple[InterfaceIdentity, dict[str, object]]] = []
        names: set[str] = set()
        indices: set[int] = set()
        for row in self._link_rows():
            try:
                identity = _identity(row)
            except ValueError as exc:
                raise ManagedWireGuardError(
                    "invalid identity in exact managed-link inventory"
                ) from exc
            if identity.ifname in names or identity.ifindex in indices:
                raise ManagedWireGuardError(
                    "duplicate identity in exact managed-link inventory"
                )
            alias = row.get("ifalias")
            if alias is not None and not isinstance(alias, str):
                raise ManagedWireGuardError(
                    "invalid alias in exact managed-link inventory"
                )
            names.add(identity.ifname)
            indices.add(identity.ifindex)
            inventory.append((identity, row))

        related = [
            (identity, row)
            for identity, row in inventory
            if row.get("ifalias") == prepared.marker
            or identity.ifname == prepared.config.interface
            or (expected is not None and identity.ifindex == expected.ifindex)
        ]
        if not related:
            return None
        if len(related) != 1:
            raise ManagedWireGuardError("ambiguous exact managed WireGuard relation")
        identity, row = related[0]
        if (
            row.get("ifalias") != prepared.marker
            or identity.ifname != prepared.config.interface
            or _link_kind(row) != "wireguard"
            or (expected is not None and identity != expected)
        ):
            raise ManagedWireGuardError("managed WireGuard exact identity or ownership changed")
        return row

    def _prepare(
        self,
        device_id: str,
        desired: ManagedWireGuardConfig,
    ) -> _PreparedBase:
        if not isinstance(device_id, str) or not device_id:
            raise ValueError("device_id must be non-empty text")
        if not isinstance(desired, ManagedWireGuardConfig):
            raise ValueError("desired must be ManagedWireGuardConfig")

        private_key = _read_wireguard_secret(
            desired.private_key_file,
            "private_key_file",
        )
        interface_public_key = self._run_script(
            ("wg", "pubkey"),
            private_key + "\n",
            "WireGuard public-key derivation",
        ).strip()
        _validate_wireguard_key(
            interface_public_key,
            "derived WireGuard public key",
        )

        peers: list[_PreparedPeer] = []
        for peer in desired.peers:
            preshared_key = None
            preshared_digest = None
            if peer.preshared_key_file is not None:
                preshared_key = _read_wireguard_secret(
                    peer.preshared_key_file,
                    f"peer {peer.peer_id!r} preshared_key_file",
                )
                preshared_digest = _key_digest(preshared_key)
            peers.append(
                _PreparedPeer(
                    public_key=peer.public_key,
                    endpoint=f"{peer.endpoint_address}:{peer.endpoint_port}",
                    probe_prefix=f"{peer.probe_target}/32",
                    preshared_key=preshared_key,
                    preshared_digest=preshared_digest,
                )
            )

        facts = {
            "interface": desired.interface,
            "address": str(desired.address),
            "interface_public_key": interface_public_key,
            "listen_port": desired.listen_port,
            "peers": sorted(
                (
                    {
                        "public_key": peer.public_key,
                        "endpoint": peer.endpoint,
                        "probe_prefix": peer.probe_prefix,
                        "preshared_digest": peer.preshared_digest,
                    }
                    for peer in peers
                ),
                key=lambda item: item["public_key"],
            ),
        }
        generation = hashlib.sha256(
            json.dumps(
                facts,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return _PreparedBase(
            device_id=device_id,
            marker=_owner_marker(device_id),
            config=desired,
            private_key=private_key,
            interface_public_key=interface_public_key,
            peers=tuple(peers),
            generation=generation,
        )

    def _matches_prepared(
        self,
        row: dict[str, object],
        prepared: _PreparedBase,
    ) -> bool:
        if row.get("ifname") != prepared.config.interface:
            return False
        if row.get("ifalias") != prepared.marker:
            return False
        if _link_kind(row) != "wireguard":
            return False
        flags = row.get("flags")
        if not isinstance(flags, list) or "UP" not in flags:
            return False

        if self._ipv4_addresses(prepared.config.interface) != {
            str(prepared.config.address)
        }:
            return False

        dump = self._run(
            self._ns_command(
                "wg",
                "show",
                prepared.config.interface,
                "dump",
            ),
            "WireGuard state observation",
        )
        return _dump_matches(dump, prepared)

    def _ipv4_addresses(self, ifname: str) -> set[str]:
        raw = self._run(
            (
                "ip",
                "-n",
                self.network_namespace,
                "-j",
                "addr",
                "show",
                "dev",
                ifname,
            ),
            "managed WireGuard address observation",
        )
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ManagedWireGuardError(
                f"invalid address inventory JSON: {exc}"
            ) from None
        if not isinstance(rows, list) or len(rows) != 1:
            raise ManagedWireGuardError(
                "managed WireGuard address inventory is not singular"
            )
        if not isinstance(rows[0], dict):
            raise ManagedWireGuardError(
                "managed WireGuard address inventory row is not an object"
            )
        info = rows[0].get("addr_info", [])
        if not isinstance(info, list):
            raise ManagedWireGuardError(
                "managed WireGuard address inventory has invalid addr_info"
            )
        result: set[str] = set()
        for item in info:
            if not isinstance(item, dict) or item.get("family") != "inet":
                continue
            local = item.get("local")
            prefixlen = item.get("prefixlen")
            if not isinstance(local, str) or type(prefixlen) is not int:
                raise ManagedWireGuardError(
                    "managed WireGuard IPv4 inventory is invalid"
                )
            result.add(f"{local}/{prefixlen}")
        return result

    def _confirmed_observation(
        self,
        row: dict[str, object],
        prepared: _PreparedBase,
    ) -> ManagedWireGuardObservation:
        return ManagedWireGuardObservation(
            device_id=prepared.device_id,
            state=ManagedWireGuardState.PRESENT,
            interface=_identity(row),
            confirmed_generation=prepared.generation,
        )

    def _delete_owned(
        self,
        row: dict[str, object],
        marker: str,
    ) -> None:
        if row.get("ifalias") != marker or _link_kind(row) != "wireguard":
            raise ManagedWireGuardError(
                "refusing to delete interface without exact managed ownership"
            )
        identity = _identity(row)
        current = self._link_by_name(identity.ifname)
        if current is None or _identity(current) != identity:
            raise ManagedWireGuardError(
                "managed WireGuard interface generation changed before delete"
            )
        if current.get("ifalias") != marker or _link_kind(current) != "wireguard":
            raise ManagedWireGuardError(
                "managed WireGuard ownership changed before delete"
            )
        self._run(
            (
                "ip",
                "-n",
                self.network_namespace,
                "link",
                "del",
                identity.ifname,
            ),
            "managed WireGuard delete",
        )

    def _cleanup_created(
        self,
        identity: InterfaceIdentity,
        marker: str,
    ) -> None:
        try:
            current = self._link_by_name(identity.ifname)
            if current is None or _identity(current) != identity:
                return
            if _link_kind(current) != "wireguard":
                return
            alias = current.get("ifalias")
            if alias not in (None, "", marker):
                return
            self._run(
                (
                    "ip",
                    "-n",
                    self.network_namespace,
                    "link",
                    "del",
                    identity.ifname,
                ),
                "failed-create cleanup",
            )
        except Exception:
            # The original failure is authoritative; uncertain cleanup remains visible
            # to the next fresh observation and is never reported as success.
            return

    def _owned_link(self, marker: str) -> dict[str, object] | None:
        matches = [
            row
            for row in self._link_rows()
            if row.get("ifalias") == marker
        ]
        if len(matches) > 1:
            raise ManagedWireGuardError(
                "multiple interfaces carry the same managed-WireGuard ownership marker"
            )
        if not matches:
            return None
        row = matches[0]
        if _link_kind(row) != "wireguard":
            raise ManagedWireGuardError(
                "managed-WireGuard ownership marker is attached to a foreign link kind"
            )
        return row

    def _link_by_name(self, ifname: str) -> dict[str, object] | None:
        matches = [
            row
            for row in self._link_rows()
            if row.get("ifname") == ifname
        ]
        if len(matches) > 1:
            raise ManagedWireGuardError(
                f"link inventory repeats interface name {ifname!r}"
            )
        return matches[0] if matches else None

    def _link_rows(self) -> list[dict[str, object]]:
        raw = self._run(
            (
                "ip",
                "-n",
                self.network_namespace,
                "-d",
                "-j",
                "link",
                "show",
            ),
            "managed WireGuard link observation",
        )
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ManagedWireGuardError(
                f"invalid managed-link inventory JSON: {exc}"
            ) from None
        if not isinstance(rows, list):
            raise ManagedWireGuardError(
                "managed-link inventory root must be an array"
            )
        if any(not isinstance(row, dict) for row in rows):
            raise ManagedWireGuardError(
                "managed-link inventory contains a non-object row"
            )
        return rows

    def _run(
        self,
        argv: Sequence[str],
        context: str,
    ) -> str:
        try:
            return self.runner.run(argv)
        except ManagedWireGuardError:
            raise
        except Exception as exc:
            raise ManagedWireGuardError(
                f"{context} failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _run_script(
        self,
        argv: Sequence[str],
        script: str,
        context: str,
    ) -> str:
        try:
            return self.runner.run_script(argv, script)
        except ManagedWireGuardError:
            raise
        except Exception as exc:
            raise ManagedWireGuardError(
                f"{context} failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _ns_command(self, *argv: str) -> tuple[str, ...]:
        return (
            "ip",
            "netns",
            "exec",
            self.network_namespace,
            *argv,
        )


def _owner_marker(device_id: str) -> str:
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("device_id must be non-empty text")
    digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
    return _OWNER_PREFIX + digest


def _identity(row: dict[str, object]) -> InterfaceIdentity:
    ifname = row.get("ifname")
    ifindex = row.get("ifindex")
    if not isinstance(ifname, str) or not ifname:
        raise ManagedWireGuardError("link row has invalid ifname")
    if type(ifindex) is not int or ifindex <= 0:
        raise ManagedWireGuardError("link row has invalid ifindex")
    return InterfaceIdentity(ifname, ifindex)


def _link_kind(row: dict[str, object]) -> str | None:
    linkinfo = row.get("linkinfo")
    if not isinstance(linkinfo, dict):
        return None
    value = linkinfo.get("info_kind")
    return value if isinstance(value, str) else None


def _read_wireguard_secret(path_text: str, where: str) -> str:
    path = Path(path_text)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ManagedWireGuardError(
            f"{where} cannot be opened safely: {exc}"
        ) from None
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ManagedWireGuardError(f"{where} is not a regular file")
        if metadata.st_uid != os.geteuid():
            raise ManagedWireGuardError(
                f"{where} owner does not match effective uid"
            )
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ManagedWireGuardError(
                f"{where} grants group/other access"
            )
        data = os.read(fd, 4096)
        if os.read(fd, 1):
            raise ManagedWireGuardError(f"{where} is unexpectedly large")
    finally:
        os.close(fd)

    try:
        value = data.decode("ascii").strip()
    except UnicodeDecodeError:
        raise ManagedWireGuardError(f"{where} is not ASCII") from None
    _validate_wireguard_key(value, where)
    return value


def _validate_wireguard_key(value: str, where: str) -> None:
    if not isinstance(value, str):
        raise ManagedWireGuardError(f"{where} is not a WireGuard key")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise ManagedWireGuardError(
            f"{where} is not a canonical WireGuard key"
        ) from None
    if (
        len(decoded) != 32
        or base64.b64encode(decoded).decode("ascii") != value
    ):
        raise ManagedWireGuardError(
            f"{where} is not a canonical WireGuard key"
        )


def _key_digest(value: str) -> str:
    decoded = base64.b64decode(value, validate=True)
    return hashlib.sha256(decoded).hexdigest()


def _render_setconf(prepared: _PreparedBase) -> str:
    lines = [
        "[Interface]",
        f"PrivateKey = {prepared.private_key}",
    ]
    if prepared.config.listen_port is not None:
        lines.append(f"ListenPort = {prepared.config.listen_port}")
    for peer in prepared.peers:
        lines.extend(
            (
                "",
                "[Peer]",
                f"PublicKey = {peer.public_key}",
            )
        )
        if peer.preshared_key is not None:
            lines.append(f"PresharedKey = {peer.preshared_key}")
        lines.extend(
            (
                f"Endpoint = {peer.endpoint}",
                f"AllowedIPs = {peer.probe_prefix}",
            )
        )
    return "\n".join(lines) + "\n"


def _dump_matches(text: str, prepared: _PreparedBase) -> bool:
    rows = [line.split("\t") for line in text.splitlines() if line]
    if not rows or len(rows[0]) < 4:
        raise ManagedWireGuardError("WireGuard dump has invalid interface row")

    interface = rows[0]
    if interface[1] != prepared.interface_public_key:
        return False
    if prepared.config.listen_port is not None:
        if interface[2] != str(prepared.config.listen_port):
            return False

    peer_rows = rows[1:]
    expected = {peer.public_key: peer for peer in prepared.peers}
    if len(peer_rows) != len(expected):
        return False

    seen: set[str] = set()
    for row in peer_rows:
        if len(row) < 5:
            raise ManagedWireGuardError("WireGuard dump has invalid peer row")
        public_key, preshared_key, endpoint, allowed_text = row[:4]
        peer = expected.get(public_key)
        if peer is None or public_key in seen:
            return False
        seen.add(public_key)

        if endpoint != peer.endpoint:
            return False

        actual_allowed = {
            item.strip()
            for item in allowed_text.split(",")
            if item.strip()
        }
        if peer.probe_prefix not in actual_allowed:
            return False
        # Additional AllowedIPs are D.002-owned runtime state. D.001 verifies
        # only its permanent peer probe prefix and does not police their owner.
        if peer.preshared_digest is None:
            if preshared_key not in _NONE_PRESHARED_KEYS:
                return False
        else:
            if preshared_key in _NONE_PRESHARED_KEYS:
                return False
            _validate_wireguard_key(
                preshared_key,
                "observed preshared key",
            )
            if _key_digest(preshared_key) != peer.preshared_digest:
                return False

    return seen == set(expected)
