# NG2 — Runner / Driver / Executor / Manager component boundary

Date: 2026-11-14
Status: agreed terminology boundary
Scope: NG2 component roles

## Runner

A Runner is an implementation-level execution / transport primitive below the Driver role.

It mechanically executes one external invocation and returns its raw transport-level result.
It has no semantic model of the managed object.

Typical shape:

```text
argv + stdin + execution options
    ->
return code + stdout + stderr
```

A Runner therefore does not know whether a command means “add a route”, “send a probe”,
“change forwarding state”, or “delete conntrack state”.

Current examples:

- `LinuxCommandRunner`;
- `SubprocessLinuxRunner`;
- `NetworkNamespaceLinuxRunner`.

Runner is intentionally **not** a peer architectural role beside Driver / Executor /
Manager. It is reusable implementation machinery under those roles.

### Runner / Driver boundary

The boundary is semantic, not based on whether both eventually execute external commands.

A Runner transports a raw invocation.

A Driver exposes a meaningful operation over an external managed object or environment.
For example, “perform one ICMP probe and return REPLY | NO_REPLY | ERROR” is a Driver
operation even if its implementation ultimately executes `setpriv` and `ping` through a
Runner.

NG2 must not promote raw command wrappers into Drivers merely to preserve a formal layer.

### Who may use Runner directly

A Driver will commonly use a Runner to implement its external interaction.

An Executor may use Drivers **and/or Runner directly**. Direct Runner usage is appropriate
when extracting a separate Driver would create a single-use wrapper without a reusable
semantic boundary.

A Manager should normally use Executor / Driver abstractions rather than Runner directly.
Direct Manager -> Runner interaction would mix lifecycle/policy ownership with raw
transport mechanics and therefore requires an explicit architectural reason.

The intended dependency shape is:

```text
Manager
    |
    v
Executor
    |
    +--> Driver --> Runner --> OS / external environment
    |
    +------------> Runner --> OS / external environment
```

This is not a requirement to instantiate every layer for every operation.

## Driver

A Driver directly interacts with an external managed object or environment.

It performs a concrete control action or reads/observes concrete external state.
A Driver does not choose desired state and does not own convergence toward a desired postcondition.

The important property is responsibility, not implementation size: a Driver is mechanically obedient external interaction.
NG2 must not atomize every one-line command into a single-use Driver wrapper.

## Executor

An Executor accepts a desired state or postcondition and is responsible for reaching and verifying it.

An Executor may use one or more Driver components, or perform driver-level external interactions directly when extracting a separate Driver would add no useful boundary.

Direct OS interaction therefore does not by itself make a component a Driver.
The defining property of an Executor is responsibility for convergence / verified postcondition.

## Manager

A Manager owns domain lifecycle and policy.

It decides what desired state should exist, when it changes, how long it remains current, and what higher-level state/event should be published.

A Manager may delegate physical convergence to an Executor and raw observations/actions to Drivers.

## Practical hierarchy

```text
Manager
    chooses / owns desired lifecycle
        |
        v
Executor
    reaches + verifies desired postcondition
        |
        +--> Driver
        |      |
        |      v
        |    Runner
        |
        +--> Runner directly
```

The direct Executor -> Runner branch is intentional. NG2 does not require artificial
one-command Driver objects merely to preserve a formal layer.

Runner is implementation machinery; Driver / Executor / Manager remain the architectural
responsibility roles.

## Consequences for current names

### LinuxIcmpProbeDriver

The component executes one observation-producing ICMP operation and returns REPLY | NO_REPLY | ERROR.
It does not own a desired external state and does not converge an endpoint toward REACHABLE.

Its architectural role is Driver. The former `LinuxIcmpProbeExecutor` name was corrected
to `LinuxIcmpProbeDriver` without changing behavior.

### LinuxNetworkExecutor

The component performs a full structural desired-state transaction: protective close,
materialization, fresh verification, optional reopen, final verification.

Its architectural role is Executor even though it also performs driver-level commands
directly through Runner. The former `LinuxNetworkDriver` class name was corrected to
`LinuxNetworkExecutor` without introducing one-command Driver wrappers.

The implementation remains in `linux_driver.py` for now because that module also owns the
shared Linux Runner primitives and lower execution result/error types. No module split is
required merely to satisfy naming symmetry.

## Conntrack cleanup placement

If probe-class conntrack cleanup is adopted, the raw conntrack delete command is driver-level interaction.

Responsibility for ordering that cleanup inside a complete verified structural transition belongs to the network Executor role, whether it invokes a separate reusable conntrack Driver or performs the command directly.

AvailabilityProbeManager must not own that physical cleanup ordering.