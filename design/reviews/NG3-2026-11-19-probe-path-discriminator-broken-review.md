# NG3 2026-11-19 — probe path discriminator recovery defect

## Verdict

**BROKEN — current NG3 probe RPDB/Driver slice lost the historical path discriminator.**

This finding blocks publication of the post-snapshot-108 explicit-target alpha integration
work as a completed main snapshot.

## Trigger

The explicit-target alpha projection correctly expands one Profile-level check:

```text
availability_check = "icmp/<IPv4>"
```

into one availability subject per current logical path.

For a multi-path outbound Profile those subjects naturally share the same target.

That exposed a lower contradiction in the current NG3 probe mechanism:

```text
same process UID
+ same ICMP protocol
+ same target
+ several probe tables/rules
```

Without another selector, Linux cannot choose which logical path's probe table is intended;
the first matching RPDB rule wins.

## Historical evidence recovered

The original EXP-022 PASS did **not** prove merely:

```text
uidrange + ipproto + exact target -> probe table
```

It proved the combined selector:

```text
uidrange
+ ipproto icmp
+ exact target
+ oif <exact probe path>
    -> dedicated probe table
```

EXP-022 result explicitly records:

```text
uidrange 65534-65534
+ ipproto icmp
+ to 203.0.113.22/32
+ oif vpn0
    -> lookup 6022
```

The old executable Driver also bound the actual attempt to the requested path:

```text
ping ... -I <request.path.ifname> <target>
```

EXP-023 then validated the same mechanism on two simultaneous real OpenConnect bindings
reaching the same endpoint. Its primary selector was:

```text
to 172.21.201.19
oif vpns00
uidrange 0-0
ipproto icmp
lookup 6023
```

The primary path could fail while the secondary path remained healthy, and the primary probe
did not escape through the alternate binding.

Therefore `oif` + bound execution are part of the proven path-specific mechanism, not
optional decoration.

## Where NG3 lost it

The current recovery sequence simplified the selected RPDB discriminator to:

```text
uidrange + ICMP + exact target
```

EXP-065 proved the current iproute2 JSON/lookup shape for that reduced selector, but it tested
only one path and therefore could not prove multi-path discrimination.

Current `ProbeRuleSpec` carries no concrete endpoint selector.

Current `LinuxProbeRoutingBackend.add_rule()` does not render `oif`.

Current `LinuxIcmpProbeDriver` invokes numeric one-shot ping without `-I <path>`.

EXP-067 likewise used one path, so its PASS proves one-shot execution/exit semantics but not
multi-path path selection.

## Observable failure mode

For one Profile:

```text
ordered paths = (A, B)
availability target = T
probe process UID = U
```

current NG3 would attempt to install:

```text
priority P1: uid U + ICMP + target T -> table A
priority P2: uid U + ICMP + target T -> table B
```

Both selectors match the same unbound ICMP attempt.

The lower-priority rule cannot select B while the first rule is present.

A successful B observation could therefore actually travel through A, violating the core
availability invariant:

> a path-specific probe must not escape through or be answered through another Device/path.

## Required correction

Do not solve this by inventing per-path UIDs merely because they would also discriminate the
rules. The accepted historical mechanism already has direct evidence.

The next cycle should recover the materially same path selector:

1. extend probe RPDB semantic/observed rule identity with concrete output-path selector;
2. prove current `ip -j -N rule` representation for `oif` and same-name/new-ifindex
   behavior;
3. render/delete the exact `oif` selector in `LinuxProbeRoutingBackend`;
4. bind `LinuxIcmpProbeDriver` attempts to the current concrete path using the proven
   `-I <ifname>` form while retaining current-generation checks;
5. add a privileged **two-path / same-target** regression proving each probe selects its own
   table/path and cannot escape through the other;
6. update EXP-065 interpretation: it remains useful JSON evidence for uid/ipproto/target
   fields but is not sufficient evidence for the full path-specific selector;
7. only then resume explicit-target alpha assembly.

The existing fail-closed probe route/RPDB convergence from snapshot 108 remains conceptually
valid, but its rule identity must include the recovered output-path discriminator.

## Requirement-state inventory

Normative R/C closure is unchanged.

Active implementation/design state:

- `broken`: **probe path discriminator incomplete — historical `oif` RPDB selector and
  bound Driver execution were omitted during NG3 recovery**;
- `decomp`: none pending;
- `unreal`: none;
- `[rejected_closure]`: none.

## Main publication boundary

Snapshot 108 remains the last code-bearing published snapshot before this correction note.

The post-snapshot-108 explicit-target integration branch is retained as working material but
must not be snapshotted wholesale until this broken discriminator is repaired and the
dependent slice is reverified.
