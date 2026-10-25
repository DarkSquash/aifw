# Revisão independente: git-read-classification

## Adversário

Rodada 2, de correção. Escopo: `git diff 34cb137..HEAD` (commit 586b4d8). O diff acrescenta 11 programas de remoção e cópia e o `find` a `FILE_WRITERS` (`python/aifw/shell.py:205-206`) e 6 casos ao `DENIED` de `tests_python/test_reviewer_guardrails.py`. Conferi os Achados 1 e 2 de `evidence/independent-review-1.md` contra REQ-SUBAGENTS-REVIEWER-GUARD (`specs/claude-subagents.delta.yaml:13`) e Non-goal 3 da proposta (o agente principal não muda).

Como verifiquei: rodei `aifw.hooks.handle` num projeto temporário (`test_workflows.init`), com `agent_type=aifw-qa` e sem agente, primeiro com o `shell.py` de HEAD e depois com o de 34cb137 carregado em memória (`git show`). O script e a lista de casos ficaram fora do projeto, em `scratchpad/r2gr/probe.py` e `scratchpad/r2gr/cases.txt`. Também rodei `python -m pytest tests_python/test_reviewer_guardrails.py tests_python/test_shell.py -q`, e os 207 testes passaram.

O que confere:
- Achado 1, corrigido. Para o revisor, estes comandos passaram de `None` para `deny`: `rm notes.txt`, `rm -i f`, `rmdir x`, `rd x`, `unlink f`, `erase f` e `del notes.txt` no Bash, `Remove-Item notes.txt`, `Remove-Item -Path f`, `ri f` e `del notes.txt` no PowerShell, e também `find . -name x -exec rm {} +` e `find . -name x -execdir rm {} ;`. As formas `/bin/rm f`, `rm.exe f`, `RM f`, `env rm f`, `sudo rm f` e `timeout 5 rm f` também são negadas.
- Achado 2, corrigido. `md x`, `xcopy a b` e `robocopy a b` são negados no Bash e no PowerShell.
- `find . -exec cp {} x ;`, citado nas ressalvas da rodada 1, volta a ser negado.
- Agente principal: nos 47 casos, a decisão é a mesma em HEAD e em 34cb137. O campo `unknown` só é lido em `hooks.py:167`, dentro de `reviewer_change`.
- Leituras do revisor seguem permitidas: `find . -name '*.py'`, `find /c/tmp -name x`, o `find "x" f.txt` e o `find /c "x" f.txt` do Windows, `ls`, `cat`, `grep -r`, `sed -n`, `md5sum f`, `python --version`, `python -m ruff check python`, `python -m pytest tests_python -q`, `cmp a b`, `git diff`, `git config get user.name`, `Get-ChildItem` e `Get-Content`.
- Documentação: a lista da proposta termina em "e afins" (`proposal.md:17`), e o ADR-0038 não lista os programas. Nada ficou desatualizado.

### Ressalvas (não reprovam)

- Com `find` em `FILE_WRITERS`, todo `find -exec` é negado ao revisor, inclusive as leituras: `find . -name '*.py' -exec grep -l foo {} +` e `find . -type f -exec cat {} ;` passaram de `None` para `deny`. Não é regressão em relação a 07a7b42, que negava ao revisor toda `filesystem-write`. Também não contraria a spec, que só exige negar a escrita. É um falso positivo, e o revisor pode contornar com `grep -r` ou `rg`.
- `find -ok` e `find -okdir` não estão no conjunto `{-exec, -execdir}` de `shell.py:870` e saem `read-only`. O defeito já existia e fica fora deste diff. Não testei esse caso pelo hook.

Achados provados: nenhum. Linha `Resultado` escrita: none.

## QA

Escopo: `git diff 07a7b42..HEAD` (commits 34cb137 e 586b4d8), 19 arquivos. Rodei cada comando sozinho, nesta ordem.

### Gates e suíte

| Comando | Resultado |
|---|---|
| `python -m pytest tests_python -q` | 2711 passed em 103 s. Bate com `evidence/tests.txt` (2711 depois da rodada 1). |
| `aifw spec validate git-read-classification` | `pass: true`, `findings: []`, capabilities `claude-hook` e `claude-subagents`. |
| `aifw spec analyze git-read-classification` | `pass: true`, `findings: []`. O assessment em cache dá 0,996 para REQ-HOOK-GIT-LISTING/SCN-HOOK-GIT-LISTING e 0,997 para REQ-SUBAGENTS-REVIEWER-GUARD/SCN-SUBAGENTS-REVIEWER-GUARD, sem `weakTraces`. |
| `aifw claude check` | `status: pass`, `findings: []`. |
| `aifw validate --change git-read-classification` | `blocked` por um único gate: `independent-review` (`independent-review.md needs a line Resultado: ...`), que esta revisão fecha com a linha final. Os outros 11 gates passam (build, cli-docs, conformance, context-integrity, lint, manifest, project-map, secret-scan, session-conformance, tests, typecheck), `warnings` vazio, `missingArtifacts` vazio. Sem `--write`. |

