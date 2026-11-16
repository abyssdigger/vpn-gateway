# EXP-016 — NG1 ECMP hash-policy prerequisite

> **Current architecture note:** the PASS remains valid ECMP/hash evidence. Because the
> persistent shadow payload fallback has been removed, `fib_multipath_hash_policy=1` is no
> longer a production NG1 namespace prerequisite. Keep this result as evidence for any
> future feature that deliberately introduces ECMP.

**Status:** PASS  
**Architecture baseline:** NG1 Draft 5 after 2026-11-12 correction review  
**Type:** namespace sysctl / Linux FIB ECMP behavior

## Purpose

Fix an explicit production value for `net.ipv4.fib_multipath_hash_policy` instead of
inheriting a kernel/host default.

The persistent shadow fallback was already implemented while its real UNAVAILABLE trigger
remained deferred. EXP-016 therefore gates future DeviceManager availability activation,
not ordinary UNKNOWN-tier routing.

## Procedure

The privileged GitHub kernel-integration runner created a disposable namespace with a
two-member direct-device IPv4 ECMP route and:

1. recorded host/namespace hash-policy state;
2. enumerated candidate values 0..4 accepted by the running kernel;
3. repeated one fixed TCP 5-tuple under policy 1;
4. varied only the TCP source port for 64 flows under policy 0 and policy 1;
5. confirmed namespace isolation of the sysctl;
6. restored the original namespace value.

Harness:

`exp-016-ecmp-hash-ci.sh`

## Result

PASS.

Observed:

```text
ACCEPTED_POLICIES: 0 1 2 3
PASS A: policy 1 keeps repeated 5-tuple on one nexthop
PASS B: policy 0 ignores L4-only variation for fixed L3 tuple
PASS C: policy 1 uses L4 flow variation across both nexthops
PASS D: fib_multipath_hash_policy is namespace-isolated
SELECTED_PRODUCTION_CANDIDATE=1
EXP_016_ECMP_HASH_POLICY=PASS
```

## Decision

Production NG1 owns:

```text
net.ipv4.fib_multipath_hash_policy=1
```

Reason:

- one flow remains deterministic;
- different L4 flows sharing one L3 pair can spread across fallback ECMP members;
- this is preferable to policy 0 for a fallback tier that may carry multiple concurrent
  TCP/UDP flows between the same endpoint addresses;
- the value is namespace-local and therefore does not impose host-global ECMP policy.

The value is now part of namespace prerequisite apply/observe/verify.

## Gate consequence

The ECMP hash-policy prerequisite gate is closed.

Future positive UNAVAILABLE classification is no longer blocked by hash-policy ambiguity.
DeviceManager/availability semantics remain future work and still require their own
review/implementation cycle.
