# VPN-GATE — Experiment Log

## EXP-003 — First live end-to-end happy-path gateway

### Motivation

Validate the RC2.5.1 happy-path implementation on a real Debian 13 gateway with an
already-established OpenConnect transport and a real protected-network target. This is the
first test of the complete forwarding path rather than isolated route/firewall adapters.

### Topology

```text
allowed Windows LAN host
  -> <gateway-lan-ip>  vpn-gatewayd / ocserv
  -> vpns0 172.20.130.1
  -> 172.20.130.5     OpenConnect client (tun0)
  -> <oc-client-lan-ip>  client LAN side / ens18
  -> <lan-router-ip>    LAN router
  -> <protected-target-ip>     protected-network target
```

Gateway profile:

```toml
managed_vpns = ["oc"]
common_allowed_sources = []

[vpn.oc]
interface = "vpns0"
network = "172.20.130.0/29"
local_address = "172.20.130.1"
peers = ["172.20.130.5"]
routes = ["10.0.0.0/8"]
allowed_sources = ["<allowed-source>"]
```

OpenConnect client forwarding/NAT used for this test:

```text
net.ipv4.ip_forward = 1
-P FORWARD ACCEPT
-A POSTROUTING -s 172.20.130.0/29 -o ens18 -j MASQUERADE
```

### Boundary preflight

After the first RC2.5 live attempt exposed that Debian 13
`iptables-save` does not support `-w`, RC2.5.1 was produced. Before retrying the daemon,
the exact external CLI forms used by the corrected adapter were checked manually:

```text
iptables-save filter rc=0
iptables-save nat rc=0
iptables-restore rc=0
```

The tested restore form was an empty `*filter ... COMMIT` payload with
`iptables-restore -w 5 --noflush`; it made no policy changes.

### Result

**Run:** 2026-11-07/08 local lab time  
**Implementation:** RC2.5.1  
**Architecture:** RC2.4.1

Foreground startup completed and remained running.

Observed gateway state:

```text
net.ipv4.ip_forward = 1
blackhole 10.0.0.0/8 metric 65536
10.0.0.0/8 via 172.20.130.5 dev vpns0 metric 10 onlink
```

The route listings were queried separately by owned protocol (`201` for the blackhole and
`202` for the VPN unicast route).

Observed fixed policy included the expected daemon-owned chains and prefix jumps:

```text
INPUT       -> VPNG-OC-INPUT
FORWARD     -> VPNG-INGRESS
FORWARD     -> VPNG-RESERVED
FORWARD     -> VPNG-OC-FORWARD
POSTROUTING -> VPNG-OC-NAT
```

The profile FORWARD chain admitted only the configured source toward `10.0.0.0/8`, then
rejected the remaining traffic for that destination. The NAT chain contained:

```text
-o vpns0 -m addrtype ! --src-type LOCAL -j MASQUERADE
```

End-to-end comparison from the allowed Windows LAN host:

Before adding the test route:

```text
1  <lan-router-ip>
2  <protected-target-ip>
```

After adding `10.0.0.0/8 via <gateway-lan-ip>`:

```text
1  <gateway-lan-ip>
2  172.20.130.5
3  <lan-router-ip>
4  <protected-target-ip>
```

The target remained reachable after the route change. The trace therefore visibly traversed
the intended vpn-gatewayd host and OpenConnect peer before returning to the LAN router and
reaching the protected target.

### Decision

**EXP-003 result: PASS.**

RC2.5.1 is confirmed to provide a working initial happy path for this topology:

- startup cleanup and materialization complete successfully;
- `ip_forward` is enabled only after policy/route setup;
- owned blackhole and preferred VPN unicast route coexist as designed;
- fixed INPUT/FORWARD/NAT policy permits the configured source and egress;
- server-side MASQUERADE through `vpns0` works in the end-to-end path;
- the OpenConnect client can forward the tunnel traffic onward when its forwarding and
  egress MASQUERADE are configured;
- a real LAN client reaches a real `10.0.0.0/8` target through the complete path.

This experiment does **not** validate graceful shutdown cleanup, crash behavior, runtime
drift repair, periodic reconciliation, or Netlink self-healing. Those remain separate work.


**Current architecture:** [VPN Gateway Architecture RC2.4.1](vpn-gateway-architecture-rc2.wip.md)

