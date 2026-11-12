# EXP-017 — NG1 ifindex-aware firewall admission

**Status:** PREPARED — firewall-backend production gate  
**Architecture baseline:** NG1 Draft 5 after 2026-11-12 safety correction  
**Type:** Linux netfilter/interface-generation experiment

## Problem

The current Python backend materializes bound-interface policy with
`iptables-legacy -i/-o <ifname>`.

Linux interface identity in the NG1 model is `(ifname, ifindex)`, but legacy iptables
interface matches are name-based. If one interface generation disappears and a new
interface reuses the same name before ROU has reconciled the disappearance, the old
name-based rules may match packets from the fresh, not-yet-verified generation.

Detecting same-name/new-ifindex in the next snapshot and switching to the structural
barrier is necessary but not sufficient to eliminate that pre-observation window.

## Goal

Prove a production materialization that binds admission to the concrete interface
generation rather than only to its reusable name.

Preferred candidate: nftables rules matching numeric input/output interface identity
(`meta iif` / `meta oif`, or another target-kernel primitive with equivalent
generation semantics).

## Required checks

On the target Debian 13 kernel/userspace:

1. create interface `vpn0` with ifindex A;
2. install allow/state rules tied to generation A;
3. verify admitted traffic on A;
4. delete A;
5. recreate `vpn0` with different ifindex B without changing firewall rules;
6. prove B does **not** inherit A's admission;
7. update rules explicitly to B and prove admission then works;
8. repeat for:
   - NEW Profile allow/drop;
   - ESTABLISHED/RELATED bound-pair acceptance;
   - Device traffic-envelope chain traversal;
   - INPUT/OUTPUT constraints where relevant;
9. verify atomic ruleset replacement and canonical state observation;
10. verify behavior when the bound interface disappears during ruleset replacement.

## Decision gate

The first production release claiming strict invariant
"unbound/fresh interface generation has no payload ACCEPT state" may not rely solely on
legacy name-based iptables rules for dynamically reusable interface names.

Possible resolutions:

- adopt an ifindex-aware nftables backend;
- or prove an equally strong kernel primitive;
- or make DeviceManager serialize interface-name reuse behind a fail-closed barrier and
  prove that lifecycle end-to-end.

Until one resolution is PASS, the current iptables backend remains suitable for
development/integration and for interface names whose generation cannot be reused before
ROU reconciliation, but strict dynamic-generation isolation is not considered proven.
