# EXP-024 — selective shared-namespace probe-process isolation

**Status:** PASS on privileged GitHub Linux CI and Debian 13 target  
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


### CI attempt 3 — PASS with conntrack-carried flow identity

The third attempt replaced INPUT socket-uid matching with:

```text
OUTPUT:
    probe uid + exact oif + target + protocol
        -> set conntrack mark
        -> accept

INPUT:
    exact iif + remote source + reply protocol + conntrack mark
        -> accept
    same candidate reply without mark
        -> drop
```

Observed final markers:

```text
PASS P1: unrelated local process remains on ordinary alt0 path
PASS P2: capability-free probe UID uses isolated bound vpn0 plane with selective INPUT/OUTPUT admission
PASS P3: same probe UID cannot escape unbound through alt0
PASS P4: probe UID cannot widen target admission
PASS P5: selective probe policy leaves unrelated local traffic intact
NG2_SELECTIVE_PROBE_PROCESS_ISOLATION=PASS
```

This proves on the CI kernel that process identity can be captured where it is observable
(OUTPUT) and carried safely to the reverse flow through conntrack state.

The result is strong enough to remove the architecture ambiguity. The same artifact has now also passed on the Debian 13 target.


## Debian 13 stand preflight

Before target confirmation, run the read-only preflight:

```bash
sudo sh 'design/experiments/EXP-024 NG2 selective shared-namespace probe process/preflight-exp024-target.sh'
```

Do not run EXP-024 unless the preflight ends with:

```text
EXP_024_TARGET_PREFLIGHT=PASS
```

A WARN/FAIL result must be reviewed first. The preflight does not mutate network state.

Because yesterday's EXP-023 outage was created on the remote `pri` client, also verify
there:

```bash
sudo iptables -S FORWARD | grep -F VPNG-EXP023 || true
```

Expected: no output.

## Debian 13 target confirmation

Target result: **PASS** on Debian GNU/Linux 13 (trixie), kernel `6.12.116+deb13-amd64`.

Run from the repository root as root (or through sudo):

```bash
sudo python3 design/NG2/code/python/rou/tests/integration_probe_process_isolation.py
```

The harness creates only disposable namespaces named:

```text
vpng2-probe-rou
vpng2-probe-pri
vpng2-probe-alt
```

and removes them in `finally`.

Target confirmation is PASS only if the final output contains all P1..P5 markers and:

```text
NG2_SELECTIVE_PROBE_PROCESS_ISOLATION=PASS
```

A target failure must be retained with the complete traceback/output; do not replace it by
a simplified manual ping check, because the relevant evidence is the combined uid, bound
oif, RPDB, nft and conntrack behavior.
