# Revisão independente 7: agent-autonomy

## Escopo

- Diff do working tree contra `HEAD` (52 arquivos) e arquivos novos: `.aifw/changes/active/agent-autonomy/`, `docs/decisions/ADR-0037-agent-autonomy.md`, `tests_python/test_agent_autonomy.py`.
- Lidos: proposal, design, threat-model, migration, specs/*.delta.yaml, tasks, traceability e ADR-0037. As revisões 1 a 6 serviram só de histórico.
- Foco: congelamento depois de `spec request-approval` (`awaiting_reply`, `pre_tool_use`), destravamento pela resposta (`user_prompt`, `record_chat_approval`, `approving`), `protected_push`, `PUBLISH`, segredos, remoção de `route activate`/`assess activate`/juiz e `spec archive` com capability sem requisitos.
- Modelo de ameaças da ADR-0037/ADR-0034: burla deliberada ficou fora do escopo e não foi procurada.
- Verificação:
  - `python -m pytest -q -p no:cacheprovider`: 2488 passed.
  - `aifw spec validate agent-autonomy`: sem achados.
  - `aifw spec analyze agent-autonomy`: pass, 15/15 requisitos com tarefa, 9/9 cenários verificados.
  - `aifw spec sync agent-autonomy --dry-run`: `opaque-judge` com ação `remove`.
  - `aifw claude check`: pass.
  - Sondas em `C:\Users\DARKSQ~1\AppData\Local\Temp\claude\C--Users-DarkSquash-Documents-Projetos-aifw\31451809-735d-4dd2-985a-991c20809a6a\scratchpad\review7\`.

## O que funciona

- Congelamento e destravamento: com `aifw spec request-approval big`, com `big --json` depois do id e com `cd . && ...`, o hook congela a sessão. Qualquer resposta destrava. "sim" aprova sem commit assinado. Outra sessão não congela. Mensagem automática não consome o pedido. Dois pedidos pendentes não aprovam nenhum. Um `change.yaml` corrompido na hora da resposta não deixa a sessão presa, porque o pedido é apagado antes.
- Push com `remoteMutation: branches`:
  - Passam sem pedir: `HEAD`, `-u origin HEAD`, `--set-upstream` e a branch de trabalho.
  - Pedem: `HEAD:main`, `main:main`, `@:main`, `refs/heads/main`, vários destinos com a main, `-o`/`--push-option`/`--repo=`, `git -C . push origin main`, `cd sub && git push origin main`, `--force-with-lease`, `:feat/old`, `gh pr merge` (inclusive `--auto`), `gh repo sync` e `gh workflow run`.
  - Com a branch padrão `master`, `git push origin master` e o `git push` sem destino também pedem.
- Publicação: `npm publish`, `pnpm -r publish`, `yarn npm publish`, `cargo publish`, `docker push` e `docker image push` pedem. Com `confidential`, são negados.
- Deploy de produção (`vercel --prod`) continua pedindo.
- `route activate` e `assess judge` não existem mais. `routing_state` aceita um `routing.yaml` antigo com `activation`. Um `aifw.yaml` antigo com `judge` não quebra o hook.
- `spec archive` apaga a spec da capability retirada e a tira de `currentSpecs`.

## Achados

1. **Média: `aifw spec request-approval --json <id>` não congela a sessão nem registra a aprovação.**
   - Onde: `python/aifw/hooks.py:369` (`REQUEST_APPROVAL`), usado em `pre_tool_use` (≈401-405) e `requested_here` (626-636).
   - Cenário: o CLI aceita `[--json] id` (`docs/cli-reference.generated.md:334`). O regex captura `--json` como id. A sessão não fica registrada como solicitante de `big`. Resultado:
     - o agente não congela;
     - o "sim" da pessoa não aprova;
     - o `approval-request.yaml` fica para trás.
   - Confirmado pela sonda `test_freeze_and_approve_variants[aifw spec request-approval --json big]`. A falha é segura, sem aprovação indevida, mas o comportamento pedido falha sem aviso.
   - Correção: pular opções antes do id, por exemplo `request-approval\s+(?:-\S+\s+)*([a-z0-9][a-z0-9-]*)`, ou gravar o id solicitante dentro do próprio `approval-request.yaml` (o CLI já recebe a sessão do ambiente, se disponível). Incluir um teste com `--json` antes do id.

2. **Média: qualquer comando que cite `.env` passa a ser negado, mesmo sem ler o arquivo.**
   - Onde: `python/aifw/shell.py:778` (`if any(SECRET_FILE.search(w) for w in args)`) somado a `python/aifw/hooks.py:263-265` (`secret-read` → deny).
   - Cenário: comandos de rotina, que antes pediam confirmação, agora são negados sem opção:
     - `echo .env >> .gitignore` e `git check-ignore .env`;
     - `cp .env.example .env`;
     - `source .env && npm run dev`;
     - `docker compose --env-file .env up -d`.
   - A spec (REQ-AUTONOMY-SECRETS) fala de *leitura*. Esses comandos citam o nome sem trazer o conteúdo ao contexto, ou só escrevem nele. Confirmado por `test_secret_args`.
   - Correção: manter deny para o Read/Grep/Glob, `printenv`/`env` e programas que exibem conteúdo (`cat`, `type`, `Get-Content`, `less`, `head`, `grep` sobre o arquivo). Para uma simples menção, voltar a `ask` (ou liberar destino de escrita e `check-ignore`). Incluir testes.

3. **Média: o primeiro commit depois da aprovação pelo chat pede confirmação.**
   - Onde: `python/aifw/hooks.py:484` (`dirty_control` com `"/change.yaml"`) e `python/aifw/hooks.py:285-287`. Na documentação, `docs/claude-code.md:63` ("porque, assinado, ele valeria como aprovação").
   - Cenário: o hook grava `approval` em `change.yaml`. O `git commit -am wip` seguinte pede "commits with the AIFW control file /change.yaml changed". O mesmo vale depois de cada `aifw spec status --set`. Confirmado pela sonda `test_approval_commit_after_chat`.
   - A justificativa, um commit assinado com `change.yaml` valer como aprovação, deixou de existir para mudanças (ADR-0037 §2: `assert_approval` não usa mais `signing`). Isso contradiz o ADR-0037: "O agente trabalha sem interrupção numa mudança aprovada, faz commit".
   - Correção: tirar `"/change.yaml"` de `dirty_control`, mantendo Charter, adoção, impasse, waiver e break-glass, que ainda dependem de assinatura. Ajustar a frase em `docs/claude-code.md:63` e incluir um teste.

4. **Média: `gh pr create` e `gh pr comment` pedem confirmação em projeto novo.**
   - Onde: `python/aifw/shell.py:739-745` (PR como `external-write` no `github`) e `templates/project-scaffold.json:224` (`externalAllowlist: []`).
   - Cenário: num projeto criado pelo scaffold, `gh pr create --fill` pede (`service-not-allowlisted`). ADR-0037 §5, README:15, SKILL:24 e o Acceptance da proposal dizem que PR roda sem perguntar. Só roda com `github` na allowlist, e nenhuma doc diz isso. Confirmado por `test_pr_in_new_project_without_github_allowlisted`.
   - Correção: documentar que `github` precisa estar em `spec.externalAllowlist` (README, docs/claude-code.md, migration), ou tratar `gh pr create/comment` como parte do fluxo de branch quando `remoteMutation: branches`.

5. **Baixa: `design.md` descreve um fallback que o código não tem.**
   - Onde: `.aifw/changes/active/agent-autonomy/design.md:12` ("senão `main`/`master`") contra `python/aifw/hooks.py:203-205`.
   - Cenário: sem `refs/remotes/<remote>/HEAD`, o código pede em todo push. A spec e `docs/claude-code.md` estão certas. Isso acontece num repositório com `git remote add` e `git push -u`, até rodar `git remote set-head origin --auto` ou até um fetch do git 2.48+ criar o HEAD.
   - O motivo exibido ("changes the default branch or the remote history") não diz ao agente que falta o HEAD do remoto.
   - Correção: alinhar o design.md. Opcional: um motivo específico que cite `git remote set-head origin --auto`.

6. **Baixa: uma linha corrompida no registro da sessão trava todas as ferramentas.**
   - Onde: `python/aifw/hooks.py:626-636` (`requested_here` faz `json.loads` em todas as linhas) e `awaiting_reply` (372), chamado fora do `try` em `pre_tool_use`.
   - Cenário: uma linha truncada em `.aifw/runs/<sessão>.jsonl` faz o PreToolUse levantar exceção (sonda `test_probe7d.py`). O fallback de `.claude/settings.json` então bloqueia toda ferramenta com a mensagem de "aifw-hook failed or is not installed". Antes desta mudança, o PreToolUse não dependia desse registro.
   - O registro também é lido por inteiro a cada chamada, mesmo sem pedido pendente.
   - Correção: fazer o glob de `approval-request.yaml` antes, ler o registro só se houver pedido e ignorar linhas que não parseiam.

7. **Baixa: `requested_here` aceita qualquer texto que cite o comando.**
   - Onde: `python/aifw/hooks.py:401-405` e `requested_here`.
   - Cenário: o PreToolUse registra `requestApproval` para qualquer comando cujo texto case com o regex, como `grep "spec request-approval big" docs`. Uma sessão que pediu `big` uma vez continua "solicitante" para sempre. Se outra sessão pedir `big` depois, as duas congelam, e a resposta em qualquer uma consome o pedido. É raro (duas sessões na mesma mudança).
   - Correção: gravar o `session_id` no `approval-request.yaml` e comparar com ele.

8. **Baixa: respostas que começam por "ok" ou "sim" e recusam depois aprovam.**
   - Onde: `python/aifw/specs.py` (`APPROVING`/`approving`).
   - Cenário: "ok, mas não faça nada ainda" aprova a mudança (sonda `test_ok_reply_with_negation`). É coerente com "começa por", mas contraria a decisão do design "resposta ambígua cancela".
   - Correção opcional: tratar `não`, `mas` e `antes` depois da palavra inicial como ambíguos, ou documentar o limite.

9. **Baixa: `docker buildx build --push` não é tratado como publicação.**
   - Onde: `python/aifw/shell.py:756`.
   - Cenário: o comando roda sem pedir (sonda). A lacuna já existia, mas REQ-AUTONOMY-PUBLISH cobre "e afins".
   - Correção: tratar `--push` em `docker buildx build`/`docker build` e `docker compose push` como `publish`.

10. **Baixa: documentação desatualizada ou incompleta.**
    - `docs/tooling-and-mcps.md:13` ainda diz "escrita remota com aprovação" para GitHub.
    - `templates/project-scaffold.json:164` passa a trazer `commits: allow`, mas proposal, ADR-0037 e migration não citam a mudança.

## Conclusão

Nenhum achado alto. Os caminhos de erro comum do agente seguem pedindo ou negando: push para a branch padrão, tags, force, merge de PR, publicação, deploy de produção, destrutivos e leitura de `.env`. O fluxo de aprovação pelo chat funciona na forma documentada. Os achados 1 a 4 merecem correção antes do archive.

Resultado: aprovado com ressalvas
