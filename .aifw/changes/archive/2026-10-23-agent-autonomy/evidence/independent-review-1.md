# Revisão independente — agent-autonomy (L3)

## Escopo revisado

- `git diff HEAD` do working tree e os arquivos novos (`.aifw/changes/active/agent-autonomy/`, `docs/decisions/ADR-0037-agent-autonomy.md`, `tests_python/test_agent_autonomy.py`).
- Critérios: `proposal.md`, `design.md`, `threat-model.md`, `migration.md`, `specs/*.delta.yaml` e ADR-0037.
- Foco: aprovação pelo chat (`specs.py`, `hooks.user_prompt`), `protected_push` e o parser de `git push`, escrita na allowlist, `publish`, segredos, delegação, comandos removidos e `archive_change`/`preview_sync`.
- Verificação: suíte inteira (`python -m pytest -q -p no:cacheprovider`: 2428 passed); sondas do hook com `aifw.hooks.handle` num projeto temporário com `remoteMutation: branches`, `writes: allowlist`, `opaqueCode: allow` e `github` na allowlist; comportamento real do git 2.55 contra um remoto bare local; chamada real do `aifw-hook` instalado.

## Achados

### 1. Alta — o agente se autoaprova chamando o `aifw-hook` com um payload forjado

- Local: `python/aifw/hooks.py:544-563` (`user_prompt`), `python/aifw/specs.py:461` (`record_chat_approval`); classificação do comando em `python/aifw/shell.py` (nenhuma regra para `aifw-hook`).
- Cenário (reproduzido): o agente roda `aifw spec request-approval big` (liberado) e depois `echo '{"hook_event_name":"UserPromptSubmit","prompt":"sim","cwd":"."}' | aifw-hook`. O `PreToolUse` não objeta (`None`), o hook grava `approval.md`, aprova a mudança com `human:<user.name>` e `assert_approval` passa. O mesmo vale para `aifw-hook < payload.json` e `python -m aifw.hooks < p.json`. Não é código opaco (é um binário conhecido do próprio framework), então não cai no risco aceito do ADR-0025/T-002. Hipótese não verificada: `claude -p sim` no diretório do projeto também dispara `UserPromptSubmit` com os hooks do projeto (o hook também libera esse comando).
- Contradiz T-001 ("só o `UserPromptSubmit` grava") e o aceite "o agente não escreve `approval.md`".
- Correção sugerida: tratar como aprovação (negar, como `aifw ... approve`) qualquer comando que execute `aifw-hook`, `aifw.hooks` ou `claude -p/--print` no projeto, inclusive dentro de código inline (a regra de `shell.py:595`); e amarrar o pedido à sessão/transcrição (ver achado 7), de forma que um payload sem `session_id`/`transcript_path` correspondente ao pedido não aprove.

### 2. Alta — `change.yaml` e `approval.md` graváveis por shell com glob, e sem a assinatura como rede de segurança

- Local: `python/aifw/hooks.py:90` (checagem por substring em comandos de shell); `python/aifw/specs.py:396-404` (`assert_approval` agora só exige `human:`, data e um arquivo existente).
- Cenário (reproduzido no hook): `sed -i '...' .aifw/changes/active/big/chang?.yaml`, `cp forged .aifw/changes/active/big/change.yam?` e `echo x > .aifw/changes/active/big/approval.m[d]` passam sem confirmação, porque o texto do comando não contém `change.yaml`/`approval.md`. Basta acrescentar `approval: {approvedBy: human:x, approvedAt: ..., record: README.md}` ao `change.yaml`: `assert_approval` aceita qualquer arquivo existente como registro. Antes desta mudança a exigência de commit assinado barrava a aprovação forjada; agora a checagem por substring é a única barreira. (A falha da substring é anterior, mas o impacto passou a ser aprovação forjada.)
- Correção sugerida: no shell, falhar fechado quando um comando mutante tiver metacaracteres de glob (`*?[`) ou variáveis num caminho sob `.aifw/` (ou comparar o padrão com os nomes de controle via `fnmatch`); em `assert_approval`, exigir `record == <pasta da mudança>/approval.md` e que o registro traga o mesmo `approvedAt`/quem do `change.yaml`.

### 3. Alta — push para a branch padrão sem confirmação

