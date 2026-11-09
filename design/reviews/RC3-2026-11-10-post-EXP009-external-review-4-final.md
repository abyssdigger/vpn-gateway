# RC3 — внешний review после EXP-009, проход 4 — FINAL

**Дата:** 2026-11-10  
**Роль рецензента:** внешний эксперт по сетевым и информационным технологиям, Linux routing,
Netfilter, VPN и эксплуатационной безопасности, без знания истории проекта.  
**Проверяемая версия:** после исправлений review passes 1–3.  
**Код не анализировался.**

## Итог

**Вердикт: ACCEPT — NO FINDINGS.**

По результатам повторного полного review замечаний к рассмотренному комплекту документов
не осталось. Архитектурный контракт после EXP-009 является внутренне непротиворечивым,
достаточно полным для реализации и терминологически однозначным в проверенной области.

## Проверенная модель selector/binding

Подтверждено:

- exact и `prefix+` — селекторы single-binding;
- `prefix%` и explicit exact set — селекторы multi-binding;
- binding cardinality является свойством формы селектора, а не текущего числа candidates;
- allowing firewall rules, NAT и routes используют только exact runtime interface names;
- `prefix%` использует numeric discovery, а deny-only guard — более широкое textual
  prefix namespace;
- multi-binding peer association в RC3 строится только по однозначному point-to-point
  `(local_address, peer)` evidence;
- отсутствие такого evidence не заменяется эвристикой.

Замечаний нет.

## Route lifecycle и EXP-009

EXP-009 остается первичной evidence-записью и не смешан с нормативным выводом.

Архитектура корректно выводит из него:

- исчезновение point-to-point interface удаляет зависимый kernel route;
- backup route с большей metric становится предпочтительным;
- повторное появление interface не восстанавливает route автоматически;
- route failback выполняется reconciliation после повторного формирования `PeerBinding`;
- Netlink event является только wakeup signal, а решение строится по текущему snapshot.

Для селектора single-binding transport-level peer handshake не является источником route
truth; постоянный interface, например `wg0`, сохраняет routes независимо от peer
handshake flapping.

Замечаний нет.

## ProfileResult и lifecycle daemon

Status semantics согласованы во всех проверенных разделах:

- profile `SUCCESS` требует минимум один verified desired UNICAST path **для каждого**
  protected destination;
- partial multi-binding failover при наличии secondary path остается `SUCCESS`;
- отсутствие path хотя бы для одного protected destination дает profile `FAIL`;
- `peers=[]` валиден как staged/fail-closed config, но operationally дает profile
  `FAIL` и daemon `DEGRADED`;
- `SUCCESS` не является end-to-end health-check;
- startup error всегда hard-fails;
- transport unavailability при корректном fail-closed desired state может завершить
  startup успешно в `RUN/DEGRADED`;
- завершенный `RUN`:
  - `SAFE + all SUCCESS + ip_forward=1 -> ACTIVE`;
  - `SAFE + (profile FAIL или confirmed ip_forward=0) -> DEGRADED`;
  - недостаточная наблюдаемость policy/ip_forward либо не-`SAFE` policy -> `ISOLATED`;
- inability to enable `ip_forward=1` во время startup остается hard failure.

Замечаний нет.

## Firewall/NAT и fail closed

Подтверждено:

- structural guards и blackhole не зависят от transport availability;
- active allowing rules/NAT строятся по exact active interfaces;
- protected destination имеет terminal reject после разрешающих правил;
- managed ingress закрыт exact blocks + guards;
- global `VPNG-FORWARD-DENY` сохраняет окончательное владение решением FORWARD;
- NAT проверяется до materialization/recovery `proto 202` routes;
- binding transition использует защитный barrier;
- INPUT-only confirmed drift остается узким исключением и не смешивается с transit repair;
- IPv6 prerequisite применяется ко всему guard namespace, включая более широкое
  пространство `prefix%`.

Замечаний нет.

## Терминология и полнота

Подтверждено:

- нормативные формы — «селектор single-binding» / «селекторы single-binding» и
  «селектор multi-binding» / «селекторы multi-binding»;
- старые нормативные понятия «жесткая привязка» и единый readiness-state удалены;
- glossary согласован с architecture;
- pre-EXP-009 readiness terminology в implementation README явно помечена как описание
  текущего старого кода, а не нормативной RC3 model;
- operational status содержит достаточно данных для различения partial failover,
  total route loss и ambiguity.

Замечаний нет.

## Структурная проверка

Автоматически и вручную подтверждено:

- 99 инвариантов, нумерация последовательная 1..99;
- ссылки вида `§N.M` разрешаются к существующим разделам;
- дубли нормативных заголовков отсутствуют;
- поврежденных regex-фрагментов после старых подстановок нет;
- в architecture/terms нет остатков старой hard-binding/readiness terminology;
- EXP-009 имеет `COMPLETE — PASS` и в журнале, и в result artifact;
- implementation README явно отделяет 125/125 pre-EXP-009 baseline от новой архитектуры.

## Финальное заключение

**Замечаний нет. Документы могут использоваться как принятая архитектурная база для
следующего этапа реализации RC3.**
