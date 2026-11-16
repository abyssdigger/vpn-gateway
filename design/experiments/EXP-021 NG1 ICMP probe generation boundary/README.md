# EXP-021 — NG1 ICMP probe admission and interface-generation boundary

> **Current interpretation:** ICMP is a proven candidate availability *condition*, not the
> definition of availability. Availability is the current ON/OFF result for a
> `(Profile, concrete binding)` pair. That result is never persisted. Exact ifindex reuse
> therefore constrains control-plane generation handling, but never licenses restoration
> of an old availability result.

**Status:** PASS — target Debian 13 kernel/mechanism evidence  
**Architecture baseline:** NG1 Draft 5 production source baseline  
**Type:** disposable-netns kernel/mechanism experiment

## Purpose

Establish the kernel/mechanism facts required before production availability policy is
fixed.

EXP-021 deliberately does **not** choose probe cadence, timeout, failure threshold,
recovery threshold, or persistence policy. It tests whether the proposed ICMP mechanism can
be narrow, unprivileged and bound to the intended Device path, and where numeric ifindex
identity stops being a sufficient generation discriminator.

## Questions

1. Can ICMP echo run with every process capability, including CAP_NET_RAW, removed when a
   namespace-local `net.ipv4.ping_group_range` admits the probe gid?
2. Before probe-specific nft admission is installed and verified, does default-DROP keep
   the detector effectively unarmed?
3. Can admission be limited to exactly:
   - OUTPUT: selected numeric oif + one destination + ICMP echo-request;
   - INPUT: selected numeric iif + the same remote source + ICMP echo-reply?
4. Do other remote addresses and non-ICMP local traffic remain blocked?
5. If an alternate Device/path can reach the same target, can the probe avoid silently
   escaping through it?
6. Does same-name/new-ifindex replacement fail closed against stale numeric nft rules?
7. If Linux is explicitly asked to recreate the interface with the **same ifindex**, do the
   stale numeric nft rules admit the new interface generation?
8. Are the tested direct-device routing semantics suitable for the WG/OC-shaped active path
   evidence established by EXP-019/020?

## Safety boundary

The script uses only disposable network namespaces and veth interfaces. It does not modify
host routes, host nftables, host sysctls, ocserv/OpenConnect, or WireGuard configuration.

The only sysctl changed is `net.ipv4.ping_group_range` inside the disposable ROU namespace.

## Topology

```text
                    primary Device
             198.18.21.0/30
  exp21-pri <----------------> exp21-rou
  target=203.0.113.21/32       vpn0

                    alternate Device
             198.18.22.0/30
  exp21-alt <----------------> exp21-rou
  target=203.0.113.21/32       alt0
```

The same target exists behind both disposable peers. ROU normally has an explicit /32
route through `vpn0`; after that route is removed, ordinary lookup resolves through
`alt0`. This makes alternate-path escape observable without touching the host network.

## Probe privilege model under test

The probe runs as uid/gid 65534 with:

- empty effective/permitted/inheritable/ambient capability sets;
- empty capability bounding set;
- `no_new_privs`;
- namespace-local `ping_group_range = 65534 65534`.

A successful echo in that state is evidence that CAP_NET_RAW is not required for this
mechanism on the target kernel/userspace combination.

## Exact-ifindex reuse interpretation

The exact-ifindex phase is diagnostic, not a preselected PASS/FAIL expectation.

If a newly created interface with the same numeric ifindex immediately matches stale nft
rules, EXP-021 records that fact explicitly. Such a result means numeric ifindex is a
routing/firewall generation discriminator only while the kernel index is not reused; H8
must then account for restart/missed-lifecycle reuse separately.

## Artifact

`exp-021-icmp-generation-boundary.sh`


## Attempt history

### Attempt 1 — HARNESS WHITESPACE BUG

The first target run reached namespace-local `ping_group_range` configuration, then the
harness compared the procfs rendering literally. The kernel rendered the two numeric fields
with tab/expanded whitespace, so the test rejected a correct value.

