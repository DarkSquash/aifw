# ADR-0032 — Ativação do roteamento de modelos

- Status: superseded by ADR-0037 (roteamento sempre ligado)
- Date: 2026-10-19
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

O roteamento (`.aifw/routing.yaml`) estava em `recommendation-only` desde a troca para haiku/sonnet/opus (0.4.0). A pessoa pediu a ativação em 2026-10-19.

## Evidência

`aifw route eval --output evidence/routing-eval.json`, em 2026-10-19:
- 32 casos, 32 aprovados (pass rate 1,0);
- nenhuma falha crítica;
- critério da policy: pelo menos 30 casos, 95% e zero falhas críticas.

## Decisão

Ativar o roteamento com `aifw route activate --report evidence/routing-eval.json --by human:DarkSquash --record docs/decisions/ADR-0032-routing-activation.md`, rodado pela pessoa no terminal dela. Os modelos-alvo continuam FAST → `claude-haiku-5-5`, WORK → `claude-sonnet-5-5` e BRAIN → `claude-opus-5-5`.

## Consequências

- `route explain` passa a responder `executionMode: automatic`: a classe recomendada vira a regra para escolher o modelo dos subagentes, e não mais uma sugestão. O AIFW continua sem trocar o modelo da sessão principal.
- Com `approvals.requireSignedCommit`, a ativação só vale depois de commitada e assinada.
- Trocar um modelo-alvo exige nova avaliação e nova aprovação (ADR-0003).

## Rollback

Voltar `enabled: false` e `mode: recommendation-only` em `.aifw/routing.yaml` e remover o bloco `approval`.
