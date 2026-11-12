# EXP-021 — NG1 local availability probe path

**Status:** PREPARED  
**Architecture baseline:** NG1 Draft 5 + EXP-017/019/020  
**Type:** local-origin routing / nft generation-aware active-probe experiment

## Purpose

Future DeviceManager active probes originate locally inside the ROU namespace, while the
current production model deliberately allows local NEW OUTPUT only through `host0` and
uses Profile RPDB dispatch only for forwarded `iif host0` payload.

EXP-019/020 proved that a tunnel-bound active probe can distinguish path liveness, but did
not prove how production ROU should route/admit such locally generated probe traffic
without opening general Device-interface local access.

This experiment tests a narrow probe-only mechanism.

## Questions

1. Does current default-DROP local policy block a locally generated Device-bound probe as
   expected?
2. For an off-link probe target, does binding ping to the Device interface alone provide a
   usable route, or is an explicit local-probe routing rule/table required?
3. Can an `ip rule oif <Device>` select a dedicated probe table for a socket bound to that
   Device without affecting forwarded host payload?
4. Can nft admit only the probe flow using numeric Device ifindex plus target/protocol?
5. Does same-name/new-ifindex replacement fail closed under the stale numeric nft rules?
6. After explicit reprojection to the new ifindex, does the probe recover?

## Disposable topology

Three namespaces:

```text
exp021-host             exp021-rou                 exp021-remote

192.0.2.1/30 h0 <----> host0 192.0.2.2/30
                         |
                         | dev0 198.51.100.1/30
                         |
                         +---------------------- r0 198.51.100.2/30
                                                  lo 203.0.113.10/32
```

ROU main table has `default via 192.0.2.1 dev host0`, matching the underlay concept.

The probe target `203.0.113.10/32` is deliberately off-link from dev0.

## Candidate mechanism

The experiment does **not** make this mechanism normative. It tests:

- probe process binds to concrete Device name (`ping -I dev0`);
- a dedicated RPDB rule selects a probe-only table by local socket output interface:
  `oif dev0 -> probe table`;
- probe table contains only the target host route via dev0;
- nft OUTPUT admits only target ICMP echo through the concrete numeric oif ifindex;
- nft INPUT admits only the matching established echo reply through the concrete numeric
  iif ifindex.

Normal ROU local OUTPUT/INPUT remain default DROP.

## Procedure

1. create topology and production-like default-DROP local nft policy;
2. prove the probe fails with no Device-local admission;
3. add numeric-ifindex probe INPUT/OUTPUT rules and observe whether interface binding alone
   is sufficient for the off-link target;
4. add dedicated `oif dev0` RPDB rule + target route and require probe success;
5. delete dev0 and recreate the same name with a new ifindex;
6. re-establish only the probe route/RPDB path, leaving old numeric nft admission intact;
7. require probe failure — fresh generation must not inherit old admission;
8. add admission for the new numeric ifindex and require recovery;
9. record rule/table state for review.

## PASS criteria

Required:

- baseline is blocked by local default-DROP policy;
- explicit probe routing + narrow numeric nft admission succeeds;
- fresh same-name/new-ifindex generation does not inherit old nft admission;
- explicit new-generation reprojection restores success;
- no broad `OUTPUT oif Device accept` or Device-wide INPUT accept is needed.

The result must state whether the dedicated probe RPDB/table is actually necessary for the
off-link target.

## Architectural consequence

If PASS, a future availability implementation can reserve a small probe-only routing
resource per concrete monitored binding without changing Profile payload tables or main
underlay semantics.

If `oif` RPDB behavior is unsuitable/unstable, another routing mechanism must be designed
before production probe wiring.

This experiment does not choose probe target/cadence/threshold configuration and does not
approve the detector-readiness proposal.


## Attempt history

### Attempt 1 — HARNESS FALSE NEGATIVE

The first privileged run reached the intended disposable topology and proved baseline
default-DROP behavior:

```text
PASS A: default-DROP local policy blocks Device-bound probe
```

It then stopped before exercising probe routing/generation behavior because the harness
serialized the nft probe rule with `comment` before `counter`. The runner's nft parser
rejected that statement ordering:

```text
syntax error, unexpected counter
```

No EXP-021 routing or same-name/new-ifindex hypothesis beyond baseline PASS A was exercised.

The harness was corrected to use the statement ordering already proven by EXP-017:

```text
... counter accept comment "..."
```

Topology, policy hypothesis and PASS criteria are unchanged.
