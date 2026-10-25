# Revisão independente — git-read-classification

## Adversário

Rodada 1. Escopo: `git diff 07a7b42..HEAD` (commit 34cb137): `python/aifw/shell.py`, `python/aifw/hooks.py`, os testes `test_shell.py`, `test_reviewer_guardrails.py` e `test_indirect_code.py`, o CHANGELOG e o ADR-0038, contra `specs/claude-hook.delta.yaml` (REQ-HOOK-GIT-LISTING), `specs/claude-subagents.delta.yaml` (REQ-SUBAGENTS-REVIEWER-GUARD) e a proposta (Scope, Non-goals, Acceptance) e o design.

Como verifiquei: rodei `analyze` ao vivo e `aifw.hooks.handle` com `agent_type=aifw-qa` num projeto temporário (`test_workflows.init`), primeiro com o código de HEAD e depois com `shell.py` e `hooks.py` de 07a7b42 carregados em memória (`git show`). Os scripts ficaram fora do projeto, em `scratchpad/probe.py` e `scratchpad/e2e.py`. Também rodei `pytest tests_python/test_shell.py tests_python/test_reviewer_guardrails.py tests_python/test_indirect_code.py`: 394 passaram.

O que confere:
- Acceptance 1: `python --version`, `python -m ruff check python`, `cmp a b`, `git config get user.name` e `git remote get-url origin` seguem. `cp`, `touch`, `mkdir`, `tee`, `echo x > f`, `sed -i`, `git branch -r -d origin/x` e `git tag -l -d v1` são negados.
- Acceptance 2: `analyze` dá a classificação pedida para os casos do SCN-HOOK-GIT-LISTING.
- Acceptance 3: o teste com `evaluate` lançando exceção nega `git commit`. A trava roda antes da política e, se ela mesma falhar, a chamada continua em `ask`, como antes.
- Composição: `cmp a b && cp a b` e `cmp a b; touch x` continuam negados, porque o filtro olha cada pedido.
- `/bin/cp`, `cp.exe`, `CP`, `Copy-Item`, `\cp`, `env`/`sudo`/`nice`/`timeout cp` continuam negados.
- O campo `unknown` só é lido em `hooks.reviewer_change`, então o agente principal não muda (Non-goal 3).

### Achado 1: apagar um arquivo do projeto volta a ser permitido ao revisor (regressão). Severidade: alta

- Onde: `python/aifw/shell.py:873-874`, no `else` final de `segment_requests`, junto com `deletion()` em `shell.py:658`.
- Spec violada: REQ-SUBAGENTS-REVIEWER-GUARD, `specs/claude-subagents.delta.yaml:13`: "negar ... o comando de shell que escreve arquivos de forma explícita ... ou altera o repositório". Também `proposal.md`, Scope: os programas que gravam arquivos por natureza "continuam como escrita explícita". A lista dali inclui `chmod` "e afins", e apagar um arquivo é mais escrita do que mudar o modo dele.
- Por que acontece: `deletion()` só marca como destrutivo o `rm` recursivo ou forçado (`-r`, `-f`), o `del /s` ou `/q` e o `Remove-Item -Recurse` ou `-Force`. A remoção simples cai no `else`. `rm`, `del`, `erase`, `Remove-Item`, `ri`, `rmdir`, `rd` e `unlink` não estão em `FILE_WRITERS`, então o pedido sai com `unknown=True` e passa pelo filtro novo de `reviewer_change` (`hooks.py:167`).
- Cenário: um `aifw-qa` ou `aifw-adversary` roda `rm notes.txt`, `del notes.txt` ou `Remove-Item notes.txt` no projeto, por exemplo para limpar uma sonda que deixou ali. O resultado esperado é `deny`. O hook não responde nada (`None`), e o arquivo é apagado.
- Evidência (`handle` com `agent_type=aifw-qa`):

  ```
  NEW 'rm notes.txt' None
  NEW 'del notes.txt' None
  NEW 'Remove-Item notes.txt' None
  NEW 'find . -name x -exec rm {} +' None
  OLD 'rm notes.txt' deny AIFW: a reviewer subagent does not write files, commit or ch
  OLD 'del notes.txt' deny AIFW: a reviewer subagent does not write files, commit or ch
  OLD 'Remove-Item notes.txt' deny AIFW: a reviewer subagent does not write files, commit or ch
  ```

  `analyze` marca `rmdir x`, `rd x`, `unlink f`, `rm -i f`, `erase f` e `Remove-Item -Path f` como `filesystem-write` com `unknown=True`, e todos passam pela trava.
- Nenhum teste cobre o caso: `DENIED`, em `tests_python/test_reviewer_guardrails.py`, não tem nenhuma remoção.

### Achado 2: os equivalentes do Windows para `mkdir` e `cp` passam pela trava (regressão). Severidade: média

- Onde: `python/aifw/shell.py:200-205` (`FILE_WRITERS`).
- Spec violada: a mesma linha do REQ-SUBAGENTS-REVIEWER-GUARD e a Acceptance da proposta, que manda continuar negando `mkdir x` e `cp a b`. O Scope cita os programas do PowerShell "e afins", e o projeto roda no Windows, com a ferramenta PowerShell.
- Cenário: um revisor roda `md x` (o `mkdir` do cmd e do PowerShell), `xcopy a b` ou `robocopy a b`. O resultado esperado é `deny`, como acontece com `mkdir x` e `cp a b`. O hook não responde nada (`None`). Antes desta mudança, os três eram negados.
- Evidência (mesmo script): `NEW 'md x' None`, `NEW 'xcopy a b' None` e `OLD 'md x' deny`, `OLD 'xcopy a b' deny`. Pelo `analyze`, `robocopy a b` também sai `filesystem-write` com `unknown=True`.

### Ressalvas (não reprovam)

- `git branch` com opção abreviada ou agrupada conta como leitura. `git branch -r --del origin/x`, `git branch -a --set-up=origin/x` e `git branch -r -dr origin/x` saem `read-only`, porque `GIT_CHANGES` compara a palavra exata e o git aceita abreviação de opção longa e opções curtas agrupadas. O REQ-HOOK-GIT-LISTING pede "olhando todas as opções" (`claude-hook.delta.yaml:13`). São formas improváveis por engano, e o código anterior também as aceitava. Não confirmei com o git real que esses comandos apagam.
- `git remote -v add x u` sai `read-only`: o `-v` vem antes do subcomando e o `add` não é olhado. O defeito já existia e fica fora do trecho "branch e tag" do requisito.
- Antes desta mudança, `find . -exec cp {} x \;` era negado ao revisor e agora passa, porque o `find` não está em `FILE_WRITERS`. Fica coerente com `xargs cp`, que já era opaco e permitido. Se o Achado 1 for corrigido, vale tratar o `find -exec` junto.
- `gzip f`, `ruff format`, `python -m ruff format` e `ruff check --fix` gravam no projeto e passam como programa desconhecido. O design aceita esse risco ("Risks and rollback"), então não reprovam.
- Fora do diff: um script de sonda que contém a palavra `requests` ou `verdict` e menciona `aifw` é lido como `external-write` com aprovação, e o revisor fica bloqueado de rodá-lo (aconteceu nesta revisão). É uma heurística anterior de `inline_script`.

Resultado: reprovado
