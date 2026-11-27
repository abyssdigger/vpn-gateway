"""9c-A pure deployment contract; never a live admission or authority evaluator."""
from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass

from core import Conflict, canonical, ident, require, strict_json
from split_journal import validate_v2_config
from v2_identity import validate_bindings

SCHEMA = "vpng-deployment-manifest/1"
MAX_BYTES = 1024 * 1024  # representation bound, not a deployment resource limit
OPS = frozenset(("material_comment", "control_comment", "aux_comment",
                 "initial_open", "issue_close", "issue_create"))
PATHS = frozenset(("model_tools", "network_clients", "git_credentials",
                   "workflows", "read_credential", "brokers", "other_writer",
                   "mutable_bootstrap", "descendants"))
COMMON = frozenset(("trusted_installation", "identity_binding", "store_continuity",
                    "read_only_provider", "recovery_isolation", "recovery_reserve",
                    "recovery_fence", "read_transport"))
NEW = frozenset(("write_custody", "exact_action_authority", "authority_lifetime",
                 "checkpoint", "aggregate_containment", "physical_headroom",
                 "ordinary_resources", "write_transport", "pair_mediation")) | PATHS
PREDICATES = COMMON | NEW
STORES = ("owner", "attempt", "input", "checkpoint", "spool")
LIFETIMES = ("bounded_irrevocable", "maintained_fence", "point_in_time_revocable")


def _shape(value, fields):
    require(type(value) is dict and set(value) == set(fields), "closed fields required")
    return value


def _id(value):
    return type(value) is str and ident(value)


def _hex(value, n=64):
    return type(value) is str and re.fullmatch("[0-9a-f]{%d}" % n, value) is not None