This document is the laboratory record for implementation/research questions that must be resolved on the target Debian environment. Each experiment records:

- the architecture requirement that motivated it;
- the exact hypothesis and safety boundary;
- the procedure and artifacts;
- observed results;
- the resulting implementation/architecture decision.

Experimental results are not silently promoted into architecture. A result first appears here; if it changes a requirement or implementation contract, the corresponding architecture revision is referenced explicitly.



---

## EXP-002A — Address inventory follow-up

**Status:** COMPLETE — PASS  
**Architecture baseline:** RC2.4.1  
**Target:** Debian 13 gateway/test host, stock iproute2  
**Script:** `vpn-gateway-exp-002a-address-inventory.sh`

### Motivation

EXP-002 demonstrated that `ip -j -4 addr show` omits an interface with no IPv4 address.
RC2.4.1 changes `SubprocessKernelInterface.list_interface_ipv4()` to read
`ip -j addr show` and filter IPv4 records in Python.

This follow-up runs the **actual RC2.4.1 adapter** inside a disposable network namespace.

### Pass criteria

The adapter snapshot must report:

```text
empty0 -> frozenset()
p2p0   -> {172.20.140.1}
```

The P2P remote endpoint field is intentionally ignored; only `local` participates in
readiness.

### Procedure

```bash
git pull --ff-only
cd "design/RC2/experiments/EXP-002A Address inventory follow-up"
sudo ./vpn-gateway-exp-002a-address-inventory.sh
```

### Result

Observed output:

```text
empty0 = frozenset()
p2p0   = frozenset({IPv4Address('172.20.140.1')})
EXP-002A OVERALL=PASS
```

### Decision

**EXP-002A result: PASS.**

The corrected RC2.4.1 address inventory contract is confirmed on the target Debian 13 /
iproute2 environment:

- an existing interface with no IPv4 address remains present with an empty IPv4 set;
- a point-to-point interface is represented by its local IPv4 address;
- remote peer/address fields do not participate in readiness.

Together with EXP-002, this closes the live validation of the RC2.4.1 route/address
`SubprocessKernelInterface` boundary. The next implementation block is
`_apply_plan()` / `_verify_plan()`.


## EXP-002 — Route adapter iproute2 live smoke

**Status:** COMPLETE — FAIL (one actionable adapter mismatch)  
**Architecture baseline:** RC2.4  
**Target:** Debian 13 gateway/test host, stock iproute2  
**Script:** `vpn-gateway-exp-002-route-adapter-smoke.sh`  
**Script SHA256:** `57658923a76d94a4926968cfd2a2dd6bdf6a373190c73bc88e280005403ac346`

### Motivation

RC2.4 implements the route/address part of `SubprocessKernelInterface` against iproute2 JSON
and explicit `ip route add|del|replace` command forms. Before `_apply_plan()` and
`_verify_plan()` depend on this boundary, the assumptions must be checked against the
actual Debian 13 target environment.

The experiment verifies both JSON inventory shape and the exact mutation forms emitted by
the adapter.

### Safety boundary

The experiment does **not** change host routing, addresses, firewall, NAT or forwarding.

All interfaces, addresses and routes are created inside one disposable network namespace.
The namespace is removed explicitly before artifact packaging and also by an EXIT trap.

Host-visible effects are limited to:

- temporary network namespace creation/removal;
- files written into the current working directory.

### Hypotheses

- **H1 — numeric protocol inventory:** `ip -j -N -4 route show table main` represents
  a connected kernel route with numeric `RTPROT_KERNEL = 2`.
- **H2 — UNICAST round-trip:** the exact RC2.4 UNICAST form can be added, identically
  replaced, observed without canonical identity drift, and deleted using the full
  `RouteSpec` fields including `proto 202`, metric, via/dev and `onlink`.
- **H3 — BLACKHOLE round-trip:** the exact BLACKHOLE form with `proto 201 metric 65536`
  can be added and deleted.
- **H4 — RTPROT_BOOT normalization:** a route added without explicit protocol is represented
  either with omitted protocol or numeric `3`, and can subsequently be deleted with
  explicit `proto 3`.
- **H5 — IPv4 address inventory:** `ip -j -4 addr show` keeps an interface with no IPv4
  as an entry with empty `addr_info`, and a point-to-point-shaped record exposes the
  local address through `addr_info[].local` independently of `peer`.
