# ADR-0002: Core independente do agente

- Status: accepted
- Date: 2026-08-22
- Impact: L3

## Contexto

Pi, Claude e Codex possuem formatos, tools e modelos diferentes. Acoplar Constitution e lifecycle a um executor tornaria decisões duráveis dependentes de produto transitório.

## Decisão

Manter config, authority, intake, lifecycle, gates, permissions, impasse, map e conformance em `src/core`. Integrar executores somente por `AgentAdapter` e documentos portáveis.

## Consequências

Trocar agente não reescreve governança. Adapters precisam traduzir e podem não suportar toda capability; essa limitação é explícita. Nenhum adapter ganha permissão de redefinir regra core.
