# NG2 — Linux instance infrastructure lifecycle review

**Дата:** 2026-11-14  
**Тип:** autonomous migration/focused implementation review  
**Scope:** namespace + veth infrastructure lifecycle below runtime bootstrap

## Review criteria

Проверялись:

- сохранение уже принятого instance schema/topology без user-visible redesign;
- отделение infrastructure ownership от NetworkRulesAdapter policy ownership;
- fail-closed restart semantics;
- partial/stale ownership ambiguity;
- exact veth/address/default-route verification;
- teardown containment;
- отсутствие NG1 planner/nft bootstrap leakage;
- privileged disposable-kernel evidence.

## Findings

### I1 — NG1 topology can be retained without retaining NG1 policy machinery

**Severity:** migration architecture  
**Disposition:** implemented.

NG2 сохраняет schema-v1 infrastructure topology:

```text
host <host_interface>/<host_address>
       <---- veth ---->
ROU namespace host0/<inner_address>
default via <host_address>
```

Новый `linux_instance.py` не импортирует NG1 Device/Profile/planner state.

No user-visible instance configuration change is introduced by this unit.

### I2 — instance lifecycle must not create bootstrap nft policy

**Severity:** ownership boundary  
**Disposition:** implemented and live-tested.

NG1 lifecycle создавал bootstrap nft tables сам. В NG2 это противоречило бы exclusive
network-policy ownership нового `LinuxNetworkRulesAdapter`.

Fresh NG2 instance therefore creates only namespace/veth/address/main-route infrastructure.
Live gate proves no nft table record exists after fresh creation.

First owner reconcile remains the first network-policy materialization.

### I3 — existing namespace must be contained before structural inspection

**Severity:** safety  
**Disposition:** implemented.

`ensure_linux_instance()` detects namespace presence and first executes the same
`LinuxNetworkDriver.close_forwarding_verified()` used by runtime bootstrap.

Thus stale existing instance is dual-stack contained before exact infrastructure
verification.

Partial state with namespace present is also protectively closed before FAILURE is
returned.

### I4 — partial or structurally divergent infrastructure must not be guessed/repaired

**Severity:** ownership/correctness  
**Disposition:** implemented and live-tested.

Only two start states are accepted:

- namespace + host veth both absent -> fresh create;
- namespace + host veth both present -> close + verify.

XOR presence is FAILURE.

For an existing complete instance, missing address/default route/wrong link type/etc. causes
FAILURE; lifecycle does not silently repair or adopt it. Live gate deletes the namespace
default route and proves `ensure` fails while forwarding remains closed.

### I5 — names/types/addresses alone do not prove the expected veth pair

**Severity:** ownership/correctness  
**Disposition:** fixed during review.

A host veth with the configured name and an unrelated namespace veth named `host0` could
otherwise satisfy independent type/address checks.

Current iproute2 JSON exposes cross-namespace veth peer index as `link_index`. Verification
now requires reciprocal:

```text
host.link_index == host0.ifindex
host0.link_index == host.ifindex
```

No persisted peer history is introduced.

### I6 — teardown is infrastructure cleanup, not semantic Adapter cleanup

**Severity:** boundary clarity  
**Disposition:** retained.

Destroy best-effort closes namespace forwarding, deletes namespace and surviving host veth,
then freshly verifies absence.

Normal runtime should still release Manager/Adapter state first when possible. Crash/stop
containment is allowed to close forwarding without semantic cleanup.

### I7 — first live harness falsely treated nft JSON metainfo as a table

**Severity:** test harness  
**Disposition:** fixed.

`nft -j list tables` may include non-table metadata records. The initial gate tested list
non-emptiness and failed despite no policy table.

The gate now filters only records containing `table`.

## Evidence

Unit suite covers instance-spec validation including /31 and unsafe identifiers.

Privileged instance lifecycle gate covers:

1. fresh create + exact verification;
2. absence of lifecycle-created nft policy;
3. restart from deliberately enabled IPv4/IPv6 forwarding -> protective close;
4. structural default-route drift -> fail-closed FAILURE without implicit repair;
5. verified destroy;
6. partial-state rejection.

Final peer-identity implementation is additionally exercised by fresh live verification.

## Final verdict

**PASS.**

Post-fix `6e6406336887fc972445065b0982429d3d705ae7` passed the complete NG2 unit and
privileged Linux integration workflow, including reciprocal live veth peer verification.

No architecture decision remains unresolved in this review unit.
