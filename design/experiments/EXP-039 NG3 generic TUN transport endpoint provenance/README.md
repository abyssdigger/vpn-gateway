# EXP-039 — generic TUN transport endpoint provenance

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

### Requirement ID migration

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0007-R7.R3.R2` -> `VPNG9001-R1.R1.R3.R2`

The original IDs in the historical body are intentionally preserved.

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R1.R3.R5]** *Чтобы упростить описание пользователем типовых проверок доступности, правил фильтрации по конечной точке VPN и других функций, которым полезна логическая привязка к конечной точке VPN вместо явного указания её IP-адреса.* | VPN-GATE должен при обнаружении или обновлении current logical VPN path уметь однозначно определить transport endpoint/peer, соответствующий текущему concrete data-plane endpoint, когда принятый discovery contract поддерживаемой integration предоставляет для этого достаточные наблюдаемые данные, и связать определённый endpoint/peer с текущей generation этого path binding. [`closed`]
- **[VPNG0001-R1.R3.R5.C1]** *Потому что надёжное получение transport-endpoint provenance ещё не подтверждено для всех поддерживаемых first-release integrations, а базовые routing, binding и явно адресованные проверки доступности не требуют этой удобной логической привязки.* | Первый release не обязан предоставлять transport-endpoint provenance для каждого VPN path. Отсутствие подтверждённого provenance не должно делать сам path непригодным для функций, которым он не нужен, но функции, чья принятая семантика требует endpoint provenance, не должны угадывать endpoint, подменять его interface name/slot или считать такую зависимую функцию действующей без подтверждённого provenance. [`closed`]
- **[VPNG0001-R1.R3.R5.C1.R1]** *Чтобы отложенная endpoint-provenance capability не превращалась для пользователя в скрыто неработающую или ложно работающую настройку.* | Когда пользователь запрашивает функцию, которая по принятой семантике требует transport-endpoint provenance, а текущая integration не может его однозначно предоставить, VPN-GATE должен до объявления этой функции действующей выдать явный диагностируемый отказ; если та же функция поддерживает явное указание IP-адреса вместо endpoint provenance, этот явный вариант должен оставаться доступным независимо от endpoint discovery. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Purpose

Determine whether a transport endpoint/peer address is an organic observable property of a
Linux point-to-point TUN data-plane interface, or whether VPN-GATE needs integration-specific
provenance to associate a current concrete interface with its transport peer.

This experiment is deliberately narrower than OpenConnect/WireGuard integration discovery.
It tests the generic Linux boundary that a shared interface-discovery implementation could
legitimately rely on.

## Requirement/design scope

**Implements evidence for:**
- `VPNG0001-R1.R3.R2`;
- `VPNG0007-R7.R3.R2`;
- `VPNG0001-R1.R3.R2`;
- `VPNG0007-R7.R3.R2`;
- `VPNG0001-R1.R3.R2`.

- `VPNG0007-R7.R3.R2`.

The experiment does not select named-endpoint config syntax and does not make endpoint
provenance a first-release prerequisite.

## Setup

One privileged userspace process:

1. creates and holds a Linux TUN interface through `/dev/net/tun`;
2. configures an inner point-to-point IPv4 peer on that interface;
3. opens a separate connected UDP socket representing a VPN transport connection;
4. observes the TUN interface through normal `ip -j -d link` and `ip -j addr` discovery;
5. replaces only the userspace transport socket's remote endpoint and repeats observation.

TEST-NET addresses are used as transport socket peers; UDP `connect()` does not require a
remote service to exist.

## Hypotheses

- **H1:** the created TUN is observable as a point-to-point data-plane interface;
- **H2:** the configured inner/network-layer peer is observable in interface address state;
- **H3:** the userspace transport peer IP is absent from generic TUN link/address state;
- **H4:** changing only the userspace transport peer leaves the generic TUN interface
  observation unchanged while `getpeername()` changes.

## Decision rule

If H1-H4 pass, transport peer identity is **not** accepted as an organic generic property of
a point-to-point TUN interface. Endpoint provenance must then come from an
integration-specific discovery/onboarding fact and be attached to the exact current path
binding; generic interface discovery must not infer it from TUN point-to-point state.

If generic interface state changes to expose the userspace transport peer, the architecture
must be revisited before accepting the opposite conclusion.
