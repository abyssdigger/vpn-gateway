# NG2 — local-process NetworkRules semantic contract review

**Дата:** 2026-11-14  
**Тип:** autonomous focused semantic-contract review  
**Scope:** NetworkRules representation required by future ProbeRules

## Trigger

EXP-024 found a selective shared-namespace implementation primitive for local probe
traffic:

- local process identity is observable at OUTPUT;
- exact admitted flow can carry a lower-domain conntrack mark;
- reverse INPUT can require that mark;
- unrelated local processes remain outside probe policy.

This removes the mechanism ambiguity identified by the ProbeRules boundary review.

## Contract extension

`NetworkEndpoint` now has:

```text
LOCAL_NETWORK
LOCAL_PROCESS
INTERFACE
```

`LOCAL_PROCESS` is semantic. It carries no uid, gid, mark or Linux interface identity.

`DispatchRuleSpec` now additionally supports:

```text
bound_output: concrete INTERFACE endpoint | none
protocol: TrafficProtocol | none
```

For a `LOCAL_PROCESS` source both are mandatory.

This encodes the property proven necessary by EXP-022/023: a local active probe must not
silently become an unbound lookup through another path.

## Composition

Dispatch conflict identity is now the complete selector:

```text
source
destination
bound_output
protocol
```

Therefore two probe owners may legitimately target the same /32 and protocol through
different concrete interface generations.

They do not become ambiguous merely because destination/source-class match.

Owner-scoped routing domains remain unchanged.

## Lower-domain mapping

No Linux identity appears in the semantic contract.

The intended first Linux materialization is:

```text
LOCAL_PROCESS
    -> configured technical local process identity at OUTPUT
    -> bound-output + destination + protocol RPDB selector
    -> dedicated owner routing domain
    -> selective nft OUTPUT admission
    -> lower-domain conntrack flow mark
    -> selective reverse INPUT admission
```

The exact uid/mark allocation belongs below NetworkRulesAdapter and must not appear in
AvailabilityProbeSetRequest or ProbeRulesCalculator output.

## Fail-closed implementation boundary

This review deliberately does **not** extend the concrete Linux routing/nft compiler yet.

The current Linux routing compiler continues to reject any dispatch source other than
`LOCAL_NETWORK`.

A regression test explicitly requires `LOCAL_PROCESS` dispatch to fail before physical
materialization.

Thus merging the semantic contract cannot accidentally create a partially isolated probe
plane.

Production Linux materialization waits for Debian 13 confirmation of EXP-024.

## ProbeRulesState

Still not introduced.

The future `ProbeRulesStateCalculator` must be based on actual apply/renew observation of
the local-process physical backend. Copying PayloadRulesState before that would make the
mandatory common-state review circular.

## Evidence

- EXP-022/023: isolated bound probe routing semantics on disposable and real OpenConnect
  paths.
- EXP-024 preliminary privileged CI PASS: selective process isolation via OUTPUT process
  identity + conntrack-carried reverse-flow identity.
- unit coverage:
  - LOCAL_PROCESS carries no Linux identity;
  - local-process dispatch requires bound output and protocol;
  - composition distinguishes same target/protocol across different bound paths;
  - concrete Linux compiler explicitly rejects local-process dispatch until implemented.

## Final verdict

**PASS for semantic contract.**

Next implementation gate for Linux materialization: confirm EXP-024 on Debian 13, then
extend routing observation/compiler and nft INPUT/OUTPUT compilation in one reviewed
physical-policy unit.
