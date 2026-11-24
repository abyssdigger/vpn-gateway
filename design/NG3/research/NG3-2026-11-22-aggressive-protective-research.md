# NG3 2026-11-22 — aggressive host-routing and protective-mode research

**Status:** completed research input for current CDC  
**Baseline:** `f88949a8b5251f7ce3a31569506c157feb1f2503`  
**Requirements:** `VPNG-U001-R5.R2*`, `VPNG-U004-R5`

## Research question

Determine a coherent architecture for the re-entered aggressive host-routing helper and
administrative protective mode, with particular attention to:

- what "authoritative" means on a Linux host with RPDB policy;
- how continuous ownership can remain fail-closed during drift-detection latency;
- how an unrecoverable aggressive-helper failure composes with public protective mode;
- whether existing lower mechanisms are sufficient or only partial evidence;
- how protective mode can preserve runtime state and still have safe enter/leave semantics.

## Existing baseline

The pre-CDC architecture had two useful but incomplete facts:

1. EXP-074 proved that the aggressive managed table can override more-specific routes inside
   ordinary host table `main`, while preserving local delivery and managed-boundary
   no-recapture.
2. C.005 `ForwardingGate` proved that `net.ipv4.ip_forward=0` is a real routed-IPv4
   barrier inside Private network.

Neither fact by itself established the full re-entered requirements.

## Platform facts

### Linux RPDB is a policy surface above ordinary route-table specificity

Linux `ip-rule(8)` defines the RPDB as an ordered rule program. Lower numerical priority
values execute first, and a successful earlier lookup terminates the RPDB search.

Source:
https://man7.org/linux/man-pages/man8/ip-rule.8.html

Consequence: placing VPN-GATE lookup before the default priority-32766 `main` rule does not
make it authoritative against arbitrary ordinary host policy rules that may execute earlier.

### Netlink notifications are useful wakeups, not reliable state truth

Linux `netlink(7)` explicitly states that kernel-to-userspace notifications can be dropped
and that applications must resynchronize after loss.

Source:
https://man7.org/linux/man-pages/man7/netlink.7.html

Consequence: rtnetlink route/rule notifications may accelerate aggressive drift reaction, but
the Manager still needs finite-cadence fresh authoritative observation. Event delivery cannot
replace reconciliation.

### `ip_forward` is narrower than public protective mode

Kernel IP sysctl documentation defines `net.ipv4.ip_forward` as forwarding packets between
interfaces.

Source:
https://kernel.org/doc/html/latest/networking/ip-sysctl.html

Consequence: the current `ForwardingGate` is a correct structural-transit barrier, but it does
not own boundary INPUT/OUTPUT and therefore cannot alone realize `VPNG-U004-R5`.

### nftables provides terminal drop and a single-transaction ruleset update

The nftables manual defines INPUT/OUTPUT/FORWARD hooks and specifies that a DROP verdict
terminates further ruleset evaluation. Netdev hooks additionally provide exact-device
ingress/egress filtering.

Source:
https://netfilter.org/projects/nftables/manpage.html

The nftables project documentation also documents `nft -f` ruleset replacement as one
atomic transaction rather than a sequence of partially applied rule commands.

Source:
https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement

## Experiment findings

### EXP-081 — current aggressive closure is insufficient

**Result: PASS, negative architecture finding.**

A foreign RPDB rule at priority 100 was inserted before the current VPN-GATE aggressive
dispatch. The same managed destination was then routed through an ordinary uplink while the
current aggressive owner still reported its own table/rules exact and conflict-free.

Disposition:

- EXP-074 remains valid evidence against competing routes inside `main`;
- EXP-074 is not sufficient closure for `VPNG-U001-R5.R2.R1`;
- the old closure candidate was correctly changed to `rejected_closure`.

### EXP-082 — two-barrier protective containment is feasible but not preferred

**Result: PASS.**

A Private-network `ForwardingGate=DISABLED` plus a host-side nft netdev gate blocked
ordinary->VPN, VPN->ordinary and VPN->VPN traffic while preserving runtime topology.

The mechanism proves feasibility but creates an unnecessary release-order problem: two
independent gates cover different portions of the public protective postcondition.

Disposition: technically valid evidence, **not the preferred architecture candidate**.

### EXP-083 — one Private-network protective gate covers the whole traffic postcondition

**Result: PASS.**

One dedicated nftables `inet` table inside Private network blocked:

- ordinary -> local Private-network IP;
- local Private-network -> ordinary IP;
- ordinary -> VPN;
- VPN -> ordinary;
- VPN -> VPN.

Interfaces, routes and `ip_forward=1` remained unchanged, and deleting the table restored all
five paths.

Disposition: **selected lower candidate** for the protective traffic gate.

### EXP-084 — aggressive safety can be independent of detection latency

**Result: PASS.**

An independent HOST nft escape guard was kept active together with correct aggressive routing.
It allowed matching managed traffic through the managed boundary. After a foreign earlier RPDB
rule redirected route lookup to the ordinary uplink, the guard dropped local and forwarded
managed traffic. Removing the foreign rule restored managed forwarding without removing the
guard.

