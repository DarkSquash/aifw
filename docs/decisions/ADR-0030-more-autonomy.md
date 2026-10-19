# ADR-0030 — Commits livres, haiku em L2 e código ilegível em arquivo

- Status: accepted
- Date: 2026-10-18
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

Depois do ADR-0025, ainda pediam confirmação todo commit, toda delegação ao `haiku` com mudança L2 ativa e todo código que o hook não consegue ler. A pessoa pediu menos confirmações, mantendo push, instalações e L3 com ela.

## Decisão

1. Nova opção `commits: ask | allow` em `permissions.yaml` (padrão `ask`). Com `allow`, criar ou reescrever commits não pede confirmação, exceto:
   - quando algum arquivo de controle (lista `CONTROL` do hook, ou um `change.yaml`) está alterado, preparado ou novo: o git desta máquina assina todo commit com a chave da pessoa, e um commit assinado com um arquivo de aprovação valeria como aprovação;
   - sem git, ou com `-S`, que continuam pedindo.

   Push continua pedindo (`remoteMutation: human-approval`). Ligada neste repositório.
2. Delegar ao `haiku` só pede confirmação com mudança L3 ativa; em L2 fica a critério do agente.
3. `opaqueCode` continua `ask`. A mensagem do hook passa a sugerir gravar o código num arquivo `.py` ou `.js` e rodar esse arquivo, que o hook lê com as mesmas regras do código inline.

## Consequências

- Neste repositório, os commits locais deixam de ser assinados (`commit.gpgsign=false` local). Antes de subir, a pessoa assina os commits ainda não enviados com `git rebase --exec "git commit --amend --no-edit -n -S" origin/main`, e um hook `pre-push` local recusa push com commit sem assinatura válida. Assim o agente nunca assina nada, e uma aprovação só vale depois de a pessoa assinar o commit dela.
- A verificação de arquivos de controle olha o `git status` antes do comando rodar. Por isso, um commit no mesmo comando que outra escrita (`python gera.py && git commit -am x`) pede confirmação; só `git add` e outros comandos locais do git podem acompanhar o commit.

## Rollback

Voltar `commits` para `ask` ou removê-lo, e desfazer as mudanças em `hooks.py`.
