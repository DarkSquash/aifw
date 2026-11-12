# Revisão independente — post-review-cleanup

## Adversário

### Escopo revisado

- Diff `main..HEAD` sem `.aifw/legacy/`: `python/aifw/hooks.py`, `python/aifw/indirect.py`, `python/aifw/cli.py`, `tests_python/test_agent_autonomy.py`, `tests_python/test_cascade.py`, `tests_python/test_orchestration.py`, `docs/claude-code.md`, `docs/python-migration.md`, ADR-0044, CHANGELOG.
- Spec: `specs/agent-autonomy.delta.yaml` (MODIFIED REQ-AUTONOMY-CHAT-APPROVAL) contra `.aifw/specs/current/agent-autonomy.yaml`; critérios em `proposal.md` (Acceptance), `design.md`, `tasks.yaml`.
- Remoção de `.aifw/legacy/`: `git grep legacy` fora de `.aifw/changes/archive/` só acha a própria mudança, `schemas/decision-catalog.schema.json` (enum `maturity: legacy`, sem relação) e as fixtures `legacy-parity.json`. Nada vivo depende do diretório.

### Verificações feitas

- `user_prompt` (hooks.py:852-853): com `prompt` já passado por `strip()`, `startswith("/")` impede `record_chat_approval`; o pedido não é removido (o `unlink` fica dentro de `record_chat_approval`), e `awaiting_reply` continua negando ferramentas porque depende só de `approval-request.yaml` e do arquivo de sessão. Isso atende ao delta, then 1 e 2 ("o comando de barra não aprova nem cancela, e um 'sim' seguinte ainda aprova"; "a mensagem automática e o comando de barra não [destravam]").
- O avaliador continua igual: `is_request` já excluía `/`.
- `pytest tests_python/test_agent_autonomy.py tests_python/test_orchestration.py tests_python/test_cascade.py`: 204 passed.
- `cli.py`: `create_parser()` mostra `--feature` com `choices` `('tasks', 'impasse', 'context', 'intake', 'traceability', 'decisions')` em `assess eval`, `report` e `verdict`, na mesma ordem e com os mesmos defaults (`None`, `tasks`, `tasks`). `FEATURES` é tupla, e o argparse a aceita. O help sai igual.
- Os dois comentários `shortcut:` seguem o formato `<limite>, <quando atualizar>` e só mudaram de texto: o código continua `continue` e `return found`.

### Achados

Nenhum achado provado.

### Ressalvas (sem prova, não reprovam)

1. **`/clear` como exemplo na doc e no ADR.** `docs/claude-code.md:101` e ADR-0044, Contexto, citam `/clear` como comando após o qual "um 'sim' seguinte ainda aprova". Em uso real, `/clear` pode nem disparar `UserPromptSubmit` e pode abrir um `session_id` novo. Nesse caso, o "sim" seguinte cai em outra sessão, e `requested_here` o ignora: o pedido não é aprovado, e a nova sessão não fica congelada. É comportamento anterior à mudança, mas a doc passa a prometer o contrário para esse exemplo. Não verifiquei: o hook do revisor negou `npx ctx7`, e o teste usa um `session_id` fixo. A evidência da própria mudança também marca como não verificado se o texto chega cru ao hook.
2. **Comentário e skill desatualizados.** `hooks.py:574` ainda diz "so the next message is that answer". `templates/claude/skills/aifw-workflow/SKILL.md:18`, e a cópia instalada, dizem "Qualquer outra resposta cancela o pedido" sem a exceção do comando de barra. Pela leitura de "resposta", a frase ainda é defensável, e o hook nega as ferramentas com mensagem clara, então o agente não age errado. Fica como ponto de texto.
3. **Gatilhos dos `shortcut:` diferentes do design.** O design (Approach, item 2) previa "quando um comando real precisar de padrão recursivo no topo, com busca limitada" e "quando um pacote local puder ser carregado por nome (`NODE_PATH`, workspace)". O código traz outros gatilhos ("if an agent reaches a control file through one"; "if installed packages start being read for the script itself"). O critério de aceite (só o formato) é cumprido.

### Não verificado

- Como o Claude Code entrega comandos de barra embutidos e de plugin ao `UserPromptSubmit`: se chegam em texto cru, se chegam expandidos (por exemplo, `<command-name>`, que já casaria com `AUTOMATIC_PROMPT`) ou se não chegam.
- As quebras propositais dos testes 4b e 4c e o `generate_cli_reference.py --check`: aceitei a evidência de `evidence/tests.txt` e não as repeti.
- A suíte inteira e o `ruff`: aceitei a evidência (2806 passed) e não os rodei de novo.
