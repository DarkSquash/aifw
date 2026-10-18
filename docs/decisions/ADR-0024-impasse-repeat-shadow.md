# ADR-0024 — Impasse: tentativa repetida avaliada em modo sombra

- Status: accepted
- Date: 2026-10-18
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

`impasse.record_attempt` só reconhece uma tentativa repetida quando hipótese e intervenção são idênticas depois de normalizar maiúsculas e espaços. Reescrever a mesma estratégia com outras palavras conta como tentativa nova e adia o congelamento.

O plano `docs/plans/2026-10-17-decider-outros-pontos.md` (seção 3, aprovado em 2026-10-18) propõe usar o Decider para esse julgamento.

## Decisão

1. Com `impasse` em `spec.assessment.features`, cada `aifw impasse attempt` pergunta ao Decider, contra cada tentativa anterior do caso:
   - pergunta `noul`;
   - estado: só o texto das duas hipóteses e intervenções.
2. Modo sombra:
   - a probabilidade máxima, a sugestão (repetição a partir de 0,7) e se o texto era idêntico vão para `.aifw/assessments/impasse.jsonl`;
   - o caso não muda.
3. `aifw assess report --feature impasse` e `aifw assess verdict --feature impasse` seguem o mesmo formato e o mesmo critério do avaliador de tarefas (ADR-0023): 50 vereditos e 90% de concordância.
4. O modo ativo fica para uma decisão posterior. Nele, a sugestão de repetição abriria o impasse. O modelo só antecipa o congelamento, nunca adia.
5. A suíte `evals/assessment/impasse-cases.yaml` tem 30 pares, metade paráfrases e metade estratégias diferentes, com gabarito a revisar antes da primeira rodada.

## Primeira rodada da suíte (2026-10-18)

| Limite | Acertos | Estratégias diferentes marcadas como repetição |
| --- | --- | --- |
| 0,5 | 30/30 | 0 |
| **0,7** | **29/30** | **0** |
| 0,8 | 29/30 | 0 |

- As estratégias diferentes ficaram todas abaixo de 0,01; as paráfrases, acima de 0,92.
- A única perda com 0,7 foi `same-plus-detail`, com 0,65: a mesma correção acrescida de um log, caso discutível.
- Custo da rodada: US$ 0,0001.

## Consequências

- Uma chamada por tentativa anterior: no máximo umas 5 por caso, cerca de US$ 0,00001 cada.
- Sem chave, sem rede ou com o recurso desligado, o impasse funciona como antes.

## Rollback

Tirar `impasse` de `spec.assessment.features` e desfazer as mudanças listadas.
