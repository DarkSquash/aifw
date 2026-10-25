# Design — Leitura do git e comandos dos revisores

## Context

`segment_requests` em `python/aifw/shell.py` termina num `else` que classifica todo programa fora de `READ_ONLY` como `filesystem-write`. Para o agente principal isso não muda nada, porque a escrita local é livre. Para os revisores (ADR-0038), que não podem escrever, isso nega `python --version` e `cmp`. `git_requests` decide a listagem pelo primeiro argumento, via `GIT_LISTING`.

## Approach

- `FILE_WRITERS`: conjunto pequeno de programas cujo papel é gravar arquivos (Unix e PowerShell). O `else` final marca `unknown=True` quando o programa não está nele e não edita no lugar (`edits_files`). O redirecionamento continua sendo um pedido próprio, sem `unknown`.
- `reviewer_change` aceita `filesystem-write` só se todos os pedidos desse tipo forem `unknown`; os outros tipos fora de `REVIEWER_KINDS` continuam negados.
- `GIT_CHANGES`: as opções que alteram para `branch` e `tag`. A listagem exige primeiro argumento de listagem e nenhum argumento em `GIT_CHANGES[sub]` (comparando o nome antes de `=`).
- `GIT_LISTING`: `config` com `get`; `remote` com `get-url`.
- Em `pre_tool_use`, `reviewer_change` roda primeiro dentro do `try`; com motivo, a decisão é `deny` sem avaliar a política. Se ela lançar exceção, vale o `ask` de sempre.
- `hooks.py` e `shell.py` são editados numa cópia e testados antes de entrar, porque o hook roda esse código ao vivo.

## Decisions

- O programa desconhecido segue para o revisor pelo mesmo motivo do código opaco: o revisor precisa rodar ferramentas de leitura, e o hook não lê o que elas fazem. A lista `FILE_WRITERS` cobre só o óbvio, como pede o modelo de ameaça (ADR-0034, ADR-0037).
- A mudança no teste antigo `git config get alias.p` (de `git-local` para `read-only`) corrige a expectativa: ler um alias não executa nada.

## Risks and rollback

- Um programa desconhecido que grava no projeto passa a seguir para o revisor. É a fronteira aceita para o código opaco.
- Rollback: reverter a mudança volta à classificação anterior.
