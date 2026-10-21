# Revisão independente (rodada 3) — hook-indirect-code

## Escopo

- Diff: `scratchpad/review3.diff` (CHANGELOG, docs/claude-code.md, ADR-0034, hooks.py, indirect.py novo, shell.py, templates/.../SKILL.md, tests_python/test_indirect_code.py, test_open_items.py).
- Spec: proposal.md, design.md, threat-model.md, migration.md, specs/claude-hook.delta.yaml. Revisões anteriores: evidence/independent-review-1.md e -2.md.
- Padrões: `principle-catalogs/engineering-principles.yaml` e a lista de smells da skill `code-review`.
- Método: skill `code-review`, com os eixos Standards e Spec feitos por mim, sem subagentes.
- Critério: o modelo de ameaças decidido no impasse (topo do threat-model.md e ADR-0034). Um caminho só reprova se um agente o seguir sem intenção de burlar o hook, se não estiver entre os residuais declarados e se for de severidade alta. Falsos positivos em comandos comuns pesam contra a mudança.
- A análise foi estática, só com chamadas a `aifw.shell.analyze` e `aifw.hooks.handle`. Nenhum comando classificado foi executado. Não houve rede, push nem instalação. O único arquivo do repositório alterado é este relatório.

## Estado dos achados da segunda revisão

Os rótulos são de `analyze(cmd, cwd=projeto temporário)`. Nos fixtures, o script, o `package.json` ou o Makefile faz `git push origin main`.

| Achado | Exemplos e rótulo atual | Estado |
| --- | --- | --- |
| N1 `node -r/--require/--import` | `node -r ./deploy.js ok.js`, `--import`, `--require`, `--require=./deploy.js`, `-r ./deploy`, `-r ./missing.js` → opaque | Corrigido. A forma colada falha em `rewritten` (novo B1) |
| N2 make | `make SHELL=./run.sh`, `--eval=...`, `-E ...`, `-e`, `MAKEFLAGS=-e make` → opaque. `make -f evil.mk -f other.mk` e a ordem inversa → git-remote | Corrigido. Continuam: `make CC=./run.sh hello` só com regras implícitas → read-only (novo B3) e `.SHELLFLAGS=` na linha → read-only (novo B2) |
| N3 `yarn/pnpm publish` com script de mesmo nome | `yarn publish`, `pnpm publish`, `yarn npm publish` → external-write | Corrigido |
| N4 `--script-shell` | `--script-shell=./run.sh`, `--script-shell ./run.sh`, `npm_config_script_shell=`, `NPM_CONFIG_SCRIPT_SHELL=`, `.npmrc` com `script-shell` (`npm --prefix rc run ok`) → opaque | Corrigido. `cd rc && npm run ok` → read-only, que cai no residual declarado "depois de `cd`" |
| N5 workspaces do yarn | `yarn workspace web deploy`, `yarn workspaces foreach run deploy`, `pnpm --filter`, `npm -w`, `pnpm -r` → opaque | Corrigido |
| N6 variáveis inline | `GIT_CONFIG_COUNT/KEY/VALUE`, `GIT_EXTERNAL_DIFF`, `GIT_SSH_COMMAND`, `NODE_OPTIONS`, `BASH_ENV`, `export X=... &&`, `env X=... git`, `X=...; export X; git fetch`, `$env:X=...; git fetch` → opaque | Corrigido. Gera falsos positivos (ver abaixo) |
| N7 fan-out entre arquivos | scripts de shell a→b→c→d: N=40 em 0,09 s, N=200 em 3,1 s | Corrigido para scripts de shell. Não vale para `package.json` e Makefile (novo B4) |
| N8 programa sem extensão fora do projeto | `../t` → filesystem-write | Residual declarado (threat model e ADR) |
| N9 intérpretes fora da lista | `python3.12 deploy.py` → opaque (corrigido). `php deploy.php`, `tsx deploy.ts` → filesystem-write | `python3.12` corrigido. `php` e `tsx` são residual declarado |
| N10 `from os import system` | `python x.py` → read-only | Residual declarado |
| N11 `committed()` sem timeout | agora `timeout=3` em cada `git`. `core.fsmonitor` não é desligado | Parcialmente corrigido. O pior caso é ~6 s, abaixo do timeout de 10 s. Alterar `.git/` pede confirmação, então aceito como está |
| N12 falsos positivos de `INSTALLED` | via `handle`: `.venv/bin/ruff format .` e `source .venv/bin/activate && pytest` → sem pergunta. Write em `.venv/` e `node_modules/` → ask. `rm -rf node_modules` → ask, pela regra de destrutivo já existente (`rm -rf dist` também pergunta) | Corrigido |
| N13 opção de `node` fora de `VALUE_OPTIONS` | `node --env-file .env deploy.js` → secret-read (ask). `--env-file=.env` → opaque. `node --title x deploy.js` → read-only quando existe um `x.py`/`x.js` inofensivo | Baixo e mantido. Na prática falha fechado, e o caso que libera exige um arquivo com o nome do valor |

