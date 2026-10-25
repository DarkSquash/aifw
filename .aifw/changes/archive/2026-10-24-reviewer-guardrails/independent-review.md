# Revisão independente — reviewer-guardrails

## Adversário

Esta é a rodada 3, a segunda de correção.

Escopo revisado:

- `git diff 78332c7..HEAD`, que é o commit 9b83f20;
- o achado de `evidence/independent-review-2.md`;
- a delta `specs/claude-subagents.delta.yaml`, em especial o REQ-SUBAGENTS-REVIEWER-GUARD: negar o que altera o repositório, "deixando seguir leitura".

Não refiz a caça no código já revisado. Os experimentos ficaram fora do projeto, em `scratchpad/r3/probe.py`.

O comando `python -m pytest tests_python/test_reviewer_guardrails.py tests_python/test_shell.py tests_python/test_indirect_code.py -q` deu 340 passed. O arquivo `test_reviewer_guardrails.py` tem 59 casos.

### Conferência do achado da rodada 2

O achado foi corrigido. A mudança está em `python/aifw/shell.py:185` e `:188`. Com ela, `shell.analyze` classifica como `read-only`:

- `git config list`;
- `git config list --show-origin`;
- `git tag -v v1`;
- `git tag --verify v1`;
- `git tag -n`;
- `git -C x tag -n`.

Os dois primeiros casos novos de `ALLOWED` cobrem `config list` e `tag -v` para os dois revisores.

### O que a correção poderia ter quebrado

- As escritas continuam `git-local`: `git config set a b`, `git config --unset a`, `git tag -a v9 -m x` e `git tag -d v1`.
- Um comando composto ainda pega a escrita: `git config list; git commit -m x` dá `commit`.
- Testei no git 2.55 as combinações em que `-n`, `-v` ou `list` vêm primeiro e a escrita vem depois:
  - `git tag -n -a v9 -m x`, `git tag -n -d v1` e `git tag -n -f v1`;
  - `git tag -v -a v9 -m x` e `git tag -v -d v1`;
  - `git config list --add a.b c` e `git config list a.b c`.

  O git rejeita todas com erro de uso (rc 128 ou 129) antes de escrever. Por isso, classificá-las como `read-only` pelo primeiro argumento não deixa passar nenhuma alteração.

### Achados

Nenhum provado.

### Ressalvas

1. A linha "Cobertura dos cenários (... 35 casos)" de `evidence/tests.txt` continua com a contagem antiga. A linha nova da rodada 2, no mesmo arquivo, já diz 59. É só documentação.
2. As ressalvas da rodada 2 sobre comportamento anterior a 9ac9cd1 continuam fora de escopo: `git config get`, `git remote get-url` e a regra do primeiro argumento em `git branch -r -d`.

## QA

Escopo: `git diff f419bd5..HEAD` (24 arquivos), mais o working tree. Comandos rodados cada um sozinho.

### Comandos e gates

| Comando | Resultado real |
|---|---|
| `python -m pytest tests_python -q` | 2633 passed in 92.67s |
| `aifw spec validate reviewer-guardrails` | `pass: true`, sem findings |
| `aifw spec analyze reviewer-guardrails` | `pass: true`; requisitos 3/3 ligados a tarefa, cenários 3/3 verificados, tarefas 3/3 concluídas; `weakTraces` vazio |
| `aifw claude check` | `status: pass`, sem findings |
| `aifw validate --change reviewer-guardrails` | Passaram build, cli-docs, conformance, context-integrity, lint, manifest, project-map, secret-scan, session-conformance, tests e typecheck. Só o gate `independent-review` falhava, por falta da linha `Resultado:` que este arquivo passa a ter |

`tests_python/test_reviewer_guardrails.py` coleta 59 casos (`pytest --co`), o número que `evidence/tests.txt` declara.

### Critérios de aceitação da proposta

| Critério | Evidência |
|---|---|
| Revisor não edita `python/aifw/claude.py`, não roda `sed -i`, `git commit`, `git stash`; escreve o `independent-review.md`, um arquivo fora do projeto, e roda `pytest`, `git diff`, `aifw spec analyze` | `tests_python/test_reviewer_guardrails.py`: `DENIED` (8 chamadas, incluindo `git stash -a`, `git tag -a`, `git reflog expire`, redirecionamento) e `ALLOWED` (11 chamadas, incluindo `git config list`, `git tag -v`), cada uma para `aifw-adversary` e `aifw-qa`. Implementação em `python/aifw/hooks.py` (`reviewer_change`, `pre_tool_use`). Eu mesmo, como `aifw-qa`, tive negados `cmp`, `ruff` e `compileall`, e passaram `pytest`, `git diff`, `aifw`, `diff` e a Write deste arquivo: o hook se comporta como descrito |
| Mesmas chamadas do agente principal ou do `aifw-executor` seguem as regras de antes | `test_other_agents_are_not_held_by_the_reviewer_lock` (sem `agent_type` e `aifw-executor`): a razão nunca é a do revisor. `git config get` e demais casos de `test_indirect_code.py` seguem passando na suíte inteira |
| Editar `.claude/agents/aifw-qa.md` pede confirmação; `aifw claude enable` não | `test_subagent_files_are_control_files` (Edit e `sed -i` dão `ask`) e `test_other_calls_do_not_touch_the_control_file_rule` (`aifw claude enable` e `.claude/agents/minha.md` sem a regra). `CONTROL` em `hooks.py` ganhou `.claude/agents/aifw-` |
| Definições não citam `code-review` como algo a executar e não têm `Agent`; adversário cobre Spec e QA cobre Standards | `test_reviewer_templates`. `templates/claude/agents/aifw-adversary.md` sem `Skill`; `aifw-qa.md` mantém `Skill` só para ler as fontes de padrão e manda aplicar o eixo ele mesmo |
| Suíte inteira passando e mudança revisada em duas etapas | 2633 passed acima; `evidence/independent-review-1.md`, `-2.md` e a seção Adversário deste arquivo |

