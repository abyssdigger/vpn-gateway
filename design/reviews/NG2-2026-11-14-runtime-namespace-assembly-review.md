# NG2 — existing namespace runtime assembly review

**Дата:** 2026-11-14  
**Тип:** autonomous focused implementation review  
**Scope:** execution of the Linux network-policy backend in a pre-existing ROU namespace

## Review criteria

Проверялись:

- соответствие dedicated ROU namespace assumption concrete Linux Adapter;
- отсутствие namespace lifecycle ownership в network-policy Driver;
- сохранение argv/stdin/check semantics через namespace boundary;
- отсутствие shell invocation/string interpolation;
- reuse production runner в privileged integration;
- bootstrap failure semantics при недоступном namespace;
- Python -> Rust alignment;
- dead/duplicate test harness paths.

## Findings

### N1 — production Driver previously had no namespace-scoped execution path

**Severity:** integration/correctness  
**Disposition:** implemented.

Concrete Linux Adapter baseline предполагает dedicated ROU namespace, но
`SubprocessLinuxRunner` исполнял команды только в namespace самого процесса.

Добавлен `NetworkNamespaceLinuxRunner`, который оборачивает существующий
`LinuxCommandRunner`:

```text
argv
  -> ("ip", "netns", "exec", namespace, *argv)
```

`input_text` и `check` передаются без изменения. Shell не используется.

### N2 — namespace runner must not acquire namespace lifecycle ownership

**Severity:** architecture  
**Disposition:** implemented/documented.

Runner умеет только исполнять command в уже существующем named namespace.

Он не:

- создает/удаляет namespace;
- создает veth;
- настраивает host-side transport;
- пытается автоматически repair'ить отсутствие namespace.

Отсутствующий namespace естественно дает command/bootstrap FAILURE.

### N3 — production assembly should not require callers to reconstruct runner stack

**Severity:** integration  
**Disposition:** implemented.

Добавлен helper:

```text
bootstrap_linux_network_rules_adapter_in_namespace(...)
```

Он собирает:

```text
host runner
 -> NetworkNamespaceLinuxRunner
 -> LinuxNetworkDriver
 -> protective bootstrap
 -> LinuxNetworkRulesAdapter
```

при этом lifecycle namespace остается внешней предпосылкой.

### N4 — privileged integration used a parallel test-only namespace runner

**Severity:** evidence/cleanup  
**Disposition:** fixed.

Integration harness раньше имел собственный `NamespaceRunner`, фактически дублирующий
production path.

Harness переведен на production `NetworkNamespaceLinuxRunner` с recording host runner.
Тем самым live Adapter gate теперь проверяет тот же namespace wrapper, который используется
production assembly.

### N5 — no additional abstraction is needed for namespace identity yet

**Severity:** abstraction review  
**Disposition:** retained.

Namespace name пока остается technical string lower domain. Отдельный NamespaceId type не
вводится без второго representation/consumer.

Empty name rejected immediately; остальные validity/errors принадлежат `ip netns exec`
и возвращаются как technical failure.

## Component-model review

`NetworkNamespaceLinuxRunner` остается Driver-level technical machinery. Он знает Linux
`ip netns exec`, но не знает NetworkRules, owners, Profiles или runtime policy.

Namespace lifecycle является другой managed responsibility и не скрывается внутри command
runner.

No synchronous back-edge or event dependency introduced.

## Evidence

Unit coverage:

- command prefix;
- stdin preservation;
- `check` preservation;
- empty namespace rejection;
- existing-namespace bootstrap assembly.

Privileged integration uses production namespace runner for the complete Linux Adapter
scenario, including bootstrap, structural apply, drift repair and cleanup.

NG2 and NG1 CI were green on the namespace assembly sequence before documentation-only
closure; final branch gate is checked separately at cycle checkpoint.

## Final verdict

**PASS after cleanup.**

No unresolved finding blocks execution inside a pre-existing ROU namespace.

The remaining namespace work is lifecycle ownership: creation/prerequisite validation,
host-side transport plumbing and shutdown behavior. It remains a separate review unit.
