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

Projetos nascem com `enabled: false` e `mode: recommendation-only`. `aifw route activate` aceita relatório de conformidade e exige identidade + ADR/registro. O core recusa ativação com menos de 30 casos, pass rate abaixo de 95%, falha crítica ou aprovação ausente. Ativação escreve evidência na routing policy; não fica em conversa. `route explain` usa os aliases e o estado gravados na policy; com `approvals.requireSignedCommit`, a ativação só vale num commit assinado.

`aifw route eval --output <report.json>` executa a suíte determinística revisável em `evals/routing/cases.yaml`. Troca de modelo-alvo exige nova avaliação e nova aprovação (ADR-0003).

## Avaliador de tarefas (modo sombra)

Com `spec.assessment.mode: shadow` em `aifw.yaml`, cada pedido da pessoa com 5 palavras ou mais é avaliado automaticamente, em segundo plano, pelo hook `UserPromptSubmit` (ADR-0031); segredos reconhecidos são mascarados antes do envio. `aifw change assess --task "<pedido>"` faz o mesmo à mão. A avaliação manda três perguntas independentes ao `perplexity/pplx-decider-v1.2`, pelo OpenRouter: risco (L0–L3), importância e complexidade. Uma regra fixa transforma as respostas no caminho:

| Caminho | Quando | Planeja | Executa | Revisa |
| --- | --- | --- | --- | --- |
| FAST | risco L0, complexidade trivial ou simples, importância baixa ou média | — | haiku | testes e gates |
| WORK | risco L1; ou L0 com complexidade moderada ou alta, ou com importância alta ou crítica | — | sonnet | testes e gates |
| PLANNED | risco L2; ou L1 com complexidade alta | opus | sonnet | opus |
| CRITICAL | risco L3 | opus | opus | revisor independente e humano |

- Com `--diff`, os fatos verificáveis do diff (autenticação, deploy, contratos, arquivos de controle) formam um piso: o risco final nunca fica abaixo dele.
- Em modo sombra nada muda no fluxo: cada avaliação é gravada em `.aifw/assessments/shadow.jsonl`.
- Só o texto do pedido sai da máquina, nunca código ou diff. O comando exige:
  - `openrouter` em `spec.externalAllowlist`;
  - a chave em `OPENROUTER_API_KEY`;
  - dados que não sejam `confidential` ou `restricted`.

  Sem isso, responde `unavailable` e não chama a API. Custo aproximado: US$ 0,00001 por pedido.
- `aifw assess report` mostra as perguntas, as respostas de cada pedido e os seus vereditos.
- `aifw assess verdict --id 1,2 --agree --by human:<nome>`, ou `--value <caminho>`, registra se você concorda. É uma aprovação humana, rodada só no seu terminal.
- **Modo ativo (ADR-0036):**
  - O critério é 50 pedidos com veredito, 90% de concordância e nenhum caso CRITICAL rebaixado, contando só os pedidos da pessoa.
  - Atingido o critério, a pessoa roda `aifw assess activate --feature tasks --by human:<nome>` no próprio terminal, assina `.aifw/assessor.yaml` e roda `aifw claude enable`.
  - A partir daí, cada pedido chega ao agente com o caminho (FAST, WORK, PLANNED ou CRITICAL), e delegar a Haiku depois de um caminho PLANNED ou CRITICAL pede confirmação.
  - Se o serviço falhar, o agente só recebe um aviso e segue a classificação de sempre.
  - Para desligar, apague `.aifw/assessor.yaml` e rode `aifw claude enable`. Ao atingir 50 avaliações, o início de sessão avisa que o relatório está pronto. Consulte o [ADR-0023](decisions/ADR-0023-task-assessor-shadow.md).