### Cenários da spec

- `SCN-SUBAGENTS-REVIEWER-GUARD`, `SCN-SUBAGENTS-DEFINITIONS-CONTROL` e `SCN-SUBAGENTS-REVIEW-FLOW`: cobertos pelos testes acima; `traceability.yaml` liga os três a `TEST-REVIEWER-GUARDRAILS` (`evidence/tests.txt`) e o `spec analyze` os conta como verificados.

### Itens 6 a 8 do ADR-0038

- Item 6 (trava por `agent_type`): `hooks.py` `REVIEWERS`, `REVIEW_FILE`, `reviewer_change`. A consequência de a trava sumir sem `agent_type` está registrada na seção Consequências.
- Item 7 (definições como arquivos de controle): `CONTROL` e teste.
- Item 8 (eixos como etapas, sem `Agent`): templates e `test_reviewer_templates`.
- O cabeçalho do ADR cita `reviewer-guardrails` em `Change`.

### Documentação e artefatos derivados

- `docs/claude-code.md`: lista de `ask` inclui a skill e `.claude/agents/aifw-*`; bullet de Subagentes descreve a trava por `agent_type` e o que segue permitido; parágrafo de revisão descreve os eixos e a ausência de `Agent`.
- `CHANGELOG.md`: três bullets, incluindo as correções do classificador (`git stash` sem argumentos ou com `-a`, `git tag -a`, `git reflog expire`/`delete`; opções de listagem por subcomando). `git config list` e `git tag -v` não entram porque nunca deixaram de ser leitura em relação ao release anterior.
- ADR-0038: itens 6 a 8 e Consequências atualizadas.
- Skill: `templates/claude/skills/aifw-workflow/SKILL.md` e `.claude/skills/aifw-workflow/SKILL.md` diferem só pelo rodapé `<!-- aifw-version: 0.4.1 -->` do `enable`. O mesmo vale para as duas definições em `.claude/agents/` contra os templates. Sem `.bak` sobrando em `.claude/`.
- `docs/routing.md` não menciona os eixos, mas o que diz continua verdadeiro e o critério não o exige.

### Eixo Standards

Fontes: `principle-catalogs/engineering-principles.yaml` (não há CONTRIBUTING nem CODING_STANDARDS; `AGENTS.md` não define padrão de código) e a lista de smells da skill `code-review`. O lint (`ruff check` do gate `lint`) passou.

Sem violação dura. Juízo:

- `clean-code-comments`: os comentários novos em `hooks.py` e `shell.py` explicam o porquê (`bare git stash saves and reverts`, `git 2.46+: git config list`). Conforme.
- `clean-code-tests`: os testes nomeiam o comportamento (`test_reviewer_cannot_change_the_project`, etc.) e os valores esperados são independentes da implementação. Conforme.
- `clean-code-side-effects`: `reviewer_change` só decide e devolve o motivo; a negação é aplicada em `pre_tool_use`. Conforme.
- `yagni-evidence` e Speculative Generality: nada além do pedido; `GIT_LISTING` por subcomando é o mínimo para corrigir os achados 1 e 2.
- Duplicated Code: o `resolve()` do alvo em `reviewer_change` repete o que `control_target` já faz para o caminho. Possível, não grave, e a `design.md` diz que o caminho é "resolvido como em `control_target`". Fica como juízo.
- Nenhum outro smell da lista (Feature Envy, Data Clumps, Shotgun Surgery etc.) aparece no diff.

### Ressalvas

1. O revisor não consegue rodar direto os gates `python -m ruff check ...` e `python -m compileall`, nem `cmp`: programas fora de `READ_ONLY` contam como `filesystem-write` (`python/aifw/shell.py:858`) e são negados pela trava. A definição do QA manda "rodar os comandos indicados". O contorno é `aifw validate --change <id>`, que roda todos os gates e funcionou aqui; fica só como atrito, a spec não promete essas ferramentas.
2. `design.md` diz que `pre_tool_use` consulta `reviewer_change` antes de `evaluate`; o código consulta depois e sobrescreve o resultado. O efeito é o mesmo no caso comum, mas se `evaluate` lançar exceção o resultado final é `ask`, não `deny`. Divergência de documentação, sem comportamento perdido.
3. As correções do classificador valem para todos os agentes, não só para revisores: `git stash` sem argumentos ou com `-a`, `git tag -a` e `git reflog expire`/`delete` deixam de ser leitura também para o agente principal. Está no CHANGELOG, mas só os testes de revisores os exercitam; não há caso direto em `test_shell.py`.
4. `evidence/tests.txt` tem a correção da contagem (59 casos) ainda não commitada no working tree, e `independent-review.md` ainda é um arquivo novo; ambos entram no commit da mudança.
5. A ressalva 2 da seção Adversário continua válida (comportamento anterior à mudança, fora do escopo).
6. A etapa 5 da skill (`SKILL.md:54`) ainda manda o agente principal invocar a skill `code-review` para mudança material; isso vale para o agente principal, que pode lançar subagentes, e não conflita com os revisores. Registrado só por clareza.

Resultado: aprovado com ressalvas
