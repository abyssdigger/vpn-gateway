# NG3 WireGuard recoverable-network-group design review — 2026-11-25

**Review unit:** generalized same-interface WireGuard recovery semantics and architecture  
**Requirements:** `VPNG-U001-R1.R3.R8*`  
**Research:** `design/NG3/research/NG3-2026-11-25-wireguard-recoverable-network-groups.md`  
**Architecture:** A.002, C.001, C.008, D.002, D.003  
**Reviewed head:** `75d5d222ef5fc15ed19c63e2e22b2799289b428e`

## Verdict

**PASS — R8 is correctly generalized from one shared-prefix owner to independently recoverable
network groups, with peer health, group end-to-end health and group ownership kept as distinct
semantics.**

The accepted design deliberately does not claim generalized runtime completion. The current
one-group D.002 code remains a valid degenerate implementation/evidence case; generalized
configuration, group ownership runtime, group endpoint probes, scoped shared-probe readiness
and split-group D.003 acceptance remain open implementation work.

## Findings and dispositions

### F1 — the old R8 wording was too narrow

**Decision:** accepted.  
**Resolution:** fixed.

The old requirement described one remote network/common prefix and therefore made the current
one-selected-peer implementation look closer to the final product contract than intended.
R8 now covers multiple independently recoverable payload-prefix groups on one managed
WireGuard interface and is decomposed into peer health, group membership/ownership, recovery,
reserve/failback, exact convergence and evidence-generation obligations.

### F2 — peer health and group health must not be collapsed

**Decision:** accepted.  
**Resolution:** fixed.

A permanent per-peer in-tunnel `probe_target /32` proves only technical reachability of that
peer. An optional group endpoint proves end-to-end reachability of that group through its
current owner. A live peer may therefore own a failed group without being itself failed.

A group endpoint must lie inside the group's payload bundle and must differ from every
permanent peer probe target; otherwise WireGuard longest-prefix selection could invalidate the
meaning of the group evidence. `local_error` remains observation failure and never becomes
negative health evidence.

### F3 — peer failure and group failure have different recovery scopes

**Decision:** accepted.  
**Resolution:** fixed.

Confirmed peer failure makes every group currently owned by that peer independently eligible
for recovery, even when a group has no individual endpoint. Confirmed group-endpoint failure
while the peer remains usable makes only that group recoverable.

A positive peer probe is only a candidate gate. For a group with an endpoint, a newly selected
candidate is accepted end-to-end only after D.003 confirms the ownership transfer and the group
endpoint replies through that owner. If all candidates are confirmed unsuitable, the group has
no confirmed owner; a known-bad last owner is not retained merely for continuity.

### F4 — sticky/reserve policy should reuse the accepted Profile semantics

**Decision:** accepted.  
**Resolution:** fixed at the semantic boundary.

No independent sticky flag is introduced. Ordinary current ownership is sticky while usable.
Reserve is local to a peer membership inside one recoverable group and permits failback to a
more-preferred usable ordinary candidate. The same peer may therefore be ordinary for one
group and reserve for another.

A small normalized ordered-membership/reserve representation may be reused with Profile
selection if it stays type-safe, but Profile and WireGuard group remain distinct semantic
owners and runtime objects.

### F5 — the one-group case remains a valid degenerate case

**Decision:** accepted.  
**Resolution:** fixed.

One group containing the complete mutable payload-prefix bundle, allowing all managed peers
and having no group endpoint degenerates to the existing D.002 behavior: confirmed failure of
the current peer transfers the complete bundle to a technically usable peer.

Because no binding release exists yet, the generalized canonical configuration may replace
the current pre-binding spelling directly; compatibility aliases are not required merely to
preserve unpublished/pre-binding schema history.

### F6 — D.003 has the right lower API but insufficient generalized evidence

**Decision:** accepted.  
**Resolution:** architecture status corrected.

The current D.003 desired type already represents arbitrary complete per-peer `AllowedIPs`
sets and its responsibility remains exact full-state convergence, not selection policy.
However EV-00100 proves one common-prefix transfer, not simultaneous split ownership of
multiple group bundles across different peers.

Accordingly the D.003 R8 contribution was deliberately changed from `full` to `partial`.
A focused kernel acceptance of exact multi-group split ownership is required before restoring
`full`.

### F7 — generalized R8 initially made existing component claims stale

**Decision:** accepted.  
**Resolution:** fixed by `75d5d222ef5fc15ed19c63e2e22b2799289b428e`.

After the requirement expansion, the old A.002 claim of full R8 normalization was no longer
true, and new R8 children needed explicit requirement-to-architecture traceability. A.002,
C.001, C.008, D.002 and D.003 now carry granular `full|partial|none` edges that reflect the
actual current implementation boundary.

In particular A.002 is only the current one-group config materialization; generalized group
identity, prefix bundles, group-local candidate/reserve policy, optional endpoint and overlap
validation do not yet exist.

### F8 — the shared probe-plane scoped-readiness design remains valid

**Decision:** accepted.  
**Resolution:** retained and generalized.

The earlier C.001 design remains the required lower model: one full accepted physical probe
union, one fresh physical snapshot, and readiness projected separately for semantic owner
subsets. Generalized R8 adds a future group-endpoint probe owner beside A.007 Profile owners
and WireGuard peer owners; it does not justify one merged health verdict.

## Configuration disposition

This review accepts required configuration **semantics**, not a final TOML spelling. The
current parser remains an explicit one-group subset. The next config-format unit must choose a
canonical representation for:

- stable recoverable-group identity and payload-prefix bundle;
- ordered allowed peer memberships with group-local reserve role;
- optional group endpoint;
- overlap rejection;
- permanent distinct peer `probe_target /32`.

The former config heading “Обратная совместимость” has been renamed to preservation of the
externally managed Device mode so it cannot be confused with the project-wide
`VPNG-M001-R4` inter-version compatibility policy.

## Evidence

- Research source: `fca2a3b4f98388b7dc1134833da7ab0d0bfcb02a`, tightened by
  `09520f218e3e88705f4e4b31566e5d9fc658e7f6`.
- Normative architecture/requirements update:
  `1a21986637d14b0e3d57ffe2462a3dcc6ae9f4c7`.
- Traceability correction:
  `75d5d222ef5fc15ed19c63e2e22b2799289b428e`.
- NG3 Python run `45561725458`, unit job `139026865259`: **PASS**.
- Actual-main lineage run `45561725341`: **PASS**.
- No production runtime code was changed by this review unit.

## Next development boundary

Choose and review the canonical normalized/config representation for recoverable groups before
rewriting D.002 runtime selection. The already planned owner-aware C.001 scoped-readiness
implementation remains valid and may proceed independently, but group endpoint probe
composition must use the new distinct semantic owner rather than extending the old one-owner
D.002 shortcut.
