# NG2 — runtime lower assembly whole-code audit

**Дата:** 2026-11-14  
**Тип:** autonomous whole-code / architecture audit  
**Scope:** Linux instance lifecycle, namespace prerequisites, protective bootstrap and
NetworkRulesAdapter publication boundary

## Audit criteria

Проверены:

- неиспользуемые artifacts и parallel abstractions;
- скрытая зависимость от истории вызовов;
- safety ordering startup/restart/failure paths;
- дублирование технических контрактов;
- ownership между lifecycle/bootstrap/Driver/Adapter;
- соответствие закрытому NG1 evidence без переноса старой architecture;
- exact verification claimed by docs vs code;
- production path vs test-only path;
- Python implementation assumptions that should remain explicit before Rust migration.

## Findings

### W1 — loopback ownership was documented but not verified

**Severity:** correctness/documentation drift  
**Disposition:** fixed.

Instance lifecycle creates and owns namespace loopback UP state, but initial verifier only
checked host veth, `host0`, addresses and default route.

`verify_linux_instance()` now requires `lo` to exist and be UP.

### W2 — LinuxInstanceSpec type hints did not enforce IPv4 at runtime

**Severity:** contract correctness  
**Disposition:** fixed.

Direct Python construction could pass `IPv6Interface` despite an IPv4-only schema/backend.

Runtime validation now rejects non-`IPv4Interface` host/inner addresses. Unit regression
covers direct IPv6 objects.

### W3 — namespace prerequisite contract existed in three manually synchronized forms

**Severity:** maintainability / verification drift  
**Disposition:** fixed.

Expected diagnostic keys, observation commands and mutation commands were initially
separate hand-written lists.

They now derive from one canonical internal tuple:

```text
(diagnostic_key, slash_safe_sysctl_path, expected_value)
```

This preserves slash-form interface safety while preventing read/write/verify drift.

### W4 — optional host runner used truthiness instead of explicit absence

**Severity:** API correctness  
**Disposition:** fixed.

`host_runner or SubprocessLinuxRunner()` could discard an intentionally falsey runner.
Assembly now tests `host_runner is not None`.

### W5 — safety-sensitive startup ordering leaked to outer callers

**Severity:** architecture / misuse resistance  
**Disposition:** fixed.

Before this audit a production caller had to remember:

```text
ensure_linux_instance()
bootstrap_linux_network_rules_adapter_in_namespace()
```

in that order.

Added:

```text
bootstrap_linux_network_rules_adapter_for_instance(spec)
```

which:

1. ensures absent/present instance infrastructure in fail-closed form;
2. independently repeats protective namespace forwarding close/verification;
3. exposes `LinuxNetworkRulesAdapter` only after both stages succeed.

Any infrastructure failure returns a failed bootstrap result with no Adapter.

The repeated protective close is retained intentionally. It removes hidden call-history
coupling between the lifecycle and Adapter-publication boundaries.

### W6 — no second namespace lifecycle abstraction is justified

**Severity:** abstraction review  
**Disposition:** retained.

`NetworkNamespaceLinuxRunner` scopes commands only.

`linux_instance.py` owns namespace/veth infrastructure lifecycle.

`runtime_bootstrap.py` composes them.

Merging these would make the command Driver responsible for lifecycle policy; introducing
another generic NamespaceManager would duplicate a single concrete responsibility without a
second domain consumer.

### W7 — broad startup exception conversion is intentional at the publication gate

**Severity:** failure-semantics review  
**Disposition:** retained.

The full-instance bootstrap converts any exception from infrastructure ensure into:

```text
FAILURE(diagnostic), adapter=None
```

At this boundary the relevant contract is whether a usable Adapter may escape. Parser,
runner, verification and lifecycle failures all mean it may not.

Lower layers retain typed exceptions for diagnostics/tests. The bootstrap does not claim a
semantic runtime state from the exception.

### W8 — no policy materialization leaked back into instance lifecycle

**Severity:** cross-domain regression audit  
**Disposition:** PASS.

Unlike NG1 lifecycle, NG2 instance creation does not create nft tables or payload routes.
The privileged fresh-start composition proves Adapter can be published with no nft policy
before any owner reconcile.

Thus infrastructure readiness is not confused with payload-policy readiness.

### W9 — NG1 safety evidence was reused selectively rather than copied structurally

**Severity:** migration audit  
**Disposition:** PASS.

Recovered NG1 facts retained in NG2:

- explicit namespace/veth topology;
- `rp_filter=0` prerequisite;
- IPv6 containment for the IPv4-only backend;
- restart fail-closed behavior;
- refusal to guess/adopt partial infrastructure.

Not retained:

- NG1 DeviceBindingSnapshot;
- NG1 EnvironmentSnapshot;
- NG1 nft bootstrap ownership;
- old planner/device-engine architecture.

This is evidence continuity, not architecture rollback.

## Production startup path after audit

```text
LinuxInstanceSpec
    |
    v
bootstrap_linux_network_rules_adapter_for_instance
    |
    +--> ensure_linux_instance
    |       |
    |       +--> absent -> create infrastructure -> exact verify
    |       |
    |       +--> present -> protective dual-stack close -> exact verify
    |
    +--> namespace bootstrap
            |
            +--> independent protective dual-stack close + fresh verify
            |
            v
      LinuxNetworkRulesAdapter
            |
            v
      first owner reconcile
            |
            +--> namespace prerequisites
            +--> routes/RPDB/nft
            +--> closed-state verification
            +--> IPv4 forwarding open only if desired and verified
```

No stage before first owner reconcile invents payload policy.

## Evidence

Relevant green implementation gates include:

- `c8dbbfe8fb8eb8d7c7af3a5feed40255988aa616` — dual-stack protective bootstrap
  post-fix: NG2 + NG1 PASS;
- `6e6406336887fc972445065b0982429d3d705ae7` — exact live veth peer verification:
  NG2 unit + privileged Linux integration PASS;
- `e1afbb8b4622be9f16c4b9c1dd1787a3471a4fad` — unified prerequisite contract:
  NG2 + NG1 PASS;
- `825e50e08d8baf59bbebd5525bd76c8f913b8186` — full startup composition helper:
  NG2 + NG1 PASS;
- `b22ddc896ecd94b2cad92983c1b0693bcfd4bbfa` — privileged absent-instance ->
  full bootstrap -> Adapter publication integration: NG2 + NG1 PASS.

The privileged path uses disposable Linux namespaces and the production namespace command
runner.

## Final verdict

**PASS.**

No unresolved safety or architecture finding blocks the runtime lower assembly baseline.

The next implementation boundary is above this baseline. Candidate work must have a real
consumer; do not add speculative Event Delivery, config parsers or scheduler abstractions
merely to fill the runtime layer.
