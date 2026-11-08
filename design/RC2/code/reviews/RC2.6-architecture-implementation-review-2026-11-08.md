# Independent technical review — RC2.6 implementation/data-model feasibility

**Date:** 2026-11-08  
**Reviewed commit:** `00c1bcd52f167ab3f77934d84fcf62a66c6713fc`  
**Scope:** typed model, config validation, kernel adapter, testability, Python package split  
**Current implementation baseline:** RC2.5.1

## Summary

RC2.6 can be implemented cleanly, but it is not a small patch over RC2.5.1.

The important architectural decision is correct: `interface = "vpns%"` is a selector only;
all kernel resources use a resolved exact interface.

A focused internal refactor should precede or accompany behavior changes. Splitting the
Python implementation into a small package is justified at the current code size.

## I1 — HIGH: introduce an explicit desired snapshot object

RC2.5.1 currently passes several parallel structures:

- config/profiles;
- interface-address mapping;
- desired routes;
- implicit firewall model.

RC2.6 adds:

- selector resolution;
- concrete name + ifindex binding;
- readiness;
- dynamic firewall/NAT desired state.

Passing these independently risks mixing snapshots from different observations.

### Recommendation

Create one immutable daemon-level pass object, conceptually:

```text
ReconciliationSnapshot
    interfaces
    resolutions_by_profile
    readiness_by_profile
    desired_routes_by_profile
    desired_policy
```

Exact class names are implementation-level.

The object should be built once from one interface snapshot + immutable config and reused
through policy build/apply/verify and route build/apply/verify.

This does **not** claim atomic kernel inventory across separate syscalls; it only prevents the
daemon from accidentally recomputing selector resolution mid-pass.

---

## I2 — HIGH: retire full CONFIGURED RouteSpec generation

Current RC2.5.1 `VpnProfile._configured_routes()` creates UNICAST RouteSpec using
`config.interface`.

That cannot survive RC2.6 because a family selector is not a kernel ifname.

The architecture correctly moves desired route construction to daemon + binding snapshot.

### Recommendation

Do not create a fake `RouteSpec(interface="vpns%")` and later rewrite it.

Keep:

- immutable profile config;
- helper for config-only BLACKHOLE templates/specs if useful;
- process-local OWNED routes.

Build UNICAST RouteSpec only after a concrete ready binding exists.

The existing `ProfileResourceSet.CONFIGURED` abstraction should be removed or narrowed
rather than preserved artificially.

---

## I3 — MEDIUM: selector intersection needs a precise pure function

Managed interface conflict validation is no longer string equality.

For:

```text
EXACT(a)
FAMILY(prefix)
```

the validator should have one pure/testable predicate:

```text
selectors_overlap(left, right) -> bool
```

Required cases include:

- exact/exact equality;
- exact/family: exact matches `^prefix[0-9]+$`;
- family/family:
  - same prefix;
  - one prefix extends the other only by digits, allowing a common concrete name;
  - respect the 15-character maximum.

Examples:

```text
vpns%  vs vpns0   -> conflict
vpns%  vs vpns1%  -> conflict (vpns10, ...)
vpns1% vs vpns2%  -> no conflict
vpns%  vs VPNS%   -> no conflict under case-sensitive Linux ifnames
```

This function should be used both runtime validation and offline lint to avoid two semantic
implementations.

---

## I4 — MEDIUM: interface inventory should reject inconsistent duplicate identities

RC2.5.1 `list_interface_ipv4()` merges duplicate records by interface name.

RC2.6 binding identity includes ifindex.

The new parser should preserve:

```text
name
ifindex
IPv4 set
```

If one inventory payload presents the same name with conflicting ifindex values, silently
merging would destroy the identity guarantee.

### Recommendation

Merge duplicate records only if identity is consistent; otherwise `KernelError`.

Continue using only `family == "inet"` and `local` for readiness addresses.

---

## I5 — MEDIUM: filtered cleanup parser must remain strict inside the marker namespace

EXP-004.5 justifies filtering unrelated foreign routes out of cleanup.

It does **not** justify silently ignoring an unsupported route that itself carries the
reserved daemon protocol marker.

Example:

```text
proto 202 + nexthops[]
```

If such a route exists, cleanup cannot safely prove ownership/materialize exact deletion with
the current RouteSpec model.

### Recommendation

`list_routes_by_proto(201/202)` remains strict for every returned selected entry.
Unsupported shape under a reserved marker -> CleanupError/KernelError, not skip.

