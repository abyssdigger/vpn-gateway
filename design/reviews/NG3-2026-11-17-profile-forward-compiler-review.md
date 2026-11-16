# VPN-GATE NG3 — semantic Profile forward compiler review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-policy-activation-35m`

## Scope

Review the pure Calculator that compiles accepted Profile permission semantics into the exact
positive `payload_forward` NEW/RETURN desired-rule contract.

The unit connects:

```text
PayloadProfileRequest
+ current logical-path endpoint realization
+ current host-boundary identity
    ->
PayloadForwardDesiredState
```

It does not mutate Linux and does not compile Device firewall, NAT, publication or
availability semantics.

## Implements

- `VPNG0002-R2.R1.R2` — remote destination/source classification semantics;
- `VPNG0002-R2.R2` / `R2.R2.2` — only current eligible bound paths may receive
  permission;
- `VPNG0002-R2.R3` / `R2.R3.3` — explicit OUT/IN/bidirectional direction;
- `VPNG0002-R2.R5.R1` — deterministic most-specific classification;
- `VPNG0004-R4.R1` / `R4.R1.R1` — zero-path remains fail-closed policy domain;
- `VPNG0004-R4.R3.R2` — structural policy must not transiently widen permission.

**Constrained by:**

- `VPNG0002-R2.R3.C1` — first-release inbound/bidirectional path-capacity constraint is
  already enforced at config normalization;
- accepted exact lower NEW/RETURN nft shape from EXP-035/036/037/038.

## Verdict

**PASS.**

The compiler preserves most-specific Profile ownership under a positive-only/default-drop
lower rule model and produces exact current-interface desired rules without I/O or hidden
policy.

No human decision is required.

## Implementation

New module:

`design/NG3/code/python/rou/payload_forward_compiler.py`

Public contracts:

- `PayloadForwardCompileError`
- `compile_payload_forward_policy(...)`

The implementation intentionally reuses:

- `build_outbound_profile_partition(...)`;
- `build_inbound_profile_partition(...)`.

It does not implement a second classifier.

## Finding F1 — naive CIDR rule union would widen policy

Suppose:

- broad Profile owns `10.0.0.0/8` and permits path B;
- more-specific Profile owns `10.20.0.0/16` and permits only path A.

A naive physical union containing:

```text
host -> B, daddr 10.0.0.0/8, accept
```

would also accept `10.20.0.0/16` on B if routing/mixed lower state sent such a packet there.
That contradicts accepted most-specific Profile selection.

**Disposition:** outbound permission is compiled from the already proven disjoint global
partition. The broad owner receives only the CIDR fragments remaining after subtraction of
more-specific owners.

Rootless regression proves no broad-path rule overlaps the specific prefix.

## Finding F2 — inbound most-specific selection is path-relative

Inbound classification first restricts candidate Profiles to those allowing the **actual
ingress logical path**, then applies most-specific remote-source selection.

Using one global inbound partition would therefore be wrong.

**Disposition:** the compiler builds one inbound partition per current logical path.

A test proves that a broad Profile allowed only on path B still owns its full `/8` on B even
when a more-specific `/16` Profile exists only on path A.

## Finding F3 — OUT rules and return rules are exact mirror contracts

For each outbound disjoint fragment and allowed path:

```text
NEW:
    ingress = host boundary
    egress  = path endpoint
    match   = remote destination fragment

RETURN:
    ingress = path endpoint
    egress  = host boundary
    match   = remote source fragment
```

The RETURN rule uses the accepted stateful lower kind and does not create independent
reverse NEW permission.

## Finding F4 — IN rules and return rules are exact mirror contracts

For each path-relative inbound fragment:

```text
NEW:
    ingress = path endpoint
    egress  = host boundary
    match   = remote source fragment

RETURN:
    ingress = host boundary
    egress  = path endpoint
    match   = remote destination fragment
```

Thus inbound user permission remains independent from outbound NEW permission while return
traffic for an accepted flow remains stateful.

## Finding F5 — bidirectional is composition, not a special lower primitive

