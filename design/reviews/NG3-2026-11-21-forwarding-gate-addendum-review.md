# NG3-2026-11-21 ForwardingGate addendum review

## Scope

Reviewed commit: `2fbe99937e3391329ec8e42aefb410b742496885`.

Reviewed artifacts:

- `design/NG3/structured-architecture.md`;
- source `design/NG3/architecture.md` root-barrier contract;
- `design/NG3/code/python/rou/forwarding_gate.py`;
- `design/component-model.md` Enforcer/Driver boundaries.

## Checks

### Component boundary

`ForwardingGate` owns one caller-supplied desired postcondition and confirms it from fresh
state. `ForwardingGateDriver` only exposes fresh read plus one mutation attempt.

This matches the component model:

- Enforcer owns observe/apply/re-observe/postcondition semantics;
- Driver owns the technical environment-access primitive;
- process/command result is not promoted to semantic success.

**Decision:** accepted.  
**Resolution:** no change required.

### Hierarchy representation

The only parenthood representation remains:

```text
@ForwardingGate
    ForwardingGateDriver
```

Both component specs remain siblings under the Space's flat `Component addenda`.

**Decision:** accepted.  
**Resolution:** no change required.

### Root-barrier semantics

The addendum preserves the source contract:

- state belongs to the managed/private network, not ordinary host-global forwarding;
- only a freshly observed disabled state is a valid structural barrier;
- the primitive is below user configuration/policy;
- a lower write result is never sufficient confirmation;
- inability to establish the barrier cannot authorize an allowing structural rebuild;
- later retry/continuous maintenance is not hidden inside the bounded Enforcer call.

**Decision:** accepted.  
**Resolution:** no change required.

### Protection scope

The addendum explicitly limits the barrier to routed IPv4 forwarding and preserves the
source warning that local INPUT/OUTPUT owner classes are not protected by
`ip_forward=0`.

It therefore does not overstate the primitive as a universal Private-network kill switch.

**Decision:** accepted.  
**Resolution:** no change required.

### Failure-result nuance

The executable reference permits a lower mutation call to raise while the overall Enforcer
still returns success if the independent final observation proves exact desired state. The
addendum preserves this distinction by defining success from authoritative state rather than
command return.

**Decision:** accepted.  
**Resolution:** no change required.

## Verdict

**PASS.**

The addendum is a faithful responsibility-oriented compression of the existing root-barrier
architecture and demonstrates that a child Driver does not need nested documentation to make
its relationship clear.
