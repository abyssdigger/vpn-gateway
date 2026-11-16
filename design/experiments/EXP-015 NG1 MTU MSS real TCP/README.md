# EXP-015 — NG1 MTU/MSS real TCP path

**Status:** PREPARED — production-readiness gate  
**Architecture baseline:** NG1 Draft 5 after 2026-11-12 correction review  
**Type:** PMTU/MSS / real VPN payload experiment

## Purpose

Determine whether ROU requires MSS clamping or explicit MTU policy for real payload TCP
across the veth plus VPN tunnel topology. No TCPMSS rule is added by assumption.

## Required topology

Use the real Debian 13 ROU test environment with at least OpenConnect; repeat with
WireGuard if its effective tunnel MTU differs materially.

## Procedure

For each transport:

1. record MTU of rouvpn0, host0 and concrete Device interface;
2. record route PMTU where observable;
3. probe payload sizes with DF set and binary-search the largest successful ICMP payload;
4. capture a real TCP SYN/SYN-ACK through ROU and record advertised MSS;
5. transfer payloads substantially larger than one segment in both directions;
6. repeat with ICMP fragmentation-needed/PTB intentionally blocked if the lab can do so
   safely;
7. compare:
   - no clamp;
   - TCPMSS clamp-to-PMTU;
   - any transport-specific explicit MSS only if clamp-to-PMTU is insufficient.

## PASS criteria

A production policy must be chosen from evidence:

- no clamp required, or
- deterministic clamp-to-PMTU, or
- explicitly justified fixed/Device-specific MSS.

The policy must avoid silent TCP black holes and must not reduce MSS unnecessarily.

## Gate

Final production-readiness signoff for real TCP payload requires EXP-015. Other control
plane implementation may proceed because this is isolated to payload MTU/MSS handling.
