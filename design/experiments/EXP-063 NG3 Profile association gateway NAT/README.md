# EXP-063 — NG3 Profile association handoff for ordinary-side gateway NAT

## Status

COMPLETE — **FAIL**. See `EXP-063-result-20261118.md`.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R1.R2.R4.R4.R4]** *Чтобы Profile мог явно задавать требуемое представление source address для уже разрешённого VPN→ordinary traffic, не заставляя пользователя воспроизводить внутреннюю NAT-механику VPN-GATE вручную.* | VPN-GATE должен позволять пользователю для Profile явно запросить source NAT уже разрешённого VPN→ordinary payload перед его выходом из managed network domain: без такого запроса payload должен выходить из managed domain с исходным remote source address, а при запросе — с выбранной для Profile IPv4 SNAT identity. Эта функция определяет source identity на managed boundary и сама по себе не обещает последующую host-side маршрутизируемость, firewall policy или внешний NAT. [`closed`]
- **[VPNG0001-R1.R2.R4.R4.R4.R1]** *Чтобы Profile-side source translation не смешивалась с Device-side VPN transport NAT и не скрывала исходный remote sender до применения разрешающей policy.* | VPN-GATE должен отличать Profile `+snat` от Device `use_outbound_nat`: Device masquerade относится к ordinary→VPN payload конкретного transport path, а Profile `+snat` — только к VPN→ordinary payload; Profile translation должна выполняться внутри managed network domain после managed firewall/policy проверки исходного remote source и до выхода payload через managed boundary. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Requirements

**Implements / provides physical evidence for:**

- `VPNG0001-R3`;

- `VPNG0001-R4.R4.R4.R4`;
- `VPNG0002-R2.R1.R3`;
- `VPNG0007-R7.R3.R4`;
- `VPNG0007-R7.R3.R4.R1`.

The accepted architecture already requires Profile ordinary-side gateway NAT to run only for
already-permitted VPN->ordinary traffic after managed policy, and already rejected host-side
source-prefix reclassification as sufficient Profile association.

## Technical question

Can the Linux data plane carry the already-established Profile association across the
managed-stack -> ordinary-host boundary without userspace per-flow state and without allowing
that transient association tag to affect ordinary host routing?

The candidate boundary protocol is:

```text
managed stack:
    established flow already has Profile association
    -> after managed forwarding policy, export a transient packet Profile tag

ordinary host boundary:
    transient tag
    -> store Profile association in host connection state
    -> clear transient packet tag before ordinary host route lookup

host forwarding:
    Profile association
    -> optional Profile gateway NAT
    -> optional established-flow return steering
```

This experiment tests a carrier/mechanism, not new product semantics.

## Distinguishing conditions

The evidence uses overlapping remote address space so that source-only host reclassification
would select a different Profile from the one established by actual managed ingress.

It also installs a deliberately hostile host-routing decision for the transient boundary tag.
Forwarding can succeed only if the host consumes and clears that tag before ordinary route
selection.

## Required evidence

The experiment must prove all of the following in one run:

1. an inbound flow associated with the broader Profile can request gateway NAT even though a
   narrower overlapping Profile would win source-only reclassification;
2. a different inbound Profile can traverse the same host boundary without gateway NAT;
3. the transient boundary tag is consumed before ordinary host routing;
4. gateway NAT happens only on the forwarded ordinary-network leg and not for host-local
   termination;
5. reverse NAT and established-flow return complete correctly;
6. unrelated host traffic remains outside the owner.

## PASS markers

```text
EXP063_PROFILE_A_ASSOCIATION=PASS
EXP063_PROFILE_A_GATEWAY_NAT=PASS
EXP063_PROFILE_B_NO_GATEWAY_NAT=PASS
EXP063_TRANSIENT_TAG_CLEARED_BEFORE_ROUTING=PASS
EXP063_HOST_LOCAL_NOT_GATEWAY_NATED=PASS
EXP063_REVERSE_RETURN=PASS
EXP063_UNRELATED_HOST_UNTOUCHED=PASS
EXP063_RESULT=PASS
```

A PASS proves technical feasibility of the boundary Profile-association carrier. Selection
and production lifecycle integration remain separate architecture/review steps.
## Post-result lifecycle

- Result remains: **FAIL**.
- Current disposition: **historical_only**.
- Applicability: **утратил применимость к текущей реализации**.

The failed transient cross-boundary Profile-tag carrier remains negative technical evidence.
Current Profile SNAT stays inside STACK and exports no Profile/behavior metadata to HOST;
EXP-076 removes the need for this carrier rather than reinterpreting the FAIL.

