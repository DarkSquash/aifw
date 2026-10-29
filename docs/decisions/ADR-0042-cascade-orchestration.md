# ADR-0042: Orquestração em cascata pela complexidade

- Status: accepted
- Date: 2026-10-28
- Impact: L2
- Change: `cascade-orchestration`
- Amends: ADR-0036 (avaliador de tarefas ativo), ADR-0038 (subagentes por papel), ADR-0040 (orquestração obrigatória)

## Contexto

O avaliador escolhia o caminho de execução pelo risco, e o Opus da conversa planejava e, nos caminhos leves, executava. A pessoa quer o contrário: o caminho vem da complexidade, cada nível tem uma cascata fixa de modelos, e o Opus da conversa nunca implementa. O risco continua decidindo a governança.

## Decisão

1. O caminho vem só da complexidade: trivial L0 (`FAST`), simples L1 (`WORK`), moderada L2 (`PLANNED`), alta L3 (`CRITICAL`). A importância é avaliada e registrada, mas não muda o caminho.
2. Cascata por nível:
   - L0: `aifw-quick` (Haiku, low) planeja e executa sozinho, sem revisor.
   - L1: `aifw-executor` (Sonnet, medium) planeja e executa sozinho, sem revisor.
   - L2: `aifw-planner` (Sonnet, high) planeja; depois do "sim", quando houver, distribui partes a um ou mais `aifw-worker` (Haiku, medium), revisa até ficar satisfeito e devolve só o resumo; o agente principal chama `aifw-adversary` e depois `aifw-qa`.
   - L3: o agente principal (Opus) planeja e divide entre um ou mais `aifw-lead` (Sonnet, medium); cada lead quebra a sua parte para `aifw-worker`, revisa e devolve; o agente principal chama os dois revisores.
3. Exceção de risco: risco alto ou crítico (nota L2 ou L3 do avaliador) em complexidade L0 vai a um `aifw-executor` sozinho; em L1, a um `aifw-senior` (Opus, high) sozinho. Os dois revisores rodam depois.
4. A governança continua pelo risco: risco alto ou crítico pede o plano aprovado no chat (`aifw spec request-approval`), spec e ADR, e os dois revisores. L0 e L1 de risco baixo ou médio não têm revisor; testes e gates continuam.
5. O agente principal só orquestra, em todos os níveis; o núcleo vivo do hook continua com ele (`orchestration.sessionPaths`, ADR-0040). `aifw-planner` e `aifw-lead` têm a ferramenta Agent (até três níveis abaixo da conversa); `aifw-worker` e `aifw-senior` não.
6. Os nomes de caminho `FAST`, `WORK`, `PLANNED` e `CRITICAL` ficam, para não quebrar `assess verdict --path` nem os relatórios. Os níveis de impacto do resto do framework (`--level`, `change.yaml`, gates, Constituição) não são renomeados e continuam significando risco; o texto do avaliador e da skill mostra o risco por extenso (baixo, médio, alto, crítico) e chama a complexidade de L0–L3.
7. Papéis: `aifw-explorer` (haiku, low), `aifw-quick` (haiku, low), `aifw-executor` (sonnet, medium), `aifw-planner` (sonnet, high), `aifw-lead` (sonnet, medium), `aifw-worker` (haiku, medium), `aifw-senior` (opus, high), `aifw-adversary` (opus, high), `aifw-qa` (sonnet, high).

## Consequências

- Haiku implementando em L2 e L3 erra mais que Sonnet; a revisão do coordenador e os dois revisores existem para pegar isso, com possível rodada extra.
- Mais níveis de subagente aumentam a latência.
- Uma avaliação de complexidade errada escolhe a cascata errada; subir de caminho continua permitido, descer nunca.
- Dois coordenadores Sonnet (planner em high, lead em medium), porque a ferramenta Agent não escolhe o esforço por chamada.
- Os nomes `FAST`/`WORK`/`PLANNED`/`CRITICAL` deixam de ter relação com o risco, e L0–L3 ganha dois sentidos (complexidade no caminho, risco nos comandos); o texto explica a diferença. Renomear o impacto em todo o framework é uma mudança à parte.
- Rollback: reverter a mudança; volta o caminho pelo risco e os cinco papéis anteriores.
