# Roteamento FAST/WORK/BRAIN

`aifw route explain` classifica uma tarefa por impacto, operação, incerteza e tentativas falhas, e recomenda uma classe cognitiva.

| Classe | Alias | Uso típico |
| --- | --- | --- |
| FAST | haiku | leitura única, classificação simples, docs/discovery de baixa incerteza |
| WORK | sonnet | implementação, testes, revisão e pesquisa comuns |
| BRAIN | opus | arquitetura, L3, alta incerteza, impasse ou falhas repetidas |

Aliases não são competências garantidas e podem apontar para outros modelos em `.aifw/routing.yaml`. L3 sempre recomenda BRAIN; uma tarefa L0 semanticamente difícil também pode usar BRAIN. O impacto continua L0.

## No Claude Code

O Claude Code não troca o modelo da sessão a pedido do AIFW. A skill `aifw` distribui planejamento, execução e revisão entre subagentes (parâmetro `model` da ferramenta Agent), usando a linha mais alta que se aplicar:

| Situação | Planeja | Executa | Revisa |
| --- | --- | --- | --- |
| impacto L3 ou rota BRAIN | opus | opus, ou sonnet com plano passo a passo | revisor independente opus + aprovação humana em L3 |
| impacto L2 | opus | sonnet | revisor independente opus |
| rota WORK | — | sonnet | testes e gates |
| rota FAST | — | haiku | testes e gates |

Revisão não substitui testes e gates, que rodam em toda classe. Trabalho trivial pode ser feito inline. Subir de modelo é permitido; L3 ou BRAIN nunca é rebaixado.

## Ativação

O roteamento fica sempre ligado (ADR-0037): `route explain` responde `executionMode: automatic` e o agente escolhe o modelo pela tabela, sem pedir confirmação. Não há comando de ativação.

`aifw route eval --output <report.json>` executa a suíte determinística revisável em `evals/routing/cases.yaml`. Mudar a tabela ou o modelo-alvo exige a suíte com pelo menos 30 casos, 95% de aprovação e nenhuma falha crítica.

## Avaliador de tarefas

Com `spec.assessment.mode: shadow` em `aifw.yaml` e o recurso `tasks` ligado, cada pedido da pessoa com 5 palavras ou mais é avaliado automaticamente pelo hook `UserPromptSubmit` (ADR-0031), antes de o agente ler a mensagem; segredos reconhecidos são mascarados antes do envio. `aifw change assess --task "<pedido>"` faz o mesmo à mão. A avaliação manda três perguntas independentes ao `perplexity/pplx-decider-v1.2`, pelo OpenRouter: risco (L0–L3), importância e complexidade. Uma regra fixa transforma as respostas no caminho:

| Caminho | Quando | Planeja | Executa | Revisa |
| --- | --- | --- | --- | --- |
| FAST | risco L0, complexidade trivial ou simples, importância baixa ou média | — | haiku | testes e gates |
| WORK | risco L1; ou L0 com complexidade moderada ou alta, ou com importância alta ou crítica | — | sonnet | testes e gates |
| PLANNED | risco L2; ou L1 com complexidade alta | opus | sonnet | opus |
| CRITICAL | risco L3 | opus | opus | revisor independente e humano |

- Com `--diff`, os fatos verificáveis do diff (autenticação, deploy, contratos, arquivos de controle) formam um piso: o risco final nunca fica abaixo dele.
- Cada avaliação é gravada em `.aifw/assessments/shadow.jsonl`. Os outros recursos (`impasse`, `context`, `intake`, `traceability`, `decisions`) continuam em modo sombra: só registram.
- Só o texto do pedido sai da máquina, nunca código ou diff. O comando exige:
  - `openrouter` em `spec.externalAllowlist`;
  - a chave em `OPENROUTER_API_KEY`;
  - dados que não sejam `confidential` ou `restricted`.

  Sem isso, responde `unavailable` e não chama a API. Custo aproximado: US$ 0,00001 por pedido.
- `aifw assess report` mostra as perguntas, as respostas de cada pedido e os seus vereditos.
- `aifw assess verdict --id 1,2 --agree --by human:<nome>`, ou `--value <caminho>`, registra se você concorda. É uma aprovação humana, rodada só no seu terminal.
- **Modo ativo (ADR-0036, ADR-0037):**
  - O recurso `tasks` é sempre ativo, sem comando de ativação: cada pedido chega ao agente com o caminho (FAST, WORK, PLANNED ou CRITICAL), que ele segue na tabela de modelos. Subir é permitido, descer nunca; a escolha do modelo não pede confirmação.
  - Se o serviço falhar, o agente só recebe um aviso e segue a classificação de sempre.
  - Para desligar, tire `tasks` de `spec.assessment.features`. Consulte o [ADR-0023](decisions/ADR-0023-task-assessor-shadow.md).
