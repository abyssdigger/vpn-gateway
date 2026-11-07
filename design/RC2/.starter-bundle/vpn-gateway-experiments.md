# VPN-GATE — Experiment Log

**Architecture baseline at experiment time:** [VPN Gateway Architecture RC2](vpn-gateway-architecture-rc2.md)  
**Decision incorporated into:** [VPN Gateway Architecture RC2.1](vpn-gateway-architecture-rc2.1.md)

This document is the laboratory record for implementation/research questions that must be resolved on the target Debian environment. Each experiment records:

- the architecture requirement that motivated it;
- the exact hypothesis and safety boundary;
- the procedure and artifacts;
- observed results;
- the resulting implementation/architecture decision.

Experimental results are not silently promoted into architecture. A result first appears here; if it changes a requirement or implementation contract, the corresponding architecture revision is referenced explicitly.

---

## EXP-001 — Fixed firewall/NAT canonical round-trip

**Status:** COMPLETE — PASS  
**Target:** Debian 13 gateway/test host using `iptables-nft`  
**Script:** `vpn-gateway-exp-001-iptables-roundtrip.sh`  
**Script SHA256:** `25b3e9d44eb59846de6c1db8ef16e9c806cbd3f6137214baa9f41650a112bfe2`

### Motivation

RC2 makes fixed firewall/NAT verification a prerequisite for both bootstrap and every runtime reconciliation pass. The daemon must distinguish:

- `SAFE` — daemon-owned fixed firewall/NAT exactly matches policy;
- `UNSAFE` — readable state with confirmed drift;
- `UNKNOWN` — state cannot be interpreted reliably.

A direct canonical-text comparison is desirable only if the daemon-owned subset emitted by `iptables-save` is stable enough after `iptables-restore`. Otherwise RC2 requires a minimal normalizer/parser for the daemon-owned subset rather than a general firewall AST.

### Architecture references

- **§8.2 — Runtime fixed firewall/NAT verification:** fixed infrastructure is verified before route/interface reconciliation; parse/normalization inability is `UNKNOWN`.
- **§9 — Firewall and blackhole:** deterministic owned chains, rule order and built-in jump placement.
- **§11 — NAT:** per-profile `VPNG-<PROFILE>-NAT` and fixed `MASQUERADE` are part of fixed infrastructure.
- **§24 — Implementation notes:** explicitly requires a target-host `iptables-restore -> iptables-save` round-trip experiment before deciding whether a normalizer/parser is necessary.
- **Invariant 134:** `iptables-restore` is atomic per table/`COMMIT`, not a cross-table transaction.
- **Invariant 148:** `MASQUERADE` belongs to the fixed firewall/NAT template and is verified with the rest of the infrastructure.
- **Invariant 153:** expected inventory/canonical parse/normalization failure is `UNKNOWN`; programming failures are not hidden.

### Safety boundary

The experiment **must not modify the host firewall**.

Every apply/save cycle runs in a disposable Linux network namespace. Inside that namespace the experiment creates the same `VPNG-*` chains and built-in jumps that RC2 specifies, but the namespace has no production traffic. The namespace is deleted after every cycle and also by an `EXIT` trap.

Host-visible effects are limited to:

- temporary network namespace creation/removal;
- loading already-available netfilter functionality if the kernel does that lazily;
- writing the result directory/archive in the current working directory.

### Test policy

Two managed profiles are represented, matching the RC2 examples closely:

| profile | interface | VPN network | protected routes | effective sources |
|---|---|---|---|---|
| `backup` | `wg0` | `172.20.126.0/29` | `100.64.0.0/10`, `192.168.0.0/16` | `10.200.200.8/32` |
| `primary` | `vpns0` | `172.20.130.0/29` | `10.0.0.0/8` | `10.200.200.8/32`, `10.200.201.0/24` |

The payload includes:

- deterministic `INPUT`, `FORWARD`, and `POSTROUTING` jumps;
- `VPNG-INGRESS`;
- `VPNG-RESERVED`;
- profile INPUT/FORWARD chains;
- conntrack state matching;
- `REJECT --reject-with icmp-host-prohibited`;
- static `MASQUERADE` with `-m addrtype ! --src-type LOCAL`.

### Comparison view

The experiment deliberately does **not** implement the future daemon normalizer.

For comparison it removes only:

1. `iptables-save` comment lines beginning with `#` (including generated/completed timestamps);
2. blank lines.

Everything else is compared byte-for-byte, line-for-line. Therefore any remaining diff is useful evidence rather than being hidden by a speculative normalizer.

### Hypotheses

#### H1 — deterministic materialization

Applying the exact same RC2 fixed firewall/NAT payload with:

```text
iptables-restore --noflush
```

in three fresh network namespaces produces identical comparison views.

**Pass criterion:** run 1 == run 2 == run 3.

#### H2 — canonical round-trip

The raw `iptables-save` output from H1/run 1 can itself be restored with `iptables-restore --noflush` into a fresh namespace, and the resulting `iptables-save` comparison view is unchanged.

**Pass criterion:** initial save == save after replay.

### Procedure

Run on the Debian 13 target/test host:

