# VPN-GATE NG3 experiment register

The active `main` contains only experiments belonging to the current NG3 line.
Historical experiments EXP-001..EXP-027 remain preserved on the corresponding legacy
branches and may be referenced explicitly when their kernel claim is reused.

Current experiment directories:

| Range | Scope |
| --- | --- |
| EXP-028..EXP-034 | lower policy space, structural routing, forwarding barrier, nft ownership/scaffold and payload NAT |
| EXP-035..EXP-040 | payload forwarding, return path, endpoint provenance and managed INPUT/OUTPUT scaffold |
| EXP-041..EXP-047 | Device firewall and local publication |
| EXP-048 | structural route/RPDB mutation |
| EXP-049 | administrator VPN onboarding applicability |
| EXP-050 | bounded VPN lifecycle applicability |
| EXP-051 | first functioning alpha |
| EXP-052 | host-side server publication DNAT lower evidence |
| EXP-053 | host-side conntrack return steering into managed stack |
| EXP-054 | host underlay endpoint pinning before full-tunnel bootstrap |
| EXP-055 | composite host-boundary actuation |
| EXP-056 | host-ingress bootstrap bypass without main-table capture |
| EXP-057 | nft-marked host bootstrap without main-table routes |
| EXP-058 | dedicated bootstrap table preserving ordinary main specificity |
| EXP-059 | paired RPDB bootstrap with suppress-prefixlength |
| EXP-060 | selected paired-RPDB host bootstrap backend |
| EXP-061 | stack established-flow return affinity across host boundary |
| EXP-062 | inbound multipath concrete-path affinity inside managed stack |
| EXP-063 | Profile-association handoff for ordinary-side gateway NAT |
| EXP-064 | fixed host-boundary behavior lanes for remote-initiated traffic |
| EXP-065 | Release-1 probe RPDB uidrange/ipproto/target selector shape |
| EXP-066 | Release-1 probe local nft owner representation / ifindex-generation shape |
| EXP-067 | Release-1 one-shot ICMP Driver execution / exit semantics |
| EXP-068 | continuous availability failover and sticky recovery |
| EXP-069 | stack-to-tambour metadata carrier search |
| EXP-070 | routed managed-stack endpoint candidates / Debian 12 routed-veth portability |
| EXP-071 | managed-boundary dataplane race: netkit L3 vs routed veth |
| EXP-072 | managed-L3 endpoint device-only host bootstrap equivalence |
| EXP-073 | routed managed-L3 gateway-less stateful return |
| EXP-074 | aggressive-helper authoritative managed-destination routing |
| EXP-075 | Profile SNAT identity reverse reachability |
| EXP-076 | combined Profile SNAT dataplane |
| EXP-077 | Release-1 peaceful host-routing helper |
| EXP-078 | scoped peaceful host-routing selectors |
| EXP-079 | managed-boundary absolute helper bypass |
| EXP-080 | scoped preserve-main non-interference |

Each experiment directory owns its README, harness and result evidence. The experiment number
is stable; historical results are not renumbered when referenced from NG3.


## Result vs disposition

The experiment artifact owns the technical **Result**. The registry owns the later
project-level **Disposition**. A disposition is assigned or changed only after the experiment
has completed and its result has been discussed; it never changes the technical Result.

Canonical dispositions:

- `pending_decision` — experiment completed, adoption decision not yet made;
- `selected` — evidence/mechanism is selected for current architecture;
- `not_selected` — technically available evidence/mechanism is deliberately not adopted;
- `deferred` — adoption decision or use is intentionally postponed behind a named gate;
- `superseded` — a newer experiment/result replaces this one for the same decision;
- `historical_only` — retained only as historical evidence/context.

### Disposition ledger

