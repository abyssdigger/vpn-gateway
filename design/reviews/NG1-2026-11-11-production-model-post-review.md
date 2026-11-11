# NG1 — post-fix production-model architecture review

Date: **2026-11-11**

Scope: second consistency pass after
`NG1-2026-11-11-production-model-review.md` and its response.

## Verification of first-pass findings

| Finding | Result |
|---|---|
| A1 disabled Device vs metric allocation | CLOSED |
| A2 /0 vs terminal blackhole metric | CLOSED |
| A3 UNKNOWN availability semantics | CLOSED |
| A4 Profile identity | CLOSED |
| A5 publication notation ambiguity | CLOSED |
| A6 duplicate rou down step | CLOSED |

## Cross-document consistency checks

### Active Device projection

PASS.

The architecture and TOML contract now agree:

- a disabled Device may be a minimal placeholder;
- an enabled Profile may reference it;
- it consumes no current metric range;
- only enabled Devices required by enabled Profiles are active for DeviceEngine discovery,
  publication and current metric allocation.

### Expected-interface hierarchy

PASS.

The domain and TOML surface agree on:

```text
Profile.device_order[]
    -> Device.expected_interfaces[]
        -> stable runtime slot
```

EXACT has quota 1. PREFIX has explicit positive quota. Aggregate Device quota is derived.

### Availability and failover

PASS with one explicit experimental gate.

UNKNOWN and AVAILABLE remain in the normal tier. Only positive UNAVAILABLE classification
is demoted.

The priority contract is:

```text
normal < UNAVAILABLE_METRIC < BLACKHOLE_METRIC
```

which is sufficient for Profiles containing `0.0.0.0/0`.

The actual direct-dev multipath kernel materialization at UNAVAILABLE_METRIC is still
correctly marked as pending live verification.

### Configuration identity and placeholders

PASS.

`[device.<id>]` and `[profile.<id>]` map to stable domain identities. `enabled` is
always explicit. Disabled entities may remain intentionally incomplete.

### Publication syntax boundary

PASS.

The old port-mapping notation is now explicitly conceptual. Human-facing TOML publication
syntax remains intentionally unresolved in `rou-config.md`.

### Historical vocabulary boundary

PASS.

No normative pre-v0 section uses BindingSpec or the old one-selector
`interface_match` model. Binding remains only where it describes the current
Device-to-ROU relationship. Old BindingSpec/capacity wording in §20 is historical
ROU-v0 evidence.

## Non-blocking implementation notes

1. Centralize Linux interface-name/prefix lexical validation in the config/domain boundary;
   the new TOML document intentionally does not yet freeze a more restrictive grammar than
   the accepted EXACT/PREFIX surface.
2. Do not implement the unresolved publication or traffic-envelope TOML syntax by
   assumption.
3. Keep the unavailable multipath projector behind tests/experimental gating until the
   dedicated live experiment closes it.

## Verdict

**PASS — architecture/config baseline is coherent for implementation to begin.**

No architecture blocker remains from this review cycle.
