# NG2 — runtime component role audit

Date: 2026-11-14
Status: current role classification
Scope: NG2 Python runtime/lower-domain components

## Purpose

Apply the agreed Runner / Driver / Executor / Manager boundary to the current NG2 code
without forcing every component into that hierarchy.

The hierarchy describes control responsibility. It is not a universal taxonomy for every
type in the codebase.

## Runner

Current Runner boundary:

- `LinuxCommandRunner` — raw command execution protocol;
- `SubprocessLinuxRunner` — host subprocess transport;
- `NetworkNamespaceLinuxRunner` — namespace-prefixed transport.

Runner receives raw invocation data and returns raw execution results. It has no semantic
model of the managed object.

Expected users:

- Driver commonly uses Runner;
- Executor may use Driver and/or Runner directly;
- Manager should normally not use Runner directly.

## Driver

Current concrete Driver:

- `LinuxIcmpProbeDriver`.

It performs one semantic external observation operation:

```text
AvailabilityProbeRequest + timeout
    ->
REPLY | NO_REPLY | ERROR
```

It validates the requested concrete interface generation and prepares the Linux ping-socket
prerequisite, but it does not own endpoint desired state, retry policy, hysteresis, or
availability convergence.

## Executor

Current class Executor:

- `LinuxNetworkExecutor`.

It owns one complete structural convergence transaction:

1. establish protective forwarding closure;
2. materialize prerequisites/routing/RPDB/nft;
3. freshly observe and verify the closed state;
4. reopen IPv4 forwarding when required;
5. freshly observe and verify final desired state;
6. fail closed on unsuccessful convergence.

Direct Runner usage inside this Executor is intentional. Separate one-command Route/Nft/
Sysctl Drivers are not required.

### Procedural instance Executors

The functions in `linux_instance.py` are also Executor-style responsibilities even though
they are not wrapped in an Executor class:

- `create_linux_instance()` creates, verifies, and rolls back on failure;
- `ensure_linux_instance()` verifies existing infrastructure or converges absent
  infrastructure to the requested instance;
- `destroy_linux_instance()` removes infrastructure and verifies the postcondition.

They use Runner directly and, for protective namespace closure, invoke
`LinuxNetworkExecutor`.

No `LinuxInstanceDriver` class should be introduced merely for symmetry. A stateless
cohesive convergence operation may remain a function until a reusable object boundary is
actually needed.

## Manager

Current Manager:

- `PayloadTrafficManager`.

It owns accepted payload desired intent, audit/reconcile lifecycle, state interpretation and
publication.

Future:

- `AvailabilityProbeManager` will own probe scheduling/evidence lifecycle once its policy
  is defined.

Managers consume semantic lower-domain interfaces; they do not belong at raw Runner level.

## Adapter is a separate role

`LinuxNetworkRulesAdapter` / `NetworkRulesAdapter` remain Adapter components rather than
being reclassified as Manager or Executor.

The Adapter:

- accepts already-selected owner `NetworkRulesSpec` intents;
- owns owner registration/composition and physical allocation continuity;
- projects semantic rules to currently available concrete interface generations;
- delegates physical convergence to the Linux network Executor;
- exposes owner-relative observed `NetworkRulesState`.

It does **not** decide payload/probe domain policy or desired lifecycle, so it is not a
Manager.

It does **not** itself implement the complete OS convergence transaction, so it is not the
physical Executor.

## Calculator and state-model components

Pure components remain outside the runtime control hierarchy:

- `PayloadRulesCalculator`;
- `ProbeRulesCalculator`;
- `PayloadRulesStateCalculator`;
- `ProbeRulesStateCalculator`;
- compilation/projection/verification pure functions.

They transform values without external side effects.

## Bootstrap / assembly

`runtime_bootstrap.py` is assembly/bootstrap machinery.

It verifies the initial fail-closed boundary and wires Runner, Executor and Adapter
dependencies. Bootstrap is a lifecycle phase, not a reusable Driver/Executor/Manager role.

## Protocol / Backend names

`LinuxNetworkBackend` and `LinuxRuntimeBootstrapBackend` are dependency protocols, not
new architectural roles.

They currently describe the subset of Executor operations required by Adapter/bootstrap.

A protocol name may describe the consumer-facing dependency boundary without implying a
separate runtime component category.

## Naming result

Completed role corrections:

- `LinuxIcmpProbeExecutor` -> `LinuxIcmpProbeDriver`;
- `LinuxNetworkDriver` -> `LinuxNetworkExecutor`.

No further component rename is justified by this audit.

The legacy generic names `LinuxDriverResult` and `LinuxDriverError` are vocabulary debt,
not component-role errors. They are shared lower-execution support types and should only be
renamed if doing so improves clarity without forcing a new abstraction.

## Result

The current model is intentionally non-total:

```text
domain Manager
    |
    v
semantic Adapter
    |
    v
physical Executor
    |
    +--> semantic Driver --> Runner
    |
    +---------------------> Runner

Calculator / bootstrap / value-state types are orthogonal roles.
```

This structure preserves semantic boundaries without manufacturing one-line Drivers or
misclassifying Adapter/Calculator infrastructure.
