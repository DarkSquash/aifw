# ADR-0023 — Avaliador de tarefas em modo sombra

- Status: accepted
- Date: 2026-10-17
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

O AIFW classifica mudanças por sinais declarados pelo agente e por fatos do diff. Não avalia o pedido em si, e não tem as dimensões de importância e complexidade.

Os testes de 2026-10-17 com o `perplexity/pplx-decider-v1.2`, pelo OpenRouter, mostraram:

- bom desempenho para avaliar risco a partir do texto do pedido;
- desempenho razoável em importância e complexidade, com erros quase sempre conservadores;
- a decisão final do caminho não precisa de modelo: uma regra fixa sobre as avaliações dá o mesmo resultado.

O plano está em `docs/plans/2026-10-17-avaliador-de-tarefas.md`.

## Decisão

1. `aifw change assess` manda três perguntas independentes (risco, importância e complexidade), em paralelo, ao modelo fixado por versão. Uma regra fixa transforma as respostas no caminho FAST, WORK, PLANNED ou CRITICAL.
2. Com `--diff`, os sinais verificáveis do diff formam um piso de risco que o modelo não pode baixar.
3. Por enquanto só existe o modo sombra: cada avaliação é gravada em `.aifw/assessments/shadow.jsonl`, e o fluxo segue como antes.
4. O comando só chama a API quando três condições valem:
   - `openrouter` está em `spec.externalAllowlist`;
   - a chave está em `OPENROUTER_API_KEY`;
   - os dados não são `confidential` nem `restricted`.

   A checagem fica no próprio comando, porque o hook trata `aifw` como leitura e não enxerga a chamada de rede.
5. `aifw assess verdict` é uma aprovação humana: só roda no terminal da pessoa, e o hook nega no shell do agente. `.aifw/assessments/` é arquivo de controle.
6. Critério para um futuro modo ativo: 50 pedidos com veredito, 90% de concordância e nenhum caso CRITICAL rebaixado. Ao atingir 50 avaliações, o início de sessão avisa que o relatório está pronto (`aifw assess report`).

## Consequências

- O texto do pedido sai da máquina para o OpenRouter e para a Perplexity; código e diffs não.
- `.aifw/assessments/` fica fora do git: os textos dos pedidos e os vereditos ficam só na máquina, sem entrar no histórico.
- Sem chave, sem rede ou com o serviço fora do ar, o comando responde ou falha sem gravar nada, e o fluxo continua.
- O modo ativo, com o caminho saindo da avaliação, exige uma nova decisão, depois do relatório da sombra.

## Rollback

Remover `spec.assessment` do `aifw.yaml` (ou usar `mode: off`) e desfazer as mudanças listadas.
