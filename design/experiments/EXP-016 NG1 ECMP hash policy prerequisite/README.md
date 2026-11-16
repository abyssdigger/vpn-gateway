# EXP-016 — NG1 ECMP hash-policy prerequisite

**Status:** PREPARED — kernel prerequisite gate  
**Architecture baseline:** NG1 Draft 5 after 2026-11-12 correction review  
**Type:** namespace sysctl / Linux FIB ECMP behavior

## Purpose

Fix an explicit production value for `net.ipv4.fib_multipath_hash_policy` instead of
inheriting a kernel/host default.

The persistent shadow fallback is already implemented, but its production availability
trigger is intentionally deferred. Therefore EXP-016 does not block ordinary UNKNOWN-tier
routing; it blocks making ECMP fallback operationally effective through a future
UNAVAILABLE detector.

## Procedure

In a disposable network namespace on the target Debian 13 kernel:

1. record kernel and iproute2 versions;
2. record the initial `fib_multipath_hash_policy`;
3. enumerate values accepted by the target kernel without assuming upstream-version
   support;
4. create a two-member direct-device IPv4 multipath route;
5. for each accepted candidate policy, sample deterministic route selection for:
   - repeated same flow;
   - changed source/destination addresses;
   - changed L4 ports where applicable;
6. confirm namespace isolation of the sysctl;
7. restore the original value.

## Decision

Select one explicit production value and document the intended hash inputs. Add it to
namespace prerequisite apply/observe/verify before enabling a DeviceManager availability
trigger.

## Gate

Future production code that can classify a member UNAVAILABLE may not be enabled until
EXP-016 is PASS and a concrete value is normative.
