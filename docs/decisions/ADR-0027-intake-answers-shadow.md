# ADR-0027 — Respostas do intake avaliadas em modo sombra

- Status: accepted
- Date: 2026-10-18
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

`intake.assess_charter` só verifica se cada campo do Charter está preenchido. Respostas como "a definir", "todos" ou "melhorar o sistema" passam, e o Charter pode ser aprovado sem guiar decisão nenhuma. O plano `docs/plans/2026-10-17-decider-outros-pontos.md` (seção 5) propõe usar o Decider.

## Decisão

1. Com `intake` em `spec.assessment.features`, `aifw intake status` pergunta ao Decider, para cada campo respondido (problema, públicos, resultados, escopo dentro e fora), se a resposta é específica o bastante para guiar decisões de produto:
   - pergunta `score` com os níveis vaga, parcial e específica;
   - estado: a pergunta do intake e a resposta.
2. O resultado traz `assessment.weakAnswers` (campos vagos ou parciais) e vai para `.aifw/assessments/intake.jsonl`.
   - Não altera `ready`, `complete` nem a aprovação.
   - A skill usa os campos fracos como próximas perguntas da entrevista.
3. A avaliação fica em cache pelo conteúdo do Charter e só roda de novo quando ele muda.
4. Relatório e vereditos com `--feature intake`. O veredito `right` significa que as respostas marcadas como fracas, e só elas, estão certas; `wrong`, o contrário. O critério de ativação é o mesmo do avaliador de tarefas.

## Primeira rodada da suíte (2026-10-18)

Suíte: `evals/assessment/intake-cases.yaml`, com 20 respostas e o gabarito do agente.

- Nível exato: 19/20. A única divergência ficou entre dois níveis fracos: "integrações" como escopo fora era parcial no gabarito e saiu vaga.
- Fraca ou não: 20/20. Nenhuma resposta fraca passou como específica, e nenhuma específica foi marcada como fraca.
- Custo da rodada: US$ 0,00007.
- No Charter deste repositório, os resultados esperados foram avaliados como parciais: são qualitativos, sem métrica.

## Consequências

- Até 5 chamadas por mudança no Charter, cerca de US$ 0,00002.
- Sem chave, sem rede ou com o recurso desligado, `intake status` funciona como antes.

## Rollback

Tirar `intake` de `spec.assessment.features` e desfazer as mudanças listadas.
