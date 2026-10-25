# Revisão independente — approved-scope

## Adversário

Rodada 2 (correção). Escopo: `git diff 02a0116..HEAD` (commit 08bd7ac) contra os três achados de `evidence/independent-review-1.md` e REQ/SCN-AUTONOMY-APPROVED-SCOPE (`specs/agent-autonomy.delta.yaml`). Não refiz a caça no código já revisado. Experimentos em `scratchpad/adv2/test_probe2.py`, fora do projeto, com `add_change`/`edit` de `tests_python/test_approved_scope.py`.

Verificação: `python -m pytest tests_python/test_approved_scope.py tests_python/test_hooks.py -q` → 56 passed; probe → 10 passed; suíte inteira `python -m pytest tests_python -q` → 2725 passed.

### Achados da rodada 1

1. **Motivo do `tasks.yaml` sem a mudança: corrigido.** `hooks.py:171-174` (Edit) e `:179-184` (shell) agora dizem "tasks.yaml of the approved change <id>", como pede o `then` do SCN ("o tasks.yaml pedem confirmação, citando a mudança", linha 19 da spec). Conferi por Edit, por `sed -i`, por `echo >`, com duas mudanças aprovadas (o motivo cita `b`, a dona do arquivo, e não a lista) e com `TASKS.yaml` em maiúsculas.
2. **Paths com `./` não casavam: corrigido.** `hooks.py:136-138` tira o `./` depois de trocar `\` por `/`. Casam `./docs/`, `.\python\aifw\claude.py` (teste do projeto), `.//docs/` e `./templates/claude/agents/*.md`. Sem regressão em pastas que começam por ponto: `.github/` e `.\.github` continuam casando com `.github/w.yml` (`removeprefix` tira só `./`, não o ponto).
3. **`changeScope: off` não desligava o `tasks.yaml`: corrigido.** `evaluate` passa `scope=policy.get("changeScope", "ask") == "ask"`, a mesma condição de `outside_plan` (`hooks.py:125`), e `control_target` só protege o `tasks.yaml` com `scope`. Com `off`, Edit e `sed -i` no `tasks.yaml` aprovado não pedem. Os outros arquivos de controle seguem pedindo com `off` (`change.yaml` e `permissions.yaml` por Edit, `approval.md` por shell). Com `ask`, o `tasks.yaml` de mudança não aprovada continua livre. O CHANGELOG agora diz que o `off` desliga também a proteção do `tasks.yaml`. `control_target` não tem outro chamador (o de `.claude/worktrees/` é uma cópia antiga, fora do pacote).

A ressalva da rodada 1 sobre as listas de arquivos de controle também foi atendida: `docs/claude-code.md:54` e a seção de hooks do SKILL.md (template e instalada, idênticas no diff) incluem "o `tasks.yaml` de uma mudança aprovada".

### Ressalvas (sem reprovação)

- **`./` sozinho (ou `.`) como path não libera nada.** Com `paths: ["./"]`, o path vira `""`, e `x.md` pede ("outside the approved plan of plan"). Antes da correção já era assim (`"."`), então não é regressão. O erro só pede a mais, não libera nada.
- **`././docs` não casa.** `removeprefix` tira só um `./`. É uma entrada improvável, e o erro também só pede a mais.
- **A lista de controle não diz que o `tasks.yaml` sai com `changeScope: off`.** `docs/claude-code.md:54` e o SKILL.md põem o `tasks.yaml` aprovado entre os arquivos de controle sem a condição. O bullet "Plano aprovado" (`docs/claude-code.md:61`) e o CHANGELOG cobrem o `off`, então não há contradição.

## QA

Verificado em 2026-10-25, branch `feat/approved-scope` (HEAD 08bd7ac), cada comando rodado sozinho, sem `--write`.

### Comandos e gates

| Comando | Resultado |
| --- | --- |
| `python -m pytest tests_python -q` | 2725 passed (88,5 s) |
| `aifw spec validate approved-scope` | `pass: true`, sem findings |
| `aifw spec analyze approved-scope` | `pass: true`; 1 requisito com tarefa, 1 cenário verificado, 2 de 2 tarefas concluídas |
| `aifw claude check` | `status: pass`, sem findings |
| `aifw validate --change approved-scope` | `blocked` por um único gate: `independent-review` ("needs a line `Resultado: ...`"), que esta seção resolve. Passaram build, cli-docs, conformance, context-integrity, lint, manifest, project-map, secret-scan, session-conformance, tests e typecheck |

### Critérios de aceitação (proposal.md) e cenário da spec

Evidência: `tests_python/test_approved_scope.py` (13 casos, dentro da suíte de 2725) e `evidence/tests.txt`.

