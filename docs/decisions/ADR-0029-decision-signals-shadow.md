# ADR-0029 — Sinais dos catálogos de decisão sugeridos em modo sombra

- Status: accepted
- Date: 2026-10-18
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

`decision recommend` ranqueia as alternativas de um catálogo a partir de sinais digitados à mão (`--signals`). Achar os sinais exige ler o Charter e responder cada direcionador. O plano `docs/plans/2026-10-17-decider-outros-pontos.md` (seção 7) propõe usar o Decider para sugeri-los.

## Decisão

1. Com `decisions` em `spec.assessment.features`, `decision recommend --suggest-signals [--context "<pedido>"]` pergunta ao Decider cada direcionador da categoria:
   - pergunta `choice`, com as alternativas do direcionador mais "não diz";
   - estado: problema, públicos, resultados, escopo, restrições e preferências técnicas do Charter, mais o pedido.
2. Um sinal é sugerido quando a resposta não é "não diz" e a confiança é de 0,6 ou mais. O campo `assessment` mostra os sinais sugeridos e o ranking que eles dariam. O registro vai para `.aifw/assessments/decisions.jsonl`.
3. O ranking oficial do comando continua usando só os sinais passados em `--signals`. `--signals` deixou de ser obrigatório, e sem ele a recomendação sai com confiança baixa, como já acontecia com sinais vazios.
4. Relatório e vereditos com `--feature decisions` (`right` e `wrong`). O critério de ativação é o mesmo do avaliador de tarefas.

## Primeira rodada da suíte (2026-10-18)

Suíte: `evals/assessment/decisions-cases.yaml`, com 8 projetos fictícios e os 11 direcionadores dos 3 catálogos, ou seja, 88 perguntas.

- **Sinais que o texto sustenta (41):**
  - 35 sugeridos certos;
  - 6 não sugeridos por falta de confiança, em 4 deles com a resposta certa abaixo de 0,6;
  - nenhum sugerido errado.
- **Direcionadores sem base no texto, segundo o gabarito (47):** em 7, o modelo sugeriu um sinal com confiança. Quase todos são deduções plausíveis:
  - um time de 3 pessoas num sistema interno vira deploy único;
  - squads donos de áreas viram deploy independente;
  - um app de agendamento vira consistência transacional.

  Por isso os sinais só valem depois de confirmados pela pessoa.
- Custo da rodada: US$ 0,0003.

## Consequências

- Até 11 chamadas por pedido de sugestão, cerca de US$ 0,00004.
- Sem chave, sem rede ou com o recurso desligado, `decision recommend` funciona como antes.

## Rollback

Tirar `decisions` de `spec.assessment.features` e desfazer as mudanças listadas.
