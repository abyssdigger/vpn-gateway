# Review archive

Файлы ревью именуются по схеме:

```text
<предмет>-YYYY-MM-DD-<описание>.md
```

Дата ставится сразу после предмета/версии. Это сохраняет естественную группировку по
предмету и хронологический порядок внутри группы.

Исходные внешние ревью сохраняются как отдельные артефакты. Ответы и принятые решения
фиксируются отдельными файлами и не переписывают исходные тексты.


## NG2 current review chain

The current NG2 semantic baseline is covered by these autonomous internal reviews, in
implementation order:

- `NG2-2026-11-14-payload-filtering-review.md`
- `NG2-2026-11-14-payload-nat-review.md`
- `NG2-2026-11-14-adapter-owner-registry-review.md` — historical review of a candidate
  owner registry later removed by the whole-slice audit as premature unused code
- `NG2-2026-11-14-payload-rules-state-review.md`
- `NG2-2026-11-14-payload-rules-relation-review.md`
- `NG2-2026-11-14-payload-traffic-state-info-review.md`
- `NG2-2026-11-14-payload-traffic-manager-request-review.md`
- `NG2-2026-11-14-payload-traffic-manager-audit-review.md`
- `NG2-2026-11-14-semantic-slice-whole-code-audit.md`
- `NG2-2026-11-14-linux-network-rules-adapter-review.md`
- `NG2-2026-11-14-linux-lower-domain-whole-code-audit.md`
- `NG2-2026-11-14-runtime-bootstrap-review.md`
- `NG2-2026-11-14-runtime-namespace-assembly-review.md`

The whole-slice audit is authoritative for current implementation presence; earlier focused
reviews remain evidence for the design decisions they examined even when a candidate helper
was later removed.
