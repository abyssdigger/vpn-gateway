# EXP-078 — scoped peaceful host-routing selectors

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R2.R2]** *Чтобы разрешенная родителем host-side автоматизация для типовой эксплуатации первого release оставалась явно управляемой и не превращалась в постоянный захват ordinary-host routing.* | Первый release должен предоставлять peaceful host-routing automation, которая через продуктовую конфигурацию по умолчанию отключена и при включении применяет route assistance только к явно выбранной администратором области ordinary-host traffic. Область должна позволять отдельно выбирать host-originated traffic, весь non-local ingress traffic или точные host ingress interfaces; traffic вне выбранной области не должен захватываться helper'ом. Peaceful helper не должен сам включать или выключать host IP forwarding. При включенной области helper устанавливает идентифицируемые host-routing contributions при start, обновляет их при поддерживаемой lifecycle reload-операции и при stop удаляет только сохранившиеся принадлежащие helper'у contributions, не удаляя заменившее их администраторское состояние. Между lifecycle-операциями helper не обязан непрерывно наблюдать или восстанавливать последующие изменения, не должен принудительно возвращать замененное администратором состояние, а такая внешняя поломка или замена сама по себе не должна переводить core managed forwarding VPN-GATE в fail-closed. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Статус

COMPLETE — PASS — SELECTED as privileged selector acceptance evidence for revised `VPNG0001-R5.R1.R1`.

## Requirement trace

- `VPNG0001-R2`;
- `VPNG0001-R5.R1.R1`.

## Вопрос

Позволяет ли Linux RPDB реализовать принятую область peaceful helper так, чтобы
`0.0.0.0/0` влиял только на явно выбранный ordinary-host traffic, при этом:

- `:local` выбирает host-originated traffic;
- `:external` выбирает non-local ingress, но не host-originated traffic;
- точный interface selector выбирает только traffic с этого ingress;
- `:any` выбирает оба класса;
- traffic из managed STACK не захватывается обратно;
- explicit non-default administrator routes в `main` сохраняют приоритет.

## Проверяемый Linux lowering

```text
iif <managed-boundary> lookup main
lookup main suppress_prefixlength 0

:local      -> iif lo lookup <helper-table>
:external   -> not iif lo lookup <helper-table>
:any        -> lookup <helper-table>
<ifname>    -> iif <ifname> lookup <helper-table>

ordinary main/default
```

`iif lo` и `not iif lo` здесь являются Linux lowering принятой продуктовой
семантики, а не user-facing spelling.

## Среда

Privileged disposable Linux network namespaces on GitHub Actions with `iproute2` and
`iputils-ping`.

Topology:

```text
LAN-A ----\
           HOST ---- ordinary GW
LAN-B ----/  |
             | managed boundary
             |
            STACK ---- remote endpoint
```

Один и тот же test target доступен через ordinary GW и через STACK, поэтому фактический
выход определяется RPDB policy, а не отсутствием альтернативного пути.

## PASS criterion

PASS требует одновременно:

1. `:local`: host-originated packet использует helper route, LAN transit — ordinary default;
2. exact ingress: LAN-A использует helper, LAN-B — ordinary default;
3. `:external`: LAN transit использует helper, host-originated traffic — ordinary default;
4. `:any`: host-originated и LAN transit используют helper;
5. для выбранного traffic explicit non-default `main` route выигрывает у helper;
6. packet с `iif <managed-boundary>` использует ordinary `main`, а не helper;
7. глобальный `suppress_prefixlength 0` не меняет effective routing traffic, который не
   совпал ни с одним helper dispatch selector;
8. experiment не изменяет ordinary `main` routes.

FAIL любого пункта возвращает revised closure `VPNG0001-R5.R1.R1` в architecture review.

## Выполнение

```sh
sudo env PYTHONPATH=design/NG3/code/python \
  python3 "design/experiments/EXP-078 NG3 peaceful host routing selectors/exp078_peaceful_host_routing_selectors.py"
```

Результат записывается отдельным result artifact после выполнения. До результата никакая
supersession/disposition не объявляется.

## Result

See `EXP-078-result-20261120.md`.

Workflow run `44758764201`, job `linux-host-managed-routing` (`136365426254`) completed
with `EXP078_RESULT=PASS`.

## Post-result lifecycle

- Logical evidence state: **PROVEN FACT / SELECTED**.
- Current disposition: selected for scoped Release-1 peaceful host-routing dispatch.
- Coverage relation: extends EXP-077; does not supersede it.
- EXP-074 remains selected only for the postponed aggressive authoritative child.