1. Arquivos do plano e pasta da mudança não pedem; `hooks.py` pede citando a mudança: `test_planned_paths_and_change_folders_do_not_ask` (claude.py, docs/x.md, docs/deep/y.md, aifw-qa.md, evidence/tests.txt, outra mudança) e `test_edit_outside_the_plan_asks` ("outside the approved plan of plan", por Edit e Write). Coberto.
2. Sem mudança aprovada ou com `changeScope: off`, `hooks.py` não pede: `test_without_an_approved_change_nothing_asks` e `test_change_scope_off`. Coberto.
3. `tasks.yaml` aprovado pede; o de mudança não aprovada não: `test_the_approved_plan_is_a_control_file` (Edit e `sed -i`, motivo "control file tasks.yaml of the approved change plan") e `test_without_an_approved_change_nothing_asks`. Com `off`, o `tasks.yaml` também sai da proteção (`test_change_scope_off`). Coberto.
4. Padrão `templates/claude/agents/*.md` casa `aifw-qa.md`: item 1. Coberto.
5. Suíte inteira passando: 2725 passed, rodada por mim. Revisão em duas etapas: adversário rodada 1 (`evidence/independent-review-1.md`, três achados, corrigidos), rodada 2 sem defeito provado, e esta etapa. Coberto.
6. Itens do Scope sem critério próprio: união de paths (`test_paths_of_every_approved_change_count`), `./` e `\` nos paths (`test_dot_slash_paths_match`), arquivo fora do projeto (`test_files_outside_the_project_do_not_ask`), `change.yaml`/`tasks.yaml` ilegível (`test_a_broken_change_is_left_out`). Cobertos. Os Non-goals (shell que escreve, L0/L1, comandos do `aifw`) não foram tocados no diff.

Rastreabilidade: `traceability.yaml` liga o SCN a `evidence/tests.txt` e o REQ ao design e ao ADR-0039; `spec analyze` confirma os elos e as duas tarefas.

### Documentação e artefatos derivados

- `docs/claude-code.md`: lista de `ask` (linha 54) inclui o `tasks.yaml` aprovado; o bullet "Plano aprovado" (linha 61) descreve a regra, os paths, a pasta livre, o shell fora e o `changeScope: off`. Atualizado.
- `CHANGELOG.md`: entrada em "Alterado" com o ADR-0039 e o `off` desligando também o `tasks.yaml`. Atualizado.
- `docs/decisions/ADR-0039-approved-scope.md`: accepted; cinco decisões, consequências e rollback conferem com o código. Atualizado.
- Skill: `templates/claude/skills/aifw-workflow/SKILL.md` e `.claude/skills/aifw-workflow/SKILL.md` têm as mesmas duas edições (passo 2 e lista de controle). A única diferença entre as cópias é o rodapé `<!-- aifw-version: 0.4.1 -->` da instalada, gerado por `claude enable`; `aifw claude check` passa. Atualizadas.
- `schemas/permissions.schema.json`: `changeScope` com `ask`/`off`. `templates/project-scaffold.json` não lista a opção, coerente com o padrão `ask`.
- `docs/cli-reference.generated.md`: não mudou, e não precisava (nenhum comando novo); o gate `cli-docs` passa.

### Standards

Fontes: `AGENTS.md` (sem regras de código), `principle-catalogs/engineering-principles.yaml`, a lista de smells da skill `code-review` e a configuração do repositório. `ruff check` nos dois arquivos de código: sem avisos (o gate `lint` também passa). Sem violação dura de padrão documentado. Os `# noqa: BLE001` seguem o uso já existente em `hooks.py` (5 ocorrências), `from test_workflows import init` é o padrão de 21 arquivos de teste, e `Path.is_relative_to` vale com `requires-python >= 3.11`. Juízos (smells, nunca violação):

- Duplicated Code, possível: `outside_plan` e o ramo de edição de `control_target` repetem a resolução do alvo (`file_path` ou `notebook_path`, `resolve`, relativo à raiz). Duas ocorrências; aceitável.
- Mysterious Name, possível: em `evaluate`, `scope` é o parâmetro booleano passado a `control_target` e também a variável do walrus que guarda o motivo textual de `outside_plan` (`elif scope := outside_plan(...)`). Nomes como `scoped` e `reason` evitariam a confusão.
- Primitive Obsession, leve: o plano é `dict[str, list[str]]` e a normalização de path (`\` para `/`, minúsculas, `./`, barras) fica inline em `outside_plan`. Proporcional ao tamanho.
- Sem Speculative Generality, Shotgun Surgery nem Middle Man: o diff toca só o hook, o schema, os testes e a documentação que a mudança exige.

### Ressalvas

- `tasks.yaml` lista `docs/cli-reference.generated.md` (TASK-SCOPE-DOCS) e esse arquivo não foi alterado no diff. Inofensivo (o plano pode ser mais largo que o diff).
- Ressalvas da rodada 2 do adversário continuam valendo, nenhuma reprovável: `./` ou `.` sozinho como path não libera nada; `././docs` não casa; a lista de controle em `docs/claude-code.md:54` e no SKILL.md não menciona a condição de `changeScope: off` para o `tasks.yaml`, mas o bullet da linha 61 e o CHANGELOG a cobrem.
- Da rodada 1, aceitas e cobertas pelo ADR: a pasta liberada é todo `.aifw/changes/active/` (a proposta fala da pasta da mudança aprovada), `*` do `fnmatch` atravessa `/`, e a comparação em minúsculas vale também em POSIX.
- Não verifiquei: comportamento em Linux/macOS (só rodei no Windows) nem desempenho com centenas de mudanças aprovadas.
- O `aifw validate --change approved-scope` sem `--write` só falhou no gate `independent-review`, que depende da linha abaixo; o `--write` final fica para o agente principal.

Resultado: aprovado com ressalvas
