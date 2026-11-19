# VPN-GATE NG3 Python reference

Current executable scope is intentionally narrow and split into reviewed units.

Implemented:

- structural Device/Profile TOML normalization;
- canonical IDs, explicit `enabled`, strict IPv4 destinations and selector/quota validation;
- Release 1 inbound/bidirectional configured-capacity validation;
- authoritative `ip -j link show` interface identity parsing;
- stateless Linux `VPNPathAdapter` runtime observation that obtains one fresh complete managed-netns inventory per call, requires the verified host-boundary generation when supplied, and is used by controller startup plus alpha periodic reconcile;
- concrete endpoint identity as `(ifname, ifindex)`;
- pure stable-slot Device binding projection with bounded waiting-candidate order;
- delayed waiting promotion only after a removal projection can become committed;
- `PayloadProfileRequest` projection, including zero-path Profile preservation;
- outbound/inbound NEW-flow Profile classification with ingress-path restriction;
- pure disjoint most-specific Profile CIDR partition for global outbound and path-relative inbound classification, proven point-equivalent to the existing point classifiers; this is Profile permission only and does not apply Device traffic envelope or compile nft rules;
- bounded availability confirmation state;
- availability-only effective priority transformation with unchanged membership;
- pure make-before-break route-priority move planning for unchanged path membership;
- partial-state route-priority convergence from a fresh observed snapshot, including safe cleanup of already-confirmed duplicate route copies;
- single-attempt route-priority Executor contract with mandatory re-observation after failure and fresh final postcondition verification;
- strict owned route-key inventory projection from current iproute2 JSON and current interface/path identity;
- bounded physical iproute2 route-priority backend with link-sandwiched observation, whole-domain verification and exact add/delete commands;
- Profile-level multi-domain priority coordinator with deterministic domain order and final fresh verification of every destination domain;
- lower Adapter route-priority realization contract for internal table/protocol/path-route identity and validated Linux metric space;
- deterministic shared lower network-policy allocator over injected table/RPDB/route-metric/nft platform resource space;
- accepted EXP-028 Linux platform constants for table/RPDB/protocol/metric/nft namespaces;
- semantic Profile/allocation to per-destination route-priority domain assembly without inferring gateway/onlink semantics;
- explicit opt-in direct-device VPN integration route realizer from verified PathBinding objects;
- EXP-061-backed Release-1 stack established-flow return affinity: deterministic per-Profile mark/RPDB allocation, pure ingress classifier projection, authoritative Linux nft/RPDB owner observation with absent/exact/stale/conflict classification, guarded convergence behind a freshly confirmed disabled ForwardingGate, exact postcondition verification, production startup/reconcile composition before structural forwarding activation, and no blind adoption of foreign reserved state;
- complete immutable payload route/RPDB desired-state projection with terminal guards, per-destination path routes and host-boundary dispatch rules;
- strict read-only structural route/RPDB inventory over the entire reserved NG3 table/priority namespaces, with explicit owner-scoped conflicts for unrepresentable reserved objects;
- pure payload actual-vs-desired structural comparison producing confirmed/missing/stale route and RPDB sets without mutation;
- EXP-030-backed managed-netns IPv4 ForwardingGate with write/reread postcondition semantics;
- EXP-031-backed read-only nft table ownership observation using the exact `vpn-gate:ng3:owner-v1` marker and canonical contained-object capture;
- EXP-032/EXP-040-backed pure managed nft scaffold contract/comparison for exact fail-closed INPUT/FORWARD/OUTPUT plus empty postrouting NAT base-chain metadata;
- guarded physical managed nft scaffold bootstrap/repair for all four invariant base chains (`stack_input`, `payload_forward`, `stack_output`, `payload_postrouting`) that closes/rechecks the managed-netns ForwardingGate and refuses mutation through conflicts or unclassified nft objects;
- canonical `release1_config.py` Adapter for `use_outbound_nat`, exact-port `allow_vpn_client`, ordered one-line Device firewall with typed `PortBundle` selectors, `publish_vpn_server` with ordered 1:1 port-bundle mapping, Profile `+snat` and `availability_check`, with strict legacy-alias rejection; lower runtime consumers receive typed normalized values;
- pure `probe_policy.py` projection from normalized concrete availability subject/target plus current path realization into dedicated probe route/RPDB and narrow EXP-024-style local ICMP admission desired state; lower process UID/conntrack mark remain platform inputs, not product config;
- EXP-065-backed probe route/RPDB observer/comparison/mutation path using exact non-root UID + ICMP + target selectors in dedicated probe resources, with exact stale cleanup and no fwmark routing discriminator;
- EXP-066-backed probe-local nft owner inside the shared `vpn_gate` composite scope: exact OUTPUT uid/oif/target/ICMP -> conntrack-mark assignment, reverse INPUT mark admission, same-name/new-ifindex stale detection, physical-rule set-union across semantic owners, and one atomic handle-delete + exact-add full-diff transaction;
- bounded `AvailabilityProbeAgent` current-context semantics: normalized subject/target/mechanism + concrete `(ifname,ifindex)` + local generation token, exact late-result rejection, and technical reply/no-reply/local-error mapping to positive/negative/no_evidence without result history or routing state;
- EXP-067-backed one-shot `LinuxIcmpProbeDriver`: dedicated numeric probe UID execution through `setpriv`, numeric one-packet ICMP, injected lower reply/process deadlines, exit 0/1/other -> reply/no-reply/local-error mapping, and bounded diagnostics;
- EXP-033-backed read-only authoritative NAT chain observation/comparison classifying exact current, missing, stale and conflicting masquerade rules against the normalized desired state; no NAT rule add/delete or mutation authority;
- EXP-035/036/037/038-backed strict read-only `payload_forward` owner observer for no-counter NEW/RETURN rules across the full IPv4 CIDR prefix-length range, with explicit current-interface-identity vs stale-generation classification; recognized shape is not desired-policy confirmation or mutation authority;
- exact immutable lower `payload_forward` desired rule data plus pure actual-vs-desired comparison yielding confirmed/missing/stale/conflicts; this layer deliberately does not compile Profile direction, most-specific selection or Device envelope semantics;
- pure semantic Profile forward compiler that uses disjoint most-specific outbound fragments and per-ingress inbound fragments to build exact NEW/RETURN positive permission rules over current path endpoints; zero-path Profiles emit no positive rules;
- bounded guarded NAT-only one-step Executor + Linux nft Driver with exact whole-scope postconditions, strict refusal of foreign/forward-rule objects, verified closed ForwardingGate, and no forwarding activation; retained as narrow reference evidence;
- EXP-041/042/043/044-backed ordered Device firewall child-chain owner/observer/desired/compiler/mutation slice, including active REJECT realization and mandatory Device-jump insertion before Profile acceptance;
- pure multi-path Device firewall composition using canonical current-path ordinals for internal `df_out_XXXXXXXX` / `df_in_XXXXXXXX` child-chain identities, with explicit omitted-policy semantics and no user IDs or persistent naming registry;
- pure complete payload desired-state assembly composing routing/RPDB, Profile forward permission, Device NAT, multi-path Device firewall and publication-local owners into the exact `PayloadRoutingDesiredState + CompositeNftDesiredState` activation input;
- EXP-045-backed combined read-only nft owner/desired comparison for the invariant scaffold plus Profile forward, Device firewall and payload NAT owner classes;
- EXP-046-backed normalized Device-transport publication-local INPUT/OUTPUT intent, exact paired desired rules and strict owner observation using current host-boundary identity, exact local IPv4/protocol/port selectors and plain accept;
- EXP-047-backed atomic publication-local mutation Driver using one transactional nft full-diff batch for stale exact-handle deletion plus missing exact-rule addition, without treating ForwardingGate as a local-plane safety barrier;
- EXP-052-backed pure host-publication desired projection plus strict ordinary-host nft owner/observer/atomic replacement backend, including local-destination proof, selector availability checks, external host-forwarding prerequisite observation, overlap rejection and no host-global sysctl ownership;
- EXP-053/059/060-backed selected host-boundary production contribution: stateful-return route/RPDB+nft owner plus paired-RPDB dedicated-table bootstrap, exact/conflict observation, contained runtime drift repair, reverse-order cleanup, and executable alpha `+route-return` materialization without host `main` route injection;
- EXP-063/064-backed host-boundary behavior carrier: transient cross-netns packet-mark handoff rejected; technically proven four-class behavior-lane candidate (adoption pending VPNG0004-R4.R6.R1.R6.R1 review), pure Profile-to-lane normalization, managed-domain support for explicit additional owned boundary pairs, and pure Profile-table lane-route projection; structural payload integration remains a separate gate;
- pure combined mutation-step planner with stale local admission cleanup first, payload restrictive cleanup next, payload additions, and missing publication-local admission last;
- guarded combined Profile/Device/NAT/publication-local nft Executor + Linux backend using one link-bracketed whole-table snapshot before and after each write, persistent closed ForwardingGate for payload safety, exact postcondition progress and no forwarding activation;
- privileged combined coexistence integration covering materialization to exact state, atomic local-publication replacement, complete cleanup back to scaffold-only, Device-before-Profile ordering and fail-closed refusal of still-unclassified local owner classes;
- EXP-048-backed structural payload route/RPDB Linux Driver using exact argv-only guard/path/dispatch add/delete primitives without independent observation;
- pure exact-before-release cross-domain structural phase planner covering desired guards, stale RPDB retirement, stale route cleanup, desired path routes, nft convergence and RPDB activation last;
- guarded cross-domain structural NetworkPolicyExecutor with one link-bracketed route/RPDB+nft snapshot, persistent closed ForwardingGate during mixed state, strict fresh postcondition progress, final forwarding activation only from exact state and immediate safety re-close when post-activation verification fails;
- explicit bounded structural transaction coordinator that repeats only verified `STEP_APPLIED` one-step results, stops immediately on terminal failure or unfinished inter-attempt regression, has no arbitrary retry budget, and derives termination from the non-negative strictly decreasing structural distance;
- bounded network-policy activation subassembly that confirms payload containment, bootstraps/repairs only a safely bounded invariant nft scaffold, runs the complete structural transaction, reports READY only from confirmed exact state, and independently re-confirms ForwardingGate=DISABLED after lower failure without retrying the failed operation;
- managed network-domain infrastructure lifecycle for a normalized namespace/veth/address spec: absent+absent create, present+present contain+exact verify, partial/divergent state refuse, reciprocal live veth peer verification, fail-closed restart and teardown without nft/payload-policy ownership;
- hardened controller lifetime exclusion using an exact-owner `0700` runtime directory, `O_NOFOLLOW`/`0600` regular lock file and non-blocking exclusive `flock`; stale files are harmless because the held kernel lock is authoritative;
- bounded controller startup assembly: lifetime lock -> non-creating contained domain preflight -> candidate policy validation -> domain ensure -> fresh interface facts -> pure complete desired build -> guarded activation; READY retains the lifetime lock and failures release it without hidden policy retries;
- phase-bounded STARTING termination checkpoints driven by a read-only stop-request predicate: no lock acquisition if already stopped, no later phase after an observed request, shared owned-domain cleanup after confirmed preflight, and a final post-activation/pre-READY cleanup boundary with retained lock context on incomplete cleanup;
- bounded controller stop assembly: retained lifetime lock -> fresh forwarding containment attempt -> independent owned managed-domain teardown -> release lifetime lock only after confirmed domain absence; failed cleanup retains the lock and distinguishes contained from uncontained incomplete stop;
- bounded controller restart composition: current READY session -> bounded stop -> only after STOPPED invoke ordinary bounded startup from fresh authoritative state; stop failure blocks start and start failure is preserved without restart-specific retry;
- Linux cross-domain backend that observes route JSON + rule JSON + nft JSON inside one current-interface bracket and delegates mutation to the already evidenced route/RPDB and composite nft Drivers;
- privileged cross-domain integration proving old-policy -> new-policy convergence without mixed-state forwarding, command-error-after-success recovery from fresh state, zero-path Profile blackhole behavior and same-name/new-ifindex fail-closed rejection before mutation;
- current-only `RuntimeStatusAgent` projection for accepted configured intent, confirmed current Profile/path state, availability/readiness and blocking problems, plus atomic alpha JSON presentation without history/replay or policy ownership;
- rootless cross-contract structural-pipeline integration scenarios.

