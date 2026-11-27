"""9b-C-B2 closed trusted staging registry/scheduler; synthetic-only exec."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import math
from pathlib import Path
import threading

from core import canonical, ident, require, strict_json, Conflict
from project_tasks import body_hash
from split_journal import validate_v2_config
from v2_identity import validate_bindings, select_identity
from v2_owner import Capability
from v2_writer_ipc import SessionBinding
from v2_writer_launcher import Limits, LaunchSpec, Supervisor, Busy
from v2_writer_coordinator import FilePin, StorePins
from v2_writer_spool import (Spool, Quotas, ResourcePolicy, MARKED, RESULT, RR,
                             MAX_CONFIG_BYTES, MAX_VERSION)

MAX_BOOTSTRAP = 2 * 1024 * 1024
FAULTS = frozenset(("none", "after_marker", "after_writer", "hold_marker"))


def _shape(value, keys):
    require(type(value) is dict and set(value) == set(keys), "closed trusted bootstrap required")
    return value


def _wall(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= 3600


def _json(value):
    require(type(value) is str and 0 < len(value.encode("utf-8")) <= MAX_CONFIG_BYTES,
            "bounded trusted JSON required")
    obj = strict_json(value)
    require(canonical(obj) == value, "noncanonical trusted JSON")
    return obj


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    policy_id: str
    ordinary_limits: Limits
    ordinary_wall: float
    recovery_limits: Limits
    recovery_wall: float

    def __post_init__(self):
        require(type(self.policy_id) is str and ident(self.policy_id)
                and type(self.ordinary_limits) is Limits and type(self.recovery_limits) is Limits
                and _wall(self.ordinary_wall) and _wall(self.recovery_wall),
                "invalid trusted resource policy")

    def identity(self):
        return ResourcePolicy(self.policy_id, hashlib.sha256(
            canonical(asdict(self)).encode("utf-8")).hexdigest())

    def lane(self, recovery):
        require(type(recovery) is bool, "invalid trusted lane")
        return ((self.recovery_limits, self.recovery_wall) if recovery else
                (self.ordinary_limits, self.ordinary_wall))


@dataclass(frozen=True, slots=True)
class SelectedPolicy:
    """Private child projection; unselected lane parameters never cross exec."""
    resource: ResourcePolicy
    limits: Limits
    wall: float
    recovery: bool

    def __post_init__(self):
        require(type(self.resource) is ResourcePolicy and type(self.limits) is Limits
                and _wall(self.wall) and type(self.recovery) is bool,
                "invalid selected resource policy")

    def identity(self):
        return self.resource

    def lane(self, recovery):
        require(type(recovery) is bool and recovery is self.recovery,
                "unselected resource lane")
        return self.limits, self.wall


@dataclass(frozen=True, slots=True)
class SyntheticFixture:
    """Fixed local synthetic adapter only; pinned immutable fixture and counter."""
    data: FilePin
    data_sha256: str
    counter: FilePin
    fault: str = "none"

    def __post_init__(self):
        require(type(self.data) is FilePin and type(self.counter) is FilePin
                and self.data.inode != self.counter.inode
                and self.data.path != self.counter.path and self.data.store_id != self.counter.store_id
                and type(self.data_sha256) is str and body_hash(self.data_sha256)
                and type(self.fault) is str and self.fault in FAULTS,
                "invalid synthetic fixture")


@dataclass(frozen=True, slots=True)
class Route:
    """Trusted current route; no worker-derived configuration or callbacks."""
    config_json: str = field(repr=False)
    bindings_json: str = field(repr=False)
    runtime_model: str
    session: SessionBinding
    capability: Capability = field(repr=False)
    pins: StorePins
    quotas: Quotas
    policy: ExecutionPolicy | SelectedPolicy
    fixture: SyntheticFixture

    def __post_init__(self):
        cfg, bindings = _json(self.config_json), _json(self.bindings_json)
        validate_v2_config(cfg)
        validate_bindings(bindings)
        require(type(self.runtime_model) is str and type(self.session) is SessionBinding
                and type(self.capability) is Capability and type(self.pins) is StorePins
                and self.pins.checkpoint is not None and type(self.quotas) is Quotas
                and type(self.policy) in (ExecutionPolicy, SelectedPolicy)
                and type(self.fixture) is SyntheticFixture,
                "invalid trusted route")
        selected = select_identity(bindings, self.runtime_model, cfg["roles"],
                                   selected_role=self.session.role)
        cap = self.capability
        require((selected["transport_role"], selected["incarnation"]) ==
                (self.session.role, self.session.incarnation)
                and (cap.transport_role, cap.incarnation, cap.generation) ==
                (self.session.role, self.session.incarnation, self.session.owner_generation)
                and cap.store_id == self.pins.owner.store_id
                and cap.repository == cfg["repository"].lower()
                and cap.journal_epoch == cfg["journal_epoch"]
                and type(cap.token) is str and body_hash(cap.token),
                "trusted route identity mismatch")
        pins = self.pins.values() + (self.fixture.data, self.fixture.counter)
        require(len({p.path for p in pins}) == len(pins)
                and len({p.inode for p in pins}) == len(pins)
                and len({p.store_id for p in pins}) == len(pins),
                "synthetic fixture/store alias")

    def key(self):
        return self.session.role, self.session.incarnation

    def launch_spec(self, recovery):
        p = self.pins
        limits, wall = self.policy.lane(recovery)
        # This staged actual-composition fixture is same-identity only.
        return LaunchSpec(self.session, (p.owner.store_id, p.checkpoint.store_id,
                                         p.attempt.store_id, p.input.store_id),
                          limits, wall)

    def _wire(self, recovery):
        require(type(self.policy) is ExecutionPolicy, "full parent policy required")
        limits, wall = self.policy.lane(recovery)
        selected = SelectedPolicy(self.policy.identity(), limits, wall, recovery)
        def pin(p):
            return dict(store_id=p.store_id, path=str(p.path), inode=list(p.inode))
        return dict(config_json=self.config_json, bindings_json=self.bindings_json,
                    runtime_model=self.runtime_model, session=asdict(self.session),
                    capability=asdict(self.capability),
                    pins={k: pin(getattr(self.pins, k)) for k in
                          ("spool", "attempt", "input", "owner", "checkpoint")},
                    quotas=asdict(self.quotas), policy=asdict(selected),
                    fixture=dict(data=pin(self.fixture.data), data_sha256=self.fixture.data_sha256,
                                 counter=pin(self.fixture.counter), fault=self.fixture.fault))

    @classmethod
    def _from_wire(cls, value):
        v = _shape(value, ("config_json", "bindings_json", "runtime_model", "session",
                           "capability", "pins", "quotas", "policy", "fixture"))
        def pin(raw):
            r = _shape(raw, ("store_id", "path", "inode"))
            require(type(r["path"]) is str and 0 < len(r["path"]) <= 4096
                    and "\0" not in r["path"] and type(r["inode"]) is list,
                    "invalid wire pin")
            return FilePin(r["store_id"], Path(r["path"]), tuple(r["inode"]))
        p = _shape(v["pins"], ("spool", "attempt", "input", "owner", "checkpoint"))
        q = _shape(v["policy"], ("resource", "limits", "wall", "recovery"))
        f = _shape(v["fixture"], ("data", "data_sha256", "counter", "fault"))
        return cls(v["config_json"], v["bindings_json"], v["runtime_model"],
                   SessionBinding(**v["session"]), Capability(**v["capability"]),
                   StorePins(**{k: pin(x) for k, x in p.items()}), Quotas(**v["quotas"]),
                   SelectedPolicy(ResourcePolicy(**q["resource"]), Limits(**q["limits"]),
                                  q["wall"], q["recovery"]),
                   SyntheticFixture(pin(f["data"]), f["data_sha256"], pin(f["counter"]), f["fault"]))


@dataclass(frozen=True, slots=True)
class Bootstrap:
    route: Route = field(repr=False)
    selection: tuple | None = None
    deadline: float | None = None  # child-only absolute monotonic deadline

    def __post_init__(self):
        require(type(self.route) is Route, "invalid trusted route")
        if self.selection is not None:
            require(type(self.selection) is tuple and len(self.selection) == 2
                    and type(self.selection[0]) is str and body_hash(self.selection[0])
                    and type(self.selection[1]) is int and 0 < self.selection[1] <= MAX_VERSION,
                    "invalid trusted recovery selector")
        if type(self.route.policy) is SelectedPolicy:
            require(self.route.policy.recovery is self.recovery
                    and type(self.deadline) in (int, float) and math.isfinite(self.deadline)
                    and self.deadline > 0, "selected lane/deadline mismatch")
        else:
            require(self.deadline is None, "parent bootstrap cannot override deadline")

    @property
    def recovery(self):
        return self.selection is not None

    def wire(self, deadline):
        require(type(self.route.policy) is ExecutionPolicy and type(deadline) in (int, float)
                and math.isfinite(deadline) and deadline > 0, "invalid parent projection")
        raw = canonical(dict(route=self.route._wire(self.recovery), selection=self.selection,
                             deadline=deadline)).encode("utf-8")
        require(0 < len(raw) <= MAX_BOOTSTRAP, "trusted bootstrap too large")
        return raw

    @classmethod
    def from_wire(cls, value):
        v = _shape(value, ("route", "selection", "deadline"))
        s = v["selection"]
        require(s is None or type(s) is list, "invalid trusted selector")
        return cls(Route._from_wire(v["route"]), None if s is None else tuple(s), v["deadline"])


class SchedulingBlocked(Conflict):
    """No trusted launch made; durable pending rows remain unchanged."""


def first_pending(inventory):
    # C-A inventory is already in exact request-id order.
    return next((r for r in inventory if r["state"] == MARKED or
                 (r["state"] == RESULT and r["classification"] == RR)), None)


class Scheduler:
    """One trusted staged launch slot for the exact pair across all routes.

    A separate independent scheduler cannot bypass the child-owned flock.
    This local slot is not host-wide/cgroup resource containment.
    """
    def __init__(self, inventory, routes):
        try:
            require(type(inventory) is Spool and type(routes) is tuple
                    and 0 < len(routes) <= 3 and all(type(r) is Route and
                    type(r.policy) is ExecutionPolicy for r in routes),
                    "invalid scheduler bootstrap")
            self._inventory = inventory
            self._routes = {r.key(): r for r in routes}
            require(len(self._routes) == len(routes), "duplicate trusted route")
            shared = routes[0].pins
            for r in routes:
                p = r.pins
                require((p.spool, p.attempt, p.input, p.owner) ==
                        (shared.spool, shared.attempt, shared.input, shared.owner)
                        and inventory._path == p.spool.path and inventory.inode == p.spool.inode
                        and inventory._scope[:3] == (p.spool.store_id, p.attempt.store_id, p.input.store_id)
                        and inventory._cfg == r.config_json.encode("utf-8")
                        and inventory._quotas == r.quotas, "scheduler pair mismatch")
            self._lock = threading.Lock()
            self._supervisor = None
            self._invocation = None
        except Exception:
            raise SchedulingBlocked("scheduler bootstrap rejected") from None

    def _launch(self, role, incarnation, recovery):
        if not self._lock.acquire(blocking=False):
            raise Busy("pair scheduler busy")
        try:
            if self._supervisor is not None:
                with self._supervisor._admission:
                    if self._supervisor._active is not None:
                        raise Busy("pair scheduler busy")
                if self._invocation is not None and not self._invocation._done.is_set():
                    raise Busy("pair scheduler reaping")
                self._supervisor = self._invocation = None
            try:
                pending = first_pending(self._inventory.list_metadata())
                if recovery:
                    require(pending is not None, "no pending recovery")
                    route = self._routes.get((pending["role"], pending["incarnation"]))
                    require(route is not None, "pending role route unavailable")
                    identity = route.policy.identity()
                    require((pending["policy_id"], pending["policy_sha256"]) ==
                            (identity.policy_id, identity.sha256), "pending policy unavailable")
                    selected = (pending["request_id"], pending["version"])
                else:
                    require(pending is None, "pair recovery pending")
                    route = self._routes.get((role, incarnation))
                    require(route is not None, "ordinary route unavailable")
                    selected = None
                bootstrap = Bootstrap(route, selected)
                supervisor = Supervisor(route.launch_spec(recovery))
            except Exception:
                raise SchedulingBlocked("trusted scheduling blocked") from None
            self._supervisor = supervisor
            client, invocation = supervisor.start_coordinated(bootstrap)
            self._invocation = invocation
            return client, invocation
        finally:
            self._lock.release()

    def start_ordinary(self, role, incarnation):
        """Trusted route selection; worker receives only returned data endpoint."""
        require(type(role) is str and type(incarnation) is str, "invalid trusted route selector")
        return self._launch(role, incarnation, False)

    def recover_next(self):
        """No worker frame, caller selector, original, or resource override."""
        client, invocation = self._launch(None, None, True)
        require(client is None, "unexpected recovery endpoint")
        return invocation
