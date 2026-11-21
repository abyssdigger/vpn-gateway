# NG3 machinery terminology transition review

**Date:** 2026-11-21  
**Scope:** component-model terminology, NG3 architecture alignment and mechanical Python reference-code naming transition  
**Branch:** `ng3-component-model-enforcer-executor-backend-reader`

## Requirement traceability

This review covers internal architecture/implementation quality only. It does not introduce
or change product behavior.

Applicable requirements:

- `VPNG0007-R7.R1`, `VPNG0007-R7.R1.R1`, `VPNG0007-R7.R2`;
- `VPNG0007-R7.R3`, `VPNG0007-R7.R3.R1`, `VPNG0007-R7.R3.R2`,
  `VPNG0007-R7.R3.R3`, `VPNG0007-R7.R3.R5`;
- `VPNG0007-R7.R4`, `VPNG0007-R7.R5`;
- `VPNG0007-R7.R6`, `VPNG0007-R7.R6.R1`;
- `VPNG0007-R7.R7`.

No requirement Statement, Purpose, Reason or closure label changed in this development block.

## Reviewed transition

The component model now distinguishes:

- `Enforcer`: bounded achievement and verification of a caller-supplied desired state or
  postcondition;
- `Executor`: one contract-defined technical actuation operation;
- `Reader`: one read-only technical observation responsibility;
- `Driver`: the technical access/error-normalization boundary to an external mechanism or
  environment;
- `Backend`: a stateless logical implementation composition/facade, not a component role.

Reader and Executor are responsibilities, not mandatory object boundaries. A Driver may
implement simple read/actuation methods directly when extracting another component would add
no architectural value.

A raw helper such as `run(argv)` is explicitly below this role model. It is not promoted to
Executor merely because it invokes a process.

## Findings and dispositions

### F1 — old Executor name described convergence, not execution

**Decision:** accepted.  
**Resolution:** fixed.

The previous component-model `Executor` responsibility was observe/plan/act/re-observe/
verify convergence. It is now named `Enforcer`. NG3 architecture uses
`NetworkPolicyEnforcer`, and live route-priority and nft-scaffold convergence modules are
`route_priority_enforcer.py` and `nft_scaffold_enforcer.py`.

Compatibility modules with the old filenames remain only as transition shims for earlier
executable evidence/imports.

### F2 — blanket Runner -> Executor rename would be semantically wrong for raw invocation helpers

**Decision:** accepted.  
**Resolution:** fixed.

The transition rule was narrowed: only a former Runner that exposes one concrete
contract-defined actuation operation maps to the new Executor responsibility. Existing raw
`run(argv)` process/test-injection helpers remain implementation primitives below the
component-role model and are not represented as false Executor components.

### F3 — narrow structural-routing and forwarding-gate Backends were actually Drivers

**Decision:** accepted.  
**Resolution:** fixed.

Current code uses:

- `LinuxStructuralRoutingDriver`;
- `LinuxForwardingGateDriver`;
- `ForwardingGateDriver` for the corresponding lower protocol contract.

The old class/protocol names remain only as explicit transitional aliases. Production call
sites use the Driver names.

### F4 — Backend must remain a composition term, not a synonym for every lower class

**Decision:** accepted.  
**Resolution:** fixed.

The model now defines Backend as a logical composition/facade. Existing broad compositions
such as probe-routing, structural-policy and composite-nft backends are not mechanically
renamed: they aggregate observation and/or multiple lower technical responsibilities and
therefore still fit the Backend definition.

No repository-wide `*Backend -> *Driver` substitution was performed.

### F5 — Reader/Executor extraction must not create micro-component explosion

**Decision:** accepted.  
**Resolution:** fixed.

The component model explicitly states that Reader/Executor are independently materialized
only when useful for reuse, testing, replacement or composition. Simple operations may stay
as Driver methods. The code transition therefore does not create one object per Linux
command.

### F6 — VPNPathAdapter diagram previously implied actuation of the managed domain

**Decision:** accepted.  
**Resolution:** fixed.

The architecture now shows the externally provisioned endpoint entering the managed network
domain first and `VPNPathAdapter` observing/resolving/verifying that fact. The Adapter does
not create, move or configure the endpoint.

## Mechanical verification

The live architecture trace points to:

- `route_priority_enforcer.py`;
- `nft_scaffold_enforcer.py`.

Historical review filenames containing `executor` are preserved as historical evidence.

A branch-content scan of current production call sites found no residual uses of the old
route-priority/nft-scaffold module names, old forwarding-gate role names or the two narrow
`Linux*Backend` class names outside their explicit compatibility aliases.

GitHub Actions on code commit `5c566ed72abe49004aef08149840623c7a4b1de4` completed
**22/22 checks successfully**, including route-priority, forwarding-barrier, probe,
structural-policy, alpha smoke and privileged Debian routed-veth coverage.

## Requirement-state inventory

Current normative requirements contain no active:

- `decomp` links;
- `unreal` links;
- `broken` links;
- `rejected_closure` nodes.

The only `rejected_closure` text match is explanatory syntax in the requirements preamble,
not an active requirement state.

## Verdict

**PASS.**

The transition changes terminology and component boundaries without changing observable
product behavior. Current architecture and production reference-code names follow the new
model; compatibility names are isolated and explicit; Backend remains a composition term;
raw process runners remain implementation primitives rather than being misclassified as
Executor components. No unresolved finding blocks publication of this development block.
