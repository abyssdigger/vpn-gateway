# RC3 — prefix stable-order review 1

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** firewall/NAT policy reviewer  
**Область:** process-local ordering of prefix bindings  
**Вердикт:** **ACCEPT — NO FINDINGS**

## Проверка

Новая семантика устраняет ненужную зависимость full policy от лексикографической позиции
имени интерфейса.

Для `prefix+`:

- surviving bindings сохраняют относительный order;
- новая binding добавляется в конец;
- удаленная binding исчезает без reorder остальных;
- simultaneous newly observed bindings используют ASCII только как tie-breaker внутри
  новой группы;
- INPUT/FORWARD/VPNG-INGRESS/NAT используют тот же process-local order;
- появление `vpns10` между `vpns1` и `vpns2` лексикографически больше не меняет
  relative order существующих blocks;
- full policy может по-прежнему применяться транзакционно целиком, но desired ordering
  существующих blocks не меняется.

Порядок не влияет на безопасность, потому что exact interface predicates различных
bindings взаимоисключающие. Guard rules и terminal denies сохраняют прежнюю семантику.

## Диагностическая семантика

Во время непрерывной работы daemon порядок exact blocks отражает порядок первого принятия
bindings текущим процессом. Это полезная диагностика lifecycle.

Это не заявлено как точная историческая chronology:

- после restart история не сохраняется;
- несколько bindings, впервые увиденных одним snapshot, не имеют наблюдаемого взаимного
  порядка и получают deterministic tie-break.

## Итог

**ACCEPT — NO FINDINGS.**