```bash
chmod 700 vpn-gateway-exp-001-iptables-roundtrip.sh
sudo ./vpn-gateway-exp-001-iptables-roundtrip.sh
```

The script produces a directory such as:

```text
vpn-gateway-exp-001-20261107-120000Z/
```

and a matching `.tar.gz`.

Important files:

```text
environment.txt
payload.rules

payload-run-1.raw
payload-run-1.norm
payload-run-2.raw
payload-run-2.norm
payload-run-3.raw
payload-run-3.norm

replay-save-1.raw
replay-save-1.norm

diff-payload-1-vs-2.txt
diff-payload-1-vs-3.txt
diff-save-vs-replay.txt

result.txt
```

### Result

**Run:** `2026-11-07T10:02:04Z`  
**Host:** `mytvpn`  
**Archive SHA256:** `bace8dfcee7921525bb53d15eb53f7a2e0a25854c65abbb213ee472a68267536`

Environment:

```text
Debian GNU/Linux 13.7 (trixie)
kernel: Linux 6.12.115+deb13.1-amd64
iptables: v1.8.11 (nf_tables)
iptables-save: v1.8.11 (nf_tables)
iptables-restore: v1.8.11 (nf_tables)
iproute2: 6.15.0
nftables: 1.1.3
iptables alternative: /usr/sbin/iptables-nft
```

Observed result:

```text
EXP-001 fixed firewall/NAT canonical round-trip
H1 same payload on fresh namespaces: PASS
  run1_vs_run2=PASS
  run1_vs_run3=PASS
H2 save -> restore -> save: PASS

OVERALL=PASS
Interpretation: after removing only volatile comments/blank lines,
the daemon-owned filter+nat representation is text-stable in this test.
This supports a minimal canonical-text comparator for the tested subset.
```

All three generated diff files are empty.

Normalized snapshot SHA256 values:

```text
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  payload-run-1.norm
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  payload-run-2.norm
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  payload-run-3.norm
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  replay-save-1.norm
```

Therefore:

- **H1 PASS:** the same payload materialized identically in three fresh network namespaces.
- **H2 PASS:** `iptables-save -> iptables-restore --noflush -> iptables-save` was stable.
- The comparison view required removal only of `iptables-save` comment lines and blank lines.

#### Observed canonicalization relative to input payload

The input `iptables-restore` payload is **not** itself the canonical comparison form.

`iptables-save` changed representation in deterministic ways, including:

1. user-defined chain declarations were emitted in canonical order rather than payload declaration order;
2. rules were emitted grouped by their owning chain rather than preserving the interleaving present in the input payload;
3. at least one rule had match options reordered, e.g. the payload form

   ```text
   -A VPNG-BACKUP-INPUT -i wg0 -s 172.20.126.0/29 -d 172.20.126.1/32 ...
   ```

   was emitted canonically as

   ```text
   -A VPNG-BACKUP-INPUT -s 172.20.126.0/29 -d 172.20.126.1/32 -i wg0 ...
   ```

After that first canonicalization, the saved representation was stable across fresh namespaces and a save/restore/save replay.

The raw files happened to be byte-identical in this run because all four saves occurred within the same timestamp second. This is **not** treated as evidence that raw `iptables-save` comments are stable; comments remain excluded from comparison by design.

### Decision

**EXP-001 result: PASS.**

For the tested Debian 13 / `iptables-nft` environment, RC2 does **not** need a semantic rule normalizer.

Implementation direction:

1. Parse `iptables-save` only far enough to identify tables, chains, chain contents, daemon-owned `VPNG-*` resources, and exact positions/uniqueness of daemon jumps in built-in chains.
2. Treat the individual rule text emitted by `iptables-save` as the canonical rule representation for this tested backend.
3. Compare daemon-owned rule strings/order in that canonical save form.
4. Strip only explicitly volatile material demonstrated by the experiment (`# ...` comments and blank lines).
5. Do not compare the original `iptables-restore` payload text directly with `iptables-save` output: the backend deterministically canonicalizes declaration/rule ordering and some option ordering.
6. If a future Debian/iptables version produces a previously unseen canonicalization difference, classify unparseable/uncomparable inventory as `UNKNOWN` as required by RC2, record a new experiment, and extend the minimal parser/normalizer only for demonstrated behavior.

A **minimal structural parser/extractor is still required** because the daemon must isolate its owned subset and verify built-in jump positions without assuming ownership of whole `filter`/`nat` tables. What EXP-001 eliminates is the need for a broader semantic firewall-rule normalizer.

This decision directly resolves the implementation/research question in RC2 §24.

The result was incorporated into RC2.1: memory-only `iptables-save`/`iptables-restore` I/O, minimal structural parsing, and canonical `iptables-save` rule-string comparison are now explicit architecture requirements.

### Follow-up

EXP-001 is closed.

Next implementation consequence:

- `_compare_fixed_firewall_nat()` should use a small `iptables-save` structural parser/extractor plus canonical rule-string comparison, not a general iptables AST and not direct payload-text comparison.

Separately, apply the already agreed post-experiment architecture/deployment updates: startup signal handling, service deployment recommendations, subprocess diagnostics, `ip_forward` read-before-write, periodic persistent-failure reminders, and related tests.