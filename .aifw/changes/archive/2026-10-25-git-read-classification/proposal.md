# Proposal — Leitura do git e comandos dos revisores

## Intent

Corrigir as ressalvas que ficaram da `reviewer-guardrails` (ADR-0038):

1. A trava dos revisores nega programas que só leem (`python --version`, `python -m ruff check`, `cmp`, `python /tmp/sonda.py`), porque o classificador trata todo programa desconhecido como escrita.
2. `git config get` e `git remote get-url` contam como alteração sem alterar nada.
3. `git branch -r -d origin/x` e `git tag -l -d v1` contam como leitura, porque só o primeiro argumento é olhado.
4. Se a avaliação da política falha, a trava dos revisores não roda, e a chamada fica em `ask` em vez de `deny`.
5. As correções do classificador do git só são exercitadas pelos testes dos revisores, sem caso direto em `test_shell.py`.

## Scope

- No classificador (`python/aifw/shell.py`):
  - o pedido de escrita que vem de um programa desconhecido passa a ser marcado como `unknown`;
  - os programas que gravam arquivos por natureza (`cp`, `mv`, `touch`, `mkdir`, `tee`, `ln`, `rsync`, `patch`, `tar`, `unzip`, `chmod`, `Copy-Item`, `Set-Content`, `Out-File` e afins), assim como `sed -i` e o awk que grava, continuam como escrita explícita.
- `GIT_LISTING`: `config` ganha `get`, `remote` ganha `get-url`. Para `branch` e `tag`, uma opção que altera em qualquer posição (`-d`, `-D`, `-m`, `-M`, `-c`, `-u`, `--set-upstream-to`, `-a`, `-s`, `-f`...) tira o comando da leitura.
- Trava dos revisores (`python/aifw/hooks.py`):
  - escrita só de programa desconhecido segue, como o código opaco;
  - redirecionamento, escrita explícita, commit e mudanças no repositório continuam negados;
  - a trava passa a rodar antes da avaliação da política, então nega mesmo quando a avaliação falha.
- Testes diretos do classificador em `tests_python/test_shell.py` e casos novos em `tests_python/test_reviewer_guardrails.py`.
- CHANGELOG e ADR-0038.

## Non-goals

- `cp modelo .claude/agents/` (destino só a pasta) e `cd .claude/agents && sed -i ...` não pedem confirmação, como hoje acontece com a pasta da skill. Fechar isso exige seguir o diretório de trabalho e o destino de cada comando, que é a caça a caminhos que a pessoa decidiu não fazer (ADR-0037).
- Restringir o revisor ao `independent-review.md` da mudança que ele revisa: o hook não sabe qual é.
- Mudar a decisão do agente principal: para ele, `unknown` não muda nada.

## Acceptance

- Um `aifw-adversary` ou `aifw-qa` roda `python --version`, `python -m ruff check python`, `cmp a b`, `git config get user.name` e `git remote get-url origin`. Continuam negados a ele `cp a b`, `touch x`, `mkdir x`, `tee x`, `echo x > f`, `sed -i`, `git branch -r -d origin/x` e `git tag -l -d v1`.
- `analyze` classifica `git branch -r -d origin/x` e `git tag -l -d v1` como `git-local`, e `git config get` e `git remote get-url` como `read-only`. As listagens corrigidas antes (`git stash list`, `git tag -v`, `git config list`) seguem como leitura.
- Com a avaliação da política falhando, a chamada de um revisor que escreve é negada.
- Suíte inteira passando e esta mudança revisada pelo fluxo de duas etapas.