| Experiment | Result | Disposition | Note |
| --- | --- | --- | --- |
| EXP-014 | PREPARED / UNPROVEN | superseded | Historical predecessor for remote-initiated multi-path return pinning; this disposition selected EXP-062 as the scoped successor evidence. EXP-062's own registry entry is authoritative for its later/current status. |
| EXP-025 | TARGET-CONFIRMED NEGATIVE FINDING | historical_only | Proves stale probe conntrack identity can survive interface replacement; retained as a real lower-level limitation, but not by itself a Release-1 correctness failure. |
| EXP-026 | PRIVILEGED-CI PASS / target confirmation open | not_selected | Narrow probe-class conntrack cleanup works in CI, but Release 1 deliberately does not adopt it: the complexity is not justified without material payload/path or accumulated-availability harm; re-enter only if such harm is demonstrated. |
| EXP-050 | PASS | selected | Selected evidence for the supported bounded VPN lifecycle/integration contract: `VPNG0001-R1.R3.C1.R1.R2`, `VPNG0001-R1.R3.C3.R1`, `VPNG0004-R4.R6`, `VPNG9101-R1.R1.R4`, `VPNG9101-R1.R1.R5`, `VPNG9101-R1.R1.R6.R2`, `VPNG9101-R1.R1.R6.R3`. The former process-only `VPNG9001-R1.R1.R7.R1.R1` requirement is retired; the experiment dossier retains its historical trace unchanged. |
| EXP-053 | PASS | historical_only | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. Host conntrack/RPDB stateful-return steering is no longer part of current architecture. The Linux fact remains historical evidence; no one-for-one successor is asserted. |
| EXP-054 | PREPARED / UNPROVEN | historical_only | Endpoint-pinning candidate lost applicability before execution. Its old host-bootstrap requirement links were removed on 2026-11-20; no current acceptance role or technical result is claimed. |
| EXP-055 | PREPARED / UNPROVEN | historical_only | Prepared composite host-boundary actuation lost applicability before completion because the host-return/bootstrap composite architecture was removed. No technical PASS is claimed. |
| EXP-056 | PASS | superseded | EXP-074 supersedes its authoritative/aggressive acceptance role: the stack-ingress bypass is retained and proven there. This does not select authoritative precedence for the simple lifecycle helper. |
| EXP-057 | FAIL | historical_only | Failed nft-marked bootstrap remains negative evidence for that removed candidate; current host routing no longer depends on packet marking for managed capture. |
| EXP-058 | PASS | superseded | The comparative mechanism was superseded for the authoritative-routing decision; its main-specificity observations remain historical lower evidence and do not define the simple helper. |
| EXP-059 | PASS | superseded | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. EXP-074 supersedes it for the aggressive authoritative-routing child. Its specificity-preserving fact may inform a future simple-helper lowering but is not reselected by this review. |
| EXP-060 | PASS | superseded | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. The production-shaped paired-RPDB backend remains valid evidence for that mechanism; EXP-074 supersedes it only for the aggressive authoritative-routing child. |
| EXP-061 | PASS | selected | Selected Release-1 Profile-routing-domain return affinity evidence. |
| EXP-062 | PASS | deferred | Concrete-path affinity is technically proven and retained as a possible future inbound/bidirectional multipath extension; the current baseline remains single-path until an explicit product decision re-enters this work. |
| EXP-063 | FAIL | historical_only | The failed transient cross-boundary Profile-tag carrier remains valid negative evidence. Its applicability to current implementation is gone because Profile SNAT no longer exports Profile/behavior metadata to HOST; EXP-076 removes the need for the carrier rather than reinterpreting this FAIL. |
| EXP-064 | PASS | superseded | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. The four host behavior lanes lost applicability when host stateful/route-return behavior and host-side gateway NAT were removed. EXP-074 replaces the host-routing role; EXP-076 replaces the Profile-SNAT applicability/return role. |
| EXP-065 | PASS | selected | Confirms current Linux representation/lookup behavior for the tested uidrange + ICMP + target selector subset. It does **not** prove that subset sufficient for multi-path path discrimination; recovered EXP-022/023 evidence requires an additional exact `oif` selector. |
| EXP-066 | PASS | selected | Confirms current nft JSON/handle shape for the accepted EXP-024 probe local OUTPUT/INPUT admission and proves same-name/new-ifindex replacement exposes the old raw ifindex instead of falsely confirming the replacement. |
| EXP-067 | PASS | selected | Confirms one-shot ICMP execution under the selected non-root UID/RPDB/nft probe plane and the technical mapping exit 0=reply, exit 1=no-reply, other=local error; test timeout is not a product guarantee. |
| EXP-068 | PASS | selected | Confirms the already accepted continuous-availability failover and sticky-recovery chain on real Linux route state. |
| EXP-069 | PASS | historical_only | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. No tested direct nft-usable local-only carrier survived the former stack→host metadata boundary, but the carrier-selection question lost applicability when host behavior lanes/Profile metadata export were removed. No successor is asserted because current design removes the need rather than replacing the carrier. |
| EXP-070 | PASS | selected | Current Release-1 applicability is the routed-veth/Proxy-ARP managed-L3 endpoint and Debian-12/Linux-6.1 portability. **Partially superseded by EXP-075 only for stack-SNAT reverse reachability**. Netkit observations remain valid evidence for a possible future alternative realization of the same managed-L3 contract, but do not define a supported Release-1 backend. |
| EXP-071 | PASS | selected | Retained as comparative selection evidence: netkit is a viable alternative managed-L3 realization, but no demonstrated steady-state dataplane advantage justifies Release-1 dual-backend machinery over the Debian-12-compatible routed-veth boundary. It does **not** define a current netkit capability. |
| EXP-072 | PASS | selected | Retained selected fact: device-only managed-prefix routing works on the current routed-veth/Proxy-ARP endpoint; its netkit equivalence result remains future-backend evidence. Its former paired-RPDB host-bootstrap semantics are not current simple-helper architecture; EXP-074 separately covers the aggressive authoritative child. |
| EXP-073 | PASS | historical_only | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. The tested gateway-less stateful host-return owner lost applicability because that owner was removed. Core return affinity is now owned inside STACK; EXP-074 covers only the postponed aggressive host-routing child, while Profile-SNAT reverse lower evidence remains in EXP-075/076. |
| EXP-074 | PASS | selected | Exact closure evidence for `VPNG0001-R5.R2.R1`, the authoritative managed-destination child of the aggressive host-routing helper. The aggressive capability is constrained out of Release 1; EXP-074 does not define simple-helper or core host-routing semantics. |
| EXP-075 | PASS with rejected baseline | selected | Selected lower evidence for the SNAT-identity route form across the addressless managed-L3 boundary. Core Profile SNAT still promises only source identity at the managed boundary; helper/admin host reachability is separate. Partially supersedes only EXP-070's reverse-route extrapolation. |
| EXP-076 | PASS | selected | Current combined core Profile-SNAT dataplane acceptance evidence. Its tested host-return route remains ancillary integration evidence, not a core host-routing ownership promise. Supersedes EXP-064 for Profile-SNAT applicability/metadata-carrier need; EXP-063 remains retained negative carrier evidence. |
| EXP-077 | PASS | selected | Selected complementary evidence for peaceful-helper main-first precedence and lifecycle-safe non-destructive cleanup. After scoped selectors were introduced, its former global behavior is the `:any` subcase; EXP-078 extends rather than supersedes it. |
| EXP-078 | PASS | selected | Selected privileged acceptance evidence for revised `VPNG0001-R5.R1.R1` selector scope: host-local, external, exact ingress, union and any dispatch preserve unselected ordinary-host routing, administrator non-default precedence and managed-boundary bypass. |
| EXP-079 | PASS | selected | Selected reusable lower evidence for absolute managed-boundary no-recapture: `iif <boundary> goto <post-helper nop>` skips helper lookup even when ordinary routing has no result; applies to peaceful and postponed aggressive helpers. |
| EXP-080 | PASS | selected | Selected correctness evidence for peaceful selector scope: global preserve-main can reorder unselected administrator RPDB policy; per-selector preserve+dispatch preserves unselected routing while retaining selected explicit-main precedence. |
