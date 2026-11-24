# EXP-076 — combined Profile SNAT dataplane

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG-U001-R1.R2.R4.R4.R4]** *Чтобы Profile мог явно задавать требуемое представление source address для уже разрешённого VPN→ordinary traffic, не заставляя пользователя воспроизводить внутреннюю NAT-механику VPN-GATE вручную.* | VPN-GATE должен позволять пользователю для Profile явно запросить source NAT уже разрешённого VPN→ordinary payload перед его выходом из managed network domain: без такого запроса payload должен выходить из managed domain с исходным remote source address, а при запросе — с выбранной для Profile IPv4 SNAT identity. Эта функция определяет source identity на managed boundary и сама по себе не обещает последующую host-side маршрутизируемость, firewall policy или внешний NAT. [`closed`]
- **[VPNG-U001-R1.R2.R4.R4.R4.R1]** *Чтобы Profile-side source translation не смешивалась с Device-side VPN transport NAT и не скрывала исходный remote sender до применения разрешающей policy.* | VPN-GATE должен отличать Profile `+snat` от Device `use_outbound_nat`: Device masquerade относится к ordinary→VPN payload конкретного transport path, а Profile `+snat` — только к VPN→ordinary payload; Profile translation должна выполняться внутри managed network domain после managed firewall/policy проверки исходного remote source и до выхода payload через managed boundary. [`closed`]
- **[VPNG-U001-R1.R2.R4.R4.R4.C1]** *Поскольку Profile source NAT имеет смысл только на VPN→ordinary leg, а адрес translation является частью того же пользовательского решения, отдельные независимые Profile toggles/поля создавали бы бессмысленные сочетания и разрывали бы одну policy на несколько мест.* | В Release 1 opt-in Profile source NAT должен кодироваться только в `direction`: допустимы `inbound+snat`, `inbound+snat>IPv4`, `bidirectional+snat` и `bidirectional+snat>IPv4`; базовые `inbound`/`bidirectional` означают отсутствие translation, `outbound+snat...` недопустим. Голый `+snat` использует top-level `default_snat_address`, а `+snat>IPv4` переопределяет его для данного Profile; если enabled Profile использует голый `+snat`, отсутствие `default_snat_address` является ошибкой конфигурации. Отдельного Profile-поля gateway/SNAT нет. [`closed`]
- **[VPNG-U001-R1.R2.R4.R4.R4.C2]** *Чтобы IPv4 source после managed boundary оставался однозначной административной identity и не мог одновременно означать реальный ненатированный remote source или другую внутреннюю роль VPN-GATE.* | Каждый effective Profile SNAT address должен быть однозначным IPv4 unicast address, не попадать в address space, которое в текущей enabled-конфигурации может выйти через managed boundary как ненатированный remote source, и не совпадать с адресом, одновременно используемым VPN-GATE для иной служебной/transport роли на этой boundary. Один и тот же SNAT address разрешено намеренно использовать нескольким `+snat` Profiles; такая общая identity означает их осознанную административную группировку. [`closed`]
- **[VPNG-U002-R2.R6]** *Чтобы ответ на входящий трафик из VPN-канала мог быть корректно обработан его отправителем.* | Для управляемого трафика, принятого со стороны VPN через разрешенный канал, VPN-GATE должен обеспечивать передачу относящегося к нему ответного трафика обратно через тот VPN-канал, через который был принят исходный трафик; наличие других разрешенных каналов для адреса отправителя не должно само по себе менять канал такого ответа. [`closed`]
- **[VPNG-U004-R4.R6.R1.R6]** *Чтобы optional Profile source translation не расширяла границу владения VPN-GATE на несвязанное networking state обычного хоста.* | Когда Profile `+snat` включён, необходимое translation state должно принадлежать managed network domain или его явно owned boundary и не должно требовать от VPN-GATE владения host-side NAT/firewall state либо произвольного изменения несвязанного host routing/firewall state. [`closed`]
- **[VPNG-U004-R4.R6.R1.R6.R1]** *Чтобы Profile source translation сохраняла свою область применимости при совместном использовании managed boundary несколькими Profiles.* | Profile `+snat` должен применяться только к уже разрешённому VPN→ordinary traffic, для которого принятая Profile policy явно запрашивает translation; traffic Profile без `+snat` должен выходить через managed boundary с исходным remote source независимо от пересечения remote prefixes, общего boundary endpoint или различающихся ingress VPN paths. Совместное использование несколькими `+snat` Profiles одного effective SNAT address не считается нарушением этой изоляции. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Requirement trace

Core Profile-SNAT acceptance evidence for:

- `VPNG-U001-R3`;

- `VPNG-U001-R4.R4.R4.R4`;
- `VPNG-U002-R2.R1.R3`;
- `VPNG-U001-R4.R4.R4.R4.C1`;
- `VPNG-U001-R3`;
- `VPNG-U003-R4`;
- `VPNG-U001-R3`;
- `VPNG-U004-R4.R6`;
- `VPNG-U001-R3`.

- `VPNG-U002-R2.R1.R3`.

## Topology and assertions

A real HOST↔STACK routed boundary carries three VPN-originated UDP flows:

- Profile A: `+snat` to `198.19.255.10`;
- Profile B: `+snat` to the same shared identity;
- Profile C: no Profile SNAT.

The STACK forward chain is `policy drop`. NEW admission matches only each original
remote source; there is no allow rule matching the translated identity. Therefore successful
A/B delivery proves firewall/policy precedes postrouting SNAT.

The experiment also requires:

- A and B both appear to the LAN server as the same SNAT identity and both replies return
  under the tested host-integration route;
- C appears as its original remote source and its reply returns;
- authoritative NAT observation contains exactly the two Profile SNAT rules;
- HOST contains no Profile SNAT nft owner;
- as ancillary lower integration evidence, the SNAT identity host route uses the stack
  service next hop, while ordinary remote destinations remain device-only.

The host route assertion is not a claim that core Profile SNAT owns host routing; equivalent
routing may be supplied by a separate helper or by the administrator.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-076 NG3 combined Profile SNAT/exp076_combined_profile_snat.py"
```
