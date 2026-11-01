# Proposal — Spec dos subagentes e docs dos revisores

## Intent

Corrigir três ressalvas do aifw-qa na mudança cascade-orchestration (ADR-0042):

1. REQ-SUBAGENTS-INSTALL na spec aceita lista só cinco subagentes; o `aifw claude enable` instala nove.
2. Em L2/L3 de risco baixo ou médio não há pasta de mudança, logo não há `independent-review.md` para os revisores.
3. A frase "sem revisor" de L0 e L1 vem antes da exceção de risco.

## Scope

- Delta que MODIFICA REQ-SUBAGENTS-INSTALL (statement e SCN-SUBAGENTS-INSTALL), aplicado pelo `spec archive`.
- Templates `aifw-adversary.md`, `aifw-qa.md` e a skill `aifw-workflow`, e `docs/claude-code.md`: sem pasta de mudança, os revisores devolvem a seção e a linha `Resultado:` na resposta e o agente principal relata à pessoa; a linha de L0 e L1 diz risco baixo ou médio e cita a exceção.
- Reinstalação das cópias em `.claude/` com `aifw claude enable` e CHANGELOG.

## Non-goals

- ADRs, código Python, hooks e o avaliador.

## Acceptance

- A spec aceita lista os nove subagentes com modelo, esforço e ferramentas dos templates.
- Os dois templates, a skill e a doc descrevem o retorno dos revisores sem pasta de mudança.
- A linha de L0 e L1 na skill e na doc diz risco baixo ou médio e a exceção de risco alto ou crítico.
- `aifw claude check` passa, a suíte inteira passa e os gates da mudança não bloqueiam.
