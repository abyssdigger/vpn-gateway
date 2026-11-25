# Возможные будущие направления

**Статус:** ненормативный проектный реестр идей, альтернатив и полезных отрицательных результатов.

Этот документ не является backlog, roadmap, Requirement, Constraint, declaration или deferral.
Запись здесь не обещает реализацию и не меняет текущую архитектуру. Назначение реестра —
быстро восстановить человеческий смысл старой идеи, понять, что уже проверялось, и решить,
стоит ли снова открывать исходные материалы.

В реестр попадают не все отвергнутые решения, а только идеи и результаты, к которым разумно
может возникнуть вопрос: «зачем мы это когда-то рассматривали и что тогда выяснили?».

## Правило поля «Смысл»

Поле **«Смысл» обязательно для каждой записи** и предназначено для человеческого чтения
после потери исходного контекста.

- только русский язык;
- без англицизмов, если существует естественное и достаточно точное русское выражение;
- кратко отвечает на вопросы «что хотели получить?» и «зачем это было нужно?»;
- обычно занимает 1–3 предложения;
- допускает существенные условия, породившие потребность;
- не объясняет способ реализации, историю архитектуры или внутреннее устройство решения;
- если смысл по историческим материалам достоверно не восстанавливается, это пишется прямо,
  без реконструкции мотива задним числом.

Технические детали, ограничения, результаты и причины отказа принадлежат следующим полям и
исходным материалам.

---

## Traffic-driven managed Device presence

**Смысл:** автоматически отключать неиспользуемые VPN-соединения и поднимать их при появлении
реальной сетевой потребности, чтобы не держать лишние соединения постоянно активными.

**What we learned:** The existing A.012/D.001 lifecycle can support a future traffic-driven
presence policy without introducing a second lifecycle owner. The hard part is product
semantics above that lifecycle: first-packet handling, inbound wake, multi-Device selection,
idle definition and shared-Device aggregation.

**Why it was not selected:** Later product discussion clarified that the current Device Manager
need is configuration-driven redundancy, not payload-triggered wake/sleep. The research remains
useful as an optional future extension and does not block the current Device Manager frontier.

**Materials:**
- `design/NG3/research/NG3-2026-11-25-managed-device-traffic-demand.md`
- `design/reviews/NG3-2026-11-25-managed-device-traffic-demand-research-review.md`

**Re-entry conditions:** A real need appears to keep fewer VPN realizations present than the
configured warm-redundancy policy requires, specifically by using actual payload activity as
the presence signal.

---

## Inbound/bidirectional multipath concrete-path affinity

**Смысл:** разрешить входящему обмену использовать несколько VPN-путей, не отправляя ответы
через другой путь и не меняя тем самым сетевое происхождение уже начавшегося обмена.

**What we learned:** EXP-062 proved concrete-path affinity for inbound multipath. The technical
mechanism is viable; the current baseline intentionally stayed single-path.

**Why it was not selected:** The additional product complexity was not needed for the current
baseline. The experiment registry retains EXP-062 as deferred future evidence rather than as
an implementation gap.

**Materials:**
- `design/experiments/EXP-062 NG3 inbound multipath concrete-path affinity/README.md`
- `design/experiments/EXP-062 NG3 inbound multipath concrete-path affinity/EXP-062-result-20261118.md`
- `design/vpn-gateway-experiments.md`

**Re-entry conditions:** A concrete inbound/bidirectional use case requires simultaneous usable
paths rather than current single-path behavior.

---

## netkit L3 as a managed-boundary backend

**Смысл:** получить более простой или более быстрый способ соединить хост с изолированной
сетевой областью без изменения пользовательского сетевого поведения VPN-GATE.

**What we learned:** netkit L3 is technically viable for the managed-L3 contract, including the
tested device-only routing/bootstrap semantics. EXP-071 found no demonstrated steady-state
dataplane advantage over routed veth + Proxy ARP on the tested runners.

**Why it was not selected:** Release-1 would have paid dual-backend complexity without a proven
performance benefit, while routed veth + Proxy ARP had the required Debian 12 portability.

