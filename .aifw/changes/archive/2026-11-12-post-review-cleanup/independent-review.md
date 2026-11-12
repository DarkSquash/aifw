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

## QA

Diff conferido: `main..HEAD` (6f959dd, 451a614), 23 arquivos fora de `.aifw/legacy/` e 72 arquivos apagados nele.

### Suíte e gates (rodados nesta revisão, HEAD 451a614)

- `python -m pytest -q -p no:cacheprovider tests_python`: 2806 passed (165 s).
- `python -m ruff check .`: All checks passed. `python -m ruff format --check .`: 307 files already formatted.
- Compilação: `compileall` foi negado pelo hook do revisor (grava `.pyc`). No lugar dele, `compile()` em memória dos 27 módulos de `python/aifw`: todos compilam. A suíte também importa todos.
- `aifw map check --json`: `current: true`. `aifw context check`: `status: pass`, `findings: []`, rc 0.
- `aifw validate --change post-review-cleanup --json` (sem `--write`): passam `build`, `cli-docs`, `conformance`, `context-integrity`, `lint`, `manifest`, `project-map`, `secret-scan`, `session-conformance`, `tests` e `typecheck`. `missingArtifacts: []`. O único bloqueio era `independent-review`, porque faltava a linha `Resultado:`, que esta seção acrescenta.
- `aifw claude check`: `status: pass`, sem findings. A cópia `.claude/skills/aifw-workflow/SKILL.md` está coerente com o template.

### Critérios de aceite (`proposal.md`, Acceptance)

1. **`/ponytail:ponytail ultra` não aprova nem cancela, o pedido continua e um "sim" seguinte aprova; teste falha sem a correção.** Atendido. Teste: `tests_python/test_agent_autonomy.py::test_slash_commands_neither_approve_nor_drop_the_request`, parametrizado com `/ponytail:ponytail ultra`, `/clear` e `"  /compact"`. Ele verifica: sem aprovação, `APPROVAL_REQUEST` ainda existe, `Bash` continua `deny`, e um "sim" seguinte aprova. O código está em `python/aifw/hooks.py:852-853`. A falha sem a correção está registrada em `evidence/tests.txt` ("Contra o hooks.py de HEAD (cópia) as 3 entradas falham"). Não a repeti: rodar o teste contra o `hooks.py` de `main` em memória foi negado pelo hook (código que monta `UserPromptSubmit`). Aceito a evidência gravada.
2. **Os dois `shortcut:` com limite e gatilho; `ruff` e `compileall` passam.** Atendido. Os comentários estão em `hooks.py:93-94` ("expand it if an agent reaches a control file through one") e `indirect.py:256-257` ("read them if installed packages start being read for the script itself"). `ruff` passa. Para a compilação, vale o substituto acima.
3. **`.aifw/legacy/` não existe; map, context e suíte passam; `docs/python-migration.md` não aponta para ele.** Atendido. `git grep "legacy/"` fora do arquivo de histórico e desta mudança só acha a linha do CHANGELOG. `docs/python-migration.md:37` foi reescrito. Map, context e suíte passam, como registrado acima.
4. **`docs/claude-code.md` traz o item 4a e cita o comando de barra na tabela do UserPromptSubmit e em Aprovações.** Atendido. O item 4a está no parágrafo do limite de aninhamento ("Nas versões 2.1.217 e 2.1.218 ... o padrão era 1 ... o `check` só avisa quando a variável está definida"). O comando de barra aparece na linha `UserPromptSubmit` da tabela e em três itens de Aprovações (comando de barra, congelamento e parágrafo final).
5. **Testes 4b e 4c falham se o plano B ou o suporte a `notebook_path` forem removidos.** Atendido. Em 4b, a frase "não devolva a implementação ao agente principal" ocorre uma vez em cada template (`templates/claude/agents/aifw-planner.md:12` e `aifw-lead.md`) e só no trecho do plano B. Remover o trecho derruba a asserção de `tests_python/test_cascade.py:173`. Em 4c, `edit()` em `tests_python/test_orchestration.py:28-32` manda só `notebook_path` para `NotebookEdit`, e o hook lê o caminho por `file_path or notebook_path` (`hooks.py:128,205,266,655`). Sem esse fallback o caminho fica vazio, e o `deny` esperado em `claude.py` deixa de acontecer. As quebras propositais estão em `evidence/tests.txt`. Não as repeti.
6. **`cli.py` usa `FEATURES`; `assess report --help` e `docs/cli-reference.generated.md` não mudam.** Atendido. `cli.py:11` importa `FEATURES`, usado em três `choices=FEATURES`. `docs/cli-reference.generated.md` não está no diff, e o gate `cli-docs` (`generate_cli_reference.py --check`) passou. Rodar o script direto foi negado pelo hook. A igualdade de choices e defaults foi conferida pelo adversário.
7. **ADR-0044 aceito; suíte e `ruff` passando; revisão em duas etapas aprovada.** Atendido. `docs/decisions/ADR-0044-slash-commands-and-approval.md` tem `Status: accepted` e `Amends: ADR-0037`, no formato dos ADR-0039 a ADR-0043. A suíte e o `ruff` passam. Esta seção fecha a segunda etapa.

