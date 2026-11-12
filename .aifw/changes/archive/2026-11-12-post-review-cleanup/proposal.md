# Proposal — Limpeza pós-revisão

## Intent

Pendências deixadas pelas revisões e pelos PRs recentes (ADR-0037, ADR-0042, ADR-0043), numa mudança só. Uma delas altera o comportamento da aprovação no chat: um comando de barra (`/ponytail:ponytail ultra`, `/clear`) hoje conta como resposta ao pedido de aprovação e o cancela, o que obriga a pessoa a pedir o plano de novo. As outras são manutenção.

## Scope

1. **Comando de barra não responde à aprovação.** Em `user_prompt` (`python/aifw/hooks.py`), uma mensagem que começa com `/` é ignorada pela aprovação, como as mensagens automáticas (`AUTOMATIC_PROMPT`): não aprova, não cancela, e o pedido continua pendente. O avaliador já ignorava esses comandos (`is_request`). O requisito aceito `REQ-AUTONOMY-CHAT-APPROVAL` muda (delta MODIFIED em `agent-autonomy`). Precisa de ADR-0044, curto, que altera o ADR-0037.
2. **Gatilho nos comentários `shortcut:`.** `hooks.py:93` (padrão recursivo `**` não expandido) e `indirect.py:256` (pacote carregado por nome não lido) passam ao formato `shortcut: <limite>, <quando atualizar>`. Só comentário.
3. **Apagar `.aifw/legacy/`** (TypeScript antigo, 1,4 MB, 72 arquivos rastreados). A busca confirmou que nada o usa: código, testes (`test_parity.py` lê só `tests_python/fixtures/legacy-parity.json`), gates, profiles, manifestos, PROJECT_MAP, CI, `pyproject.toml`, `MANIFEST.in` e scripts. Só `docs/python-migration.md` (linha 37) o cita; as menções em `.aifw/changes/archive/` são histórico e ficam. Ajustar o texto da migração.
4. **Ressalvas de revisões arquivadas**, conferidas no código atual:
   - a. Aberta. `docs/claude-code.md`: nas versões 2.1.217 e 2.1.218 do Claude Code o padrão de `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` era 1, e o `aifw claude check` só avisa quando a variável está definida.
   - b. Aberta. `test_planner_lead_and_skill_carry_the_fallback`: `"sem worker"` não existia antes do ADR-0043 e serve; `"agente principal"` já aparecia 3 vezes nos dois templates e passaria sem o plano B. A asserção passa a procurar `"não devolva a implementação ao agente principal"`.
   - c. Aberta. `tests_python/test_orchestration.py::edit` manda `file_path` e `notebook_path` juntos, e o teste do NotebookEdit passaria sem suporte a `notebook_path`. Para `NotebookEdit`, mandar só `notebook_path`.
   - d. **Já fechada, não entra.** O `last_path` e a regra de delegação a Haiku, que liam o log do avaliador e geravam o `AttributeError`, saíram no ADR-0037 (`grep last_path` não acha nada em `python/`). Os leitores atuais do log (`read_lines`) não têm esse caso.
   - e. Aberta. `python/aifw/cli.py` repete `["tasks", "impasse", ...]` três vezes (`assess eval`, `assess report`, `assess verdict`): usar `assessment.FEATURES`, sem mudar a CLI nem a referência gerada.
5. ADR-0044 e CHANGELOG.

## Non-goals

- Tratar outras mensagens (por exemplo, só pontuação) como não respostas.
- Mexer no pedido de aprovação em si, no congelamento da sessão ou no formato do `approval.md`.
- Procurar caminhos de bypass da aprovação (o hook protege contra erro, não contra forja).
- Mudar o schema do manifesto, que também lista os recursos do avaliador.
- Apagar as menções históricas ao diretório legado em `.aifw/changes/archive/`.
- Item 4d (já fechado).

## Acceptance

- Com um pedido de aprovação pendente, `/ponytail:ponytail ultra` não aprova nem cancela, o arquivo de pedido continua, e um "sim" seguinte aprova; teste cobre isso e falha sem a correção.
- Os dois comentários `shortcut:` seguem o formato com limite e gatilho; `ruff` e `compileall` passam.
- `.aifw/legacy/` não existe; `aifw map check`, `aifw context check` e a suíte passam sem ele; `docs/python-migration.md` não aponta mais para o diretório.
- `docs/claude-code.md` traz o item 4a e cita o comando de barra na tabela do UserPromptSubmit e em Aprovações.
- Os testes 4b e 4c falham se o trecho do plano B ou o suporte a `notebook_path` forem removidos.
- `cli.py` usa `FEATURES`; `aifw assess report --help` e `docs/cli-reference.generated.md` não mudam.
- ADR-0044 aceito; suíte inteira e `ruff` passando; revisão em duas etapas aprovada.