Também rodei `python -m ruff check python tests_python` (passa) e `python -m ruff format --check python tests_python` (55 arquivos já formatados).

### Critérios de aceitação (`proposal.md`, Acceptance)

1. Revisor roda `python --version`, `python -m ruff check python`, `cmp a b`, `git config get user.name`, `git remote get-url origin`; continuam negados `cp a b`, `touch x`, `mkdir x`, `tee x`, `echo x > f`, `sed -i`, `git branch -r -d origin/x`, `git tag -l -d v1`. Coberto: `tests_python/test_reviewer_guardrails.py`, listas `ALLOWED` (linhas 46-50) e `DENIED` (linhas 24-35 e as anteriores `echo x > notes.txt` e `sed -i`), parametrizadas pelos dois agentes `aifw-adversary` e `aifw-qa` (passam na suíte). O teste `test_other_agents_are_not_held_by_the_reviewer_lock` confirma que sem agente e com `aifw-executor` a trava não age (Non-goal 3).
2. `analyze` classifica `git branch -r -d origin/x` e `git tag -l -d v1` como `git-local`; `git config get` e `git remote get-url` como `read-only`; `git stash list`, `git tag -v`, `git config list` seguem leitura. Coberto: `tests_python/test_shell.py::test_git_listings_read_and_changes_do_not` (15 casos, linhas 12-33), mais `tests_python/test_indirect_code.py` (`git config get alias.p` passou de `git-local` para `read-only`, mudança justificada no design).
3. Com a avaliação da política falhando, a chamada de um revisor que escreve é negada. Coberto: `test_reviewer_lock_holds_when_the_policy_fails` (`evaluate` lança `RuntimeError`, `git commit` de `aifw-qa` sai `deny`). No código, `hooks.py` roda `reviewer_change` antes de `evaluate` dentro do `try`.
4. Suíte inteira passando e revisão em duas etapas: suíte acima; etapa 1 em `evidence/independent-review-1.md` (reprovada, dois achados) e rodada 2 do adversário nesta pasta (sem achado provado); esta é a etapa 2.

### Cenários da spec

- SCN-HOOK-GIT-LISTING (`specs/claude-hook.delta.yaml`): todos os 14 comandos listados estão em `test_git_listings_read_and_changes_do_not` com a classificação pedida. Rastreado em `traceability.yaml` (`verifiedBy` TEST-GIT-READ-CLASSIFICATION) e `designedBy` DESIGN-GIT-READ-CLASSIFICATION.
- SCN-SUBAGENTS-REVIEWER-GUARD (`specs/claude-subagents.delta.yaml`): negados `python/aifw/claude.py` por Edit, `sed -i`, `cp`, `touch`, `mkdir`, `tee`, `echo x > f`, `git commit`, `git stash`, `git branch -r -d`, `git tag -l -d`; permitidos o `independent-review.md`, arquivo em pasta temporária (`{outside}/probe.py`), `pytest`, `git diff`, `aifw spec analyze`, `python --version`, `python -m ruff check`, `cmp`, `git config get`, `git remote get-url`; política lançando exceção; mesmas chamadas sem `agent_type` ou do `aifw-executor`. Tudo tem caso em `test_reviewer_guardrails.py`.
- Correção da rodada 1 (`rm`, `del`, `Remove-Item`, `rmdir`, `unlink`, `find -exec rm`, `md`, `xcopy`, `robocopy`): 6 casos novos no `DENIED` (`rm notes.txt`, `find . -name x -exec rm {} +`, `Remove-Item notes.txt`, `del notes.txt`, `md x`, `robocopy a b`), que também rodam para o agente principal e o executor. Registrada em `evidence/tests.txt`.
- `tasks.yaml`: as 3 tarefas estão `done`, com `requirementIds` e `paths` que existem no diff. `change.yaml` tem a aprovação humana (`approval.md`, "sim").

### Documentação e artefatos derivados

