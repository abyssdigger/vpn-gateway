# NG3-2026-11-21 NetworkPolicyAdapter addendum review

## Scope

Reviewed commit: `7e2a69dcacc77166060d781e681bef7101920739`.

Sources:

- `design/NG3/architecture.md` NetworkPolicyAdapter and route-realization boundary;
- current `NetworkPolicyLayoutCalculator` and `NetworkPolicyEnforcer` structured specs;
- `design/component-model.md` Adapter boundary.

## Checks

### Semantic boundary

The addendum keeps Linux allocation, routing representation, nft/sysctl details and command
ordering below the Adapter. Upper clients remain semantic-policy clients.

**Decision:** accepted.  
**Resolution:** no change required.

### Owner preservation

Shared physical machinery does not merge payload/probe semantic owner scopes.

**Decision:** accepted.  
**Resolution:** no change required.

### Realization composition

The Adapter combines semantic intent, verified path/integration facts and internal allocation
without promoting lower physical values to user configuration.

**Decision:** accepted.  
**Resolution:** no change required.

### Fail-closed incomplete realization

Missing/ambiguous lower realization remains unconfirmed/restrictive and cannot be replaced by
ambient-route guessing or silent path dropping.

**Decision:** accepted.  
**Resolution:** no change required.

### Child responsibility split

The structured tree and addenda now give the two proven children distinct responsibilities:

- `NetworkPolicyLayoutCalculator` chooses deterministic internal resource layout;
- `NetworkPolicyEnforcer` reaches/verifies supplied desired lower state.

Neither child independently expands the Space API.

**Decision:** accepted.  
**Resolution:** no change required.

### F1 — decomposition findings are not architectural decisions

The current addendum puts the host-publication cross-Space problem under
`Architectural decisions`. This is categorically different from accepted component
semantics: it records an unresolved placement problem discovered while restructuring the
flat architecture.

Mixing such findings into the decision list makes it impossible to read the addendum as a
clean statement of accepted architecture.

**Decision:** accepted.  
**Resolution:** add an optional `Findings` block to component-addendum methodology and move
the host-publication issue there. Apply the same rule to the unresolved route-realization
ownership note in `VPNPathAdapter`.

A finding is diagnostic/review state, not normative architecture. When resolved, its accepted
result must move into the appropriate `Architectural decisions` / tree / other Space and the
finding may be closed or removed from the active structured view while remaining preserved in
review history.

## Verdict

**PASS after F1.**
