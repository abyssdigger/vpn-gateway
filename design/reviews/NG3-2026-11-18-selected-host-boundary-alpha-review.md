# NG3 2026-11-18 — selected host-boundary alpha integration review

## Verdict

**PASS for Release-1 host bootstrap/stateful-return/route-return alpha materialization.**

This block composes the already selected EXP-053 stateful return mechanism with the
EXP-059/060 paired-RPDB host bootstrap and wires the composite boundary contribution into the
normal alpha startup, runtime audit/repair and stop lifecycle.

No user-facing grammar or product semantics changed.

## Requirements

**Implements:**

- `VPNG0002-R2.R3.R1.R1`;
- `VPNG0002-R2.R3.R1.R1.R1`;
- `VPNG0002-R2.R3.R1.R1.R2`;
- `VPNG0002-R2.R3.R3.R1`;
- `VPNG0002-R2.R3.R3.R1.R1`;
- `VPNG0004-R4.R6.R1.R1`;
- `VPNG0004-R4.R6.R1.R2`.

The canonical `+route-return` semantics and selected Linux mechanisms were already accepted.
This block only closes their executable-alpha integration gap.

## Selected composite owner

Added `selected_host_boundary.py`.

The composite retains two separate lower owners:

```text
stateful return:
    reserved return table/rule
    + owned nft connection association

ordinary/local bootstrap:
    selected dedicated bootstrap table
    + paired suppress-prefixlength RPDB rules
    + managed-ingress bypass
```

The historical main-table bootstrap route representation is not used.

Apply order:

```text
prepare dormant stateful-return route/rule
    -> converge return nft
    -> expose selected paired-RPDB bootstrap last
```

Cleanup reverses the safety direction:

```text
remove bootstrap capture
    -> remove return nft
    -> remove return route/rule dependencies
```

## Ownership / crash safety

The selected bootstrap backend can distinguish owned stale state through its explicit
protocol/resource allocation and may reconcile it.

The older return route/RPDB owner has no equivalent protocol owner tag on its reserved RPDB
rule. Therefore the production composite deliberately accepts only:

- ABSENT, when no return owner is desired;
- exact desired state, when stateful return is desired.

Any different occupant of the reserved return table/priority is a conflict. It is not
blind-adopted or automatically deleted as presumed stale state.

The nft return owner remains identified by its explicit owner table/comments.

## Runtime reconciliation

The alpha no longer treats the host-boundary contribution as startup-only state.

Runtime audit is:

```text
observe selected host boundary
    -> exact: no mutation, forwarding remains untouched
    -> drift:
         close and freshly confirm managed ForwardingGate
         converge boundary contribution
         freshly require exact boundary state
         ordinary payload reconciliation may later reopen forwarding
    -> conflict / failed observation / failed repair:
         keep/force forwarding contained
         report current failure
```

Thus host-boundary mutation is never performed merely because a periodic loop ran while
payload forwarding remained enabled.

## Alpha grammar/materialization

The alpha now accepts canonical `+route-return`.

For an inbound/bidirectional Profile with `+route-return`:

- selected bootstrap contains the Profile remote destination;
- no stateful host-return owner is generated for that Profile;
- host replies follow route-based bootstrap semantics.

Profile ordinary-side `+snat` remains rejected and is not affected by this block.

## Evidence

Rootless unit evidence on the final implementation line covers:

- selected bootstrap vs stateful-return desired composition;
- inbound default stateful mode;
- inbound `+route-return` mode;
- bidirectional combined mode;
- exact/foreign reserved return-owner observation;
- runtime exact no-op;
- drift repair only after ForwardingGate containment;
- conflict containment without adoption.

Workflow `44315295284` on implementation commit
`aa6ace0344d07b68645c6e36c8563fc8e68d7d87`:

- unit job `134839668262` — **success**;
- host-return regression `134839668757` — **success**;
- installed Debian 13 alpha smoke `134839668640` — **success**.

The installed alpha used a canonical `bidirectional+route-return` Profile and produced:

```text
EXP051_SELECTED_HOST_BOOTSTRAP=PASS
EXP051_ROUTE_RETURN_STATEFUL_OWNER_ABSENT=PASS
EXP051_FIRST_PAYLOAD=PASS
EXP051_ROUTE_RETURN_HOST_LOCAL_REPLY=PASS
EXP051_RUNTIME_STATUS_NEW_GENERATION=PASS
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS
EXP051_SERVER_PUBLICATION_STOP_CLEAN=PASS
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

The test deliberately removed the old manually installed host route to the remote VPN address.
The selected host bootstrap therefore supplies the actual route-based reachability.

The inherited `linux-nft-marked-host-bootstrap` EXP-057 job remains intentionally failing;
EXP-057 is the rejected shared-mark bootstrap alternative and is not a regression.

## Review findings

### F1 — first installed-alpha route-return probe accidentally left the generated Profile outbound-only

The harness edit initially changed the wrong text occurrence. Diagnostic evidence showed
selected host bootstrap and host route lookup were correct, but the managed
`payload_forward` chain contained no inbound NEW rule.

**Disposition:** harness corrected to generate the actual canonical
`bidirectional+route-return` config. The rerun passed the remote-initiated host-local reply
probe. This was a harness defect, not a mechanism failure.

### F2 — periodic boundary convergence could otherwise mutate while forwarding was enabled

Startup already converged the contribution under containment, but directly reusing
`converge()` from the periodic alpha loop would violate the selected bootstrap backend's
safety precondition.

**Disposition:** fixed by a dedicated bounded runtime coordinator with explicit
observe/contain/converge/fresh-postcondition ordering.

### F3 — stale-vs-foreign ambiguity for the historical return RPDB allocation

Unlike selected bootstrap rules, the older return rule does not carry a protocol ownership
tag suitable for safe stale adoption after a changed config/crash.

**Disposition:** fail closed. Only absent or exact state is accepted; any different reserved
occupant is conflict. No product capability is reduced.

## Requirement-state inventory

No requirement-state transitions occurred.

- resolved `decomp`: six, unchanged;
- pending `decomp`: none;
- active `unreal`: none;
- active `broken`: none;
- active `[rejected_closure]`: none.

The previously identified suspect `VPNG0004-R4.R6.R1.R6.R1` remains unresolved and continues
to gate Profile ordinary-side `+snat`; this block does not depend on or modify it.

## Conclusion

The prior alpha limitation for `+route-return` is closed. Release-1 host bootstrap,
default stateful host return, explicit route-return opt-out, runtime drift containment and
owned cleanup now share the same executable alpha lifecycle.
