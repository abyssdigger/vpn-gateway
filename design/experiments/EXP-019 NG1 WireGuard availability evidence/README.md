# EXP-019 — NG1 WireGuard availability evidence

**Status:** PASS — raw WireGuard availability evidence  
**Architecture baseline:** NG1 Draft 5 + EXP-016  
**Type:** real WireGuard-in-netns liveness experiment

## Purpose

Determine which observable can justify normalized WireGuard `UNAVAILABLE` while the bound
WireGuard interface itself remains present.

The experiment intentionally does not define user-facing DeviceManager configuration. It
tests raw evidence only.

## Questions

1. Does `wg0` remain present/up when the UDP underlay path is broken?
2. Does an active probe to the peer's tunnel address fail specifically during that break and
   recover without replacing the WireGuard interface generation?
3. What happens to `wg show ... latest-handshakes` during a short outage/recovery?
4. Is latest-handshake age alone sufficient for a prompt availability decision, or must
   DeviceManager use an active/protocol-specific probe?

## Topology

Two disposable namespaces:

```text
wg-a: a0 192.0.2.1/30 ---- 192.0.2.2/30 b0 :wg-b
      wg0 10.23.0.1/30      10.23.0.2/30 wg0
```

WireGuard peers use the underlay addresses as UDP endpoints. The tunnel addresses create a
normal connected route, so the active probe does not require Profile routing tables.

## Procedure

1. create both namespaces, veth underlay and WireGuard interfaces;
2. configure reciprocal peers and PersistentKeepalive;
3. prove tunnel ping and record A's wg0 ifindex + latest successful handshake;
4. break B's underlay while leaving both wg0 interfaces untouched;
5. prove A's wg0 identity remains unchanged and tunnel ping fails;
6. record latest-handshake evidence during the outage;
7. restore underlay;
8. prove tunnel ping recovers without replacing A's wg0 generation;
9. record post-recovery handshake evidence.

## Decision boundary

A positive production UNAVAILABLE trigger must be based on evidence that actually proves
the particular Device path unavailable.

If short outage/recovery does not force a new successful WireGuard handshake, handshake age
alone is not a sufficient fast liveness signal. An active probe may be suitable evidence,
but its target/admission semantics would then require a separate DeviceManager design
decision and human agreement because that changes user-facing configuration.

## Artifact

`exp-019-wireguard-availability-ci.sh`

## Attempt history

### Attempt 1 — HARNESS FALSE NEGATIVE

The first GitHub run did not reach WireGuard setup. The harness created a temporary key
directory and then called its initial cleanup routine, which also removed that fresh
directory. Key generation therefore failed with `Directory nonexistent`.

No kernel/WireGuard hypothesis was exercised. The procedure was corrected by separating
pre-run namespace cleanup from final temp-directory cleanup; the hypothesis and topology
are unchanged.

### Attempt 2 — ENVIRONMENT/HARNESS BLOCK BEFORE HYPOTHESIS

The corrected harness reached WireGuard configuration but `wg set ... private-key`
failed with `fopen: Permission denied` for a root-owned mode-0600 key below a temporary
`/tmp` directory when invoked through `ip netns exec` on the hosted runner.

No tunnel was established, so the availability hypothesis was still not exercised.
Attempt 3 moves ephemeral keys to a private directory under `/run` and first checks file
readability from each namespace without logging key contents.

### Attempt 3 — WG TOOL FILE-OPEN RESTRICTION

Moving the key files to a private directory under `/run` did not change the failure.
Generic `test -r` from inside each network namespace succeeded, but `wg set ...
private-key <path>` still returned `fopen: Permission denied` on the hosted runner.

This isolates the issue to the WireGuard userspace file-open path in that CI environment,
not generic namespace visibility. Attempt 4 feeds the ephemeral private key through stdin
(`private-key /dev/stdin`) so the experiment no longer depends on that path behavior.

## Attempt 4 — PASS

The stdin-key variant reached the intended WireGuard experiment and passed on the GitHub
privileged kernel runner.

Observed:

```text
PASS A: WireGuard tunnel established ifindex=2 handshake=1794480627
PASS B: wg0 remains same generation while active tunnel probe fails
HANDSHAKE_BEFORE=1794480627
HANDSHAKE_DURING_OUTAGE=1794480627
PASS C: active tunnel probe recovered on the same wg0 generation
HANDSHAKE_AFTER_RECOVERY=1794480627
OBSERVATION: outage did not create a new successful handshake
OBSERVATION: recovered data path did not require a new successful handshake
EXP_019_WIREGUARD_AVAILABILITY_EVIDENCE=PASS
```

## Result and architectural consequence

The experiment establishes three useful facts for future WireGuard DeviceManager work:

1. interface presence/admin-up is not liveness evidence: `wg0` remained present with the
   same ifindex while its remote path was unusable;
2. an active probe bound to that tunnel path distinguished live -> unavailable -> live
   without replacing the interface generation;
3. latest-successful-handshake age is **not** a sufficient prompt liveness trigger. A
   short underlay failure and successful data-path recovery occurred with the recorded
   latest-handshake timestamp unchanged throughout.

Therefore a future positive WireGuard `UNAVAILABLE` detector must not classify solely from
interface presence or latest-handshake age. Active/protocol-specific path evidence is a
viable basis, but choosing probe target, cadence, failure threshold and admission semantics
is a DeviceManager product/configuration decision and is deliberately not invented by this
experiment.

The experiment closes the raw-evidence question only; it does not yet define normalized
availability policy.