## Achados novos

Nenhum é de severidade alta sob o modelo decidido. Não encontrei caminho que um agente seguiria sem intenção de burlar o hook, que não esteja entre os residuais declarados e que libere publicação, instalação, push ou envio.

### MÉDIA (falsos positivos; o modelo pede poucas confirmações)

**M1. `EXEC_ENVIRONMENT` marca como opaque variáveis com valores inofensivos e comuns** (`python/aifw/shell.py:362-378`)
- Exemplos via `handle`, todos com ask:
  - `GIT_EDITOR=true git rebase --continue` e `EDITOR=true ...`: é a forma usual de um agente continuar um rebase sem editor interativo;
  - `GIT_PAGER=cat git log -3` e `PAGER=cat ...`;
  - `GIT_CONFIG_NOSYSTEM=1 git status`, porque `GIT_CONFIG\w*` também casa `NOSYSTEM` e `GLOBAL`;
  - `NODE_OPTIONS=--max-old-space-size=4096 npm run build`.
- O caso mais caro: um script do `package.json` com `"test": "NODE_OPTIONS=--experimental-vm-modules jest"` faz todo `npm test` pedir confirmação. Esse é o padrão documentado do Jest com ESM, e `npm test` é a verificação que o Stop cobra.
- Impacto: confirmações frequentes em comandos legítimos, contra a regra "quanto menos aprovações, melhor". O ADR lista as variáveis, mas não lista essas confirmações a mais em "Consequências".
- Sugestão barata:
  - liberar valores conhecidos (`cat`, `true`, `:`, `less`, editores comuns);
  - em `NODE_OPTIONS`, tratar como opaque só quando houver `-r`, `--require`, `--import` ou `--loader`;
  - em `GIT_CONFIG*`, tratar só `COUNT`, `KEY_*`, `VALUE_*`, `PARAMETERS` e um `GLOBAL`/`SYSTEM` diferente de `/dev/null`.

**M2. O Makefile lido como superconjunto faz `make test` pedir quando outro alvo instala ou publica** (`indirect.py:465-494`)
- Exemplos:
  - um Makefile Python com `install: pip install -e .[dev]` faz `make -C py test` dar install e ask;
  - com `release: git push --tags`, `make -C rel test` dá git-remote e ask.
- Alvos `install` e `release` são comuns em projetos reais. Então `make test`, uma verificação, pergunta em boa parte dos repositórios que têm Makefile.
- O atalho está declarado no código (`shortcut:`) e no design, mas não está em "Consequências" do ADR.
- Sugestão: ler só o alvo pedido e suas dependências diretas quando o alvo existir literalmente. Usar o superconjunto apenas para `make` sem alvo ou para regras com `%`.

### BAIXA

**B1. Preload colado não entra em `rewritten`** (`indirect.py:560`)
- `files_run` só lê os pares `-r X`, enquanto `preload_requests` também lê `--require=X`.
- Exemplo: `echo "<push>" > pre.js && node --require=./pre.js ok.js`, com um `pre.js` inofensivo já existente, dá filesystem-write. A forma separada (`-r ./pre.js`) dá opaque.
- Exige sobrescrever um arquivo existente e rodá-lo no mesmo comando com a forma colada, então não é um caminho óbvio. É também um caso de Duplicated Code: a lógica de preload aparece em dois lugares e já divergiu.

