# Revisão independente — mandatory-orchestration

## Adversário

Rodada 2 (correção). Escopo: `git diff 2257b56..HEAD` (commit f8272d7) contra o achado A1 e as ressalvas R1, R2 e R4 de `evidence/independent-review-1.md`, e a spec `specs/claude-subagents.delta.yaml`. O código revisado na rodada 1 não foi reexaminado. Modelo de ameaça: erro do agente (ADR-0034, ADR-0037).

### Conferência dos achados da rodada 1

- **A1 (corrigido).** A spec pede, na linha 24, "o aifw-quick nas tarefas rápidas de L2 e L3". Agora as tabelas nomeiam o `aifw-quick` nas linhas L2 e L3:
  - nas linhas 83-84 das duas cópias da skill (`templates/claude/skills/aifw-workflow/SKILL.md` e `.claude/skills/aifw-workflow/SKILL.md`);
  - nas linhas 19-20 de `docs/routing.md`, como já fazia a tabela do avaliador nas linhas 40-41.

  O papel do `aifw-quick` passou a ser "tarefas do caminho FAST e tarefas rápidas e mecânicas de L2/L3" na linha 91 da skill e na linha 142 de `docs/claude-code.md`. Fora o carimbo de versão, as duas cópias da skill são iguais, e as duas cópias de `aifw-quick.md` também (conferido com `diff`). O texto de `aifw-quick.md` (description e corpo) cobre o caminho FAST e as subtarefas de L2/L3. Ele bate com o bullet da linha 100 da skill e com o item 1 do ADR-0040. Procurei com `grep` outra menção ao `aifw-quick` limitada ao caminho FAST e só achei a do ADR-0038, linha 22. Ela é histórica e foi substituída pelo ADR-0040, então não conta como contradição.
- **R1 (tratada).** O motivo da negação em `hooks.py:171` agora termina com "only the person changes orchestration in permissions.yaml", e o ADR-0040 ganhou a linha correspondente. Isso é coerente com a spec: a sessão recebe `deny`, e um subagente recebe `ask` de control file, que a pessoa confirma. O teste que confere o motivo (`test_orchestration.py:49`) continua passando, porque o motivo ainda cita `aifw-executor` e `aifw-quick`.
- **R2 (tratada).** A linha 101 da skill diz que fazer inline só vale "sem mudança L2/L3 aprovada ativa", o que bate com o hook e com a spec.
- **R4 (tratada em parte; ver ressalva abaixo).** Entraram testes de MultiEdit e NotebookEdit e de formatos de `sessionPaths`: pasta, padrão, `./`, barra invertida, maiúsculas e `./` não liberando o projeto.

### Verificações

- `python -m pytest tests_python/test_orchestration.py tests_python/test_role_subagents.py -q -p no:cacheprovider`: 27 passed.
- `aifw claude check`: `status: pass`, sem findings.
- O caso `Docs/X.md` com `docs/` não depende do sistema de arquivos ser case-insensitive. Quem acerta a caixa é o `edited_file`, que passa o caminho para minúsculas, então o teste vale também em POSIX.

### Achados

Nenhum achado provado nesta rodada.

### Ressalvas (sem reprovação)

- **R6. O teste de NotebookEdit não exercita `notebook_path`.** O helper `edit` em `tests_python/test_orchestration.py:29-35` manda `file_path` e `notebook_path` juntos, e `edited_file` (`hooks.py:126`) lê primeiro o `file_path`. Por isso `test_multiedit_and_notebookedit_follow_the_same_rule` passaria mesmo sem suporte a `notebook_path`, que é o único campo que o NotebookEdit real envia. O comportamento está certo: num diretório temporário, `edited_file(r, {"notebook_path": r/"a.ipynb"})` devolve `a.ipynb`, e com os dois campos devolve o do `file_path`. A lacuna fica só no teste. Para fechá-la, basta mandar só `notebook_path` quando `tool == "NotebookEdit"`.

## QA

Escopo: `git diff main...HEAD` (27 arquivos), spec `specs/claude-subagents.delta.yaml`, `proposal.md` (Acceptance e Non-goals), `design.md`, ADR-0040, `tasks.yaml`, `traceability.yaml` e `evidence/tests.txt`. Não editei nada fora deste arquivo.

### Gates, um por vez

| Comando | Resultado |
| --- | --- |
| `python -m pytest tests_python -q -p no:cacheprovider` | 2742 passed em 110,97 s (bate com `evidence/tests.txt`) |
| `aifw spec validate mandatory-orchestration` | `pass: true`, sem findings; capability `claude-subagents` |
| `aifw spec analyze mandatory-orchestration` | `pass: true`, sem findings; requisitos 2/2 ligados a tarefa, cenários 2/2 verificados, tarefas 3/3 concluídas; `weakTraces` vazio |
| `aifw claude check` | `status: pass`, sem findings |
| `aifw validate --change mandatory-orchestration` | `blocked` por um único bloqueio: o gate `independent-review` ("needs a line `Resultado: ...`"), que esta revisão fecha na última linha. Passam build, cli-docs, conformance, context-integrity, lint, manifest, project-map, secret-scan, session-conformance, tests e typecheck. `missingArtifacts` vazio; sem `--write`. |

