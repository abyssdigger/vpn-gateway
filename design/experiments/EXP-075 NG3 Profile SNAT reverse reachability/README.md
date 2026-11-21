# EXP-075 — Profile SNAT identity reverse reachability

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R1.R2.R4.R4.R4]** *Чтобы Profile мог явно задавать требуемое представление source address для уже разрешённого VPN→ordinary traffic, не заставляя пользователя воспроизводить внутреннюю NAT-механику VPN-GATE вручную.* | VPN-GATE должен позволять пользователю для Profile явно запросить source NAT уже разрешённого VPN→ordinary payload перед его выходом из managed network domain: без такого запроса payload должен выходить из managed domain с исходным remote source address, а при запросе — с выбранной для Profile IPv4 SNAT identity. Эта функция определяет source identity на managed boundary и сама по себе не обещает последующую host-side маршрутизируемость, firewall policy или внешний NAT. [`closed`]
- **[VPNG0004-R4.R6.R1.R6]** *Чтобы optional Profile source translation не расширяла границу владения VPN-GATE на несвязанное networking state обычного хоста.* | Когда Profile `+snat` включён, необходимое translation state должно принадлежать managed network domain или его явно owned boundary и не должно требовать от VPN-GATE владения host-side NAT/firewall state либо произвольного изменения несвязанного host routing/firewall state. [`closed`]
- **[VPNG0002-R2.R6]** *Чтобы ответ на входящий трафик из VPN-канала мог быть корректно обработан его отправителем.* | Для управляемого трафика, принятого со стороны VPN через разрешенный канал, VPN-GATE должен обеспечивать передачу относящегося к нему ответного трафика обратно через тот VPN-канал, через который был принят исходный трафик; наличие других разрешенных каналов для адреса отправителя не должно само по себе менять канал такого ответа. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Current evidence scope

The experiment retains a lower Linux integration fact used alongside:

- `VPNG0001-R3` — Profile source identity exists at the managed boundary;
- `VPNG0001-R3` — translation state remains inside the managed domain.

It does **not** extend those requirements into a promise that core Profile SNAT owns ordinary
host routing. The tested /32 route form may be installed by a host-routing helper or by the
administrator. `VPNG0003-R4` remains the STACK-side return-affinity requirement once the
reply is delivered back into the managed domain.

## Question

With the current selected architecture only:

- Profile SNAT is performed inside STACK;
- HOST owns `<snat identity>/32 dev vpng0`;
- the routed veth boundary has Proxy ARP enabled on both endpoints;

can a real reply addressed to the SNAT identity cross the addressless managed L3
boundary back into STACK without any additional stack-local route/address/proxy-neighbour
for the identity?

The experiment intentionally does **not** add such a workaround. A failure is an
architecture finding, not a test failure to be hidden.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-075 NG3 Profile SNAT reverse reachability/exp075_profile_snat_reverse.py"
```