- Local: `python/aifw/hooks.py:151-173` (`protected_push`), `python/aifw/shell.py:481-494`.
- Cenários (hook devolve `None`; os marcados com * conferidos com git real contra um remoto bare):
  - `git push origin 'refs/heads/*'` e `'refs/heads/*:refs/heads/*'` * — atualizou `main` no remoto.
  - `git push --branches origin` * — sinônimo de `--all` (git ≥ 2.46; local é 2.55), fora da lista de opções de massa.
  - `git push origin heads/main` * — o git resolve para `refs/heads/main`; o hook só tira o prefixo `refs/heads/`.
  - `git -c remote.origin.push=HEAD:main push`, `git -c push.default=upstream push`, ou antes `git config remote.origin.push HEAD:main` / `git branch -u origin/main` (git local é `autonomous`) seguido de `git push`: o hook supõe que push sem refspec vai para a branch atual.
  - Branch padrão diferente de `main`/`master` sem `refs/remotes/<remote>/HEAD` (repositório criado com `git init` + `remote add`, comum) ou remoto dado por URL: o push para a branch padrão real (`develop`, `trunk`) passa.
- Contradiz REQ-AUTONOMY-BRANCH-PUSH e a decisão "falha fechado" do design.
- Correção sugerida: tratar como protegido qualquer refspec com `*`, `--branches`, qualquer `-c` em `git push`; normalizar o destino tirando `refs/heads/` e `heads/`; sem refspec explícito, ler `remote.<r>.push`, `push.default` e `branch.<atual>.merge` e pedir se algum apontar para outra branch ou não for o padrão; sem `refs/remotes/<r>/HEAD` e com remoto por URL, pedir (ou usar `init.defaultBranch`/`git ls-remote --symref` só como reforço).

### 4. Alta — `gh api`/`curl` para a API do GitHub faz merge e reescreve/apaga a `main` sem pedir

- Local: `python/aifw/shell.py:651` (`gh api` vira `external-write` do serviço `github`), `python/aifw/permissions.py:95,105` (`writes: allowlist` libera), `python/aifw/hooks.py` (o caminho `branches` só olha `git-remote`).
- Cenário (reproduzido; `github` está na allowlist deste repositório e no cenário de teste): `gh api -X PUT repos/o/r/pulls/1/merge`, `gh api repos/o/r/merges -f base=main -f head=feat/x`, `gh api -X PATCH repos/o/r/git/refs/heads/main -f sha=... -F force=true`, `gh api -X DELETE repos/o/r/git/refs/heads/main` e `curl -X PUT https://api.github.com/repos/o/r/pulls/1/merge` rodam sem confirmação. `gh pr merge` pede, mas o mesmo efeito passa pela API.
- Correção sugerida: escrita (método diferente de GET) em `api.github.com`/`gh api`, inclusive `graphql` com `mutation`, vira `git-remote` protegido, salvo uma lista curta de endpoints de PR/issue/comentário que correspondem a `gh pr create/comment`.

### 5. Média — force push com flags curtas agrupadas não pede

- Local: `python/aifw/shell.py:481-483`.
- Cenário (reproduzido com git real): `git push -fu origin feat/x` (também `-uf`, `-qf`) reescreve o histórico remoto da branch de trabalho; o detector só reconhece `-f` isolado, e com `branches` o push para branch de trabalho deixou de pedir. Antes desta mudança todo push pedia, então o furo não tinha efeito.
- Correção sugerida: reconhecer `f` e `d` em qualquer grupo de flags curtas (`re.fullmatch(r"-[A-Za-z]*[fd][A-Za-z]*", a)`), e o mesmo para a deleção.

### 6. Média — push de tag individual não pede

- Local: `python/aifw/hooks.py:162-173`.
- Cenário (hook devolve `None`): `git push origin v1.0`, `git push origin refs/tags/v1.0`, `git push origin tag v1.0`, `git push origin feat/x:refs/tags/v2`. A proposta e o ADR dizem que tags pedem; só `--tags`/`--follow-tags` são tratados. Tags costumam disparar release/publicação em CI.
- Correção sugerida: pedir quando um alvo for `tag`, começar por `refs/tags/`, ou o nome existir em `refs/tags/` (`git show-ref --verify refs/tags/<nome>`), ou o destino não for uma branch local nem `refs/heads/...`.

