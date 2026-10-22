# Design — Modo ativo do avaliador de tarefas

## Context

`assessment.assess` avalia risco, importância e complexidade em três chamadas paralelas ao modelo de decisão e transforma o resultado num caminho por uma regra fixa, com o piso do diff. Hoje o hook `UserPromptSubmit` roda em segundo plano (`async`) e só grava em `.aifw/assessments/shadow.jsonl`. O roteamento já tem um padrão de ativação humana: `route activate`, com o registro e a assinatura.

## Approach

Em `python/aifw/assessment.py`:
- `activate(root, feature, by, at)` confere o critério com `report()`. Ali só contam os pedidos da pessoa, sem as mensagens automáticas. Grava `.aifw/assessor.yaml` (`kind: AssessorActivation`, `features.tasks`) com quem aprovou, quando, o modelo e o retrato do relatório.
- `activation()` lê o registro e exige `human:` e `signing.approved`. `active()` exige também a avaliação ligada no `aifw.yaml`.
- `assess(..., session=)` grava a sessão e o modo (`shadow` ou `active`) em cada registro. `last_path()` lê o último caminho da sessão.
- `path_context()` monta o texto entregue ao agente, em português, com a regra do caminho.
- `report()` mostra `active`. `pending_notices()` avisa quando a ativação é possível e quando ela está valendo.

Em `python/aifw/hooks.py`:
- `user_prompt`, com o modo ativo, roda `assess(use_diff=True)` e devolve `hookSpecificOutput.additionalContext`. Um `AifwError` vira o aviso de indisponível.
- `evaluate(..., session=)` passa a sessão à delegação. Com o modo ativo, delegar a Haiku pede confirmação se `last_path` da sessão for PLANNED ou CRITICAL.
- `.aifw/assessor.yaml` entra em `CONTROL`.

Em `python/aifw/claude.py`, `entries_for(event, root)` instala `ACTIVE_PROMPT` (síncrono, 60 s) quando `active(root)`. A instalação e a checagem usam a raiz.

Em `python/aifw/cli.py`, `assess activate` entra em `APPROVALS` (terminal humano e id do projeto). O hook já trata `aifw … activate` como aprovação.

## Decisions

- **A ativação é um arquivo próprio, não um `mode: active` no manifesto:** assim a assinatura cobre só a decisão da pessoa, como no roteamento, e desligar é apagar o arquivo.
- **O hook de pedidos só fica síncrono com a ativação:** no modo sombra continua sem atraso.
- **Falha do serviço não bloqueia o pedido:** o plano original diz que o avaliador nunca bloqueia o trabalho.
- **O piso do diff vale no modo ativo:** ele só sobe o risco. No início de uma tarefa, o diff pode ser de trabalho anterior, e isso só deixa o caminho mais cauteloso.

## Risks and rollback

- Atraso de 1 a 2 s por pedido no modo ativo, e até 60 s se o serviço estiver lento; qualquer falha vira aviso.
- Texto do pedido enviado ao OpenRouter: igual ao modo sombra, com as mesmas guardas (allowlist, classificação, `redact`, só pedidos da pessoa).
- Rollback: apagar `.aifw/assessor.yaml` e rodar `aifw claude enable`; ou `git revert` do commit. Nada é migrado.