**B2. `.SHELLFLAGS=` na linha do make não é detectado** (`indirect.py:396`, `:402`; `shell.py:17`)
- `ASSIGNMENT` exige que o nome comece por letra ou `_`, então `.SHELLFLAGS=...` nunca vira override.
- Exemplo: `make '.SHELLFLAGS=-c "git push origin main" x'` dá read-only.
- O ADR, no item 12, diz que essa forma é ilegível. É divergência entre documentação e código, e o bypass exige intenção.

**B3. `make CC=./x` com regras implícitas** (`indirect.py:465`)
- Exemplo: Makefile com `hello: hello.c` e o comando `make -C c CC=./run.sh hello` dá read-only.
- Exige intenção, mas não aparece entre os residuais. Basta declarar.

**B4. Fan-out em `package.json` e Makefile não é memorizado e passa do timeout** (`indirect.py:290-355`, `:497-527`)

  | Caso | Tempo |
  | --- | --- |
  | `npm run a`, com 3 níveis e N chamadas por nível, N=10 | 2,6 s |
  | o mesmo, N=20 | 19,8 s |
  | o mesmo, N=40 | 154 s |
  | `$(MAKE) -C`, 3 níveis, 20×20×20 | 3,6 s |
  | o mesmo, 40×40×40 | 27 s |

- O resultado falha fechado (opaque, ou block no timeout) e exige uma construção artificial.
- T-007 e o design afirmam "leitura única por arquivo" e "pior caso abaixo de 2 s", o que só vale para scripts de shell. Corrigir o texto ou memorizar `package_requests` e `make_requests`.

**B5. Falsos positivos menores**

| Comando | Rótulo | Causa ou observação |
| --- | --- | --- |
| `source env/bin/activate` (venv chamado `env`, o nome do tutorial oficial) | secret-read e ask | `VIRTUAL_ENV="/.../env"` é lido como segredo, porque `env` não está em `INSTALLED_TOOLS` |
| `source ~/.bashrc`, `. "$HOME/.cargo/env"` | opaque e ask | `~` e `$HOME` não são resolvidos |
| `./gradlew build` | opaque e ask | Antes da mudança era filesystem-write. O wrapper só passa sem leitura em testes, e o `eval` do gradlew é opaque. É uma regressão para projetos Java, fora do perfil Python e Node |
| `make -C docs html` com o Makefile padrão do Sphinx | opaque | `$(O)` é indefinida |
| `make` com `$(patsubst)`, `$(HOME)` ou `include .env` | opaque | Declarado no ADR |

**B6. Fora do escopo, registrado para não se perder**
- `bun publish` → filesystem-write: `PUBLISH` não tem `bun`. A lacuna é anterior à mudança, no comando direto, que um agente usaria sem intenção de burlar. Vale um item próprio.
- Write em `.husky/pre-commit`, com `core.hooksPath` já configurado, não pergunta. O hook do git roda sem leitura no próximo commit. Pôr um push num pre-commit exige intenção. Declarar como residual.

## Eixo Standards

- **clean-code-side-effects / Speculative state (julgamento):** `_READ` e `_READING` são estado global. A chave de `_READ` não inclui `depth`, e o efeito é só conservador:
  - um arquivo lido primeiro em profundidade alta guarda o resultado opaque e pergunta a mais;
  - no caso inverso, o resultado é mais completo.

  O ciclo a↔b dá git-remote nas três ordens testadas.
- **dry-stable-knowledge / Duplicated Code (julgamento):** `files_run` repete a decisão de qual arquivo cada parte roda, e já divergiu de `preload_requests` (B1). `{"node", "deno", "bun"}` se repete em `read_file`, `family` e `files_run`.
- **kiss-simplicity:** `package_requests` acumula ramos por gerenciador. Está legível, mas no limite.
- **clean-code-comments:** os comentários `shortcut:` estão corretos. O docstring de `make_options` promete tratar `.SHELLFLAGS`, que não é detectado (B2).
- **clean-code-tests:** os novos testes cobrem N1–N6 e N12. Faltam testes para:
  - fan-out de `npm` e `make`;
  - a forma colada em `rewritten`;
  - falsos positivos com `GIT_EDITOR=true` e `NODE_OPTIONS=--max-old-space-size`.