The comparison was corrected to parse exactly two numeric fields. No experiment hypothesis
was exercised by this failure.

### Attempt 2 — HARNESS EXPECTATION BUG IN ALTERNATE-PATH PHASE

The second target run proved unprivileged ICMP and narrow nft admission, then reported:

```text
ALTERNATE_ROUTE_GET=203.0.113.21 dev alt0 ...
FAIL: Device-bound probe escaped through alternate path
```

The failure was in the harness interpretation. `ping -I vpn0` remained bound to the
intended Device even though an ordinary unbound route lookup selected `alt0`. The narrow
nft policy also admitted only the concrete `vpn0` ifindex.

Stage 7 was corrected to require the bound probe to keep succeeding through `vpn0`, while
an otherwise identical unbound probe follows `alt0` and is rejected.

### Attempt 3 — PASS ON TARGET

Observed on the target Debian 13 system:

```text
PASS A: primary and alternate paths both reach the same target
PASS B: default-DROP prevents evidence before probe admission exists

PROBE_POLICY_VERIFIED_IFINDEX=2
CapInh: 0000000000000000
CapPrm: 0000000000000000
CapEff: 0000000000000000
CapBnd: 0000000000000000
CapAmb: 0000000000000000
NoNewPrivs:     1

PASS C: ICMP echo succeeds with empty capability sets; CAP_NET_RAW not required in this setup
PASS D: other destination and TCP traffic remain blocked

ALTERNATE_ROUTE_GET=203.0.113.21 dev alt0 src 198.18.22.2 uid 0
PASS E1: bound probe remains on vpn0 while ordinary route lookup selects alt0
PASS E2: unbound probe follows alt0 and is rejected by narrow nft admission

PASS F: same-name/new-ifindex=4 does not inherit stale rules for 2
PASS G: refreshed verified policy arms the new interface generation

EXACT_IFINDEX_REUSE_SUPPORTED=1
EXACT_IFINDEX_REUSED=4
EXACT_IFINDEX_STALE_NFT_MATCH=1
OBSERVATION: a fresh interface with the same numeric ifindex matches stale probe admission

EXP_021_ICMP_GENERATION_BOUNDARY=PASS
```

## Result and architectural consequence

EXP-021 establishes the following mechanism facts for production availability design:

1. **CAP_NET_RAW is not required for the tested ICMP probe mechanism.** A ping socket works
   as uid/gid 65534 with empty inheritable, permitted, effective, bounding and ambient
   capability sets, `NoNewPrivs=1`, and a namespace-local `ping_group_range` admitting
   only the probe gid.
2. **Probe admission can be narrow.** Default-DROP keeps the detector unarmed until the
   probe rules exist; the tested rules admit only one destination, echo request/reply and
   one concrete numeric interface generation. A second destination and TCP remained
   blocked.
3. **The probe can be bound to the intended Device path.** Even when ordinary routing
   selected another Device capable of reaching the same target, the interface-bound probe
   remained on the intended Device. The equivalent unbound probe followed the alternate
   route and was rejected by the narrow nft policy.
4. **Same name with a different ifindex fails closed against stale numeric rules.** This
   confirms the production same-name/new-ifindex lifecycle treatment.
5. **Numeric ifindex is not a globally unique interface-generation identifier.** Linux on
   the target allowed explicit recreation of a fresh interface with the same ifindex, and
   the stale numeric nft admission immediately matched that new interface.

The fifth result is the important H8 boundary. Numeric ifindex remains a useful
kernel-facing selector while a generation is continuously observed, but persisted
availability or persisted assumptions about generation identity must not treat a reused
ifindex as proof that the old interface generation survived a restart or missed lifecycle
event.

EXP-021 does not choose persistence semantics, probe cadence, timeout or hysteresis. Those
remain architecture/configuration decisions.
