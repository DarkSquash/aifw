# Revisão independente — reviewer-guardrails

## Adversário

Rodada 2, de correção. Escopo: `git diff 9ac9cd1..HEAD` (commit 78332c7), os achados de `evidence/independent-review-1.md` e a delta `specs/claude-subagents.delta.yaml`. Não refiz a caça no código já revisado. Os experimentos ficaram fora do projeto, em `scratchpad/r2/test_r2.py` e `test_r2_handle.py`:

- `test_r2.py` compara `analyze()` da versão `9ac9cd1` (lida por `git show`) com a atual, em 40 comandos.
- `test_r2_handle.py` chama `handle()` com `agent_type` sobre um projeto criado por `test_workflows.init`.

`python -m pytest tests_python/test_reviewer_guardrails.py tests_python/test_shell.py -q` deu 125 passed.

### Conferência dos achados da rodada 1

- Achado 1 (`git stash -a`): corrigido. O comando passou de `read-only` para `git-local` e é negado aos dois revisores. `git stash list` e `git stash show` continuam `read-only`. `git stash --all` e `-u` continuam `git-local`.
- Achado 2: corrigido.
  - `git tag -a v9 -m x` passou de `read-only` para `git-local`.
  - `git reflog expire --expire=now --all`, `git reflog delete HEAD@{0}` e `git -C x reflog expire --all` passaram de `read-only` para `git-local`.
  - `git reflog`, `git reflog show` e `git reflog exists HEAD` continuam `read-only`.
  - Pôr `reflog` em `GIT_LOCAL` não afeta outro caminho: a constante só é usada em `shell.py:572`.
- Listagens que deviam continuar como leitura: sem mudança. Seguem `read-only` antes e depois:
  - `git branch`, com `-a`, `-r`, `-v`, `-vv`, `--list` ou `--show-current`;
  - `git tag`, `git tag -l` e `git tag --list`;
  - `git remote`, `git remote -v` e `git remote show origin`;
  - `git stash list`;
  - `git config --get`, `--get-all`, `-l` e `--list`;
  - `git worktree list`;
  - `git submodule`;
  - `git reflog`;
  - `git --no-pager branch -a`.
- Um ganho: `git submodule status` passou de `git-local` para `read-only`.

### Achado 1 — a correção passou `git config list` de leitura para alteração do repositório (severidade baixa)

- Arquivo: `python/aifw/shell.py:183-191`. A tabela nova de `config` é `{"-l", "--list", "--get", "--get-all"}` e não traz o `list`. Antes, o `list` estava em `LIST_ARGS`, que valia para qualquer subcomando de listagem.
- O `git config list` é a forma de subcomando do git 2.46+. O próprio `shell.py:520-521` já trata essa sintaxe (`git config set`, `keys[0] not in {"get", "list", "unset"}`), e o git instalado é o 2.55.0.
- Spec: o REQ-SUBAGENTS-REVIEWER-GUARD (`statement`) manda negar o que altera o repositório, "deixando seguir leitura".
- Cenário: chamada `Bash` com `command="git config list"` e `agent_type` igual a `aifw-adversary` ou `aifw-qa`.
  - Esperado: segue, como em `9ac9cd1`, quando o comando era `read-only`.
  - Obtido: `analyze` classifica como `['git-local']`, e `handle()` devolve `deny` com "AIFW: a reviewer subagent does not write files, commit or change the repository; read, test or probe instead".
  - Sem `agent_type`, a resposta é `None`, então o agente principal não é afetado.
- Mesmo efeito, menos provável: `git tag -v v1` só verifica a assinatura e não altera nada. Era `read-only` (pelo `-v` de `LIST_ARGS`), agora é `git-local` e é negado aos dois revisores.
- Correção sugerida: acrescentar `"list"` a `GIT_LISTING["config"]` e `"-v"`/`"--verify"` a `GIT_LISTING["tag"]`, com casos em `ALLOWED`.

### Ressalvas

1. `tests.txt` ficou desatualizado: diz "35 casos" em `test_reviewer_guardrails.py`, mas o arquivo tem 55.
2. Falsos positivos anteriores à rodada, que a correção não criou: `git config get user.name`, `git tag -n` e `git remote get-url origin` são `git-local` em `9ac9cd1` e na versão atual. A regra do primeiro argumento também continua, por exemplo em `git branch -r -d origin/x`, que fica como leitura pelo `-r`. Nada disso foi introduzido por esta rodada.

Resultado: reprovado
