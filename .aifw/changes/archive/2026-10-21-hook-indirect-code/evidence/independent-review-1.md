# Revisão independente — hook-indirect-code

## Escopo revisado

- Diff: `review.diff` (CHANGELOG, docs/claude-code.md, ADR-0034, hooks.py, shell.py, templates/.../SKILL.md, tests_python/test_indirect_code.py, test_open_items.py).
- Spec: proposal.md, design.md, threat-model.md, migration.md, specs/claude-hook.delta.yaml.
- Padrões: `principle-catalogs/engineering-principles.yaml`.
- Método: skill `code-review`, adaptada. Os eixos Standards e Spec foram feitos em sequência, sem subagentes, e são relatados separadamente no fim.
- Não alterei nenhum arquivo do repositório além deste relatório.

## Como verifiquei

- `python -m pytest -q -p no:cacheprovider tests_python/test_indirect_code.py tests_python/test_open_items.py`: 76 passaram.
- Suíte completa (`tests_python`): 2242 passaram.
- Rodei scripts de sondagem no scratchpad (`review_probe.py`, `review_probe2.py`, `review_probe3.py`):
  - chamam `analyze(cmd, cwd=...)` sobre projetos temporários;
  - chamam `handle(...)` ponta a ponta, num projeto criado com `test_workflows.init`;
  - chamam `control_target(...)` para os caminhos de `.git`.
- Confirmei com npm real que `npm run x` aceita `package.json` com BOM UTF-8: imprimiu `BOM-OK`.
- Leitura de `.claude/settings.json`: PreToolUse tem `timeout: 10` e `onFailure: block`.

Nas tabelas abaixo, "passa" significa que o tipo resultante é `filesystem-write` não destrutivo, `read-only`, `git-local` ou `commit` (este último com `commits: allow`). Nesses casos o hook não pergunta nada, embora o script faça `git push`. O resultado ponta a ponta `handle → None` foi confirmado para `source run.sh`, `make release` (com `$(PUSH)`), `python -m pytest` (com `pytest.py` local) e `git config diff.external ./run.sh`.

## Achados (ordenados por severidade)

### ALTA — bypasses não declarados em vetores do próprio escopo

**A1. `source x.sh` não é lido** (`python/aifw/shell.py:35-50`, `680-754`)
- `OPAQUE` contém `.` mas não `source`. `source run.sh`, `bash -c 'source run.sh'` e `printf 'git push' > new.sh && source new.sh` caem em `filesystem-write` e passam.
- Impacto: `git push` dentro de qualquer script, sem confirmação. É exatamente o vetor da proposal ("scripts de shell rodados por um shell").
- O threat model não declara esse residual. O mesmo vale para `call run.bat` e `cmd /c call run.bat`.