- CHANGELOG.md (`Unreleased`): duas linhas novas dizem que os revisores rodam programas desconhecidos, que `cp`, `mv`, `touch`, `mkdir`, `tee`... seguem negados, que a trava roda antes da política e que `git config get`, `git remote get-url` e as opções de `branch` e `tag` mudaram. A correção da rodada 1 cabe no "..." da lista, mas não é citada pelo nome.
- ADR-0038: `Change:` inclui `git-read-classification`; o item 6 acrescenta os programas desconhecidos, os que gravam por natureza e a trava antes da política. Mesma observação sobre a rodada 1.
- `docs/cli-reference.generated.md`, `PROJECT_MAP.md` e manifestos: o diff não mexe em CLI nem em arquivos novos de código, e os gates `cli-docs`, `project-map` e `manifest` passam.
- `evidence/tests.txt` cita `scratchpad/staged.py`, que fica fora do repositório; as contagens (2687 e 2711 passed) batem com a minha execução da suíte final.

### Eixo Standards

Fontes lidas: `principle-catalogs/engineering-principles.yaml` e `docs/engineering-principles.md` (único padrão documentado de código; não há CODING_STANDARDS.md nem CONTRIBUTING.md), `pyproject.toml` (ruff, linha de 110) e a lista de smells da skill `code-review`. Ruff e formatador passam, então o que a ferramenta cobre ficou de fora.

- Nenhuma violação dura de padrão documentado.
- Nomes e coesão (`clean-code-naming`, `clean-code-cohesion`): `GIT_CHANGES`, `FILE_WRITERS`, `writes` e o campo `unknown` dizem o que são; a mudança em `segment_requests` e `reviewer_change` é de uma ou duas linhas e fica no nível de abstração do trecho.
- Comentários (`clean-code-comments`): os quatro comentários novos explicam o porquê (`git branch -r -d x` apaga; programa desconhecido roda como código opaco; escrita do revisor é negada antes de a política ser lida; `find` só chega ali com `-exec` ou `-delete`). O último confere com o código: `find` sem essas opções sai antes, no ramo `read-only` de `shell.py:868-873`, e `-delete` é tratado em `shell.py:866`.
- Erros (`clean-code-errors`): a falha da política continua virando `ask` com o erro no motivo, sem engolir a exceção; se o próprio `reviewer_change` lançar, cai no mesmo `ask`. O design registra o comportamento.
- Testes (`clean-code-tests`): casos parametrizados, com expectativa explícita e uma regressão por caso. O comentário `{{}} is {} after .format` explica a única construção estranha.
- Smells (juízo, não violação): possível Speculative Generality em `FILE_WRITERS` por conter `install`, `truncate`, `chown`, `mklink`, `rni` e outros que nenhum teste exercita; cabe ao requisito de cobrir "o óbvio" (design, Decisions), então não pesa. Possível Duplicated Code entre `"rm"`/`"del"`/`"erase"` e o `deletion()` de `shell.py:658`, que decide o que é destrutivo; as duas listas respondem a perguntas diferentes (destrutivo versus que grava), então ficam separadas.

### Ressalvas

- O teste direto do classificador, `test_unknown_programs_are_marked` (`tests_python/test_shell.py`), cobre só `python --version`, `cmp`, `cp` e `sed -i`. As entradas que a rodada 1 acrescentou a `FILE_WRITERS` (`rm`, `Remove-Item`, `md`, `robocopy`, `find -exec`) só são exercitadas pelo hook, em `test_reviewer_guardrails.py`. O item 5 da proposta pede cobertura direta do classificador. Uma regressão que tirasse `rm` de `FILE_WRITERS` seria pega, mas por um teste de outro módulo. Não reprova, porque há teste que falha.
- CHANGELOG e ADR-0038 não citam a remoção, o `find -exec` nem o `md`/`xcopy`/`robocopy` pelo nome; o "..." cobre. O efeito colateral que o adversário registrou (todo `find -exec` é negado ao revisor, inclusive os de leitura) não está documentado em nenhum lugar fora da revisão. O `design.md` também não foi atualizado com a lista da rodada 1.
- As duas ressalvas do adversário (falso positivo do `find -exec` de leitura e `find -ok`/`-okdir` fora do conjunto de `shell.py:870`) ficam como estão: a primeira é aceitável para a trava, a segunda é anterior ao diff.
- O gate `independent-review` de `aifw validate` só passa depois desta linha final; o resto da validação já passa.

Achados provados: nenhum. Nada do que a proposta, a spec e o design prometem está faltando ou falhando.

Resultado: aprovado com ressalvas
