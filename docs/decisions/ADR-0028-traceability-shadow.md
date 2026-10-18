# ADR-0028 — Rastreabilidade da spec avaliada em modo sombra

- Status: accepted
- Date: 2026-10-18
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

`specs.analyze_change` confere se cada requisito tem cenário, tarefa e teste ligados, e se os arquivos de evidência existem. Não confere se o cenário realmente verifica o requisito: um cenário copiado de outro requisito passa. O plano `docs/plans/2026-10-17-decider-outros-pontos.md` (seção 6) propõe usar o Decider.

## Decisão

1. Com `traceability` em `spec.assessment.features`, `aifw spec analyze` pergunta ao Decider, para cada par de requisito e cenário (requisitos adicionados ou modificados), se o cenário verifica o comportamento exigido:
   - pergunta `noul`;
   - estado: o requisito (força e texto) e os passos dado, quando e então.
2. Pares com probabilidade abaixo de 0,5 vão para `assessment.weakTraces`. Os achados e o `pass` da análise não mudam, e o archive nunca é bloqueado por isso. O registro vai para `.aifw/assessments/traceability.jsonl`.
3. A avaliação fica em cache pelo texto dos pares e só roda de novo quando a spec muda.
4. Relatório e vereditos com `--feature traceability`, com os mesmos valores `right` e `wrong` do intake. O critério de ativação é o mesmo do avaliador de tarefas.

## Primeira rodada da suíte (2026-10-18)

Suíte: `evals/assessment/traceability-cases.yaml`, com 18 pares reais das specs aceitas e arquivadas. Nove trocam o cenário pelo de outro requisito da mesma capability.

| Limite | Acertos | Trocados que passaram | Bons marcados como fracos |
| --- | --- | --- | --- |
| 0,3 | 16/18 | 2 | 0 |
| **0,5** | **18/18** | **0** | **0** |
| 0,7 | 18/18 | 0 | 0 |

- Os pares corretos ficaram entre 0,78 e 1,00. Os trocados ficaram abaixo de 0,1, exceto dois (0,43 e 0,47), em que o cenário trocado tem relação parcial com o requisito.
- O plano previa 30 pares; o repositório só tem 18.
- Custo da rodada: US$ 0,00006.

## Consequências

- Uma chamada por par a cada mudança na spec, cerca de US$ 0,000004 por par.
- Sem chave, sem rede ou com o recurso desligado, `spec analyze` funciona como antes.

## Rollback

Tirar `traceability` de `spec.assessment.features` e desfazer as mudanças listadas.