A bidirectional Profile contributes both outbound and inbound semantic permission.

The compiler produces four rule roles for one path/fragment:

- host->path NEW;
- path->host RETURN;
- path->host NEW;
- host->path RETURN.

No new nft action or direction-specific physical object type is introduced.

## Finding F6 — zero-path Profile produces no positive permission

A zero-path Profile still appears in semantic classification and routing desired state, but
there is no current eligible endpoint that may receive positive forwarding permission.

**Disposition:** compiler emits zero `PayloadForwardRuleSpec` values for that Profile.

Fail-closed behavior is supplied by the invariant `payload_forward policy drop` plus the
separate terminal routing guard/RPDB desired state.

This avoids accidentally converting “no current path” into ambient forwarding.

## Finding F7 — endpoint realization is an explicit lower input

The compiler does not infer interface names, gateway/onlink facts or Device transport
topology.

It accepts `RoutePriorityPathRoute` values only for the current semantic path set and
requires exact membership equality.

It rejects:

- extra physical path realizations;
- missing physical path realizations;
- duplicate logical-path realizations;
- one endpoint backing multiple logical paths;
- host boundary reused as a VPN path endpoint.

This keeps current endpoint provenance outside the semantic compiler.

## Finding F8 — Device firewall remains a separate narrowing layer

The generated Profile rules are the hard positive permission gate.

They do not encode:

- Device ordered ALLOW/DENY/REJECT;
- terminal Device no-match drop;
- NAT;
- transport publication.

The already accepted lower ordering remains:

```text
Device firewall child chain
    -> RETURN only when Device permits continuation
    -> Profile NEW/RETURN hard gate
    -> base-chain DROP otherwise
```

The compiler therefore cannot widen Device policy or be mistaken for the complete nft policy
compiler.

## Evidence

Workflow `43965457397`: **SUCCESS**

```text
Ran 477 tests
OK
```

Direct compiler tests cover:

- outbound;
- inbound;
- bidirectional;
- zero-path;
- broad/specific outbound overlap;
- path-relative inbound selection;
- exact physical path membership;
- endpoint uniqueness;
- host-boundary/path separation;
- duplicate Profile identity.

The existing pure structural pipeline now additionally proves:

```text
config normalization
    -> current binding projection
    -> PayloadProfileRequest
    -> Profile classification/effective order
    -> PayloadForwardDesiredState
```

No privileged evidence is required for this unit because it introduces no new Linux
representation or mutation fact. Physical rule forms remain covered by EXP-035/036/037/038
and the combined nft convergence integrations.

## Component-model review

This is a pure `PayloadPolicyCalculator` responsibility:

- deterministic;
- no I/O;
- no mutable state;
- no retry;
- no lifecycle;
- no event handling.

No new Manager/Agent/Driver is introduced.

## Simplification review

Not introduced:

- second most-specific algorithm;
- ordered Profile firewall rules;
- per-Profile nft chain;
- rule-priority semantics;
- endpoint discovery;
- route calculation;
- NAT/firewall composition;
- provenance history.

The disjoint partition is reused because it is the minimal mechanism that makes an unordered
positive-rule set equivalent to accepted Profile classification.

## Residual desired-state assembly gap

After this PASS, the remaining pure assembly before full activation input can be composed is
narrower:

- payload routing desired state already exists;
- Profile forward desired state is now compiled;
- Device NAT desired projection exists;
- Device firewall per-policy compiler exists;
- publication-local desired projection exists.

A later pure composition unit may combine these already-normalized owner projections into one
`PayloadRoutingDesiredState + CompositeNftDesiredState` input for
`activate_network_policy(...)`. It must not invent deferred external policy grammar.

## Accumulated requirement-state inventory

### `decomp`

All six accumulated links remain **resolved**. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

## Conclusion

**PASS.**

Most-specific Profile permission is now compiled into exact lower positive NEW/RETURN rules
without widening broad Profiles, without losing ingress-path semantics, and without coupling
the Calculator to Linux mutation or Device firewall policy.