Disposition: **selected lower candidate** for aggressive fail-closed enforcement.

## Selected architectural direction

### 1. Aggressive host routing is a Manager, not peaceful Machinery

The aggressive helper continuously observes and actuates the same delegated host-routing
domain. Under `design/component-model.md` that makes it an Engine/Manager.

Create an `AggressiveHostRoutingManager` in the `VPN-GATE-managed host state` Space.

It owns the current aggressive desired scope and current confirmation/problem projection.
It may use rtnetlink notifications as wakeups but performs finite-cadence fresh observation.

The existing E.002 `HostRoutingContribution` remains peaceful Direct lifecycle Machinery and
does not acquire continuous ownership semantics.

### 2. Active aggressive state has routing plus an independent escape guard

For every active delegated destination scope:

- managed routing should select the exact current managed boundary;
- an independently owned HOST nft guard should prevent that same scope from leaving through a
  non-managed egress.

Safe activation order:

1. materialize and verify the escape guard;
2. converge and verify managed routing;
3. report the aggressive scope confirmed.

Safe deactivation order:

1. remove/disable managed routing capture;
2. remove the escape guard only after the aggressive scope is no longer claimed active.

Thus a routing drift can degrade availability to DROP but cannot silently leak the managed
scope through ordinary routing while the Manager is still detecting/recovering the drift.

### 3. Continuous recovery must observe the guarantee, not only owned objects

The current wording of `VPNG-U001-R5.R2.R2` mentions only helper-owned routing state.
EXP-081 shows that all owned objects can remain exact while external earlier RPDB policy
invalidates the effective guarantee.

The requirement should therefore cover:

- helper-owned routing/guard state; and
- relevant competing host policy capable of invalidating the effective authoritative
  postcondition.

Fresh full observation remains required even if events normally wake reconciliation earlier.

### 4. Unrecoverable aggressive failure is locally contained before global escalation

`VPNG-U001-R5.R2.R3` should be decomposed into two responsibilities:

1. keep/establish helper-local containment of the delegated scope independently from the
   untrusted routing decision;
2. request the public protective mode and retain local containment until the broader state is
   confirmed or the aggressive helper is explicitly disabled.

Failure to confirm either required containment remains an explicit alarm.

### 5. Protective mode has its own Manager and one Private-network lower gate

Create a `ProtectiveModeManager` in STACK. The mode is product-level safety state and is not
owned by the aggressive helper.

Aggressive routing is one caller/escalation source; operator/automation is another.

The Manager owns the semantic state:

- requested active/inactive intent;
- current confirmed protective postcondition;
- problem/unknown state when the required lower condition cannot be proved.

Its lower traffic primitive is a dedicated `ProtectivePayloadGate` Enforcer in Private
network, realized on Linux by one independently owned nftables table covering:

- ordinary-boundary INPUT;
- ordinary-boundary OUTPUT;
- IPv4 FORWARD.

The existing C.005 `ForwardingGate` remains a structural-policy transition barrier and is not
repurposed as the public protective-mode owner.

### 6. Protective mode requires continuous confirmation

A public "mode" must not silently disappear after external drift. While protective mode is
requested active, the Manager periodically fresh-observes the dedicated gate, can use lower
events only as wakeups, and repairs the exact owned gate when safe.

If it cannot prove the protective postcondition, current status must remain explicitly
problem/unknown rather than claiming protection.

### 7. Leaving protective mode is a policy transition, not merely deleting a table

Before removing the protective gate, the Manager must freshly confirm that the normal desired
network policy/bindings required for release are in an acceptable state.

The gate remains installed during that validation. Only after the release preconditions are
confirmed is the dedicated table removed in its single owned operation.

A failed leave therefore leaves the protective gate active rather than silently returning the
product to an unverified data plane.

This composes with `VPNG-U004-R4.R3*`: while transitioning out of a policy that prohibits all
managed payload traffic, no traffic is released before the transition is ready to complete.

## Requirement refinements justified by the research

The research supports, without adding new product scope:

- refine `VPNG-U001-R5.R2.R2` so continuous observation covers relevant competing policy,
  not only helper-owned objects;
- decompose `VPNG-U001-R5.R2.R3` into local containment and protective escalation;
- decompose `VPNG-U004-R5` into:
  - explicit mode control/lifecycle;
  - full traffic postcondition;
  - diagnostic/recovery state preservation;
  - continuous confirmation and safe leave.

These refinements are direct decomposition of already accepted parent promises.

## Non-goals / unresolved implementation details

This research does not require:

- mutating arbitrary unrelated administrator routing to make aggressive mode work;
- treating rtnetlink notification history as authoritative state;
- reusing the peaceful helper as a hidden Manager;
- changing Release-1 constraints;
- selecting a final user-facing CLI/API spelling for protective enter/leave;
- implementing the new Managers in this research block.

The exact Rust/Python implementation boundary remains governed by the existing development
constraints and should be decided only when implementation work begins.
