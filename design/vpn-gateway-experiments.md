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
| EXP-074 | authoritative current host managed-destination routing |
| EXP-075 | Profile SNAT identity reverse reachability |
| EXP-076 | combined Profile SNAT dataplane |

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
| EXP-014 | PREPARED / UNPROVEN | superseded | Historical predecessor for remote-initiated multi-path return pinning; EXP-062 is the current scoped experiment. |
| EXP-025 | TARGET-CONFIRMED NEGATIVE FINDING | historical_only | Proves stale probe conntrack identity can survive interface replacement; retained as a real lower-level limitation, but not by itself a Release-1 correctness failure. |
| EXP-026 | PRIVILEGED-CI PASS / target confirmation open | not_selected | Narrow probe-class conntrack cleanup works in CI, but Release 1 deliberately does not adopt it: the complexity is not justified without material payload/path or accumulated-availability harm; re-enter only if such harm is demonstrated. |
| EXP-053 | PASS | historical_only | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. Host conntrack/RPDB stateful-return steering is no longer part of current architecture. The Linux fact remains historical evidence; no one-for-one successor is asserted. |
| EXP-054 | PREPARED / UNPROVEN | historical_only | Endpoint-pinning candidate lost applicability before execution. EXP-056 explicitly removed its immediate need, and current host-routing acceptance is EXP-074. No technical result is claimed. |
| EXP-055 | PREPARED / UNPROVEN | historical_only | Prepared composite host-boundary actuation lost applicability before completion because the host-return/bootstrap composite architecture was removed. No technical PASS is claimed. |
| EXP-056 | PASS | superseded | EXP-074 supersedes its current acceptance role: the stack-ingress `iif vpng0 -> main` bypass is retained inside the new authoritative managed-routing owner and is proven there together with the current routing semantics. |
| EXP-057 | FAIL | historical_only | Failed nft-marked bootstrap remains negative evidence for that removed candidate; current host routing no longer depends on packet marking for managed capture. |
| EXP-058 | PASS | superseded | The comparative dedicated-table/main-specificity fallback was superseded first by the selected paired-RPDB mechanism EXP-059; current host-routing semantics are now covered by EXP-074. |
| EXP-059 | PASS | superseded | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. EXP-074 supersedes the paired-RPDB specificity-preserving mechanism for current host-routing acceptance. |
| EXP-060 | PASS | superseded | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. The selected paired-RPDB backend remains a valid fact about that removed mechanism, but EXP-074 supersedes its current host-routing acceptance role with authoritative managed-destination routing. |
| EXP-061 | PASS | selected | Selected Release-1 Profile-routing-domain return affinity evidence. |
| EXP-062 | PASS | deferred | Concrete-path affinity is technically proven and retained as a possible future inbound/bidirectional multipath extension; the current baseline remains single-path until an explicit product decision re-enters this work. |
| EXP-063 | FAIL | historical_only | The failed transient cross-boundary Profile-tag carrier remains valid negative evidence. Its applicability to current implementation is gone because Profile SNAT no longer exports Profile/behavior metadata to HOST; EXP-076 removes the need for the carrier rather than reinterpreting this FAIL. |
| EXP-064 | PASS | superseded | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. The four host behavior lanes lost applicability when host stateful/route-return behavior and host-side gateway NAT were removed. EXP-074 replaces the host-routing role; EXP-076 replaces the Profile-SNAT applicability/return role. |
| EXP-065 | PASS | selected | Confirms current Linux representation/lookup behavior for the tested uidrange + ICMP + target selector subset. It does **not** prove that subset sufficient for multi-path path discrimination; recovered EXP-022/023 evidence requires an additional exact `oif` selector. |
| EXP-066 | PASS | selected | Confirms current nft JSON/handle shape for the accepted EXP-024 probe local OUTPUT/INPUT admission and proves same-name/new-ifindex replacement exposes the old raw ifindex instead of falsely confirming the replacement. |
| EXP-067 | PASS | selected | Confirms one-shot ICMP execution under the selected non-root UID/RPDB/nft probe plane and the technical mapping exit 0=reply, exit 1=no-reply, other=local error; test timeout is not a product guarantee. |
| EXP-068 | PASS | selected | Confirms the already accepted continuous-availability failover and sticky-recovery chain on real Linux route state. |
| EXP-069 | PASS | historical_only | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. No tested direct nft-usable local-only carrier survived the former stack→host metadata boundary, but the carrier-selection question lost applicability when host behavior lanes/Profile metadata export were removed. No successor is asserted because current design removes the need rather than replacing the carrier. |
| EXP-070 | PASS | selected | Current applicability is the routed-veth/Proxy-ARP managed-L3 endpoint and Debian-12/Linux-6.1 portability. **Partially superseded by EXP-075 only for stack-SNAT reverse reachability**. Netkit/other candidate observations remain valid experiment facts but do not define a supported current backend. |
| EXP-071 | PASS | selected | Retained only as comparative selection evidence: no demonstrated steady-state dataplane reason requires netkit over the Debian-12-compatible routed-veth boundary. It does **not** define a dual-backend/current netkit capability. |
| EXP-072 | PASS | selected | **Partially superseded by EXP-074** for current bootstrap/host-routing semantics, including the removed host-`main` specificity escape. Retained selected fact: device-only managed-prefix routing works on the current routed-veth/Proxy-ARP endpoint; its netkit equivalence result is no longer a supported-backend promise. |
| EXP-073 | PASS | historical_only | Logical state: **PROVEN FACT / SUPERSEDED DESIGN**. The tested gateway-less stateful host-return owner lost applicability because that owner was removed. Current routing/return coverage is provided by EXP-074 plus STACK flow affinity, with Profile-SNAT reverse coverage in EXP-075/076; no one-for-one successor is claimed. |
| EXP-074 | PASS | selected | Current authoritative host managed-routing acceptance evidence. Supersedes EXP-056/059/060 and the host-routing acceptance role of EXP-072; the result records the coverage transition explicitly. |
| EXP-075 | PASS with rejected baseline | selected | Current Profile-SNAT reverse-reachability evidence. Partially supersedes only EXP-070's stack-SNAT reverse-route interpretation; retains EXP-070 boundary/backend evidence. |
| EXP-076 | PASS | selected | Current combined Profile-SNAT dataplane acceptance evidence. Supersedes EXP-064 for the Profile-SNAT applicability/return architecture; EXP-063 remains retained negative carrier evidence. |
