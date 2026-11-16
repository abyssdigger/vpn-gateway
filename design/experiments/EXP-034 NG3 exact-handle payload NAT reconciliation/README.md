# EXP-034 — NG3 nft exact-handle payload NAT reconciliation

**Status:** experimental gate; result not yet accepted  
**Stage:** NG3  
**Date:** 2026-11-16

## Hypothesis

In an owned `table ip vpn_gate / chain payload_postrouting`, an nft
masquerade rule created with exact numeric ifindices retains a usable
kernel rule handle after its interface disappears. After creating a
same-name replacement interface and its new distinct NAT rule,
`nft delete rule ... handle <old handle>` removes only the stale
old rule. A delete for a nonexistent handle fails without changing
other rules.

This is a **kernel/nft technical fact** needed by eventual guarded
structural NAT reconciliation. It does not specify product semantics.

## Required environment

GitHub Ubuntu privileged runner with `iproute2` and `nftables`,
within a new disposable Linux network namespace; `ip_forward=0`.
No existing VPN, host routes, or production policy is touched.

## Procedure and artifacts

Script: `exp034_exact_nat_handle.py`.
It uses the accepted nft namespace observer, NAT observer and fresh
interface inventory. It compares raw current objects and recognized
handle values before and after exact deletion; checks same-name
replacement, correct stale recognition, and failed-delete isolation.

Run:

```sh
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-034 NG3 exact-handle payload NAT reconciliation/exp034_exact_nat_handle.py"
```

## Result

PENDING — see dated evidence result after GitHub Actions completes.

## Architectural consequence

PASS is evidence for **exact one-rule handle deletion** in the future
guarded NAT Executor; it is not a blanket permission to mutate nft.
A production mutator still requires full owned-scope classification,
fresh observation, no conflicts, confirmed disabled ForwardingGate
and exact re-observed postconditions. FAIL blocks that physical
deletion mechanism pending redesign/target-specific investigation.