Também: `python -m ruff check python tests_python` passa, e `ruff format --check` nos três arquivos Python alterados (hooks.py, assessment.py, test_orchestration.py) já está formatado.

### Critérios de aceitação (proposal.md) e evidência

| Critério | Evidência |
| --- | --- |
| Sessão (sem `agent_id`) editando `python/aifw/claude.py` é negada com o motivo | `tests_python/test_orchestration.py::test_the_session_is_denied_and_told_who_to_delegate_to` (Edit e Write; o motivo cita `orchestrated`, `aifw-executor`, `aifw-quick`); implementação em `python/aifw/hooks.py:session_edit` |
| A mesma edição com `agent_id` segue | `test_a_subagent_is_not_denied`; `test_multiedit_and_notebookedit_follow_the_same_rule` (deny sem `agent_id`, livre com ele) |
| Pasta da mudança, arquivo fora do projeto e `sessionPaths` seguem para a sessão | `test_session_paths_change_folders_and_outside_files_are_free`; formatos de `sessionPaths` em `test_session_paths_match_folder_pattern_dot_slash_backslash_and_case` (7 casos) e `test_a_dot_slash_session_path_does_not_free_the_whole_project` |
| Sem mudança aprovada ativa, ou com `mode: off`, a sessão edita como antes | `test_without_an_approved_change_the_session_edits` (inclui mudança não aprovada), `test_mode_off` |
| Contexto do avaliador cita `aifw-executor` no CRITICAL e `aifw-quick` em PLANNED e CRITICAL | `tests_python/test_role_subagents.py` (parametrização PLANNED e CRITICAL com os dois nomes), `test_assessor_active.py` (PLANNED com `aifw-quick`); fonte: `PATH_RULE` em `python/aifw/assessment.py` |
| Skill descreve a orquestração obrigatória em L2/L3 e o Haiku nas tarefas rápidas | `templates/claude/skills/aifw-workflow/SKILL.md` linhas 83-84, 91, 100-101; a cópia instalada `.claude/skills/aifw-workflow/SKILL.md` tem o mesmo texto (só diverge no carimbo `aifw-version` do fim, esperado); `aifw claude check` passa |
| Suíte inteira passando | 2742 passed, rodado por mim (acima) |
| Revisão em duas etapas aprovada | Adversário: rodada 1 com A1 (corrigido), rodada 2 sem achado provado; esta etapa fecha com o resultado abaixo |
| Mudança executada pelo `aifw-executor`, salvo o núcleo do hook | Só consta em `evidence/tests.txt` ("Divisão do trabalho"). O git não registra qual agente editou, então não consigo comprovar de forma independente. A divisão declarada bate com o diff: `hooks.py` (núcleo, em `sessionPaths`), schema e `permissions.yaml` pela sessão |

### Spec

- `REQ-SUBAGENTS-MANDATORY-ORCHESTRATION` / `SCN-SUBAGENTS-MANDATORY-ORCHESTRATION`: cobertos pelos testes acima. A ligação `verifiedBy` está em `traceability.yaml` e o `spec analyze` conta o cenário como verificado. Os dois "then" da spec (negação citando os dois subagentes; sem mudança ou com `off`, sem negação) têm teste.
- `REQ-SUBAGENTS-DELEGATION` / `SCN-SUBAGENTS-DELEGATION`: o contexto cita os subagentes por caminho (testes de `test_role_subagents.py`). A skill manda delegar por `subagent_type` sem `model` e só passar `model` para subir (SKILL.md, bullet da linha 96).
- Non-goals respeitados: nenhum código novo trata comandos de shell que escrevem; sem mudança aprovada não há negação (testado), então L0/L1 não são afetados; o hook só exige "não ser a sessão" e não escolhe o subagente.
- Risco do design (o Claude Code deixar de enviar `agent_id`): fixado pelos testes com o formato documentado, limitação aceita no design.

### Documentação e artefatos derivados

