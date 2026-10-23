# Design — Mais autonomia para o agente

## Context

O hook `aifw-hook` decide cada ação por `.aifw/permissions.yaml`. Aprovações humanas eram comandos que só rodam no terminal da pessoa e, com `requireSignedCommit`, só valiam num commit assinado. O agente não consegue escrever no terminal da pessoa, mas consegue ler e escrever arquivos; por isso a prova de aprovação precisa vir de algo que só a pessoa produz.

## Approach

- **Aprovação pelo chat** (`specs.py`, `hooks.py`): `request_approval` grava `approval-request.yaml` na pasta da mudança. No `UserPromptSubmit`, que o Claude Code dispara com o texto digitado pela pessoa, `record_chat_approval` consome todos os pedidos pendentes. Com exatamente um e uma resposta que `approving()` aceita (começa por sim/aprovo/ok/bora/fechado, ou "pode" sozinho ou com verbo de seguir, e não tem "?" nem ressalva como "mas", "não", "antes", "ainda"; quando cancela, o hook avisa o agente), grava `approval.md` citando a mensagem e chama `approve_change` com `human:<git user.name>`. `assert_approval` deixa de exigir commit assinado. O pedido vale só na sessão que rodou o comando: o PreToolUse, ao ver `aifw spec request-approval [opções] <id>` no início de uma linha de comando (não num `grep` que o cite), anota a sessão em `.aifw/runs/approvals/<id>.session`. Enquanto o pedido espera, essa sessão fica congelada; o registro da sessão não é lido. Rodar `aifw-hook`, `python -m aifw.hooks` ou `claude -p` é negado. A proteção mira erro do agente, não um agente decidido a forjar a aprovação (ADR-0037, decisão de 2026-10-23). `approval.md` entra nos arquivos de controle do hook, então editar ou escrever nele pede confirmação. Mensagens automáticas (`AUTOMATIC_PROMPT`) não passam por aqui e não consomem o pedido.
- **Roteamento** (`routing.py`, `cli.py`): `routing_state` sempre retorna ligado; saem as funções e o comando de ativação, e o `activationReady` da saída de `route eval`.
- **Avaliador** (`assessment.py`, `claude.py`): `active()` é `tasks` ligado; o hook de pedidos fica síncrono com timeout de 60 s, sempre.
- **Push** (`shell.py`, `hooks.py`): o parser de `git push` separa destinos e opções. Com `remoteMutation: branches`, `protected_push` pede confirmação para opções de massa (`--all`, `--branches`, `--mirror`, `--tags`, `--follow-tags`, `--prune`), tags, destino igual à branch padrão (a de `refs/remotes/<remote>/HEAD`), push sem destino que a configuração leva à branch padrão, e branch atual desconhecida. Sem `refs/remotes/<remote>/HEAD`, todo push pede, e o motivo diz para rodar `git remote set-head <remote> --auto`. Force e delete continuam como destrutivos. `gh pr create/comment` (e os endpoints de PR, issue e comentário da API) são discussão: rodam sem confirmação mesmo sem `github` na allowlist (com dados confidential o GitHub precisa estar nela; com restricted a escrita é negada); `gh pr merge` e outros `gh` de escrita ficam protegidos.
- **Escrita externa** (`permissions.py`): com `writes: allowlist`, a escrita num serviço da allowlist não pede.
- **Publicação** (`shell.py`, `hooks.py`): `npm publish`, `twine upload`, `docker push`, `gh release create`, `gradle publish*`, `mvn deploy` viram `publish`, que pede sempre e nega com dados confidential/restricted.
- **Segredos** (`hooks.py`): `secret-read` passa de ask para deny.
- **Delegação** (`hooks.py`): sai a regra do Haiku em L3 e do caminho do avaliador; fica só a sessão na nuvem.
- **Juiz** removido por inteiro; `ours()` ainda reconhece a entrada antiga para `aifw claude enable` limpá-la.
- **Archive** (`specs.py`): capability sem requisitos tem a ação `remove` e o arquivo é apagado na mesma transação.

## Decisions

- A aprovação vem do hook, não do agente: o texto do `UserPromptSubmit` é o que a pessoa digitou, e o agente não consegue disparar esse evento.
- Assinatura sai só da aprovação de mudança. Charter, adoção, impasse, waiver e break-glass continuam com assinatura, e só eles, com a política, fazem o commit pedir confirmação.
- Resposta ambígua cancela em vez de aprovar: errar para o lado de perguntar de novo.
- A escolha de "branch padrão" falha fechado: sem saber a branch atual, pede.

## Risks and rollback

- Riscos: ver `threat-model.md`.
- Rollback: reverter o commit da mudança. As configurações antigas (`remoteMutation: human-approval`, `writes: human-approval`, `opaqueCode: ask`) continuam válidas e restauram o comportamento anterior por projeto sem mudar código.
