# Revisão independente — quiet-enable-and-status

## Adversário

Rodada 2 (correção). Escopo: `git diff bdcfbf2..HEAD` (`python/aifw/hooks.py` `widens_plan`, `tests_python/test_approved_scope.py`, `CHANGELOG.md`, `evidence/tests.txt`) contra os achados de `evidence/independent-review-1.md` e `specs/agent-autonomy.delta.yaml:12` (REQ-AUTONOMY-APPROVED-SCOPE). O código já revisado na rodada 1 não foi caçado de novo.

`python -m pytest tests_python/test_approved_scope.py tests_python/test_orchestration.py -q`: 38 passed. As sondas rodaram por `python -m pytest` numa pasta temporária fora do projeto, com os helpers de `test_approved_scope.py` (`add_change`, `plan_call`) e `aifw.hooks.handle`/`approved_plans`.

### Achados da rodada 1

- Achado 1 (chave duplicada): corrigido. `widens_plan` agora usa `parse_yaml` (o `CoreLoader` de `read_yaml`/`approved_plans`). O Edit que insere `status: done` sem apagar `status: pending` pede (teste novo `test_duplicate_key_asks_and_keeps_the_plan_on` e sonda). A mudança continua em `approved_plans`, e o Edit fora do plano continua pedindo.
- Achado 2 (tarefa copiada com o mesmo `id` ou sem `id`): corrigido. A comparação é uma lista ordenada de pares `(id, paths)`, ou seja, um multiconjunto. A cópia de `TASK-X` com outro path pede, por Edit e por Write, e a tarefa sem `id` com paths também pede (teste novo e sonda).
- Achado 3 (CHANGELOG): corrigido. `CHANGELOG.md:7` agora diz que editar sem mudar os `paths` de nenhuma tarefa fica livre e que mudar `paths`, acrescentar ou duplicar tarefa com paths, edição não aplicável, YAML ilegível ou com chave duplicada e shell continuam pedindo. Isso bate com o código.

### O que a correção pode ter quebrado (conferido sem quebra)

- Troca de `status` continua livre:
  - Edit, Write e MultiEdit: `test_status_edits_of_the_approved_plan_do_not_ask`;
  - `replace_all` com duas tarefas: livre;
  - o próprio `tasks.yaml` desta mudança, copiado para o projeto temporário: trocar o status por Edit e por Write não pede, e trocar o título não pede.
- Troca de título livre: teste novo `test_title_edits_of_the_approved_plan_do_not_ask` e sonda.
- Mudar paths pede: incluir, remover, trocar, mover um path entre tarefas, renomear `paths` para `Paths` e `!!binary` (o `json.dumps` falha e a exceção conta como mudança).
- Reordenar as tarefas continua livre: as listas ordenadas são iguais.
- BOM no disco: `widens_plan` lê com `utf-8`, então o `﻿` entra no texto, e o scanner do PyYAML o descarta. Com o BOM, o status por Edit não pede, o Write com e sem BOM não pede, e incluir um path pede. A mudança continua em `approved_plans` (`read_yaml` usa `utf-8-sig`).
- Datas e booleanos com o `CoreLoader`:
  - o arquivo tem `createdAt: 2026-10-28`, `flag: yes`, `id: 2026-10-28`, `done: no`, `due: 2026-10-28T10:00:00Z`, e `2026-10-28` e `on` nos `paths`;
  - `approved_plans` dá `['docs/', '2026-10-28', 'on', 'src/']`;
  - o status (simples e `replace_all`) e `done: no` → `true` não pedem;
  - incluir um path pede.
- `json` já era importado em `hooks.py`, e a remoção de `import yaml` não deixa uso pendente: os testes do hook passam, e `evidence/tests.txt` registra 2755 passed na suíte inteira.

### Ressalvas