**A2. Makefile: vários jeitos de rodar comando que `make_recipes` não vê** (`shell.py:640-667`, sobretudo `:662` e `:664`)
- `PUSH = git push origin main` com a receita `\t$(PUSH)`: a variável vira `makevar`, um programa desconhecido, e o resultado é `filesystem-write`. Passa. Já `\t$(GIT) push` resulta em `opaque`.
- Receita na linha do alvo, `release: ; git push origin main`: só são lidas linhas que começam com TAB. Resulta em `read-only` e passa.
- `X := $(shell git push origin main)` fora de receita: é avaliado quando o make lê o arquivo, mas não é lido pelo hook. Passa.
- Continuação de receita (`\`) cuja linha seguinte não começa com TAB: passa.
- `include other.mk`: passa.
- `.RECIPEPREFIX = >`: passa.
- Opções coladas ou com `=` são ignoradas (`:646-651`): `make --directory=sub`, `make -Csub`, `make --file=other.mk` e `make -fother.mk` não leem nada e passam. As formas com espaço funcionam.
- O docstring diz "may ask more than needed and never less", e o ADR-0034 diz "pode perguntar a mais, nunca a menos". As duas afirmações são falsas.

**A3. Script escrito no mesmo comando: o mitigador não cobre vários casos** (`shell.py:593-610`, `613-620`)
- `missing_script` só reconhece nomes com extensão de script ou começados por `./`. `files_read` não conhece `-f` do make nem o nome do módulo de `python -m`.
- Passam, todos com `filesystem-write`:
  - `printf '...' > newmod.py && python -m newmod`
  - `printf 'git push' > new && bash new`
  - `printf '...' > new && python new`
  - `printf 'all:\n\tgit push' > new.mk && make -f new.mk`
  - o mesmo com `other.mk` já existente e inofensivo
- O threat model afirma que o TOCTOU está mitigado. O único residual declarado é o de "programa que não cita o nome do arquivo", e todos os casos acima citam o nome.

**A4. Programas de teste locais e módulos que sombreiam o test runner não são lidos** (`shell.py:546`, `:610`, `749-752`)
- `executed_file` e `missing_script` retornam cedo quando `is_test(words)`. Por isso passam como `read-only`:
  - `./gradlew test` com um `gradlew` escrito pelo agente que faz `git push`;
  - `./pytest`;
  - `python -m pytest` com `pytest.py` local, que o Python executa antes do pacote instalado;
  - `printf x > gradlew && ./gradlew test` (TOCTOU).
- Ligado a isso, e mais amplo: todo test runner executa código do projeto (`conftest.py`, arquivos de teste, o script de `jest`). Esse é o caso mais geral de "código executado indiretamente".
- Manter os testes como verificação é um requisito de aceitação, e isso é razoável. Mas o risco não aparece como residual no threat model nem no ADR-0034.

**A5. Configurações do git que executam programas e escapam de `EXEC_CONFIG`** (`shell.py:76-81`, `341-361`)
- `git config diff.external ./run.sh` resulta em `git-local` e passa. Depois, `git diff` (`read-only`) roda o programa. A regex só cobre `diff.<x>.command|textconv`.
- Opções que levam valor não são puladas na lista de chaves. Assim, a chave lida é o valor da opção:
  - `git config --file ~/.gitconfig core.hooksPath /tmp/h`
  - `git config -f x.cfg alias.p push`
  - `git config --type path core.hooksPath /tmp/h`
  - Os três resultam em `git-local`. Com `commits: allow` (a política deste repo), o commit seguinte roda hooks não lidos.
- `git --config-env core.hooksPath=H commit` e `git --config-env=core.pager=P log`: `--config-env` é pulado como opção e o valor não entra em `configs`. Resultam em `commit` e `read-only`; com `commits: allow`, passam.
- `submodule.<n>.update '!cmd'` resulta em `git-local`, e `git submodule update` executa o comando.
- `git -c protocol.ext.allow=always fetch 'ext::sh run.sh'` resulta em `git-local` e executa um comando arbitrário.
- O threat model declara como residual apenas as variáveis de ambiente (`GIT_SSH_COMMAND`). Nenhum dos casos acima está declarado.

### MÉDIA

**M1. Leitura com erro libera a ação (fail-open), em contradição com T-008** (`shell.py:572-574`, `:655-657`)
- `package_scripts` retorna `None` em `ValueError`/`OSError`. `make_recipes` faz o mesmo em `OSError`. O comando cai no caminho comum e passa.
- Confirmado: um `package.json` com BOM UTF-8 que o npm aceita (testado) faz `npm run deploy` com `git push` passar. Um JSON que o npm aceita e o `json` do Python rejeita também passa.
- O T-008 diz "ler com erro vira ilegível (`opaque`)", e isso vale só para `file_requests`.
- Princípio `clean-code-errors`: o erro desaparece em silêncio e a falha resulta em liberação.

**M2. Executores de pacote: formas comuns não reconhecidas** (`shell.py:575-584`)
- `bun deploy` passa (`bun <script>` roda o script do package.json); `pnpm deploy` foi detectado.
- `npm --prefix web run deploy`, `npm run deploy --prefix web` e `npm -C web run deploy` passam. A opção com valor desloca o primeiro argumento, e o `package.json` lido é sempre o da pasta da sessão.
- Os scripts de ciclo de vida de `npm version`, `npm pack` e `npm rebuild` (`preversion` e afins) também passam.
- A proposal cita `bun`. O residual declarado é `cd`, não `--prefix`.

**M3. Arquivos de controle `.git`: a checagem de shell é por substring sensível a maiúsculas** (`hooks.py:51-52`, `78-80`)
- `cp x .GIT/hooks/pre-commit` (NTFS não diferencia maiúsculas) e `cp x .git/hook*/pre-commit` não são detectados. As duas resultam em `None`.
- Hooks de submódulo também escapam: `.git/modules/<n>/hooks/` não é controle nem pelo Edit.
- O Edit normaliza maiúsculas porque `resolve()` faz isso. A fraqueza da substring já existia para os outros arquivos de controle, mas aqui é nova superfície.

**M4. Wrappers não reconhecidos escondem o script** (`shell.py:107`, `317-332`)
- `timeout 10 bash run.sh` passa.
- `uv run --with rich x.py` toma `rich` como programa, e `x.py` não é lido.
- A lacuna de wrappers é anterior à mudança, mas agora anula vetores do escopo.

### BAIXA

**B1. Disponibilidade (fail-closed, não trava a sessão)** (`shell.py:224-237`, `524-541`)
- Nenhum caminho de exceção trava a sessão. Exceções em `evaluate` são capturadas em `hooks.py:284` e viram `ask`. Erros de caminho no Windows (`local_file` captura `OSError`/`ValueError`), JSON inválido e `RecursionError` em JSON profundo caem aí. Não achei exceção fora do `try`.
- Lentidão:
  - Um `loop.sh` com 20 linhas `bash loop.sh` leva 3,5 s, porque o espalhamento é N³ até a profundidade 3. Com cerca de 30 linhas passa dos 10 s do timeout.
  - Um `.sh` ou `.bat` com 3000 linhas e um apóstrofo sem par no início leva 52 s. `logical_lines` relexa o buffer a cada linha, o que é quadrático. Isso acontece com `.bat` válido como `echo It's`.
- Com `onFailure: block`, o comando é bloqueado, não liberado. O efeito é só o comando afetado não rodar. O T-005 cobre o caso do arquivo grande, mas não o do espalhamento.

**B2. Falsos positivos**
- `npm test && git add package.json` resulta em `opaque`. `rewritten` trata o `git add` que cita `package.json` como reescrita.
- `pwsh -File scripts/check.ps1` com `$files = ...` resulta em `opaque`. Está declarado no design, mas na prática todo `.ps1` não trivial vai perguntar.
- `python manage.py` sem o arquivo resulta em `opaque`. É aceitável.
- Não houve falso positivo para:
  - `python -m pytest`, `npm test`, `./gradlew test`;
  - `.venv/bin/ruff`;
  - `C:/Windows/System32/where.exe`;
  - `git config --get` e `--list`;
  - `git diff`, `bash -n ok.sh` e `cat ok.sh && bash ok.sh`.

**B3. Coerência da documentação**
- `design.md` (Decisions) diz "Arquivo inexistente mantém o comportamento anterior". O Approach, o código e `test_open_items.py` dizem que ele é `opaque`.
- O ADR-0034 e o docstring de `make_recipes` prometem "nunca a menos" (veja A2).
- O T-008 contradiz M1.
- A lista de configs do ADR não traz `sequence.editor` nem `core.gitproxy`, que o código cobre, e não traz `diff.external`, que nenhum dos dois cobre.
- CHANGELOG, docs/claude-code.md e SKILL.md estão coerentes com o código, exceto por esses pontos.

**B4. Limite herdado de `inline_script`**
- `from os import system; system('git push')` em `x.py` resulta em `read-only`.
- É anterior à mudança (ADR-0022), mas agora vale para todos os novos vetores Python.

## Eixo Standards (principle-catalogs)

- **clean-code-errors (violação):** M1. O retorno `None` em erro de leitura é indistinguível de "não há script" e libera a ação.
- **dry-stable-knowledge / possível Duplicated Code e Divergent Change (julgamento):**
  - `files_read` (`:613-620`) refaz, de forma parcial, a decisão de `segment_requests` sobre qual arquivo é executado. As duas já divergiram: `make -f`, `python -m` e arquivo sem extensão, que é a causa de A3.
  - `name in INTERPRETERS or name in SHELLS` e `SCRIPT_SUFFIXES + SHELL_SUFFIXES` se repetem em 3 a 4 lugares.
  - Uma única função que devolvesse "arquivos que este segmento executa" serviria às duas.
- **separation-of-concerns / clean-code-side-effects (julgamento):** `shell.py`, que era um leitor de texto, passou a fazer E/S de arquivo, parse de JSON e de Makefile. Teria valor isolar os leitores de arquivo num módulo próprio, que hoje é pouco testável sem disco.
- **clean-code-comments:** os comentários `shortcut:` estão bem usados. Só o de `make_recipes` promete uma garantia falsa.
- **clean-code-tests:** os testes são legíveis e parametrizados, mas faltam casos negativos para as variações acima: `source`, opções com valor e TOCTOU sem extensão.

## Eixo Spec

- **Aceitação:**
  - Os vetores listados com `git push` perguntam, e os inofensivos passam.
  - `pytest`, `npm test` e `gradlew` continuam como verificação.
  - Leitura e escrita de git config se comportam como pedido.
  - `.git/hooks` e `.git/config` perguntam.
  - A suíte passa.
  - Os testes cobrem cada critério, mas não `pnpm`/`bun` nem `npm start`.
- **Parcial ou incorreto:**
  - REQ-HOOK-SCRIPT-FILES: falta `source` (A1).
  - REQ-HOOK-TASK-RUNNERS: Makefile (A2) e `bun X`/`--prefix` (M2).
  - REQ-HOOK-UNREADABLE-CODE: TOCTOU (A3) e erro de leitura liberando (M1).
  - REQ-HOOK-GIT-EXEC: `diff.external`, `--file`/`--type` e `--config-env` (A5).
- **Fora do pedido:** nada relevante.

## Resumo

- Standards: 1 violação (clean-code-errors) e 2 julgamentos. O pior é o fail-open em erro de leitura.
- Spec: os 4 requisitos estão implementados de forma parcial, com bypasses de severidade alta não declarados no threat model. O pior é `source x.sh` e `$(VAR)` no Makefile, triviais e dentro do escopo.
- Nenhum caminho de exceção trava o hook. Lentidão leva a bloqueio, não a liberação.

Resultado: reprovado
