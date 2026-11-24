# NG3-2026-11-21 VPNPathAdapter addendum review

## Scope

Reviewed commit: `ad885bc29e188a4b92ac644a2e2ec9709f5b61e0`.

Sources:

- `design/NG3/architecture.md` VPNPathAdapter section;
- `design/NG3/code/python/rou/linux_vpn_path_adapter.py`;
- `design/component-model.md` Adapter boundary.

## Checks

### Boundary

The addendum preserves the accepted boundary: logical VPN-path semantics are mapped to
already-provisioned concrete endpoints. The Adapter observes/verifies lower facts and does
not create VPN sessions or own protocol credentials/configuration.

**Decision:** accepted.  
**Resolution:** no change required.

### Fresh observation

The addendum preserves the source rule that every authoritative observation is fresh and a
timer is only a wakeup mechanism. Command/parse failure is not converted into an empty
inventory.

**Decision:** accepted.  
**Resolution:** no change required.

### Endpoint generation identity

Exact current endpoint identity remains tied to concrete interface generation
`(ifname, ifindex)`; same-name replacement is not silently adopted and a replacement
becomes current only after fresh observation/verification.

**Decision:** accepted.  
**Resolution:** no change required.

### Policy separation

The Adapter does not acquire Profile policy, Device preference, payload eligibility,
availability health or human-grammar ownership.

**Decision:** accepted.  
**Resolution:** no change required.

### Optional provenance

Optional transport provenance remains bound to the exact current PathBinding and may be
absent/unresolved. The addendum does not infer it from generic interface/route facts.

**Decision:** accepted.  
**Resolution:** no change required.

### F1 — route gateway/onlink realization ownership remains unresolved

The flat architecture requires an integration-specific verified route realization in
addition to PathBinding, while also forbidding NetworkPolicyAdapter from guessing it.
The current structured tree does not yet prove whether this is:

- another VPNPathAdapter method;
- a child integration-realization component;
- or a contract belonging to a transition/VPN-end Space.

**Decision:** accepted.  
**Resolution:** deferred. Re-entry condition: first structured decomposition of the VPN
integration/transition path. The current addendum explicitly records the gap instead of
assigning it by implementation proximity.

## Verdict

**PASS with F1 deferred.**

The bounded VPNPathAdapter spec is internally coherent and does not require resolution of the
separate route-realization ownership question.
