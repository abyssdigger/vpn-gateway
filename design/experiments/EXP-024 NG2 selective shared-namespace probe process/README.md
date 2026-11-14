# EXP-024 — selective shared-namespace probe-process isolation

**Status:** preliminary CI mechanism gate pending target confirmation  
**Architecture baseline:** NG2 runtime lower assembly  
**Type:** disposable-netns kernel/mechanism experiment

## Purpose

Close the remaining mechanism gap before implementing `ProbeRulesCalculator` and extending
the common `NetworkRulesAdapter` to local-process traffic.

EXP-021/022 proved narrow probe INPUT/OUTPUT policy using a probe-focused namespace with
default-DROP local policy. Production ROU also hosts unrelated local control/transport
processes, so a global local-traffic default-DROP cannot be assumed before those processes
have a common policy model.

EXP-024 asks whether the probe process can instead be isolated selectively by socket uid
while unrelated local processes retain ordinary namespace networking.

## Topology

```text
                    intended probe path
             198.18.24.0/30
  PRI <------------------------------> ROU
  target 203.0.113.24/32               vpn0

                    ordinary alternate path
             198.18.25.0/30
  ALT <------------------------------> ROU
  same target 203.0.113.24/32           alt0
```

ROU main routing deliberately selects `alt0`.

The probe plane uses:

```text
uidrange 65534-65534
+ ipproto icmp
+ target /32
+ bound oif vpn0
    -> dedicated table 6024
```

The table has the intended route plus terminal unreachable.

## Selective nft boundary under test

OUTPUT:

- matching probe uid + `vpn0` + exact target + ICMP echo-request -> accept;
- every other packet from probe uid -> drop;
- unrelated local uid traffic -> ordinary policy accept.

INPUT:

- exact `vpn0` + target source + echo-reply + receiving socket uid 65534 -> accept;
- the same candidate reply without the intended socket uid -> drop;
- unrelated local traffic -> ordinary policy accept.

The important mechanism question is whether Linux/nft exposes the receiving ping socket
owner through `meta skuid` at the local INPUT hook. A passing echo proves this exact
selective path rather than merely OUTPUT filtering.

## Probe privilege model

Same direction as EXP-021:

- uid/gid 65534;
- empty capability bounding set;
- `NoNewPrivs`;
- namespace-local `ping_group_range` restricted to 65534.

No CAP_NET_RAW is intended.

## Assertions

1. unrelated root/local traffic reaches the target through ordinary `alt0`;
2. capability-free probe uid bound to `vpn0` reaches the target through the isolated
   probe table and selective INPUT/OUTPUT policy;
3. same probe uid without interface binding cannot escape through `alt0`;
4. probe uid cannot reach a different target through `vpn0`;
5. unrelated local traffic still works after probe policy is armed.

## Interpretation

PASS means a future common NetworkRules backend can add an owner-relative/local-process
endpoint without imposing a global INPUT/OUTPUT default-DROP on all ROU processes. Linux
uid remains a technical lower-domain mapping, not an AvailabilityProbe semantic field.

FAIL specifically on INPUT socket uid means the architecture must choose another
process/flow identity primitive (or a complete common local-traffic policy) before
ProbeRules implementation.

GitHub CI is useful as an early kernel/mechanism gate. Because the intended production
target is Debian 13, a production architecture decision still requires target confirmation
before the mechanism is treated as final evidence.

## Artifact

`design/NG2/code/python/rou/tests/integration_probe_process_isolation.py`


## Attempt history

### CI attempt 1 — packaged ping file-capability exec boundary

The first GitHub runner attempt passed ordinary alternate-path traffic, then failed before
the probe socket was created:

```text
PASS P1: unrelated local process remains on ordinary alt0 path
setpriv: failed to execute ping: Operation not permitted
```

The runner's packaged `ping` carries a file-capability setup that cannot be executed after
the process bounding set is emptied. This does not exercise nft `meta skuid`.

The harness now copies the ping executable without extended attributes/file capabilities and
executes that copy under the empty capability bounding set. This preserves the intended
EXP-021 ping-socket model instead of relying on distribution packaging.


### CI attempt 2 — INPUT socket uid is not a usable discriminator

After removing the packaged ping file-capability artifact, the intended probe request
reached the exact OUTPUT allow rule and the RPDB lookup selected table 6024:

```text
OUTPUT probe accept: packets 1
route: target via primary dev vpn0 table 6024 uid 65534
```

The echo reply arrived on `vpn0`, but:

```text
INPUT meta skuid 65534 accept: packets 0
INPUT exact-reply fallback drop: packets 1
```

Therefore `meta skuid` is usable for the locally generated OUTPUT packet but does not
identify the receiving probe socket at the INPUT hook on this runner/kernel.

That mechanism is rejected for reply admission.

The next attempt marks the admitted OUTPUT conntrack entry and matches the reverse INPUT
packet by that conntrack mark plus exact interface/source/protocol. This carries proven
process identity from the point where it is observable into the return flow without
requiring global INPUT default-DROP.
