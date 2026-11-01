# Design — Spec dos subagentes e docs dos revisores

## Context

`.aifw/specs/current/claude-subagents.yaml` ficou com cinco subagentes depois de ADR-0042 acrescentar quatro. A skill e os templates não dizem o que os revisores fazem quando a governança não cria pasta de mudança.

## Approach

- Delta `claude-subagents.delta.yaml` com `modified` de REQ-SUBAGENTS-INSTALL; o `spec archive` faz o sync em `current/`.
- Uma frase em cada template de revisor, ajuste do bullet "Revisores" da skill e do parágrafo da revisão em `docs/claude-code.md`; reescrita mínima da linha de L0 e L1 nos dois.
- `aifw claude enable` reinstala as cópias em `.claude/`; `aifw claude check` confere.

## Decisions

- Nível L1 (risco médio): documentação e spec, sem mudança de comportamento do código.
- Não duplicar a exceção de risco que a doc já tem como bullet; só ajustar a linha de L0 e L1.

## Risks and rollback

- Texto apenas; reverter o commit e rodar `aifw claude enable` restaura as cópias. O archive é a única operação com efeito em `specs/current/`.
