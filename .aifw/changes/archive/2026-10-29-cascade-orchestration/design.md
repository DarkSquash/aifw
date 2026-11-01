# Design — Orquestração em cascata pela complexidade

## Context

`assessment.path_for(risk, importance, complexity)` decide o caminho pelo risco, e `PATH_RULE`/`path_context` escrevem o texto que o agente recebe a cada pedido. `assessment_eval` usa `path_for` para medir as avaliações. `claude.AGENTS` lista os subagentes que o `enable` instala. O Claude Code deixa um subagente com a ferramenta `Agent` lançar subagentes até três níveis abaixo da conversa.

## Approach

- `path_for`: só a complexidade escolhe o caminho; a assinatura fica igual, para `assessment_eval` e os testes não mudarem de forma.
- `path_context`: monta o texto pelo caminho e pelo risco final (`finalRisk`):
  - cascata do nível;
  - com risco L2/L3 em FAST ou WORK, a exceção (Sonnet ou `aifw-senior` sozinho, depois os dois revisores);
  - com risco L2/L3, a linha da governança (plano aprovado no chat, spec, ADR, dois revisores);
  - o risco aparece como baixo (L0), médio (L1), alto (L2) ou crítico (L3).
- Templates novos em `templates/claude/agents/`:
  - `aifw-planner`: sonnet, high, com Agent; planeja L2, distribui aos workers, revisa e resume.
  - `aifw-lead`: sonnet, medium, com Agent; recebe uma parte de L3, quebra, distribui, revisa e resume.
  - `aifw-worker`: haiku, medium, sem Agent; implementa uma tarefa pequena e relata.
  - `aifw-senior`: opus, high; faz sozinho uma tarefa simples de risco alto ou crítico.
- `claude.AGENTS` com os quatro nomes novos.
- O `aifw-quick` e o `aifw-executor` passam a dizer que planejam e executam sozinhos o L0 e o L1. O `aifw-executor` também é o "Sonnet sozinho" da exceção em L0.
- A skill troca a tabela de modelos pela tabela da cascata.
- Execução orquestrada: `assessment.py`, `claude.py`, templates, testes e documentação pelo `aifw-executor`. No núcleo do hook muda só o texto da negação da orquestração (ADR-0040), que passa a citar os papéis da cascata; a regra não muda.

## Decisions

- Os nomes dos caminhos ficam: `FAST`, `WORK`, `PLANNED` e `CRITICAL` são o L0–L3 da complexidade, e só o texto explica.
- Os níveis de impacto (risco) do framework não são renomeados; o texto do avaliador e da skill mostra o risco por extenso para não confundir com o L0–L3 da complexidade.
- Dois coordenadores Sonnet (high e medium) porque a ferramenta Agent não escolhe o esforço por chamada.
- Revisores: complexidade L2/L3, ou risco alto ou crítico. L0/L1 de risco baixo ou médio não têm revisor; testes e gates continuam.

## Risks and rollback

- Haiku implementando em L2/L3 erra mais que Sonnet; a revisão do coordenador e os dois revisores existem para pegar isso, com possível rodada extra.
- Mais níveis de subagente aumentam a latência.
- Uma avaliação de complexidade errada escolhe a cascata errada; subir de caminho continua permitido, descer nunca.
- Rollback: reverter a mudança volta ao caminho pelo risco e aos cinco papéis.