Important non-goals of the current reference:

- no Device Engine;
- no Netlink event state/history/replay;
- no generic local/system stack_input/stack_output exception framework; publication, supported-integration and probe-local traffic use separate bounded owner-specific contracts inside the shared composite nft owner;
- no full daemon/lifecycle assembly;
- no production probe scheduling/cadence assembly yet; one-shot normalized-target ICMP execution exists, but target derivation specializations and ongoing runtime orchestration remain separate;
- no Profile ordinary-side `+snat` physical materialization yet;
- no availability probe runtime assembly or user timing knobs.

Those omitted areas remain behind their current architecture/evidence gates and must not be
guessed from historical NG1/NG2 code.

Rootless test command:

```sh
PYTHONPATH=design/NG3/code/python \
python3 -m unittest discover \
    -s design/NG3/code/python/rou/tests \
    -p 'test_*.py' -v
```

Code reviews for each unit are stored under `design/reviews/`.


GitHub CI additionally runs privileged disposable-network-namespace integrations for the
physical route-priority backend, managed-netns forwarding gate, nft owner/mutation units and
the complete cross-domain structural convergence and activation references. These exercise
real route/RPDB+nft transition ordering, verified forwarding activation, fail-closed
zero-path behavior, current-interface-generation rejection, absent-scaffold bootstrap and
subsequent current-path activation through the same bounded assembly.