- **separation-of-concerns:** mantido. A E/S fica em `indirect.py`, e `shell.py` tem um ponto de chamada e o `exec_environment`.

## Eixo Spec

- REQ-HOOK-SCRIPT-FILES, REQ-HOOK-TASK-RUNNERS, REQ-HOOK-UNREADABLE-CODE e REQ-HOOK-GIT-EXEC estão atendidos para os vetores listados. Os casos fora deles estão nos residuais declarados ou nos baixos acima.
- Aceitação da proposal:
  - os vetores com push perguntam, e os inofensivos passam;
  - `python -m pytest`, `npm test` e `./gradlew test` commitado continuam como verificação;
  - `git config --get` e `--list` são livres;
  - `.git/hooks` e `.git/config` pedem confirmação;
  - a suíte passa.
- Documentação com divergência: ADR item 12 (`.SHELLFLAGS`, B2); T-007 e design ("leitura única", "< 2 s", B4); "Consequências" do ADR, que não cita M1 e M2.
- Fora do pedido: `EXEC_ENVIRONMENT` amplo. A forma vem da decisão do impasse, mas a lista atual cobre mais do que precisa (M1).

## Falsos positivos

- Causados pela mudança e comuns:
  - `GIT_EDITOR=true git rebase --continue`, `GIT_PAGER=cat git ...` e `GIT_CONFIG_NOSYSTEM=1 git ...` (M1);
  - qualquer `npm test` ou `npm run X` cujo script use `NODE_OPTIONS=` (M1);
  - `make test` em Makefiles com alvo `install` ou `release` (M2).
- Menores: `source env/bin/activate`, `source ~/.bashrc`, `./gradlew build`, o Makefile do Sphinx e `make SHELL=/bin/bash` (B5).
- Sem pergunta, conferidos:
  - Python: `pytest`, `python -m pytest`, `py -m pytest`, `uv run pytest`, `uv sync`, `python check.py`, `python manage.py migrate/test` (manage.py do Django), `source .venv/bin/activate`, `.venv/bin/ruff format .`;
  - Node: `node ok.js`, `node --test`, `npm test`, `npm run build`, `lint`, `dev`, `npm run`, `pnpm test/run build`, `yarn test/build`, `bun test`, `bun run build`;
  - make: `make`, `make -n`, `make -j4`, `make -C py2 test/lint`;
  - shell e git: `bash ok.sh`, `./ok.sh`, `sh -c 'bash ok.sh'`, `git status/log/diff`, `git --no-pager log`, `git config --get/--list`.
- Via `handle`, sem pergunta: `pytest`, `python -m pytest`, `npm test`, `npm run build`, `npm run lint`, `make test`, `make`, `bash ok.sh`, `source .venv/bin/activate && pytest`, `.venv/bin/ruff format .`, `uv sync`, `git config --get user.name` e `git status`.

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python/test_indirect_code.py`: 155 passaram em 8,6 s.
- `python -m pytest -q -p no:cacheprovider tests_python`: 2330 passaram em 42,3 s.
- `scratchpad/review3_probe.py`:
  - fixtures em diretório temporário;
  - rótulo de cada achado da rodada 2 e de casos novos;
  - cerca de 60 comandos comuns;
  - `handle` ponta a ponta num projeto criado por `test_workflows.init`, para Bash e Write;
  - tempos: fan-out de shell N=10/20/40/200; make aninhado 20³ e 40³; fan-out de npm N=10/20/40; `loop.sh` recursivo em 0,02 s; aspas abertas em 3000 linhas, opaque em 0,01 s; scripts de 96 mil caracteres, de 0,0 a 0,4 s.
- `review3_probe2.py` a `review3_probe5.py`:
  - causa do secret-read no `activate`;
  - decisão de `handle` para os falsos positivos;
  - `rm -rf` (regra anterior);
  - `.SHELLFLAGS`;
  - preload colado em `rewritten`.
- Não verifiquei:
  - o comportamento real das ferramentas (`make` com `.SHELLFLAGS` na linha, `bun publish`, `pnpm deploy`). A avaliação vem do conhecimento documentado dessas ferramentas, sem rede;
  - `committed()` num repositório git real, porque exigiria criar commits.

Resultado: aprovado com ressalvas
