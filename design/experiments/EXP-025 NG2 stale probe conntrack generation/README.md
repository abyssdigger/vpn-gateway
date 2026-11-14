# EXP-025 — stale conntrack mark across probe generations

**Status:** READY FOR CI/TARGET
**Architecture baseline:** NG2 LOCAL_PROCESS probe plane
**Type:** disposable-netns kernel/mechanism experiment

## Purpose

EXP-024 proved that process identity observed on local OUTPUT can be carried into reverse
INPUT through a conntrack mark.

The remaining generation question is independent:

> Can that marked ICMP conntrack state survive replacement of the concrete bound interface
> generation and then be inherited by a later probe that deliberately reuses the same
> conntrack tuple / ICMP identifier?

If yes, exact RPDB/nft generation verification alone does not prove that reverse-flow
identity belongs to the current probe generation.

## Topology

The experiment uses disposable namespaces only:

- `vpng2-ct-rou`;
- `vpng2-ct-peer-a`;
- `vpng2-ct-peer-b`.

Generation A and B both use the same semantic link parameters:

- ROU interface name: `vpn0`;
- ROU address: `198.18.26.2/30`;
- peer address: `198.18.26.1/30`;
- target: `203.0.113.25/32`.

The veth is deleted between generations and recreated, so generation B must have a
different ifindex.

The probe runs as uid/gid 65534 with a capability-free ping copy and fixed ICMP identifier
4242.

## Policy under test

RPDB:

```text
uidrange 65534-65534
+ ipproto icmp
+ target /32
+ oif vpn0
    -> table 6025
```

nft OUTPUT for the current concrete ifindex:

- NEW exact probe request -> set `ct mark 0x25`, counter, accept;
- ESTABLISHED exact probe request with `ct mark 0x25` -> separate counter, accept;
- all other packets from uid 65534 -> drop.

nft INPUT for the current concrete ifindex:

- exact echo reply with `ct mark 0x25` -> accept;
- exact candidate reply without mark -> drop.

The separate NEW and ESTABLISHED counters are the key evidence.

## Assertions

### C1 — generation A creates marked state

Generation A probe succeeds, increments NEW+mark-set, and leaves a matching conntrack entry
with mark 0x25.

### C2 — interface replacement is a real generation change

Generation A `vpn0` is deleted. Generation B recreates the same name/address topology with
a different ifindex and rebuilds nft policy for that new ifindex.

### C3 — observe conntrack lifetime before tuple reuse

Immediately after generation replacement, inspect whether the generation-A marked entry
still exists.

If it is already gone, the stale-inheritance path is not present for this transition and
the experiment records that stronger kernel behavior.

### C4 — deliberate tuple reuse

If the stale entry survives, generation B repeats the probe with the same uid, source,
target and fixed ICMP identifier.

A stale inheritance is proven only if the generation-B packet increments the
ESTABLISHED-marked OUTPUT counter rather than NEW+mark-set.

### C5 — control after explicit entry deletion

Delete only the matching ICMP conntrack entry, repeat the same fixed-identifier probe and
verify that it now increments NEW+mark-set instead of the stale ESTABLISHED counter.

This control distinguishes stale conntrack inheritance from an unrelated successful ping.

## Interpretation

### PASS-NO-SURVIVAL

The marked entry is destroyed by the tested interface-generation transition. The specific
stale inheritance hypothesis is rejected for that kernel transition.

### PASS-NO-INHERITANCE

The stale entry survives but deliberate tuple reuse does not inherit its marked established
state.

### STALE-INHERITANCE

Generation B reuses the stale marked conntrack entry. This is an architecture finding, not
a harness failure. The backend then needs a narrow generation-boundary mechanism before its
generation-isolation proof is complete.

Do not respond by globally flushing conntrack. Any remediation must first be reviewed for
scope and coexistence with unrelated ROU flows.

## Requirements

- root;
- iproute2;
- nftables;
- iputils-ping;
- conntrack;
- setpriv;
- Python 3.

The harness creates and cleans only disposable namespaces and a temporary capability-free
ping copy.

## Artifact

`design/NG2/code/python/rou/tests/integration_probe_conntrack_generation.py`
