# Roteamento FAST/WORK/BRAIN

`aifw route explain` classifica uma tarefa por impacto, operação, incerteza e tentativas falhas, e recomenda uma classe cognitiva.

| Classe | Alias | Uso típico |
| --- | --- | --- |
| FAST | haiku | leitura única, classificação simples, docs/discovery de baixa incerteza |
| WORK | sonnet | implementação, testes, revisão e pesquisa comuns |
| BRAIN | opus | arquitetura, L3, alta incerteza, impasse ou falhas repetidas |

Aliases não são competências garantidas e podem apontar para outros modelos em `.aifw/routing.yaml`. L3 sempre recomenda BRAIN; uma tarefa L0 semanticamente difícil também pode usar BRAIN. O impacto continua L0.

## No Claude Code

O Claude Code não troca o modelo da sessão a pedido do AIFW. A skill `aifw-workflow` distribui planejamento, execução e revisão entre os subagentes por papel que o `aifw claude enable` instala (ADR-0038), delegando pelo nome, sem passar `model`, para valer o modelo e o esforço da definição. O caminho vem da complexidade da tarefa (ADR-0042), e o agente principal só orquestra:

| Complexidade (caminho) | Planeja | Executa | Revisa |
| --- | --- | --- | --- |
| L0, trivial (FAST) | `aifw-quick` (haiku) | `aifw-quick`, sozinho | testes e gates |
| L1, simples (WORK) | `aifw-executor` (sonnet) | `aifw-executor`, sozinho | testes e gates |
| L2, moderada (PLANNED) | `aifw-planner` (sonnet) | `aifw-worker` (haiku), um ou mais, distribuídos e revisados pelo planner | `aifw-adversary` (opus), depois `aifw-qa` (sonnet) |
| L3, alta (CRITICAL) | agente principal (opus) | `aifw-lead` (sonnet), um ou mais, que quebram a parte para `aifw-worker` (haiku) e revisam | `aifw-adversary`, depois `aifw-qa` |

Exceção de risco: com risco alto ou crítico, L0 vai a um `aifw-executor` (sonnet) sozinho e L1 a um `aifw-senior` (opus) sozinho, seguidos dos dois revisores. Risco alto ou crítico também pede o plano aprovado no chat, spec e ADR. Subir de caminho é permitido; descer, nunca.

A revisão independente tem duas etapas: o `aifw-adversary` tenta provar que a mudança está errada e só reprova com um cenário concreto que falha; sem achado provado, o `aifw-qa` confere critérios, evidências e documentação. Revisão não substitui testes e gates, que rodam em toda classe. A orquestração é obrigatória em todos os níveis (ADR-0040, ADR-0042): a sessão principal planeja (em L3) e delega, nunca implementa. Subir de modelo é permitido; L3 ou BRAIN nunca é rebaixado. Os modelos e esforços de cada subagente estão em [Claude Code](claude-code.md#modelos).

## Ativação

O roteamento fica sempre ligado (ADR-0037): `route explain` responde `executionMode: automatic` e o agente escolhe o modelo pela tabela, sem pedir confirmação. Não há comando de ativação.

`aifw route eval --output <report.json>` executa a suíte determinística revisável em `evals/routing/cases.yaml`. Mudar a tabela ou o modelo-alvo exige a suíte com pelo menos 30 casos, 95% de aprovação e nenhuma falha crítica.

## Avaliador de tarefas

Com `spec.assessment.mode: shadow` em `aifw.yaml` e o recurso `tasks` ligado, cada pedido da pessoa com 5 palavras ou mais é avaliado automaticamente pelo hook `UserPromptSubmit` (ADR-0031), antes de o agente ler a mensagem; segredos reconhecidos são mascarados antes do envio. `aifw change assess --task "<pedido>"` faz o mesmo à mão. A avaliação manda três perguntas independentes ao `perplexity/pplx-decider-v1.2`, pelo OpenRouter: risco (baixo, médio, alto ou crítico; L0–L3 nos comandos do framework), importância e complexidade. Só a complexidade escolhe o caminho (ADR-0042); o risco decide a governança e a exceção:

| Caminho | Quando (complexidade) | Planeja | Executa | Revisa |
| --- | --- | --- | --- | --- |
| FAST | L0, trivial | `aifw-quick` (haiku) | `aifw-quick`, sozinho | testes e gates |
| WORK | L1, simples | `aifw-executor` (sonnet) | `aifw-executor`, sozinho | testes e gates |
| PLANNED | L2, moderada | `aifw-planner` (sonnet) | `aifw-worker` (haiku), distribuído e revisado pelo planner | `aifw-adversary`, depois `aifw-qa` |
| CRITICAL | L3, alta | agente principal (opus) | `aifw-lead` (sonnet), que quebra a parte para `aifw-worker` | `aifw-adversary`, depois `aifw-qa` |

- Com risco alto ou crítico em FAST, um `aifw-executor` faz sozinho; em WORK, um `aifw-senior` (opus) faz sozinho; depois, os dois revisores. Risco alto ou crítico também pede o plano aprovado no chat, spec e ADR. A importância é avaliada e registrada, mas não muda o caminho.

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