- **H6 — supported route forms:** BLACKHOLE, UNREACHABLE, PROHIBIT, THROW and default
  UNICAST routes have the JSON type/protocol/metric representation expected by RC2.4.

### Procedure

From the repository root on the Debian 13 test host:

```bash
git pull --ff-only
cd "design/RC2/experiments/EXP-002 Route adapter iproute2 live smoke"
sudo ./vpn-gateway-exp-002-route-adapter-smoke.sh
```

The script creates:

```text
vpn-gateway-exp-002-<UTC timestamp>/
vpn-gateway-exp-002-<UTC timestamp>.tar.gz
vpn-gateway-exp-002-<UTC timestamp>.tar.gz.sha256
```

The result directory contains environment data, raw route/address JSON snapshots,
per-command return codes/stdout/stderr and `result.txt`.

### Result

**Run:** `2026-11-07T17:03:04Z`  
**Host:** `testing`  
**Archive SHA256:** `8f905a83df018cfeef5d4c00387b05beeaae5b0ee6b9f3f8a7988ab7c5badf1c`

Environment:

```text
Debian GNU/Linux 13.7 (trixie)
kernel: Linux 6.12.115+deb13.1-amd64
iproute2: 6.15.0
libbpf: 1.5.0
Python: 3.13.5
```

Observed analyzer result:

```text
H1 numeric route protocol inventory: PASS
H2 UNICAST add -> replace -> delete: PASS
H3 BLACKHOLE add -> delete: FAIL
H4 RTPROT_BOOT normalization/delete: PASS
H5 IPv4 address local/peer/empty interface shape: FAIL
H6 supported route types/default JSON shape: FAIL
OVERALL=FAIL
```

The raw observations show three distinct findings.

#### Finding A — `-N` numeric route types: analyzer false negatives

For non-UNICAST route types, `ip -j -N` returned numeric decimal strings:

```text
BLACKHOLE   -> "type": "6"
UNREACHABLE -> "type": "7"
PROHIBIT    -> "type": "8"
THROW       -> "type": "9"
```

RC2.4 adapter already accepts these numeric/string forms in `_parse_route_type()`.
Therefore the H3/H6 FAIL labels were caused by EXP-002 expecting textual type names,
not by an adapter defect.

H3's add/delete commands themselves succeeded and the BLACKHOLE route had the expected
`proto=201` and `metric=65536`.

#### Finding B — P2P remote-peer field: analyzer false negative

The point-to-point record was:

```json
{"family":"inet","local":"172.20.140.1","address":"172.20.140.2","prefixlen":32,...}
```

The remote endpoint is exposed as `address`, not `peer`, on this iproute2 build.
The adapter deliberately consumes only `addr_info[].local`, so the observed local address
matches the runtime readiness contract. No adapter change is required for P2P semantics.

#### Finding C — addressless interface omission: real adapter mismatch

`empty0` was absent from `ip -j -4 addr show`.

Therefore RC2.4 could not satisfy its own `KernelInterface.list_interface_ipv4()` contract:

```text
existing interface without IPv4 -> empty frozenset
missing key -> interface does not exist
```

This distinction is not currently required to decide readiness (both states are not-ready),
but it is part of the kernel-boundary contract and must not be represented incorrectly.

### Decision

EXP-002 produced one actionable implementation correction:

```text
ip -j -4 addr show
        ->
ip -j addr show
```

The adapter now reads the complete interface/address snapshot and filters
`addr_info[].family == "inet"` in Python. This preserves addressless interfaces as
empty IPv4 sets without introducing a second independently sampled `ip link` snapshot.

The route parser/mutator design is retained. Architecture RC2.4.1 records the actual
numeric route-type behavior and the corrected address inventory command.

A narrow EXP-002A validates the corrected adapter itself against the target iproute2.


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
| `backup` | `wg0` | `172.20.126.0/29` | `100.64.0.0/10`, `192.168.0.0/16` | `<protected-target-ip>/32` |
| `primary` | `vpns0` | `172.20.130.0/29` | `10.0.0.0/8` | `<protected-target-ip>/32`, `10.200.201.0/24` |

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

The post-experiment architecture/deployment updates were incorporated in RC2.1.