- Acrescentar uma tarefa sem `paths` (`- id: C\n  status: pending`) pede confirmação, porque o par `('C', '[]')` muda a lista. A REQ (`agent-autonomy.delta.yaml:12`) só exige pedir quando os paths mudam, então isso é conservador. O comportamento já existia antes da correção (a chave nova no dicionário) e não amplia o plano. Não reprova.
- Um `id` e o texto `"None"` se confundem em `str(task.get("id"))`. Isso não tem efeito, porque os paths entram no par.
- As ressalvas da rodada 1 continuam valendo (linha em branco no fim da cópia gera `.bak`; reordenar `paths` pede; `root` na assinatura do design).

## QA

### Gates e suíte (cada comando rodado sozinho, sem `--write`)

- `python -m pytest tests_python -q`: 2755 passed em 101,73 s, igual ao registrado em `evidence/tests.txt`.
- `aifw spec validate quiet-enable-and-status`: `pass: true`, sem findings.
- `aifw spec analyze quiet-enable-and-status`: `pass: true`; 2 requisitos ligados a tarefa, 2 cenários verificados, 3 de 3 tarefas concluídas; nenhum `weakTraces`.
- `aifw claude check`: `status: pass`, sem findings.
- `aifw validate --change quiet-enable-and-status`: todos os gates passam (build, cli-docs, conformance, context-integrity, lint, manifest, project-map, secret-scan, session-conformance, tests, typecheck). O único bloqueio é `independent-review`, que espera a linha `Resultado:` deste arquivo, escrita abaixo.

### Critérios da seção Acceptance de `proposal.md`

- Instalar, mudar o template e instalar de novo não cria `.bak`; cópia editada cria; cópia sem hash e diferente cria:
  - `tests_python/test_role_subagents.py`: `test_new_template_replaces_an_untouched_copy_without_backup`, `test_edited_copy_is_backed_up_even_when_the_template_changed` e `test_copy_without_a_hash_is_backed_up`, cada um parametrizado para a skill e para o `aifw-qa`;
  - implementação em `python/aifw/claude.py` (`install_template`, `HASH`, `INSTALLED`).
- `aifw claude check` passa depois da instalação: `test_copy_without_a_hash_is_backed_up` e `test_check_reports_a_subagent_from_another_version` (atualizado para `agentBackups == []`) chamam `check_project`; rodei o comando no repositório e passa.
- Status trocado por Edit não pede; incluir path ou reescrever com Write mudando `paths` pede; `sed -i` pede (`tests_python/test_approved_scope.py`):
  - `test_status_edits_of_the_approved_plan_do_not_ask` (Edit, Write, MultiEdit);
  - `test_path_edits_of_the_approved_plan_ask` (Edit, Write, MultiEdit);
  - `test_the_approved_plan_is_a_control_file_in_the_shell` (`sed -i` pede);
  - `test_edits_that_do_not_apply_ask`, `test_duplicate_key_asks_and_keeps_the_plan_on`, `test_duplicate_or_idless_tasks_with_paths_ask` e `test_title_edits_of_the_approved_plan_do_not_ask` cobrem os casos da rodada 1;
  - `test_change_scope_off_lets_every_plan_edit_through` cobre `changeScope: off`.
- Suíte inteira passando: 2755 passed (acima).
- Revisão em duas etapas: etapa do adversário (rodadas 1 e 2) neste arquivo e em `evidence/independent-review-1.md`; esta é a segunda etapa.

### Cenários da spec

- `SCN-SUBAGENTS-EDITED-BACKUP` (`specs/claude-subagents.delta.yaml`): coberto pelos três testes de backup acima; ligado a `evidence/tests.txt` em `traceability.yaml`.
- `SCN-AUTONOMY-APPROVED-SCOPE` (`specs/agent-autonomy.delta.yaml`): coberto pelos testes de `test_approved_scope.py` acima; o trecho "Sem mudança aprovada ativa, ou com changeScope off" fica com `test_change_scope_off_lets_every_plan_edit_through` e com os testes anteriores do arquivo, que seguem passando.

### Documentação e artefatos derivados

