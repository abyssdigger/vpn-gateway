# NG3 2026-11-19 — one-shot ICMP probe Driver review

## Verdict

**PASS — one-shot Release-1 ICMP execution now has direct Linux evidence and a bounded Driver
contract.**

## Scope

This unit implements only the physical one-attempt Driver for an already normalized concrete
probe context whose lower probe route/RPDB and local nft preconditions are already
materialized.

It does not:

- derive omitted targets;
- schedule repeated checks;
- choose user-visible timing policy;
- own freshness/generation state;
- own confirmation hysteresis;
- change route preference.

## EXP-067

New privileged experiment:

```text
EXP-067 NG3 one-shot ICMP driver execution
```

runs one packet under the selected probe plane:

- dedicated non-root UID/GID 4242 via `setpriv`;
- exact UID + ICMP + target RPDB selector;
- dedicated probe table;
- exact /32 path route;
- terminal blackhole guard;
- DROP-policy local INPUT/OUTPUT;
- exact EXP-066 probe-local admission and conntrack mark.

Observed on GitHub Actions:

```text
UID 4242 route lookup:
    dev=path0
    table=3221225472 (0xC0000000)

reachable peer:
    ping exit 0
    one reply

exact routed but silent target:
    ping exit 1
    no reply

target without route/precondition:
    ping exit 2
    "Network is unreachable"
```

Therefore the selected current Linux/iputils mapping is:

```text
0     -> REPLY
1     -> NO_REPLY
other -> LOCAL_ERROR
```

The experiment uses one second only as a test-local bounded deadline. It does not establish a
one-second product guarantee.

## Driver

New `icmp_probe_driver.py` provides:

- `IcmpProbeExecutionPolicy`;
- `ProbeCommandRunner`;
- `SubprocessProbeCommandRunner`;
- `LinuxIcmpProbeDriver`.

The generated command is deliberately numeric and narrow:

```text
ip netns exec <managed>
setpriv --reuid <probe-uid> --regid <probe-uid> --clear-groups
ping -n -c 1 -W <reply-timeout-seconds> <concrete-IPv4>
```

There is no hostname lookup and no Driver-side target derivation.

## Bounded execution

The Driver takes two finite lower runtime values:

```text
reply_timeout_seconds
process_grace_seconds
```

and enforces an outer process deadline:

```text
reply timeout + process grace
```

These values are implementation policy parameters. They are not Release-1 user configuration
and not latency guarantees.

A subprocess spawn failure or outer timeout is `LOCAL_ERROR`, hence the Agent maps it to
`NO_EVIDENCE + diagnostic`, not negative path evidence.

## Diagnostics

Only local execution failure carries Driver diagnostics.

stderr/stdout is compacted and bounded to 1024 characters before entering current runtime
status material. The Driver does not retain command-output history.

## Separation from Agent

The Driver receives immutable `ProbeObservationContext` but does not own its generation.

```text
Driver:
    current technical attempt -> REPLY | NO_REPLY | LOCAL_ERROR

AvailabilityProbeAgent:
    verify attempted context is still current
    -> map to positive | negative | no_evidence
    -> discard superseded result
```

This keeps physical execution and stale-result rejection separate.

## Verification

Current code-bearing workflow:

```text
GitHub Actions run: 44465555127
head: a823f1a61308b6e3da30e72545940a67bbc72f23

unit: PASS — 769 tests
linux-probe-runtime: PASS
linux-structural-inventory-shape: PASS
```

EXP-067 in the same run again produced:

```text
EXP067_REPLY_RC=0
EXP067_NO_REPLY_RC=1
EXP067_LOCAL_ERROR_RC=2
EXP067_RESULT=PASS
```

Known unrelated privileged host-bootstrap failures remain outside this unit.

## Requirement / architecture integrity

No normative Requirement or Constraint changed.

Mechanical state:

```text
normative R/C nodes:             172
closed:                          172
pending_closure:                   0
rejected_closure:                  0
open:                              0

architecture requirement IDs:   172
missing exact refs:                0
extra refs:                        0
```

## Requirement-state inventory

Active:

- `decomp`: none pending;
- `unreal`: none;
- `broken`: none;
- `[rejected_closure]`: none.

## Preliminary user-expectation declarations in this snapshot

The cycle also records additional non-normative product expectations without changing the
requirement tree:

1. Profile network prefixes may eventually be sourced from external files, mixed with inline
   prefixes, assembled into one runtime bundle during reload, with current runtime remaining
   active until the new desired state is published and malformed individual lines producing
   warnings rather than automatically disabling the Profile.
2. A future, explicitly non-first-release integration layer may render VPN configuration from
   templates and execute supported VPN start/reload/restart/stop commands using gate config
   data.

The unresolved semantics of those expectations remain requirement-discussion work and are
carried in the cycle handoff.

## Remaining availability runtime boundary

The current pieces now include:

```text
normalized concrete probe intent
    -> lower route/RPDB desired/observe/mutate
    -> lower local nft desired/observe/mutate
    -> bounded current observation context
    -> one-shot ICMP Driver
    -> current technical-result mapping
    -> existing bounded confirmation transition
    -> existing active-route state/effective-order logic
    -> existing route-priority convergence
```

Still not assembled end-to-end:

- integration-specific derivation for bare `availability_check = "icmp"`;
- ongoing scheduling/cadence owner;
- orchestration that ensures lower probe preconditions are confirmed before invoking the
  Driver;
- feeding accepted evidence through confirmation and route-order convergence in the alpha
  runtime;
- selecting concrete lower timeout/cadence defaults for production runtime.

## Conclusion

The first-release ICMP Driver no longer depends on assumed `ping` behavior. Its one-attempt
technical result contract is backed by direct evidence on the same UID/RPDB/nft mechanism used
by the NG3 probe plane.
