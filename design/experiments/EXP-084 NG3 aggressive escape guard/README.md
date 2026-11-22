# EXP-084 — aggressive routing independent escape guard

## Status

Research experiment for active `VPNG-U001-R5.R2*` design after EXP-081 rejected the
EXP-074-only closure candidate.

## Question

Can the aggressive helper pair its desired host routing with an independent nftables guard
that prevents managed destinations from escaping through an ordinary-host route even when an
earlier foreign RPDB rule bypasses the VPN-GATE routing rule?

Candidate invariant:

> for a destination in the active aggressive managed set, HOST OUTPUT/FORWARD traffic may
> leave only through the exact current managed boundary; any other egress is dropped.

The guard does not choose the route. It makes an incorrect competing route fail closed.

## Hypotheses

- **H1:** with correct aggressive routing, local and forwarded managed traffic uses the
  managed boundary and still passes with the guard active;
- **H2:** an earlier foreign RPDB rule can still change route lookup to an ordinary uplink,
  reproducing EXP-081;
- **H3:** while the foreign rule wins route lookup, the independent guard blocks both local
  and forwarded managed traffic rather than allowing ordinary-host escape;
- **H4:** when the foreign rule is removed, traffic resumes through the managed boundary
  without removing the guard.

## Interpretation

A PASS would make the safety property independent from the timing of continuous drift
detection: the future Manager may use rtnetlink/timers to detect and repair drift, while the
guard prevents leakage during the detection/recovery window.

It does not by itself implement Manager lifecycle, alert/escalation or the broader public
protective mode.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-084 NG3 aggressive escape guard/exp084_aggressive_escape_guard.py"
```
