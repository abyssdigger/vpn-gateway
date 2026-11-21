# VPN-GATE NG3 — unresolved Purpose/parent questions

**Status:** non-normative research artifact  
**Branch:** `ng3-research-20261120-requirement-purpose-parent-consistency-30m`  
**Baseline:** main snapshot 145 `623a688e4080de56e5ac14675ffca028c3865d18`  
**Current research draft:** requirement remap through branch HEAD

Исходный audit содержал 20 findings: 2 safe corrections и 18 вопросов, требовавших human
decision. Все 18 вопросов получили product-holder disposition и применены к
`NG3-2026-11-20-purpose-parent-corrected-requirements-draft.md`.

## Нерешённые вопросы

**Нет.**

Последними закрыты:

- priority-only continuity: прежний `VPNG-U004-R4.R3.R1` перенесён в
  `VPNG-U003-R3.R9` как гарантия отсутствия искусственного разрыва при изменении только
  эффективного порядка неизменного набора разрешённых VPN-путей;
- `reload`: обязательная product capability удалена; возможность обновлять конфигурацию
  поднята в `VPNG-U005` / `VPNG-U005-R5` / `VPNG-U005-R5.R6`, а `reload` остаётся
  необязательным механизмом интерфейса управления.

## Уже закрытые adjacent findings

Следующие вопросы также не должны снова появляться в decision queue:

- Profile source identity / `+snat` поднят в самостоятельную capability;
- Device NAT/firewall и VPN transport/control capabilities отделены от config placement;
- transport endpoint provenance удалён из requirement tree;
- peaceful/aggressive host-routing helpers получили положительный общий parent;
- user-selected availability criterion подтверждён;
- Device-default/Profile-override перенесён из-под ICMP-only constraint;
- timing/hysteresis limitation вынесен в sibling constraint `VPNG-U003-R3.R6.R3.R1.C2`;
- host-state safety сделан mechanism-neutral, managed network domain и literal DROP остаются
  architecture/evidence;
- protective mode поднят непосредственно под `VPNG-U004`;
- return-flow affinity перенесён из `VPNG-U002-R2.R6` в прямой child `VPNG-U003-R4`;
- второй VPN lifecycle evidence gate удалён из requirement tree; EXP-050 остаётся
  историческим evidence для соответствующих product/lifecycle/safety obligations.

Нормативный remap `design/NG3/requirements.md` больше не блокируется отсутствующим
product-holder решением. Перед promotion требуется итоговая проверка целостности research
tree и атомарный remap актуальной traceability.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005` -> `VPNG-M001-R1`
- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
