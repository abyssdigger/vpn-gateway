# VPN-GATE NG3 — ordinary-side Profile gateway NAT closure review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-endpoint-provenance-35m`

## Scope

Optional Profile-scoped source NAT on the ordinary/host side for already-permitted
VPN-originated traffic that the VPN-GATE host forwards onward into an ordinary network.

This is distinct from Device VPN-side masquerade.

## Requirement gate

### VPNG-U001-R1.R2.R4.R4.R4

**Purpose / Зачем:** allow VPN-originated traffic to reach ordinary-network hosts that do not
have return routes for remote VPN prefixes without forcing route installation on every host.

**Who:** VPN-GATE.

**What:** allow one Profile to request ordinary-side gateway source NAT only for already
permitted VPN->ordinary traffic forwarded beyond the VPN-GATE host.

**When:** when that Profile has the capability enabled and the host acts as a gateway to
another ordinary-network endpoint. Host-local termination does not require this NAT.

### R4.R4.R4.R1

Two NAT purposes and orderings are separate:

```text
ordinary -> managed firewall -> Device/path MASQUERADE -> VPN

VPN -> managed firewall -> host boundary -> optional Profile gateway MASQUERADE -> ordinary LAN
```

Inbound source filtering therefore runs before ordinary-side gateway NAT and still sees the
original remote payload sender.

### R4.R4.R4.C1

Exact external configuration syntax is postponed to configuration-format review. The
architecture consumes only normalized semantic intent.

### R4.R6.R1.R6 / R1.R6.R1

Host-side state is explicit boundary ownership, not generic host-firewall ownership.
Per-Profile gateway NAT requires a verifiable association between the Profile already
selected inside the managed domain and the packet/flow crossing the common host boundary.

Source-CIDR-only reclassification is insufficient because inbound Profile selection is
path-relative and overlapping remote prefixes can remain valid on different ingress paths.

## Architecture

The semantic owner remains payload/Profile policy; no new long-lived Manager is introduced.

The lower NetworkPolicyAdapter receives a separate host-boundary realization contract:

```text
ProfileGatewayNatOwner(profile_id)
```

plus the lower semantic association:

```text
selected Profile
    -> packet/flow crossing explicit boundary
    -> BoundaryProfileAssociation
    -> ProfileGatewayNatOwner
```

The exact Linux carrier is deliberately unselected. Packet mark, conntrack metadata,
distinct boundary resources or another mechanism require evidence before acceptance.

Host-side owner scope is disjoint from managed-domain `table ip vpn_gate` ownership and
must treat unrelated host firewall/routing state as foreign.

## Safety / return path

Gateway NAT applies only after managed Device/Profile firewall acceptance. Conntrack reverse
NAT restores the remote destination on replies before routing back toward the managed
boundary.

If association, ownership or NAT state cannot be confirmed, the capability remains unready;
VPN-GATE does not guess a Profile.

A structural transition involving this NAT is not eligible for the pure route-priority fast
path.

## Simplification

Not introduced:

- universal host-firewall Manager;
- host-wide route editor;
- userspace per-packet proxy;
- durable association journal;
- source-prefix reclassification after the boundary.

## Evidence gate

Before physical implementation, prove one selected Linux association mechanism with:

- overlapping remote prefixes on distinct ingress paths;
- exact per-Profile host-side NAT selection;
- ordinary downstream forwarding;
- host-local traffic not gateway-NATed;
- unrelated host traffic untouched;
- reverse-NAT return path.

## Verdict

**PASS.** Product semantics and architecture are sufficient for closure. Physical realization
remains evidence-gated; external config spelling remains postponed.
