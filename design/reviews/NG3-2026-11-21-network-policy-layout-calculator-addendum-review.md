# NG3-2026-11-21 NetworkPolicyLayoutCalculator addendum review

## Scope

Reviewed commit: `8c47bdb6c61091f46edc055e2974203e65085877`.

Sources:

- `design/NG3/architecture.md` shared lower network-policy ownership/allocation layout;
- `design/NG3/code/python/rou/network_policy_layout.py`;
- `design/component-model.md` Calculator boundary.

## Checks

### Calculator purity

The component consumes semantic owner demand plus an injected platform resource space and
returns a deterministic `NetworkPolicyLayout`. It performs no external observation or
mutation.

**Decision:** accepted.  
**Resolution:** no change required.

### Semantic owner identity versus numeric realization

The addendum preserves the flat architecture rule that semantic owner scopes are authoritative
while table/RPDB/protocol/metric numbers are internal realization.

**Decision:** accepted.  
**Resolution:** no change required.

### Determinism without durable numeric identity

The addendum correctly distinguishes deterministic allocation for one accepted input from a
promise that numeric IDs remain stable across structural configuration changes. No durable
allocation journal is introduced.

**Decision:** accepted.  
**Resolution:** no change required.

### Resource separation and precedence

Payload/probe table and RPDB pools remain disjoint; probe rules precede payload dispatch and
payload dispatch precedes ambient/main lookup.

**Decision:** accepted.  
**Resolution:** no change required.

### Zero-path and metric semantics

The structured spec preserves the selected lower realization:

- payload Profile table exists even at zero paths;
- zero-path has terminal guard but no preference/scratch metric space;
- nonzero path sets receive preference slots and scratch space when required;
- unrepresentable metric demand fails before mutation.

**Decision:** accepted.  
**Resolution:** no change required.

### Cleanup boundary

The statement that allocation is not cleanup authority is a negative contract boundary, not
an attempt to make the Calculator perform cleanup. It prevents consumers from treating a
reserved numeric range/current map as sufficient ownership proof.

**Decision:** accepted.  
**Resolution:** no change required.

### Platform facts

Concrete Linux pool values remain outside the Calculator decisions and are supplied by the
injected platform contract. This keeps evidence-gated numeric constants out of the semantic
component API.

**Decision:** accepted.  
**Resolution:** no change required.

## Verdict

**PASS.**
