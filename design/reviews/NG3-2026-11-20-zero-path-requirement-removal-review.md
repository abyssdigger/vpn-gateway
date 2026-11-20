# VPN-GATE NG3 — zero-path requirement removal review

**Date:** 2026-11-20  
**Branch:** `ng3-design-cycle-20261120-rudiment-cleanup-finish-35m`  
**Reviewed range:** `e690acc6fc6683a89bfe00bdef3971259f4f4cd7..0699e77fe2f9f4f98089099b38368df67677503e`

## Verdict

**PASS.**

`VPNG0004-R4.R1.R1` was removed from the current requirement tree.

The node was both redundant and mis-scoped:

- its "Profile does not disappear when paths = 0" statement is already owned by
  `VPNG0001-R1.R2.R4.R4.R2`;
- its concrete-path membership premise is already constrained by
  `VPNG0002-R2.R2.R2`;
- its fail-closed result inside VPN-GATE follows from the root safety obligation
  `VPNG0004-R4`: managed traffic must not be forwarded by a behavior outside current
  accepted policy;
- the deleted Purpose incorrectly described ordinary host `ambient/main` routing as if
  VPN-GATE owned it, which conflicts with the accepted host-network non-interference boundary.

The immediate parent `VPNG0004-R4.R1` is about an **ambiguous/indeterminate policy result**.
A Profile with zero effective paths is not ambiguous: the permitted concrete-path set is
unambiguously empty. The removed child therefore did not naturally refine its immediate
parent.

## Current zero-path semantics

No product behavior was removed.

The current normative chain is:

```text
Profile logical identity persists with zero usable paths
    <- VPNG0001-R1.R2.R4.R4.R2

effective concrete membership comes only from valid current bindings
    <- VPNG0002-R2.R2.R2

zero valid concrete paths therefore means no permitted VPN forwarding result

managed traffic must not be forwarded outside accepted current policy
    <- VPNG0004-R4
```

Consequently a zero-path Profile remains present in structural policy and the selected lower
architecture may continue to materialize terminal fail-closed behavior.

The guarantee applies after traffic is accepted/classified into the managed policy domain.
It does not constrain administrator-owned ordinary-host routing before traffic is handed to
VPN-GATE.

## Traceability cleanup

All current normative references to `VPNG0004-R4.R1.R1` were removed.

- `design/NG3/config-model.md` now traces zero-path structural behavior to the Profile
  persistence / concrete-path membership requirements plus root safety.
- `design/NG3/architecture.md` maps Profile-domain persistence, PayloadTrafficManager and
  lower table/terminal-guard realization to the surviving requirements.
- wording that previously said zero-path traffic must not fall through ordinary
  `ambient/main` host routing was narrowed to the managed policy domain.

The historical
`design/reviews/NG3-2026-11-16-structural-routing-activation-boundary-review.md` retains its
then-current requirement reference, but now explicitly records the deleted requirement's
historical meaning and the current replacement mapping. It is not a dangling current link.

## Architecture consequence

The following lower behavior remains valid:

- an enabled Profile may keep an internal policy/routing domain even with no current paths;
- terminal fail-closed behavior may remain materialized in that domain;
- path-route changes may continue to mutate only the ordinary path entries while preserving
  the structural terminal result.

These are architecture choices closing the surviving requirements. They are no longer used
to justify a separate product requirement derived from the Linux fallback mechanism.

## Requirement-state presentation convention

The same review unit also normalized requirement-state presentation.

In normal Markdown prose/tree text, only the constant label/link name is rendered as inline
code:

- [`closed`], [`pending_closure`], [`rejected_closure`];
- [`decomp`: ...], [`unreal`: ...], [`broken`: ...].

Brackets, colons, commas, arrows and concrete IDs/values remain ordinary text. Fenced code
blocks are unchanged because the whole block is already monospaced.

The convention is recorded in `design/requirements-model.md` and applied to the current
`design/NG3/requirements.md` plus normative requirement-process text in
`CONTINUOUS-DEVELOPMENT.md`.

This presentation-only normalization did not change requirement IDs, requirement ordering,
closure/link names or their semantic values.

## Static checks

Current normative files contain zero occurrences of `VPNG0004-R4.R1.R1`:

- `design/NG3/requirements.md`;
- `design/NG3/config-model.md`;
- `design/NG3/architecture.md`.

Outside fenced code blocks, the old whole-token presentation forms such as
`[closed]` and `[decomp: ...]` no longer occur in the three current normative
requirement/process documents; they render as [`closed`] and [`decomp`: ...] instead.

## Next suspicious requirement

The next candidate from the original review list is `VPNG0005-R5.C1`.

Its underlying need — bounded recovery after arbitrary root/admin mutation — is plausible,
but its current fail-closed scope must be rechecked against the newly separated distinction
between authoritative VPN-GATE-owned runtime state and administrator-owned / peaceful-helper
host routing.
