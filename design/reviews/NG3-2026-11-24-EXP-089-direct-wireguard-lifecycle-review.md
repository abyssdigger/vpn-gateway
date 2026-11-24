# NG3 2026-11-24 — ревью EXP-089 и нижней реализации D.001 для WireGuard

**Эксперимент:** EXP-089  
**Source:** `b2723ae448394bddeabce191a71db013e5a6149c`  
**Run:** `45467124175`  
**Job:** `138705009864`

## Вердикт

**PASS — DIRECT KERNEL WIREGUARD LIFECYCLE SELECTED FOR D.001 LOWER REALIZATION.**

## Findings и решения

### F1 — отдельный WireGuard systemd unit не требуется

EXP-089 подтвердил start, идемпотентный exact-present, changed-generation restart через
подтвержденное absence и stop для настоящего kernel WireGuard-интерфейса без отдельной службы.
Base configuration применяется через `wg setconf ... /dev/stdin`; сгенерированный файл на
диске не нужен.

### F2 — ownership нельзя выводить только из имени интерфейса

Same-name `wg0` без ожидаемого `ifalias` marker был оставлен неизменным как foreign
conflict. Stop также отказался удалять чужой объект. `ifalias` является наблюдаемым marker
происхождения, но не security boundary против root; fresh exact verification остается
обязательной.

### F3 — secret-file gate технически применим

Regular file mode 0600 с владельцем effective UID принят. Group-readable 0640 и symbolic link
отвергнуты до создания интерфейса.

### F4 — changed generation проходит через confirmed absence

Старый owned interface удаляется, отсутствие подтверждается, затем создается и проверяется
новое поколение. Наблюдавшийся ifindex 3 -> 4 не считается архитектурной гарантией.

### F5 — systemd остается допустимым для daemon-based VPN

EXP-050 и EXP-089 совместимы: D.001 скрывает protocol-specific реализацию. WireGuard
использует direct kernel realization, а процессные VPN могут использовать service manager.
Универсальный `SystemdDriver` не вводится из одного совпадения технической команды.

### F6 — production materialization не заявляется

Рабочего D.001 Adapter еще нет. EXP-089 является lower evidence, поэтому component-local
материализация R7/R7.R2 этим review не повышается.

## Итог

Stable evidence address: `EV-00060`. Нижняя WireGuard-граница D.001 определена достаточно
для следующей production implementation unit.