- `docs/claude-code.md`: linha 32 (backup só de cópia editada, sha256 do corpo), a lista de `ask` (agora "os `paths` do `tasks.yaml`") e o item "Plano aprovado" (status livre, ADR-0041). Reflete a mudança.
- `CHANGELOG.md:7`: descreve o hash e o `.bak` condicional, o status livre e o que continua pedindo (`paths`, tarefa copiada com paths, edição não aplicável, YAML ilegível ou com chave duplicada, shell). Bate com o código.
- `docs/decisions/ADR-0041-quiet-enable-and-status.md`: contexto, decisão em 4 itens, consequências (primeira atualização cria `.bak` uma vez; o hash não detém adulteração deliberada) e rollback; declara `Amends` de ADR-0038 e ADR-0039. Bate com `claude.py` (`INSTALLED` exige corpo, carimbo, hash e nada depois) e com `hooks.py`.
- Skill: conferi por script que o corpo do template (`templates/claude/skills/aifw-workflow/SKILL.md`) é igual ao da cópia (`.claude/skills/aifw-workflow/SKILL.md`) e que o sha256 gravado na cópia é o do corpo do template. O mesmo vale para os cinco `.claude/agents/aifw-*.md`. Os dois trechos alterados da skill (passo 2 e parágrafo do hook) dizem a mesma coisa nas duas.
- `tasks.yaml` x diff: todo arquivo do diff fora da pasta da mudança está nos `paths` (`hooks.py`, `test_approved_scope.py`, `claude.py`, `test_role_subagents.py`, `.claude/agents/`, a cópia da skill, o template, `docs/claude-code.md`, o ADR, `CHANGELOG.md`). `tests_python/test_third_audit.py` está listado e não mudou no diff; é sobra inofensiva do plano.

### Standards (feito por mim, sem subagente)

Fontes lidas: `AGENTS.md`, `principle-catalogs/engineering-principles.yaml`, `[tool.ruff]` de `pyproject.toml` (110 colunas; o gate `lint` passa) e a lista de smells da skill `code-review`. O repositório não tem `CODING_STANDARDS.md` nem `CONTRIBUTING.md`. Nenhuma violação dura de padrão documentado. Julgamentos, não violações:

- `python/aifw/hooks.py`, `widens_plan`: o `except Exception` largo engole a causa. É falha fechada (pede confirmação), tem `noqa` com motivo e teste (`test_edits_that_do_not_apply_ask`). Compatível com `clean-code-errors`, com custo de diagnóstico.
- `widens_plan` (possível Mysterious Name): devolve verdadeiro também para remover ou trocar path e para falha de leitura, não só para "ampliar". O docstring diz isso; o nome é mais estreito que o comportamento.
- `python/aifw/claude.py`, `INSTALLED`: o nome da constante (regex do formato instalado) coincide com um `INSTALLED` de `hooks.py` com outro sentido. Módulos distintos, sem conflito.
- `tests_python/test_approved_scope.py`: `BLOCK` repete parte de `TASKS` (possível Duplicated Code), aceitável em teste e legível.
- Design x código: o design descreve `widens_plan(root, path, tool_name, tool_input)`; o código tem `widens_plan(path, tool_name, tool_input)`, sem `root`. A versão do código é mais simples e não deixa uso pendente.
- Nada de Speculative Generality, Shotgun Surgery ou Middle Man. O que `AGENTS.md` pede (conferir dependentes, testes, documentação e derivados) foi cumprido.

### Ressalvas (não reprovam)

- `.aifw/specs/current/agent-autonomy.yaml` ainda traz a redação antiga de `REQ-AUTONOMY-APPROVED-SCOPE` (tasks.yaml aprovado como arquivo de controle inteiro). É esperado enquanto a mudança está ativa; o arquivamento precisa promover os dois deltas.
- Limites já conhecidos e documentados: o hash detecta edição acidental, não adulteração (ADR-0041); reordenar `paths` e acrescentar tarefa sem `paths` pedem confirmação (conservador, e não é o que a REQ exige); linha em branco no fim da cópia instalada gera `.bak` uma vez (ressalvas do adversário).
- Não verifiquei o comportamento do Claude Code real com o hook; a evidência são os testes do `handle` e a execução desta própria mudança, que marcou tarefas como `done` sem pedir confirmação (`evidence/tests.txt`).

Resultado: aprovado com ressalvas