**Materials:**
- `design/experiments/EXP-070 NG3 routed managed stack endpoint/README.md`
- `design/experiments/EXP-071 NG3 boundary dataplane race/README.md`
- `design/experiments/EXP-071 NG3 boundary dataplane race/EXP-071-result-20261119.md`
- `design/experiments/EXP-072 NG3 managed L3 host bootstrap/README.md`
- `design/reviews/NG3-2026-11-19-managed-l3-endpoint-selection-review.md`

**Re-entry conditions:** netkit gains a demonstrated operational/performance advantage, or a
future platform makes routed-veth realization materially less attractive.

---

## Cross-boundary Profile metadata carrier

**Смысл:** сохранить принадлежность пакета к профилю при переходе между изолированными частями
системы, чтобы после перехода можно было применить правила именно этого профиля.

**What we learned:** EXP-063 disproved the tested transient packet-mark handoff. EXP-069 then
found no tested direct nft-usable local-only metadata carrier that survived the former
cross-netns boundary. IPv4 DSCP survived as an on-wire field, but its external packet semantics
made it unsuitable as an internal product carrier.

**Why it was not selected:** The later architecture removed the need to export Profile/behavior
metadata to HOST. The negative evidence remains useful if a future design creates a similar
cross-boundary association problem.

**Materials:**
- `design/experiments/EXP-063 NG3 Profile association gateway NAT/EXP-063-result-20261118.md`
- `design/experiments/EXP-069 NG3 stack tambour metadata carriers/README.md`
- `design/experiments/EXP-069 NG3 stack tambour metadata carriers/EXP-069-result-20261119.md`
- `design/reviews/NG3-2026-11-19-EXP-069-boundary-metadata-review.md`
- `design/vpn-gateway-experiments.md`

**Re-entry conditions:** A future architecture again requires durable per-Profile association to
cross a namespace/boundary where the receiving side cannot derive it from current owned state.

---

## Host-side return steering, route-return and behavior lanes

**Смысл:** обеспечить правильное возвращение ответного трафика через VPN-GATE при отсутствии
сетевой изоляции от хоста и при различающихся правилах профилей.

**What we learned:** The host-side stateful-return/route-return and four behavior-lane design was
technically realizable; EXP-064 passed. Its evidence is retained as PROVEN FACT /
SUPERSEDED DESIGN.

**Why it was not selected:** The design lost applicability when host stateful/route-return
behavior and host-side gateway NAT were removed. Current return affinity is owned inside the
managed stack; later experiments cover the remaining host-routing and Profile-SNAT roles.

**Materials:**
- `design/experiments/EXP-064 NG3 host boundary behavior lanes/README.md`
- `design/experiments/EXP-064 NG3 host boundary behavior lanes/EXP-064-result-20261118.md`
- `design/reviews/NG3-2026-11-18-host-bootstrap-return-steering-review.md`
- `design/vpn-gateway-experiments.md`

**Re-entry conditions:** A future topology again places return-policy ownership on the host side
or needs per-Profile host-boundary behavior that cannot be derived from current managed state.

---

## Universal SystemdDriver for managed VPN lifecycle

**Смысл:** свести управление жизненным циклом разных VPN к общей служебной границе там, где
это действительно уменьшает дублирование и не скрывает различия между технологиями.

**What we learned:** Similarity of one service-manager command is not enough to define a reusable
VPN lifecycle contract. WireGuard is correctly realized directly in the kernel, while
process-based VPN technologies may legitimately use systemd or another service manager below
their technology-specific Adapter.

**Why it was not selected:** A universal SystemdDriver would abstract the coincidental mechanism
instead of the complete lifecycle contract and would incorrectly force unlike VPN technologies
through one lower model.

**Materials:**
- `design/NG3/research/NG3-2026-11-24-managed-device-lifecycle-wireguard-multipeer.md`
- `design/reviews/NG3-2026-11-24-EXP-089-direct-wireguard-lifecycle-review.md`
- `design/NG3/architecture-ng.md`

**Re-entry conditions:** Two or more supported VPN integrations demonstrate the same complete
lower lifecycle contract—not merely the same service-manager command—and extracting it removes
real duplication without weakening technology-specific guarantees.