def _int(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**63-1


def _path(value):
    return (type(value) is str and 1 < len(value) <= 4096 and value.startswith("/")
            and not value.startswith("//") and "\0" not in value
            and posixpath.normpath(value) == value)


def _enum(*values):
    return lambda v: type(v) is str and v in values


def _ids(value):
    return (type(value) is list and 0 < len(value) <= 128 and all(_id(x) for x in value)
            and len(set(value)) == len(value))


def _groups(value):
    return (type(value) is list and len(value) <= 128 and all(_int(x) for x in value)
            and len(set(value)) == len(value))


def _wire(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "bounded canonical bytes required")
    try:
        obj = strict_json(raw.decode("utf-8"))
        require(canonical(obj).encode("utf-8") == raw, "noncanonical representation")
        return obj
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise Conflict("invalid canonical deployment data") from exc


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical_text(value):
    if type(value) is not str:
        return False
    try:
        _wire(value.encode("utf-8"))
        return True
    except (ValueError, UnicodeError):
        return False


# Each scalar is explicitly typed. None means unresolved ONLY in design mode.
FIELDS = {
    "trust": dict(deployment_root=_id, manifest_path=_path, evidence_registry_sha256=_hex),
    "identity": dict(repository=lambda v: type(v) is str and
                     re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", v) is not None
                     and all(x not in (".", "..") for x in v.split("/")),
                     epoch=_id, config_json=_canonical_text, bindings_json=_canonical_text),
    "environment": dict(runtime_id=_id, service_manager=_id, tool_context=_id),
    "installation": dict(commit=lambda v: _hex(v, 40), protocol=_enum("vpng-collab/2"),
                         executable_sha256=_hex, interpreter_sha256=_hex,
                         imports_sha256=_hex, config_sha256=_hex),
    "isolation": dict(worker_uid=lambda v: _int(v, 1), worker_gid=lambda v: _int(v, 1),
                      trusted_uid=lambda v: _int(v, 1), trusted_gid=lambda v: _int(v, 1),
                      worker_groups=_groups, trusted_groups=_groups,
                      capability_policy_sha256=_hex, fd_environment_policy_sha256=_hex,
                      cgroup_owner=_id, ordinary_unit=_id, recovery_unit=_id),
    "credentials": dict(read_principal=_id, read_provider=_id, read_source=_id,
                        read_scope=_id, write_principal=_id, write_provider=_id,
                        write_source=_id, write_scope=_id),
    "authority": dict(source=_id, lifetime=_enum(*LIFETIMES), lifetime_policy_sha256=_hex,
                      owner_fence_policy_sha256=_hex),
    "transport": dict(read_adapter_sha256=_hex, write_adapter_sha256=_hex,
                      destination_policy_sha256=_hex, egress_policy_sha256=_hex,
                      kind=_enum("reviewed_external", "synthetic")),
    "resources": dict(pair_quota_sha256=_hex, ordinary_policy_sha256=_hex,
                      recovery_policy_sha256=_hex, aggregate_policy_sha256=_hex,
                      physical_reserve_policy_sha256=_hex, recovery_owner=_id),
    "continuity": dict(installation_id=_id, occupancy_policy_sha256=_hex,
                       rollback_policy_sha256=_hex, restart_policy_sha256=_hex),
    "recovery": dict(selector_policy_sha256=_hex, routing_policy_sha256=_hex,
                     escalation_owner=_id, reserve_owner=_id),
}
PIN = dict(store_id=_id, path=_path, device=_int, inode=lambda v: _int(v, 1),
           owner_uid=lambda v: _int(v, 1), mode=_enum("0600"), kind=_enum("regular-single-link"))
TOP = set(FIELDS) | {"schema", "mode", "revision", "stores", "targets", "alternate_paths", "evidence"}


def _fields(row, spec, prefix, unresolved):
    _shape(row, spec)
    for name, check in spec.items():
        value = row[name]
        if value is None:
            unresolved.append(prefix + "." + name)
        else:
            require(check(value), "invalid field: " + prefix + "." + name)


def _manifest(raw):
    m = _shape(_wire(raw), TOP)
    require(m["schema"] == SCHEMA and _enum("design", "deployment")(m["mode"])
            and _id(m["revision"]), "invalid manifest identity")
    unresolved = []
    for section, spec in FIELDS.items():
        _fields(m[section], spec, section, unresolved)
    identity = m["identity"]
    cfg = None
    if identity["config_json"] is not None:
        cfg = validate_v2_config(_wire(identity["config_json"].encode("utf-8")))
        require(identity["repository"] in (None, cfg["repository"])
                and identity["epoch"] in (None, cfg["journal_epoch"]), "configuration scope mismatch")
        require(m["installation"]["config_sha256"] in
                (None, _hash(identity["config_json"].encode("utf-8"))), "configuration digest mismatch")
    if identity["bindings_json"] is not None:
        bindings = validate_bindings(_wire(identity["bindings_json"].encode("utf-8")))
        if cfg is not None:
            admitted = {(p["transport_role"], p["incarnation"])
                        for b in bindings["bindings"] if b["status"] == "admitted"
                        for p in b["transport_pairs"]}
            require(all((role, row["incarnation"]) in admitted
                        for role, row in cfg["roles"].items()), "unadmitted configured role")
    iso = m["isolation"]
    for a, b in (("worker_uid", "trusted_uid"), ("worker_gid", "trusted_gid"),
                 ("ordinary_unit", "recovery_unit")):
        require(iso[a] is None or iso[b] is None or iso[a] != iso[b], "isolation identity alias")
    if iso["worker_groups"] is not None and iso["trusted_gid"] is not None:
        require(iso["trusted_gid"] not in iso["worker_groups"], "worker inherits trusted group")
    creds = m["credentials"]
    for a, b in (("read_source", "write_source"), ("read_principal", "write_principal")):
        require(creds[a] is None or creds[b] is None or creds[a] != creds[b], "credential custody alias")
    stores = _shape(m["stores"], STORES)
    ids, paths, inodes = set(), set(), set()
    for name, pin in stores.items():
        _fields(pin, PIN, "stores." + name, unresolved)
        for key, seen in (("store_id", ids), ("path", paths)):
            if pin[key] is not None:
                require(pin[key] not in seen, "store alias")
                seen.add(pin[key])
        if pin["device"] is not None and pin["inode"] is not None:
            p = (pin["device"], pin["inode"])
            require(p not in inodes, "physical store alias")
            inodes.add(p)
        if pin["owner_uid"] is not None and iso["trusted_uid"] is not None:
            require(pin["owner_uid"] == iso["trusted_uid"], "store owner mismatch")
    targets = m["targets"]
    if targets is None:
        unresolved.append("targets")
    else:
        require(type(targets) is list and 0 < len(targets) <= 1024, "invalid target inventory")
        seen = set()
        for row in targets:
            _shape(row, ("role", "incarnation", "actor_id", "operation", "room"))
            require(_enum("SPEC", "GUARD", "BUILDER")(row["role"])
                    and _id(row["incarnation"]) and _int(row["actor_id"], 1)
                    and type(row["operation"]) is str and row["operation"] in OPS
                    and (row["room"] is None if row["operation"] == "issue_create"
                         else _int(row["room"], 1)), "invalid target")
            if cfg is not None:
                role = cfg["roles"][row["role"]]
                require((row["incarnation"], row["actor_id"]) ==
                        (role["incarnation"], role["actor_id"]), "target identity mismatch")
            key = (row["role"], row["operation"], row["room"])
            require(key not in seen, "duplicate target")
            seen.add(key)
    paths = _shape(m["alternate_paths"], PATHS)
    for path, value in paths.items():
        if value is None:
            unresolved.append("alternate_paths." + path)
        else:
            require(_enum("excluded", "mediated", "not_applicable", "present")(value),
                    "unknown path disposition")
    evidence = _shape(m["evidence"], PREDICATES)
    seen = set()
    for predicate, ref in evidence.items():
        if ref is None:
            unresolved.append("evidence." + predicate)
        else:
            require(_id(ref) and ref not in seen, "invalid or duplicate evidence reference")
            seen.add(ref)
    require(m["mode"] == "design" or not unresolved, "unresolved deployment binding")
    return m, tuple(sorted(unresolved))


@dataclass(frozen=True, slots=True)
class ContractReport:
    manifest_sha256: str
    unresolved: tuple[str, ...]
    new_effect_blockers: tuple[str, ...]
    recovery_only_blockers: tuple[str, ...]
    # Deliberately no success/authority token, regardless of supplied observations.


def inspect_contract(raw, *, expected_root=None, observations=None, now=None):
    """Pure consistency check. Inputs besides raw must come from a trusted caller.

    expected_root is external to the manifest. Observations are claims supplied
    by that caller, NOT authenticated or collected here. An empty blocker list
    means only that the supplied contract inputs are structurally consistent
    for that lane, NEVER live admission, proof of enforcement or send authority.
    """
    m, unresolved = _manifest(raw)
    sha = _hash(raw)
    common = set()
    new = set()
    if m["mode"] == "design":
        common.add("design_only")
    if unresolved:
        common.add("unresolved_bindings")
    registry = None
    if expected_root is None:
        common.add("external_root_missing")
    else:
        root = _shape(_wire(expected_root), ("deployment_root", "manifest_path",
                      "revision", "manifest_sha256", "registry"))
        require(_id(root["deployment_root"]) and _path(root["manifest_path"])
                and _id(root["revision"]) and _hex(root["manifest_sha256"]), "invalid external root")
        registry = _shape(root["registry"], PREDICATES)
        for entry in registry.values():
            _shape(entry, ("observer", "adapter_sha256", "anchor_sha256"))
            require(_id(entry["observer"]) and _hex(entry["adapter_sha256"])
                    and _hex(entry["anchor_sha256"]), "invalid evidence trust entry")
        trust = m["trust"]
        if (root["deployment_root"], root["manifest_path"], root["revision"],
            root["manifest_sha256"], _hash(canonical(registry).encode("utf-8"))) != (
                trust["deployment_root"], trust["manifest_path"], m["revision"],
                sha, trust["evidence_registry_sha256"]):
            common.add("external_root_mismatch")
    claims = {}
    if observations is not None:
        obs = _wire(observations)
        require(type(obs) is list and len(obs) <= len(PREDICATES), "invalid observation set")
        require(_int(now), "external observation time required")
        for row in obs:
            _shape(row, ("predicate", "ref", "manifest_sha256", "observer",
                         "adapter_sha256", "anchor_sha256", "method", "observation_sha256",
                         "not_before", "not_after", "status"))
            p = row["predicate"]
            require(type(p) is str and p in PREDICATES and p not in claims
                    and _id(row["ref"]) and _hex(row["manifest_sha256"])
                    and _id(row["observer"]) and _hex(row["adapter_sha256"])
                    and _hex(row["anchor_sha256"]) and _id(row["method"])
                    and _hex(row["observation_sha256"]) and _int(row["not_before"])
                    and _int(row["not_after"]) and row["not_before"] < row["not_after"]
                    and _enum("PASS", "FAIL", "UNKNOWN")(row["status"]), "invalid observation")
            claims[p] = row
    for p in PREDICATES:
        row = claims.get(p)
        entry = registry[p] if registry is not None else None
        if not (row is not None and entry is not None and
                row["ref"] == m["evidence"][p] and row["manifest_sha256"] == sha
                and all(row[k] == entry[k] for k in entry)
                and row["not_before"] <= now < row["not_after"] and row["status"] == "PASS"):
            (common if p in COMMON else new).add("evidence:" + p)
    for path, disposition in m["alternate_paths"].items():
        if disposition not in ("excluded", "mediated", "not_applicable"):
            new.add("alternate_path:" + path)
            # These paths contradict common trust premises even for read-only recovery.
            if path in ("read_credential", "mutable_bootstrap"):
                common.add("alternate_path:" + path)
    if m["authority"]["lifetime"] not in ("bounded_irrevocable", "maintained_fence"):
        new.add("authority_lifetime")
    if m["transport"]["kind"] != "reviewed_external":
        common.add("synthetic_or_unbound_transport")
    # Current write availability, checkpoint freshness and exact action/owner
    # checks remain in trusted runtime; evidence here cannot replace them.
    return ContractReport(sha, unresolved, tuple(sorted(common | new)), tuple(sorted(common)))