- `docs/claude-code.md`: bullet "Orquestração" (linha 62) e papel do `aifw-quick` na tabela de subagentes (linha 142). Confere com o hook.
- `docs/routing.md`: tabelas L2/L3 e PLANNED/CRITICAL com `aifw-executor` e `aifw-quick`, e a frase "orquestração obrigatória ... inline só em L0 e L1". Saíram "opus executa" e "trabalho trivial pode ser feito inline" (grep em docs, templates e skill: nenhum resquício fora de ADRs históricos).
- `CHANGELOG.md`: entrada em "Alterado" com ADR-0040, `sessionPaths`, `mode: off`, L3 pelo executor e caminhos do avaliador.
- `docs/decisions/ADR-0040-mandatory-orchestration.md`: status, data, impacto, mudança e `Amends` ADR-0038/0039; decisão, consequências e rollback coerentes com o hook (inclui a frase da R1).
- `templates/claude/agents/aifw-quick.md` e `.claude/agents/aifw-quick.md`: idênticos entre si, com o novo escopo L2/L3.
- `schemas/permissions.schema.json`: `orchestration` com `mode` (`required`/`off`) e `sessionPaths`, com `additionalProperties: false`; `test_the_schema_rejects_an_unknown_mode` prova a recusa. `.aifw/effective-policy.json` não contém campos de permissões (0 ocorrências de `orchestration` e `changeScope`), então não há derivado a regenerar.
- `.aifw/specs/current/claude-subagents.yaml` ainda não traz o delta. É o estado esperado enquanto a mudança está ativa; o delta entra no arquivamento.

### tasks.yaml contra o diff (ressalva R3 do adversário)

Alterados pelo diff e fora do `paths` de qualquer tarefa (a pasta `.aifw/changes/active/` é livre e ficou de fora da conta):

- `templates/claude/agents/aifw-quick.md`
- `.claude/agents/aifw-quick.md`
- `tests_python/test_approved_scope.py`

No sentido inverso, `.aifw/effective-policy.json` está listado e não foi alterado. Os outros 18 arquivos de código, teste e documentação do diff estão listados. Não reprova: as três edições vieram da correção da rodada 1 (o `aifw-quick.md`) e dos 8 testes de `test_approved_scope.py` que a própria regra nova quebrou, e não deixaram finding no `spec analyze` nem no `session-conformance`. Fica como ressalva de rastreabilidade, para o plano refletir o que foi feito.

### Eixo Standards

Fontes lidas: `AGENTS.md` (alterações e efeitos relacionados, escopo), `principle-catalogs/engineering-principles.yaml` (nomes, coesão, erros, comentários, testes), `pyproject.toml` (ruff, 110 colunas, regras E4/E7/E9/F) e a lista de smells da skill `code-review`. Nenhum documento do repositório define estilo além disso; o ruff passa.

- **Padrões documentados: nenhuma violação.**
  - Nomes (`edited_file`, `in_paths`, `session_edit`) revelam a intenção.
  - A extração de `edited_file` e `in_paths` de `outside_plan` mantém o comportamento do ADR-0039, e os 8 testes de `test_approved_scope.py` seguem passando (agora como subagente).
  - Erro explícito: `session_edit` roda dentro do `try` de `pre_tool_use`; um `permissions.yaml` inválido vira `ask` com a causa e nunca passa em silêncio.
  - Os comentários dizem o porquê.
  - Os testes são comportamentais e nomeados pela regressão. Os efeitos relacionados (skill, docs, CHANGELOG, ADR, schema, testes antigos) foram tratados, como pede o `AGENTS.md`.
- **Smells (juízo, não violação):**
  - Possível Duplicated Code: `outside_plan` e `session_edit` repetem a sequência "planos, `edited_file`, sai se `None` ou `.aifw/changes/active/`, `in_paths`". Já compartilham os dois helpers; um terceiro para o prefixo trocaria três linhas por indireção, então não vejo ganho claro.
  - Possível Primitive Obsession leve: `orchestration` e `changeScope` são lidos como dict e strings soltos de `policy`. É o padrão do restante de `hooks.py`.
  - `session_edit` lê o `permissions.yaml`, que `evaluate` lê de novo logo depois. Só ocorre em edição sem `agent_id` com mudança aprovada ativa, e o custo é irrelevante.
  - Há linhas de mensagem com mais de 110 colunas em `hooks.py` (incluindo a de `session_edit`). O ruff não as acusa, porque `E501` não está em `select`, e várias já existiam antes da mudança.

### Ressalvas

- **R3 (mantida, não reprova):** três arquivos alterados fora dos `paths` do `tasks.yaml` e um listado sem alteração (detalhe acima). Sugestão: acrescentar os três ao `tasks.yaml` (arquivo de controle, com confirmação da pessoa).
- **R6 (do adversário, mantida):** o teste de NotebookEdit manda `file_path` junto com `notebook_path` e passaria mesmo sem suporte a `notebook_path`. O comportamento está correto e a lacuna é só do teste.
- A execução pelo `aifw-executor` é afirmada em `evidence/tests.txt`, mas não é verificável a partir do git.
- `aifw validate --change` só chega a `pass` depois da linha de resultado abaixo; não o rodei de novo após escrevê-la.

### Achados provados

Nenhum.

Resultado: aprovado com ressalvas
