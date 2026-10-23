# Revisão independente final: agent-autonomy

## Escopo

- Diff do working tree contra `HEAD` (`c0321e6`, 52 arquivos) e os arquivos novos: `.aifw/changes/active/agent-autonomy/`, `docs/decisions/ADR-0037-agent-autonomy.md` e `tests_python/test_agent_autonomy.py`.
- Base: os 10 achados de `evidence/independent-review-7.md`, os relatórios dos cinco verificadores da rodada 8 e as sondas do revisor final.
- Reproduzi por conta própria cada problema alto ou médio relatado pelos verificadores. Sondas em `C:\Users\DARKSQ~1\AppData\Local\Temp\claude\C--Users-DarkSquash-Documents-Projetos-aifw\31451809-735d-4dd2-985a-991c20809a6a\scratchpad\verify8\final\`:
  - `test_final.py`: 40 casos;
  - `test_cmd_suffix.py`: 19 casos;
  - `test_head_compare.py` roda os mesmos comandos no código de `HEAD`. O snapshot fica em `verify8\g4-9\head`, e conferi com `cmp` que `hooks.py`, `shell.py`, `indirect.py` e `specs.py` são idênticos a `git show HEAD:...`;
  - `test_now_publish.py`.
- Modelo de ameaças (ADR-0037/ADR-0034): o hook protege contra erro do agente e caminhos óbvios. Burla deliberada (globs, grafias alternativas usadas para contornar, cópia forjada, código opaco, `git merge` de outra worktree) ficou fora e não foi procurada nem pontuada.
- Severidade:
  - alta: o comportamento pedido não funciona, ou um erro comum do agente passa sem pedir em push para a branch padrão, publicação, deploy de produção, ação destrutiva ou leitura de segredo;
  - média: regressão em comando de rotina, ou doc errada;
  - baixa: o resto.
- Lacunas anteriores à mudança seguem a convenção da revisão 7 e entram como baixa.

## Situação dos 10 achados da revisão 7

1. **Resolvido.** `aifw spec request-approval --json <id>` agora congela a sessão e aprova. O `REQUEST_APPROVAL` (`python/aifw/hooks.py:388-391`) pula opções antes do id. O verificador cobriu 13 variantes com Bash e PowerShell: `--json` antes e depois, `python -m`, `uv run`, `cd . &&`, `(...)`, `; echo`, `2>&1`, `aifw.exe` com caminho e `& aifw`. Fica o resíduo baixo B1.
2. **Resolvido no cenário descrito.** Os cinco comandos que só citam o arquivo pedem: `echo .env >> .gitignore`, `git check-ignore .env`, `cp .env.example .env`, `source .env` e `--env-file .env`. Mostrar o conteúdo é negado. A correção, porém, introduziu a regressão M1 e deixou a lacuna M5.
3. **Resolvido para o `change.yaml`.** O commit depois da aprovação pelo chat roda (`test_committing_after_the_chat_approval_runs`, sonda do verificador). O mesmo sintoma continua depois de `aifw validate --change <id> --write` (M4).
4. **Resolvido.** `gh pr create`, `gh pr comment` e `gh issue create/comment` rodam em projeto novo com a allowlist vazia. `gh pr merge` e as escritas na API fora de discussão pedem. Com `confidential` ou `restricted` sem `github`, a ação é negada.
5. **Resolvido.** Sem `refs/remotes/<remoto>/HEAD`, o motivo cita `git remote set-head origin --auto`. `design.md:12` e `migration.md:4` não descrevem mais o fallback `main`/`master`. Fica o resíduo baixo B6, sobre o motivo dado para um remoto por URL.
6. **Resolvido.** O registro `.aifw/runs/<sessão>.jsonl` não é mais lido. O dono do pedido fica em `.aifw/runs/approvals/<id>.session`. Um jsonl corrompido, um arquivo de dono vazio ou um diretório no lugar dele não travam a sessão. Fica o resíduo baixo B3, com UTF-8 inválido no `.session`.
7. **Resolvido no cenário descrito.** `grep`, `rg`, `git log --grep`, `echo` e um commit sem pontuação que citam o comando não tiram a posse do pedido. Fica o resíduo baixo B2, com `(`, `;` ou `|` dentro da mensagem de commit.
8. **Resolvido.** "ok, mas não faça nada ainda" cancela o pedido e avisa o agente, e outras dez ressalvas também cancelam. A correção trouxe falsos cancelamentos (M2).
9. **Resolvido.** `docker buildx build --push`, `docker build --push`, `docker compose push`, `docker compose build --push`, `buildx bake --push` e `podman push` pedem, e são negados com `confidential`. Em `HEAD`, `buildx build --push` rodava. Os resíduos são anteriores à mudança (B8).
10. **Resolvido.** `docs/tooling-and-mcps.md:13` bate com o código. `commits: allow` no scaffold aparece em proposal, ADR §13 e migration. Os resíduos de documentação estão em B9.

## Achados novos confirmados

Nenhum achado alto. Os médios abaixo foram reproduzidos pelas sondas do revisor final.

### M1. Média: o padrão de busca e o destino de escrita contam como leitura de segredo e são negados

- Onde: `python/aifw/shell.py:792-795`. `any(SECRET_FILE.search(w) for w in args)` olha todos os argumentos, e `shows = name in SHOWS_CONTENT` vale para o programa inteiro.
- Cenário (sonda `test_final.py::test_secret_regression_deny`): estes comandos são negados, sem opção de confirmar. Em `HEAD`, todos pediam (`test_head_compare.py`).
  - `grep .env .gitignore`
  - `grep -qxF .env .gitignore || echo .env >> .gitignore`
  - `rg -n 'process\.env' src`
  - `git ls-files | grep .env`
  - `cat > .env <<'EOF' ... EOF`
  - `cat .env.example > .env`
- Nenhum deles mostra o conteúdo do segredo. Isso contradiz `docs/claude-code.md:52` ("por um comando que mostra o conteúdo"), que manda pedir quando o comando só cita o arquivo.
- Confirmado ao vivo: um `grep -n "segredo\|secret\|\.env" docs/claude-code.md` deste revisor foi negado pelo hook instalado ("reads files or variables that usually hold secrets").
- Correção:
  - em `grep`/`egrep`/`fgrep`/`rg`/`ag`/`findstr`/`select-string`/`sls`/`git grep`, não conferir o padrão (o primeiro posicional sem `-e`/`-f`, ou o valor de `-e`/`--regexp`/`-Pattern`);
  - as palavras logo depois de `>`, `>>`, `>|` e `&>` são destino de escrita e contam como menção (`ask`);
  - incluir esses casos em `test_naming_a_secret_file_asks`.

### M2. Média: aprovações afirmativas com "não", "ainda" ou "not" cancelam o pedido

- Onde: `python/aifw/specs.py:445-449` (`HOLDING`), usado em `approving` (`:451-455`).
- Cenário (`test_final.py::test_holding_false_cancel`, 5 de 5 reproduzidos): estas respostas cancelam, e o agente recebe "a resposta não aprovou o plano de big; o pedido foi cancelado".
  - "sim, não tenho objeções"
  - "ok, não tem problema"
  - "Pode seguir, não vejo problema"
  - "yes, not a problem"
  - "Aprovado, não esqueça de rodar os testes"
- Antes da correção do achado 8, essas respostas aprovavam. O ADR §1 lista "não" e "ainda" como ressalva, então o código segue a letra da doc. Mesmo assim, a falha cai na resposta de confirmação mais natural em pt-BR e custa uma volta extra. A falha é segura: não aprova nada indevidamente.
- Correção:
  - manter as formas de adiamento: `mas|porém|espera|calma|antes|depois que|só depois|ainda não|não (agora|ainda|faça|comece|siga|prossiga|implemente|mexa|execute)|but|wait|don't|not yet`;
  - tirar `não`, `ainda` e `not` soltos;
  - ajustar a lista do ADR §1;
  - incluir "sim, não tenho objeções" como caso que aprova. "ok, mas não faça nada ainda" continua cancelando pelo `mas`.

### M3. Média: `gh api graphql` de leitura pede, com motivo enganoso

- Onde: `python/aifw/shell.py:566-587` (`gh_api` trata qualquer `-f`/`-F` como escrita) e `:556-563` (`github_write`).
- Cenário (`test_final.py::test_gh_graphql_read`): com `github` na allowlist, como neste repositório (`aifw.yaml:19`), `gh api graphql -f query='query { viewer { login } }'` pede "changes the default branch or the remote history". Em `HEAD`, rodava (`verify8\g4-9\test_probe_head.py`). É o caminho comum para ler as threads de revisão de um PR.
- Correção:
  - path `graphql` sem `mutation` nos campos vira `external-read` de `github`;
  - antes de casar `GITHUB_DISCUSSION`, tirar o esquema e o host do path, como faz `http_request`.

### M4. Média: o commit depois de `aifw validate --change <id> --write` ou do archive pede

- Onde: `python/aifw/hooks.py:503-521` (`dirty_control`), com `CONTROL` contendo `evidence/validation.json`, `.aifw/specs/current/`, `policies/` e `.aifw/decisions/` (`:29-54`). A comparação é por substring de `git status`.
- Cenários:
  - `test_final.py::test_commit_after_validate_write`: depois do passo 7 da skill, que grava `evidence/validation.json`, `git add -A && git commit -m wip` pede "commits with the AIFW control file evidence/validation.json changed". O commit do `spec archive` pede pelo mesmo motivo, porque o archive grava `.aifw/specs/current/`.
  - `test_final.py::test_commit_with_project_policies_folder`: num projeto com `app/policies/`, como as policies do Pundit no Rails, todo commit que toca essa pasta pede ("policies/").
- A lógica já existia, mas o scaffold agora traz `commits: allow`. A lista em `docs/claude-code.md:63` ("Charter, permissões, impasses, waivers, break-glass") e a consequência do ADR ("faz commit") deixam de valer em toda mudança L2/L3.
- Correção:
  - em `dirty_control`, verificar só o que depende de assinatura (`.aifw/charter.yaml`, `.aifw/adoption/status.yaml`, `.aifw/impasses/`, `.aifw/waivers/`, `.aifw/break-glass/`) e o que muda a política (`aifw.yaml`, `.aifw/permissions.yaml`...);
  - comparar pelo caminho da linha do porcelain, não por substring;
  - incluir um teste de commit depois de `validate --write`.

### M5. Média: com uma opção global do git, a leitura de segredo só pede

- Onde: `python/aifw/shell.py:794` (`lowered[0] in GIT_SHOWS`): `lowered[0]` é a opção global, não o subcomando.
- Cenário (`test_final.py::test_secret_git_global_option_only_asks`): `git --no-pager diff .env`, `git -C . diff .env` e `git --no-pager show HEAD -- .env` pedem, em vez de negar como exige REQ-AUTONOMY-SECRETS ("negada, sem opção de confirmar"). Agentes usam `--no-pager` com frequência. O comando não passa livre, por isso não é alto.
- Correção: achar o subcomando pulando as opções globais, com o mesmo laço de `git_requests` e `GIT_VALUE_OPTIONS`, e incluir o teste.

### M6. Média: com `opaqueCode: allow`, publicação e deploy de produção por alguns lançadores passam sem pedir

- Onde:
  - `python/aifw/indirect.py:302`: um nome com sufixo `.cmd`/`.bat`/`.ps1`/`.sh` que não existe na pasta vira código opaco, mesmo sem caminho;
  - `:306`: só o wrapper commitado escapa da leitura;
  - `python/aifw/hooks.py:263` e `templates/project-scaffold.json` (`opaqueCode: allow`, novo nesta mudança).
- Cenário (`test_cmd_suffix.py` e `test_final.py::test_gradlew`):
  - passam sem pedir: `npm.cmd publish`, `pnpm.cmd publish`, `vercel.cmd --prod`, `npx.cmd vercel --prod` e `npm.cmd install lodash`;
  - também passam: `./gradlew publish`, `.\gradlew.bat publish` e `./mvnw deploy` com o wrapper ainda não commitado, e `sh gradlew publish` mesmo commitado;
  - em `HEAD`, todos pediam (código opaco pedia);
  - isso contradiz `docs/claude-code.md:63` ("gradle publish, mvn deploy ... sempre pede").
- Por que não é alto: as formas comuns pedem. São elas `npm publish`, `vercel --prod` e `./gradlew publish`, `.\gradlew.bat publish` e `./mvnw deploy` com o wrapper commitado, todas reproduzidas. Neste ambiente, o PowerShell roda com `Process: Bypass` e `npm` resolve para `npm.ps1`, e os transcritos locais não mostram uso real de `npm.cmd` pelo agente, só sondas. O sufixo `.cmd` fica perto de "grafia alternativa", que está fora do escopo.
- Correção:
  - quando o nome não existe na pasta e não tem separador de caminho, devolver `None` em `direct_requests`, para que `name_of` (que já tira `.cmd`) classifique normalmente; o `rewritten()` já cobre um script escrito pelo mesmo comando;
  - aplicar `build_publishes`/`PUBLISH` antes de `indirect.requests`, ou somar `publish` ao resultado dele, e tratar `sh gradlew` como wrapper;
  - incluir testes com `npm.cmd publish` e com um `gradlew` real.

### Baixos

Os baixos foram reproduzidos pelos verificadores. Não reproduzi um por um, salvo onde está indicado.

- **B1:** `python/aifw/hooks.py:388-391`.
  - O pedido não congela, sem aviso nenhum, quando o comando vem depois de uma quebra de linha, de uma continuação `\`, de espaço inicial, com `py -m aifw`, `.venv\Scripts\python.exe -m aifw`, `uv run python -m aifw`, `uvx aifw` ou com `VAR=1 aifw`.
  - O `approval-request.yaml` fica sem dono. A forma documentada funciona.
  - Correção: `re.MULTILINE` com `(?:^\s*|[;&|(\n]\s*)`, e aceitar `py`/`python.exe`. Opcional: o `UserPromptSubmit` avisa o agente quando existe pedido sem dono.
- **B2:** `hooks.py:388-391`. Uma mensagem de commit com `(`, `;` ou `|` antes do comando citado toma a posse do pedido, mas só com duas sessões na mesma mudança. Correção: gravar o dono no PostToolUse, quando o `approval-request.yaml` foi de fato criado, ou documentar o limite.
- **B3:** `hooks.py:663-667`. Um `.session` com UTF-8 inválido levanta `UnicodeDecodeError` e trava a sessão. Correção: `except (OSError, ValueError)`.
- **B4:** `specs.py` (`APPROVING`). "Pode sim", "Perfeito, pode seguir", "Beleza, pode seguir", "Claro", "Tá bom" e "go ahead" cancelam. Isso faz parte do desenho "começa por", mas vale incluir pelo menos `pode sim` e um prefixo curto (`perfeito|beleza|ótimo|isso|certo|claro`).
- **B5:** `specs.py:477-484` e `hooks.py:695-699`. Se a pessoa aprova no terminal e depois responde no chat, o agente recebe "não aprovou". Correção: com `approval` já gravada, devolver uma mensagem própria.
- **B6:** push.
  - `git commit -am x && git push -u origin feat/x` pede "creates or rewrites a commit" (`hooks.py:365`, regra `mixed`). Correção: não contar o push como mistura.
  - Com `push.followTags=true`, uma tag anotada vai junto, sem pedir.
  - `remote.origin.push` com refspec explícito leva o push à `main` sem pedir. É configuração incomum.
  - O motivo dado para `git push https://... feat/x` sugere `git remote set-head <URL>`, que não é um comando válido.
- **B7:** segredos. São lacunas anteriores à mudança, ou desta mudança sem caminho comum de leitura que passe livre:
  - `git show HEAD:.env` e `git cat-file -p HEAD:.env` passam livres, porque falta `:` no prefixo de `SECRET_FILE` (`shell.py:25`; reproduzido em `test_final.py::test_secret_rev_path_free`);
  - `git log --oneline -- .env` e `sed -i ... .env` são negados;
  - o Glob `**/.env` é negado, mas só lista nomes;
  - `.env.local.example` é tratado como segredo, enquanto `secrets.py` o trata como template;
  - `echo $OPENAI_API_KEY`, `gh auth status -t`, `gcloud auth print-access-token` e `~/.aws/credentials` passam livres;
  - o `aifw secrets scan` deixou de apontar `.env.sample`, `.env.template` e `.env.dist` como secret-file, e isso não está no CHANGELOG.
- **B8:** PR e publicação.
  - `gh pr review --approve` e `.../reviews -f event=APPROVE` rodam sem pedir. Em `HEAD`, pediam. Isso bate com `docs/claude-code.md:67` ("revisão"), mas o ADR §5 fala só em "comentários". A pessoa decide.
  - `gh pr view`, `gh pr checks` e `gh pr list` pedem com a allowlist vazia, embora criar o PR rode.
  - `pnpm --filter pkg publish` e `npm -w pkg publish` passam livres, já em `HEAD` (`test_head_compare.py`, `test_now_publish.py`).
  - `helm push`, `goreleaser release` e `buildx --output type=registry` também passam livres, já em `HEAD`.
  - `docker run img tool --push` vira publicação.
- **B9:** documentação.
  - `ADR-0037:23`: o item 10 está colado no fim do item 9 (confirmado).
  - `CHANGELOG.md:22`, `:23`, `:50` e `:54` ainda descrevem `assess activate`, a delegação a Haiku que pede e o `UserPromptSubmit` em segundo plano (confirmado).
  - `docs/claude-code.md:63`, `migration.md:5`, `design.md:12`, `ADR-0037:19` e `CHANGELOG.md:12` dizem que basta `github` na allowlist com `confidential`/`restricted`. Com `restricted`, o PR é negado mesmo assim (`hooks.py:335`).
  - ADR §2, `design.md:23`, `proposal.md:20` e `.aifw/permissions.yaml:14` citam "decisões" assinadas, que não passam por `signing.approved`.
  - O Scope da proposal não cita `opaqueCode: allow` no scaffold.
  - `command -v aifw-hook` e `find ... -name aifw-hook` são negados como "aprovação".

## Verificação

Rodado a partir de `C:\Users\DarkSquash\Documents\Projetos\aifw`:

- `python -m pytest -q -p no:cacheprovider`: 2506 passed (85,9 s).
- `python -m aifw spec validate agent-autonomy --json`: sem achados.
- `python -m aifw spec analyze agent-autonomy --json`:
  - `pass: true`, sem achados;
  - 15/15 requisitos ligados a tarefa, 9/9 cenários verificados e 5/5 tarefas concluídas;
  - `weakTraces` vazio.
- `python -m aifw spec sync agent-autonomy --dry-run --json`: `agent-autonomy` com ação `create`, `aifw-control-plane` e `task-assessor` com `update`, `opaque-judge` com `remove`.
- `python -m aifw claude check`: pass, sem achados.
- Sondas do revisor final: `test_final.py` (40 passed), `test_cmd_suffix.py` (19 passed), `test_head_compare.py` (8 passed) e `test_now_publish.py` (4 passed). As asserções reproduzem os cenários acima.

Não verifiquei:

- o comportamento no Claude Code real, além do `handle()` chamado em pytest e da negação ao vivo de M1;
- se os subagentes recebem o mesmo `session_id`;
- o `AskUserQuestion` durante o congelamento;
- `HOW_TO_USE.md`, `docs/routing.md` e os runbooks, linha a linha.

## Conclusão

Os 10 achados da revisão 7 estão resolvidos nos cenários descritos. Continuam pedindo ou negando, nas formas comuns:

- o push para a branch padrão, as tags e o force push;
- o merge de PR;
- a publicação (`npm publish`, `./gradlew publish` commitado, `docker buildx build --push`) e o deploy de produção;
- os destrutivos e a leitura de `.env` por Read, `cat` e `git diff`.

A aprovação pelo chat funciona na forma documentada.

Nenhum alto se confirmou. Há seis médios:

- M1 (segredos: busca e redirecionamento negados), M2 (falsos cancelamentos) e M3 (graphql) são regressões de rotina introduzidas aqui e merecem correção antes do archive;
- M4 e M5 são doc ou requisito não cumpridos em caminho comum;
- M6 é uma regressão de `opaqueCode: allow` em lançadores menos comuns.

Resultado: aprovado com ressalvas
