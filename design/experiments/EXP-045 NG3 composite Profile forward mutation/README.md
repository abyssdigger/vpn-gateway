# EXP-045 — composite Profile forward mutation primitives

## Purpose

Prove the minimum nftables write primitives needed by a combined structural Executor for
Profile forward rules when Device-firewall and payload-NAT owner classes already coexist.

The experiment is lower-mechanism evidence only. It does not select Profile semantics.

## Preconditions

The owned table contains:

- invariant `payload_forward` and `payload_postrouting` base chains;
- one Device-firewall child chain and an inserted Device jump before Profile acceptance;
- one owned payload NAT rule.

## Questions

1. Does ordinary `add rule` for a Profile NEW/RETURN rule append **after** the existing
   Device jump, preserving Device-before-Profile ordering?
2. Can an exact Profile rule be deleted by observed handle without disturbing the Device
   jump, Device child chain or NAT rule?
3. Does real forwarded traffic follow the expected result before and after exact deletion?

## Procedure

- create ordinary -> managed -> VPN disposable topology;
- create Device child rule that returns for the tested destination;
- insert Device jump;
- create owned NAT contribution;
- add Profile NEW and RETURN rules using exact current ifindex operands;
- verify physical order is Device jump, then Profile rules;
- verify ping succeeds;
- delete only the NEW Profile rule by exact handle;
- verify ping fails while Device jump/child and NAT remain unchanged.

## Decision

PASS establishes:

- `add rule` as sufficient for a new Profile forward rule after Device jumps;
- exact-handle delete as sufficient for stale Profile forward cleanup;
- coexistence with Device and NAT owner classes for these primitives.

PASS does not authorize whole-policy convergence. Fresh whole-scope observation and the
ForwardingGate remain mandatory.
