# NG3 config-driven managed Device presence research review — 2026-11-25

**Review unit:** replace the accidentally explored traffic-driven Device-demand frontier with
the clarified configuration-driven warm-presence model  
**Reviewed research:** `design/NG3/research/NG3-2026-11-25-config-driven-managed-device-presence.md`  
**Reviewed source:** `e62bafe792c8511acef158b813f8d9148d22cb64`  
**Current normative basis:** `VPNG-U001-R1.R3.R7*`; A.012, C.004, D.001

## Scope

Review whether the research faithfully represents the clarified product need without importing
payload wake/sleep semantics, violating the existing availability boundary, creating a second
Device lifecycle owner, or silently selecting a user-facing configuration spelling.

## Findings and dispositions

### F1 — the active need is configuration-driven warm presence, not traffic wake

**Decision:** accepted.  
**Resolution:** fixed.

The clarified product need is a Profile policy describing how many VPN paths/endpoints should
be kept present. Payload traffic, first-packet arrival and idle time are not inputs to that
policy.

The separate traffic-driven research remains technically valid as optional future work and is
correctly indexed in `design/future-possibilities.md`.

### F2 — `0 | N | all` is the correct behavior-level value domain

**Decision:** accepted.  
**Resolution:** fixed.

The three semantic cases cover the stated product need:

- `0` — this Profile creates no managed-presence demand;
- positive `N` — keep a bounded number of current paths/endpoints available;
- `all` — preserve the existing behavior where every enabled managed Device membership is
  demanded.

Treating omission as `all` preserves the existing R7.R3 behavior for configurations that do
not opt into the new policy. The exact TOML field name remains intentionally undecided.

### F3 — warm satisfaction is endpoint presence, not availability health

**Decision:** accepted.  
**Resolution:** fixed.

A current endpoint from an allowed enabled Device membership contributes to the warm count
regardless of whether the Device is externally prepared or explicitly managed. Ownership only
controls actuation: A.012/D.001 may create/remove managed Devices and must not adopt an external
one.

A.007 availability and D.002 peer/group health remain separate. Negative remote evidence may
change effective priority but must not silently increase lifecycle demand while the underlying
endpoint still exists.

### F4 — deficit filling is bounded and deterministic

**Decision:** accepted.  
**Resolution:** fixed.

When current endpoint count is below a numeric target, managed demand is filled according to
the existing Profile/Device baseline hierarchy. A single projection need only request the
minimum additional configured capacity required for the current deficit; it must not interpret
zero current endpoints as a request to start every managed Device.

After a lifecycle attempt, a fresh cycle can expand demand if the expected endpoint did not
materialize. A failed preferred candidate therefore does not permanently consume the only
warm slot while a lower candidate could satisfy the Profile.

### F5 — the target is cardinality, not proactive identity restoration

**Decision:** accepted.  
**Resolution:** fixed.

Already present eligible endpoints satisfy the numeric target. A sleeping higher-baseline
managed Device is not started solely to replace an already present lower-baseline endpoint
when the target is otherwise satisfied.

This is consistent with the existing survivor-preserving binding model and ordinary-path
stickiness: configuration determines the required warm cardinality, while `device_order`
deterministically fills a deficit and orders surplus removal. It does not create a new
failback mechanism.

A surplus managed Device may become no longer demanded, but actual deletion remains behind the
existing A.012 dependency-release gate. No lifecycle decision may manufacture permission to
break current product-owned payload/return state.

### F6 — shared Device demand aggregates across Profiles

**Decision:** accepted.  
**Resolution:** fixed.

A Device is one lifecycle object. Per-Profile demand must therefore be OR-aggregated before
A.012. One Profile cannot stop a Device that another still requires.

### F7 — pre-A.012 presence observation does not create an ownership cycle

**Decision:** accepted.  
**Resolution:** fixed.

C.004 is a stateless observation/verification Adapter and does not provision VPN endpoints.
Using one fresh presence-only observation before demand projection is therefore compatible with
A.012 remaining the sole managed base-presence owner.

The accepted candidate ordering is:

```text
Private network ready
    -> fresh endpoint observation
    -> pure warm-demand projection
    -> A.012 / D.001 convergence
    -> fresh C.004 observation + normal binding projection
    -> dependent payload / availability policy
```

The first observation must not commit payload binding state.

### F8 — current R7.R3 closure is no longer sufficient

**Decision:** accepted.  
**Resolution:** fixed.

The current R7.R3 Statement equates structural reference with managed presence demand. That is
now known to be too narrow. Under the requirement model, its semantic change requires status
re-review.

R7.R3 should return to `open` and `decomposition: incomplete` until the warm-target
configuration and full demand-selection contract are normalized and accepted. A.012 currently
implements only the `all` subcase, so its R7.R3 contribution becomes `partial`.

The R7 parent, R7.R1 and R7.R2 do not change meaning and retain their existing status: the
parent still has direct accepted A.012 coverage for explicitly managed lifecycle ownership, and
the opt-in/generation/postcondition contracts remain valid.

## Remaining frontier

No additional traffic-driven product decision blocks the current work.

The next bounded unit is configuration normalization:

1. choose one canonical Profile field name for the `0 | N | all` warm-presence target;
2. add the normalized value to A.002/current config;
3. then define/materialize the pure demand Calculator and A.012 integration.

Exact runtime implementation is not accepted by this review.

## Verdict

**PASS — configuration-driven warm presence is the correct active Device Manager frontier.
R7.R3 must be reopened and A.012 downgraded to a partial contribution for that node; payload
traffic and availability health remain outside managed-presence demand.**


## Later product decision — reserve refinement

After this review, projectholder clarified that Profile-local `:reserve` is not part of the
warm set. Consequently F2–F5 remain valid only for **ordinary** memberships. Reserve paths are
a temporary exception when ordinary convergence still leaves a regular deficit; reserve
presence does not satisfy `warm_paths`, and ordinary recovery demand therefore remains active.

The refined model, canonical `warm_paths` surface and two-phase ordinary→reserve convergence
are accepted separately in
`design/reviews/NG3-2026-11-25-warm-paths-reserve-model-review.md`.
This note does not rewrite the historical verdict of the research question reviewed here.