### Cenário da spec (`SCN-AUTONOMY-CHAT-APPROVAL`, delta MODIFIED)

- Then 1: o comando de barra não aprova nem cancela, e um "sim" seguinte aprova. Coberto pelo teste novo. "/sim" não aprova pelo mesmo ramo `startswith("/")`, sem caso dedicado. As outras cláusulas (outra resposta cancela, mensagem automática, dois pedidos, outra sessão) seguem cobertas pelos testes existentes do mesmo arquivo, que passam.
- Then 2: o comando de barra não destrava. Coberto pela asserção `call(change, "Bash", ...) == "deny"` do teste novo.
- Then 3: sem mudança de texto em relação à spec atual. Os testes existentes passam.
- A rastreabilidade (`traceability.yaml`) liga o SCN a `evidence/tests.txt`, e o REQ ao design e ao ADR-0044. `.aifw/specs/current/agent-autonomy.yaml:41` ainda tem o texto antigo. Isso é esperado: a spec atual só muda no archive.

### Documentação e artefatos derivados

- A mudança chega a `docs/claude-code.md`, ADR-0044, CHANGELOG (seção "Alterado"), `docs/python-migration.md`, o template da skill `aifw-workflow` e sua cópia instalada (sha do cabeçalho atualizado, `aifw claude check` passa). O comentário de `pre_tool_use` também foi atualizado. As ressalvas 1 e 2 do adversário foram resolvidas em 451a614: o exemplo `/clear` virou `/model` na doc e no ADR, e a skill e o comentário citam o comando de barra.
- ADR-0037 continua com "a mensagem seguinte da pessoa é a resposta ao plano". Isso segue a convenção do repositório: os ADRs emendados (por exemplo, pelos ADR-0039 a ADR-0043) não são reescritos, e a emenda fica no `Amends:` do novo.
- `PROJECT_MAP.md` não lista ADR-0040 a ADR-0044. Isso já era assim antes da mudança, e `map check` dá `current`.

### Standards (padrões do repositório, `principle-catalogs/engineering-principles.yaml` e lista de smells)

- `clean-code-comments`: os comentários novos e reescritos explicam o porquê, como "a slash command is not an answer and leaves the request waiting", e os limites dos `shortcut:`. Nenhum narra sintaxe. O formato `shortcut: <limite>, <quando atualizar>` é cumprido.
- `clean-code-tests`: o nome do teste novo diz o comportamento, as expectativas são independentes da implementação (arquivo de pedido, decisão do hook, `approval.md`) e ele falha pela regressão específica.
- Duplicated Code (juízo, leve): o filtro "começa com `/` ou casa `AUTOMATIC_PROMPT`" agora existe em `hooks.user_prompt` e em `assessment.is_request`. O design escolheu não criar função nova. Com duas ocorrências e uma regra que muda em conjunto, é aceitável. Fica como ponto se uma terceira aparecer.

### Ressalvas (não reprovam)

1. **Plano não acompanhou o segundo commit.** 451a614 alterou `templates/claude/skills/aifw-workflow/SKILL.md` e `.claude/skills/aifw-workflow/SKILL.md`, mas nenhum `paths` de `tasks.yaml` os lista. `design.md` ainda diz "As cópias instaladas em `.claude/` não mudam (nenhum template muda)". Pelo ADR-0039, editar fora dos paths pede confirmação, mas não bloqueia. Não verifiquei se houve confirmação. Nenhum critério de aceite depende disso. É só desalinhamento de rastreabilidade.
2. **Import antecipado em `cli.py` (juízo, desempenho).** `cli.py` carrega os módulos do projeto sob demanda (`cli.py:354`) e, no topo, só `common`. A linha nova `from .assessment import FEATURES` (`cli.py:11`) traz `concurrent.futures`, `urllib.request` e `http.client` para todo comando `aifw`. Medido com `python -X importtime -c "import aifw.cli"`: `aifw.assessment` soma cerca de 160 ms cumulativos, dos quais uns 32 ms são de `aifw.common`, que já era carregado. O total foi de uns 200 ms. Isso não fere critério de aceite nem padrão documentado. Se o tempo de início importar, uma alternativa é mover `FEATURES` para `common` ou importar sob demanda.
3. **Ressalva 3 do adversário (gatilhos dos `shortcut:`).** O critério de aceite 2 pede só o formato com limite e gatilho, e isso é cumprido. Os gatilhos do código diferem do texto do design, mas são concretos e verificáveis. Não fere nenhum critério. Fica como desalinhamento entre design e código.

### Não verificado

- Se o Claude Code entrega o texto cru do `/comando` ao `UserPromptSubmit` em uso real. Só há o teste do hook, com payload montado, e indício indireto. Se o harness não disparar o hook para comandos embutidos, a correção não tem efeito para eles, mas também não piora nada.
- A falha do teste novo contra o `hooks.py` de `main` e as quebras propositais de 4b e 4c: o hook negou a reexecução em memória. Aceitei `evidence/tests.txt`.
- `compileall` e `generate_cli_reference.py --check` rodados diretamente: o hook negou os dois. Os substitutos estão acima (`compile()` em memória e o gate `cli-docs`).

Resultado: aprovado com ressalvas
