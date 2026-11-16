# NG2 — Adapter / Executor boundary review

Date: 2026-11-14
Status: PASS — no additional split justified
Scope: LinuxNetworkRulesAdapter / LinuxNetworkBackend / LinuxNetworkExecutor

## Question

After adopting the Runner / Driver / Executor / Manager model, does the existing
`LinuxNetworkRulesAdapter -> LinuxNetworkBackend -> LinuxNetworkExecutor` boundary hide
mixed responsibilities that require another Driver or API split?

## Current boundary

The Adapter owns:

- owner registration/lifetime;
- composition of owner NetworkRules intents;
- projection onto currently realisable interface generations;
- routing-allocation continuity;
- commit of semantic owner generation only after physical SUCCESS;
- owner-relative NetworkRulesState.

The physical backend owns:

- Linux interface observation required by projection;
- structural Linux desired-state convergence;
- fresh exact verification;
- protective forwarding closure on failure.

The concrete implementation is `LinuxNetworkExecutor`.

## Driver-style observation on the Executor

`LinuxNetworkExecutor.observe_interfaces()` is an observation operation rather than a
convergence operation.

That does not justify a separate `LinuxInterfaceDriver`.

Reasons:

- the observation belongs to the same concrete Linux network environment the Executor
  converges;
- it uses the same Runner boundary and exact interface-generation representation;
- it is consumed only as part of Adapter projection / physical convergence workflow;
- extracting a one-method Driver would not create a reusable semantic boundary;
- the agreed component model allows Executor to perform driver-level interactions directly
  when a separate Driver adds no architectural value.

Component role is determined by the responsibility of the component as a whole, not by a
rule that every public method must have identical operation shape.

## Adapter is not a Manager

The Adapter does not choose payload/probe policy.

Caller Managers provide already-derived NetworkRulesSpec intents. The Adapter only
translates/composes those intents into one shared lower-domain physical generation and
reports observed owner-relative state.

Therefore owner registry and allocation continuity do not make the Adapter a Manager.

## Adapter is not the physical Executor

The Adapter defines the semantic transaction:

- stage owner candidate;
- derive physical desired state;
- invoke physical convergence;
- commit semantic generation only after verified physical success.

It does not itself implement the OS convergence sequence.

That sequence remains behind `LinuxNetworkExecutor.materialize_structural()`.

## Backend protocol naming

`LinuxNetworkBackend` is a consumer-facing dependency protocol, not another component role.

It intentionally contains the small capability set the Adapter needs:

- `observe_interfaces()`;
- `materialize_structural(desired)`;
- `verify_current(desired)`.

Renaming it merely to mirror the concrete class would not improve the semantic boundary.

## Result

PASS.

Do not add:

- `LinuxInterfaceDriver`;
- per-command route/nft/sysctl Drivers;
- another Adapter between NetworkRulesAdapter and LinuxNetworkExecutor.

The current boundary is cohesive and consistent with the Runner / Driver / Executor /
Manager model without artificial atomisation.