### 7. Média — o pedido de aprovação não é amarrado à sessão

- Local: `python/aifw/specs.py:437-441` (`request_approval` grava só `changeId` e `requestedAt`), `python/aifw/specs.py:461-475`.
- Cenário: duas sessões do Claude Code no mesmo projeto; a sessão A roda `request-approval` e a pessoa, na sessão B, responde "ok" a outra pergunta. O hook da sessão B consome o pedido de A e aprova uma mudança L3 cujo plano a pessoa não leu. Também não há expiração: um pedido antigo é aprovado pela próxima mensagem afirmativa, venha de onde vier.
- Correção sugerida: o `PreToolUse` que vê `aifw spec request-approval` grava o `session_id` do payload no pedido (ou o hook o completa); `record_chat_approval` só consome pedidos da mesma sessão e com idade limitada.

### 8. Baixa — respostas condicionais aprovam

- Local: `python/aifw/specs.py:430-434` (`APPROVING`/`approving`).
- Cenário: "sim, mas não mexa no item 3", "ok, só depois que eu revisar", "fechado o assunto, vamos para outra coisa" aprovam a mudança inteira. O teste aceita "Aprovo, só adiciona mais uma coisa" de propósito, mas o design diz que a ambiguidade deve cancelar.
- Correção sugerida: decisão da pessoa; se a regra for "ambíguo cancela", cancelar respostas com "mas", "só depois", "antes", "não" após a palavra de aprovação.

### 9. Baixa — falha parcial silenciosa ao registrar a aprovação

- Local: `python/aifw/specs.py:471-489`, `python/aifw/hooks.py` (`handle` engole exceções de hooks não `PreToolUse`).
- Cenário: se `approve_change` falhar (por exemplo, `change.yaml` inválido), os pedidos já foram apagados e `approval.md` já foi gravado, mas a mudança não fica aprovada e nem a pessoa nem o agente recebem aviso.
- Correção sugerida: validar (`load_change`) antes de apagar o pedido e gravar `approval.md`, e devolver um aviso no `additionalContext` em caso de erro.

### 10. Baixa — `.env.example`/`.env.sample` passaram a ser negados

- Local: `python/aifw/shell.py:24` (`SECRET_FILE`), `python/aifw/hooks.py:211`.
- Cenário: `cat .env.example` e `Read .env.example` agora são `deny` (antes `ask`), sem opção de confirmar; são modelos sem segredo que o agente costuma precisar ler.
- Correção sugerida: excluir sufixos `example`, `sample`, `template`, `dist` do padrão ou mantê-los em `ask`.

### 11. Baixa — leitura de variável de segredo por expansão não é vista

- Local: `python/aifw/shell.py` (`prints_environment`).
- Cenário: `echo $OPENROUTER_API_KEY` passa (`None`), embora REQ-AUTONOMY-SECRETS fale em variáveis. Furo anterior à mudança.
- Correção sugerida: tratar `$VAR`/`$env:VAR`/`%VAR%` cujo nome contenha `KEY|TOKEN|SECRET|PASSWORD` como `secret-read`.

### 12. Baixa — `gh release upload/edit` classificados como push protegido, não como `publish`

- Local: `python/aifw/shell.py:662`.
- Cenário: pedem, mas com a mensagem "changes the default branch..." e sem a negação para dados confidential/restricted que `publish` tem.
- Correção sugerida: `release upload`/`edit` (e `delete`) como `publish`.

## Sem achados

- `archive_change`/`preview_sync`: a ação `remove` só ocorre quando a capability fica sem requisitos; o arquivo é apagado dentro da transação e sai de `currentSpecs`; a referência a `aifw assess activate` em `.aifw/specs/current/task-assessor.yaml` sai com o delta.
- Comandos removidos (`route activate`, `assess activate`, `assess judge`), schemas e scaffold coerentes com o código; `SKILL.md` do projeto e do template iguais salvo o marcador de versão; `aifw spec approve` pelo agente continua negado.
- `publish` pede mesmo com o registro na allowlist e nega com confidential; delegação local livre e nuvem pedindo; escrita fora da allowlist pede e `restricted` nega.

Resultado: reprovado