For `proto 201`, delete only BLACKHOLE + metric 65536; other proto-201 shapes are marker
conflicts and should fail cleanup rather than be silently adopted/deleted.

---

## I6 — MEDIUM: secure runtime-directory creation should validate the opened directory

A simple:

```python
if not exists:
    mkdir(...)
lstat(...)
```

has avoidable pathname races.

`/run` itself is a trusted root-owned parent, so the implementation need not become a
general secure-path framework, but it can stay simple and robust.

### Recommendation

Implementation direction:

1. try `mkdir("/run/vpn-gateway", 0o700)`;
2. on EEXIST continue;
3. open final directory with `O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`;
4. `fstat` the opened object for directory/owner/mode;
5. open lock relative to that dirfd if practical, also `O_NOFOLLOW`.

This mirrors the project's config-file “validate opened object” security style.

Do not auto-chmod/chown an unexpected existing directory.

---

## I7 — MEDIUM: package split is justified, but split by policy boundary

The current file size is already large enough that RC2.6's new model will be easier to audit
as a small package.

Recommended rough boundaries:

```text
vpn_gateway/
    config.py      # TOML, selectors, validation/lint
    model.py       # immutable enums/dataclasses
    kernel.py      # subprocess/procfs/netlink physical boundary
    policy.py      # desired firewall/NAT + route derivation, pure helpers
    daemon.py      # lifecycle, reconciliation, state machine
vpn-gatewayd       # thin CLI/entry point
```

This is a recommendation, not a required exact file layout.

Avoid splitting tiny helper modules or creating import cycles. Domain model should remain
dependency-light and policy helpers should be as pure as possible.

This layout maps naturally to future Rust modules while deployment still exposes one
executable command.

---

## I8 — MEDIUM: policy builder should have an explicit deny-only form

The safety review identifies a cross-table ordering issue when forwarding cannot be disabled.

From an implementation perspective this is easiest if the policy layer can derive both:

```text
desired_full_policy(snapshot)
desired_isolation_policy(snapshot/config)
```

The isolation policy should contain no binding-specific forwarding ACCEPT and no permissive
selector wildcard. It should retain:

- INPUT guards;
- transport-network rejects;
- protected-destination rejects;
- final global FORWARD deny.

This makes deny-first repair testable as a pure policy transformation rather than ad-hoc rule
surgery in orchestration code.

---

## I9 — LOW: status needs binding/readiness fields

Because daemon ACTIVE can coexist with an absent VPN interface by design, status should expose
per profile at least:

```text
selector
binding: <ifname/ifindex> | absent | ambiguous
ready: yes/no
route result
```

This is operationally important but not an implementation blocker.

---

## I10 — TEST MATRIX required before live RC2.6

Minimum new unit coverage:

### Config/selectors

- exact valid/invalid names;
- family valid/invalid sentinel placement;
- 14-character prefix + one digit boundary;
- exact/family overlap;
- family/family overlap/non-overlap;
- unmanaged overlap warning.

### Binding

- zero/one/multiple matches;
- exact selector;
- family selector;
- same name new ifindex;
- local address missing/present;
- inconsistent duplicate ifindex inventory.

### Desired policy

- absent -> no exact allow/NAT;
- ready -> exact ifname in all allow/NAT rules;
- ambiguous -> no exact allow/NAT;
- selector sentinel never appears in materialized policy;
- protected REJECT and terminal FORWARD deny always present;
- deny-only isolation policy has no forwarding ACCEPT.

### Routes

- blackhole config-only;
- unicast uses concrete binding;
- rebind vpns0 -> vpns1 changes RouteSpec.interface;
- no binding/ambiguous removes desired proto202;
- marker-selective cleanup protocol context.

### Lifecycle

- binding change isolates before policy mutation;
- inability to disable forwarding follows deny-first repair;
- interface inventory failure -> ISOLATED;
- policy verify before route restore;
- OWNED/binding commit after verify and before forwarding enable.

### Runtime directory

- absent -> create 0700;
- existing correct -> accept;
- symlink/non-directory/wrong owner/wrong mode -> fatal;
- busy lock -> explicit instance error.

## Overall verdict

RC2.6 is implementable and the proposed package split is appropriate.

Before coding, incorporate the safety review's deny-first cross-table repair and explicit
interface-inventory failure semantics. After that, a staged refactor/implementation is
preferable to trying to patch RC2.5.1 in place without new typed boundaries.
