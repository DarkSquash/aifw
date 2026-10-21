# Revisão independente (rodada 2) — hook-indirect-code

## Escopo

- Diff revisado: `scratchpad/review2.diff`. Arquivos: CHANGELOG, docs/claude-code.md, ADR-0034, hooks.py, indirect.py (novo), shell.py, templates/.../SKILL.md, tests_python/test_indirect_code.py e test_open_items.py.
- Spec: proposal.md, design.md, threat-model.md, migration.md, specs/claude-hook.delta.yaml.
- Relatório anterior: evidence/independent-review-1.md.
- Padrões: `principle-catalogs/engineering-principles.yaml`.
- Método: skill `code-review`, adaptada. Os eixos Standards e Spec foram feitos por mim, sem subagentes, e aparecem em seções separadas.
- Análise estática e chamadas a `aifw.shell.analyze` e `aifw.hooks.handle`. Nenhum comando classificado foi executado. Não houve rede, push ou instalação.
- O único arquivo alterado no repositório é este relatório.

## Achados da primeira revisão

Rótulo obtido com `analyze(cmd, cwd=projeto temporário)`. Em cada caso, o script, o `package.json` ou o Makefile faz `git push origin main`.

| Achado | Comando de exemplo | Rótulo | Estado |
| --- | --- | --- | --- |
| A1 `source`/`call` | `source run.sh`, `. run.sh`, `bash -c 'source run.sh'`, `cmd /c call run.bat` | git-remote | Corrigido |
| A1 | `printf 'git push' > new.sh && source new.sh` | opaque | Corrigido |
| A2 Makefile | `$(PUSH)`; `release: ; git push` | git-remote | Corrigido |
| A2 | `$(shell ...)` fora de receita; `include`; `.RECIPEPREFIX` | opaque | Corrigido |
| A2 | continuação `true && \` + linha sem TAB | git-remote | Corrigido |
| A2 | `make --directory=sub`, `-Csub`, `--file=evil.mk`, `-fevil.mk` | git-remote | Corrigido, mas há formas novas que passam (N2) |
| A3 TOCTOU | `> newmod.py && python -m newmod`, `> new && bash new`, `> new && python new`, `> new.mk && make -f new.mk`, `> other.mk && make -f other.mk` | opaque | Corrigido |
| A4 test runners locais | `./gradlew test` não commitado, `./pytest`, `python -m pytest` com `pytest.py` local, `printf x > gradlew && ./gradlew test` | opaque | Corrigido. O código de teste fica como residual declarado (T-005, ADR-0034) |
| A5 git config | `diff.external`; `--file`, `-f`, `--type`; `--config-env` com e sem `=`; `submodule.x.update`; `-c protocol.ext.allow` | opaque | Corrigido. A forma por variável inline continua aberta (N6) |
| M1 erro de leitura | `package.json` com BOM | git-remote | Corrigido |
| M1 | JSON inválido | opaque | Corrigido |
| M2 executores de pacote | `bun deploy`, `npm --prefix web run deploy`, `npm run deploy --prefix web`, `npm -C web run deploy`, `npm version patch` | git-remote | Corrigido. `npm rebuild` dá filesystem-write; não verifiquei se o npm roda os scripts da raiz nesse caso, e ele está fora da lista do ADR |
| M3 `.git` em shell | `cp x .GIT/hooks/pre-commit`, `cp x .git/hook*/pre-commit`, Write `.git/modules/n/hooks/...`, `.GIT/config`, `sub/.git/hooks/x` | ask (via `handle`) | Corrigido |
| M4 wrappers | `timeout 10 bash run.sh` | git-remote | Corrigido |
| M4 | `uv run --with rich deploy.py` | opaque | Corrigido. Wrappers não listados (`wsl bash run.sh` dá filesystem-write) são residual declarado em T-009 |
| B1 desempenho | `loop.sh` recursivo | git-remote | Corrigido (< 2 s) |
| B1 | aspas abertas com 3000 linhas | opaque em 0,09 s | Corrigido |
| B1 | fan-out entre arquivos distintos | — | Ainda aberto (N7) |
| B2 falsos positivos | `npm test && git add package.json` | git-local | Corrigido |
| B2 | `pwsh -File check.ps1` com `$x` | opaque | Aceito, declarado no design e no ADR |
| B2 | `python manage.py` sem arquivo | opaque | Aceito |
| B3 documentação | "nunca a menos" | — | Corrigido: saiu do ADR e do docstring. Resta uma ocorrência sobre `.ps1` em design.md:40, que está correta nesse contexto |
| B3 | `design.md` e o arquivo inexistente | — | Corrigido |
| B3 | T-008 contra o código | — | Corrigido |
| B4 `inline_script` | `from os import system; system('git push')` em `x.py` | read-only | Ainda aberto. É anterior à mudança (ADR-0022) e não está declarado como residual (N10) |

### Comandos comuns, que devem continuar livres

| Comando | Resultado |
| --- | --- |
| `pytest`, `npm test`, `source .venv/bin/activate`, `git config --get user.name`, `git config --list`, `make` e `make -C m_ok` (Makefile só com `echo`), `bash ok.sh`, `./ok.sh`, `node ok.js`, `npm run ok`, `cat run.sh && bash ok.sh` | read-only |
| `git config user.name x` | git-local |
| `uv sync` | filesystem-write |
| `pytest`, `python -m pytest`, `uv sync`, `make`, `bash ok.sh`, `git config --get user.name` via `handle` | `None`, ou seja, sem pergunta |

`python -m pytest` deu opaque apenas no diretório de sondagem que tinha um `pytest.py` local. Esse é o comportamento pedido em A4.

## Achados novos

### ALTA — classificações erradas não declaradas como residuais

**N1. `node -r/--require/--import` não lê o módulo pré-carregado. É regressão da correção de A2/M4.** (`python/aifw/indirect.py:30`, `:182-183`)
- Exemplos: `node -r ./deploy.js ok.js`, `node --import ./deploy.js ok.js`, `node --require ./deploy.js ok.js`. Os três dão read-only, e `handle` devolve `None`.
- `VALUE_OPTIONS["node"]` pula o valor de `-r` como se fosse dado, mas esse valor é código que o node executa antes do script.
- Antes da mudança, `script_source` lia o primeiro argumento sem `-`, ou seja, `./deploy.js`, e o resultado era opaque. Agora o resultado é read-only.
- Impacto: `git push` ou rede sem confirmação, só por mudar a posição do arquivo. Isso não é "import de um script": o arquivo está nomeado na linha de comando.

**N2. Make: opções e variáveis da linha de comando que mudam o que roda** (`indirect.py:304-330`, `:398`, `:419`)
- `make SHELL=./run.sh` com um Makefile só de `echo`: read-only, e `handle` devolve `None`. O make roda cada receita pelo `./run.sh`.
  - `MAKE_UNREADABLE` só procura `SHELL` no texto do Makefile, e não nos `overrides`.
- `make --eval='$(shell git push origin main)'`: read-only. `--eval`/`-E` não é tratado. O make avalia a string como uma linha de Makefile.
- `make -f evil.mk -f other.mk`: read-only. Só o último `-f` é lido, mas o make lê todos.
- `make CC=./run.sh hello` com `hello.c` e regras implícitas: read-only. As regras implícitas (`$(CC) ...`) não estão no arquivo, então o override não aparece em nenhum comando lido.
- Impacto: os mesmos vetores de REQ-HOOK-TASK-RUNNERS que a primeira revisão marcou como altos em A2, agora por outras opções.
- O ADR-0034 diz que as variáveis da linha de comando são lidas e que `SHELL` é ilegível. O código só cumpre isso dentro do arquivo.
- O residual declarado é "variáveis exportadas antes", e não estas da linha de comando.

**N3. `yarn publish` e `pnpm publish` deixam de ser publicação quando o `package.json` tem um script `publish`. É regressão.** (`indirect.py:275-278`; o ramo `PUBLISH` fica em `shell.py:578`, depois de `indirect.requests` em `shell.py:558`)
- Exemplo: com `"publish": "echo hi"`, `yarn publish` e `pnpm publish` dão read-only. Sem o script, dão external-write.
- `package_requests` trata `yarn X` e `pnpm X` como script quando a chave existe. Para os comandos embutidos, porém, o yarn e o pnpm rodam o comando embutido, e o script `publish` só roda como ciclo de vida dele.
- Impacto: publicação no registro sem confirmação. Basta o agente escrever o script no `package.json`, o que é um filesystem-write livre.

**N4. `npm ... --script-shell` escolhe o programa que roda os scripts** (`indirect.py:244-261`)
- `npm test --script-shell=./run.sh`, `npm test --script-shell ./run.sh` e `npm_config_script_shell=./run.sh npm run ok` dão read-only.
- O npm roda o script `ok` ou `test`, que são inofensivos, através de `./run.sh`.
- Do mesmo tipo e não declarado: `script-shell` num `.npmrc`, que é um arquivo escrito livremente e não é controle.
- Impacto: igual a N2, no vetor do `package.json`.

### MÉDIA

**N5. `yarn workspace <pkg> <script>` e `yarn workspaces foreach run X` não são lidos nem dão opaque** (`indirect.py:250`, `:258`, `:275`)
- `yarn workspace web deploy` e `yarn workspaces foreach run deploy` dão filesystem-write.
- O design e o ADR dizem que os workspaces são opaque. Isso só vale para `--filter`, `-w`, `-r` e `--workspaces`.

**N6. Variáveis inline antes do programa que fazem outro código rodar** (`shell.py:336`, em `program_at`, que só pula as atribuições)
- Exemplos:
  - `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=h git commit -m x` dá commit. Com `commits: allow`, passa.
  - `GIT_EXTERNAL_DIFF=./run.sh git diff` dá read-only.
  - `GIT_SSH_COMMAND='sh run.sh' git fetch` dá git-local.
  - `NODE_OPTIONS='--require ./deploy.js' node ok.js` dá read-only.
  - `BASH_ENV=./run.sh bash ok.sh` dá read-only.
- O threat model (T-004) e o ADR declaram "variáveis de ambiente exportadas antes". A forma inline está no próprio texto do comando e tem o mesmo efeito de `git -c`, que REQ-HOOK-GIT-EXEC exige tratar.
- Pela proximidade com o residual declarado, classifico como média. É preciso tratar o caso ou declará-lo explicitamente.

**N7. Fan-out entre arquivos distintos passa do timeout de 10 s. A afirmação "leitura única por arquivo" é falsa.** (`indirect.py:140-155`)
- `_READING` só impede a recursão na pilha atual. Arquivos irmãos chamados várias vezes são relidos a cada chamada.
- Medido com `a.sh → b.sh → c.sh → d.sh`, cada arquivo com N linhas que chamam o próximo:

  | N | Tempo |
  | --- | --- |
  | 10 | 1,9 s |
  | 20 | 16,4 s |
  | 40 | 128,8 s |

- Um Makefile com 40 `$(MAKE) -C sub`, cada `sub` com 40 `bash ../a.sh`, levou 14,2 s.
- Efeito: com `onFailure: block`, o comando é bloqueado, e não liberado. A sessão não fica presa, porque o Claude Code encerra o hook em 10 s.
- T-007 ("nenhum conhecido", "leitura única por arquivo") e o design ("pior caso conhecido abaixo de 2 s") estão incorretos.
- Correção sugerida: memorizar o resultado por (arquivo, profundidade) dentro de uma avaliação.

**N8. Programa sem extensão fora do projeto roda sem leitura** (`indirect.py:233`)
- Sequência: `printf 'git push origin main' > ../t && chmod +x ../t` e depois `../t`. Os dois dão filesystem-write.
- Está escrito como decisão no ADR (item 4) e em docs/claude-code.md, mas não aparece como risco residual no threat model, nem em "Riscos residuais" do ADR.
- A intenção declarada é cobrir programas do sistema como `git.exe`. O efeito, porém, é um bypass em dois comandos.

**N9. Intérpretes fora da lista executam arquivos do projeto sem leitura** (`shell.py:67`, `indirect.py:193`)
- `python3.12 deploy.py`, `php deploy.php` e `tsx deploy.ts` dão filesystem-write.
- O caso `python3.12` é anterior à mudança, mas está no escopo de REQ-HOOK-SCRIPT-FILES ("interpretador").
- `php` e `tsx` ferem o espírito de REQ-HOOK-UNREADABLE-CODE: arquivo do projeto que o hook não sabe ler deveria ser opaque.
- Os non-goals citam apenas "executores de tarefas".

### BAIXA

**N10. B4 continua aberto** (`shell.py:54-57`)
- `from os import system` seguido de `system(...)` não casa com `RUNS_PROGRAMS`.
- É anterior à mudança, mas agora vale para todos os novos vetores Python. Não está declarado como residual.

**N11. `committed()` executa `git status` sem timeout dentro do hook** (`indirect.py:104-112`)
- O `git status` executa o `core.fsmonitor` configurado e pode demorar em repositórios grandes.
- O risco é mitigado, porque alterar `.git/` agora pede confirmação. Ainda assim, convém passar `timeout=` e `-c core.fsmonitor=false`.

**N12. Falsos positivos de `INSTALLED`** (`hooks.py:61`, `:90`)
- `rm -rf node_modules`, `.venv/bin/ruff format .` e `source .venv/bin/activate && ruff format .` pedem confirmação via `handle`.
- Isso é coerente com a decisão "alterar essas pastas fora de instalação pede". Mesmo assim, a substring casa com qualquer comando que muda arquivos e menciona `.venv/`, mesmo quando não altera `.venv/`.
- Os dois últimos exemplos são comuns no dia a dia e não estão listados no ADR como confirmações a mais.

**N13. Opção de `node` com valor fora de `VALUE_OPTIONS` desloca o script** (`indirect.py:30`)
- Exemplos: `--env-file x`, `--title x`.
- Falha fechada na maioria dos casos: o valor não existe e dá opaque, ou é `.env` e dá secret-read. Só libera quando o valor é um arquivo existente e inofensivo.

## Eixo Standards (principle-catalogs)

- **separation-of-concerns, clean-code-cohesion:** a sugestão da primeira revisão foi atendida. A E/S de arquivos foi para `indirect.py`, e `shell.py` voltou a ser só leitor de texto, com um ponto de chamada.
- **clean-code-errors:** atendido. Os erros de leitura viram opaque. `RecursionError` em JSON profundo não é capturado em `package_requests`, mas o `evaluate` do hook transforma a exceção em `ask` (falha fechada).
- **clean-code-side-effects (julgamento):**
  - `_READING` é estado global mutável do módulo. O `try/finally` o mantém consistente, e o hook roda um processo por chamada, então não há problema de concorrência.
  - Ainda assim, um conjunto passado por parâmetro deixaria a função pura e permitiria a memorização que N7 precisa.
  - `committed()` dispara processos `git` dentro de um classificador (N11).
- **dry-stable-knowledge, possível Duplicated Code/Divergent Change (julgamento):**
  - `files_run` (`indirect.py:468-487`) refaz a decisão de qual arquivo cada parte executa, separada de `runner_requests`, `make_requests` e `package_requests`.
  - As duas já divergem: os módulos de `node -r` e os vários `-f` do make não entram em nenhuma das duas.
- **Repeated Switches (julgamento):** `{"node", "deno", "bun"}` e `name in INTERPRETERS or name in SHELLS` se repetem em `file_requests`, `family`, `runner_requests` e `files_run`.
- **clean-code-comments:** o docstring de `make_commands` agora descreve um superconjunto que "pode perguntar a mais". Isso é correto para as receitas, mas não para os overrides (N2).
- **clean-code-tests:**
  - Os testes são bons e cobrem os casos da primeira revisão.
  - Faltam casos para:
    - `node -r`;
    - `yarn/pnpm publish` com script;
    - `make SHELL=`, `--eval` e `-f` repetido;
    - `npm --script-shell`;
    - `yarn workspace`;
    - fan-out entre arquivos.
  - O teste de desempenho mede só a recursão.

## Eixo Spec

- **Aceitação (proposal):**
  - Cada vetor listado com `git push` pede confirmação, e as versões inofensivas passam.
  - `python -m pytest`, `npm test` e `./gradlew test` commitado continuam como verificação (`test_test_runners_still_count_as_verification`).
  - `git config --get` e `--list` estão livres; `git config alias.p push` e `git -c core.hooksPath=x commit` pedem confirmação.
  - `.git/hooks` e `.git/config` pedem confirmação.
  - A suíte passa.
- **Parcial ou incorreto:**
  - REQ-HOOK-SCRIPT-FILES: N1 (regressão), N9.
  - REQ-HOOK-TASK-RUNNERS: N2, N4, N5 e a regressão N3, que reduz uma publicação a read-only.
  - REQ-HOOK-GIT-EXEC: N6 (variáveis inline).
  - REQ-HOOK-UNREADABLE-CODE: N8 e N9.
- **Documentação:** CHANGELOG, docs/claude-code.md, os dois SKILL.md e o ADR estão coerentes com o código, com estas exceções:
  - o ADR item 6 ("variáveis da linha de comando" e "`SHELL` ilegível") não vale para os overrides (N2);
  - os workspaces só valem para os flags (N5);
  - T-007 e design ("leitura única", "< 2 s") estão errados (N7);
  - o threat model não cita N8.
- **Fora do pedido:** `INSTALLED` como controle é extensão razoável e está documentada. Os efeitos colaterais estão em N12.

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python/test_indirect_code.py`: 128 passaram em 5,0 s.
- `python -m pytest -q -p no:cacheprovider tests_python`: 2303 passaram em 42,0 s.
- `scratchpad/review2_probe.py`:
  - cria fixtures num diretório temporário: scripts com `git push origin main`, `package.json` (normal, com BOM e inválido), Makefiles por variante e `.venv/bin/activate`;
  - imprime a tabela `analyze` acima;
  - chama `handle` ponta a ponta num projeto criado por `test_workflows.init`, para Bash e Write;
  - mede o desempenho (fan-out, aspas abertas e script de 96 mil caracteres, que deu opaque em 0,01 s).
- `scratchpad/review2_probe2.py`:
  - confirma que importar `aifw.indirect` antes de `aifw.shell` funciona, ou seja, o ciclo de import é seguro;
  - testa a continuação real de receita, `pnpm/yarn publish` sem script (external-write) e o fan-out com N=10 e N=20.
- Exceções: nenhum caminho novo encontrado sai do `try` de `evaluate`. Erros de caminho, JSON e permissão viram opaque ou `ask`.
- Não executei nenhum comando classificado. Não verifiquei em ferramentas reais o comportamento de `npm rebuild`, `--script-shell` e `make --eval`. A avaliação deles vem da documentação conhecida das ferramentas, sem acesso à rede nesta revisão.

Resultado: reprovado
