# Revisão independente (rodada 4) — hook-indirect-code

## Escopo

- Só o delta entre `scratchpad/review3.diff` e `scratchpad/review4.diff`:
  - `indirect.py`: `make_rules`/`make_commands`, `make_options` com goals, `expand` com variável indefinida vazia, memo de `package_requests` e de `make_requests`, `source` de fora do projeto, `env` em `INSTALLED_TOOLS`, `BUILD_WRAPPERS`, `MAKE_PROGRAMS`, preload colado em `files_run`;
  - `shell.py`: `harmless_setting` e `bun publish`;
  - `hooks.py`: `.husky/`;
  - ADR-0034 (item 13 e residuais), docs/claude-code.md, CHANGELOG e testes novos.
- Spec: proposal.md, design.md, threat-model.md e specs/claude-hook.delta.yaml. Referência: evidence/independent-review-3.md.
- Método: skill `code-review`, com os eixos Standards e Spec feitos por mim, sem subagentes.
- Critério: o modelo decidido no impasse. Reprova só uma regressão de severidade alta, seguida sem intenção de burlar e fora dos residuais declarados, ou um caminho que trave o hook.
- Análise estática, só com `aifw.shell.analyze` e `aifw.hooks.handle`. Nada classificado foi executado. Sem rede, push nem instalação. O único arquivo do repositório alterado é este relatório.

## Estado das ressalvas da terceira revisão

Nos fixtures, o script, alvo ou `package.json` faz `git push origin main`.

| Item | Exemplos e rótulo atual | Estado |
| --- | --- | --- |
| M1 variáveis vigiadas | `GIT_PAGER=cat git log -3`, `PAGER=cat`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null` → read-only; `NODE_OPTIONS=--max-old-space-size=4096 npm run build` e `npm test` com `NODE_OPTIONS=--experimental-vm-modules jest` → filesystem-write, sem pergunta via `handle`. `GIT_EDITOR=true git rebase --continue` ainda pergunta, mas pela regra de commit: `git rebase --continue` sozinho também pergunta. Continuam opaque: `NODE_OPTIONS` com `--require ./x`, `--require=`, `-r` no meio, `--import=`, `--loader=`, `--experimental-loader=`, `export NODE_OPTIONS='-r ...' &&`, `GIT_EDITOR='true; git push'`, `GIT_CONFIG_GLOBAL=./x.cfg`, `GIT_PAGER='sh -c x'`, `GIT_CONFIG_COUNT/KEY/VALUE` | Corrigido |
| M2 make como superconjunto | `make test` com alvo `install` ou `release` ao lado → read-only; via `handle`, sem pergunta. `make release` → ask | Corrigido. A resolução de alvos abriu lacunas (N-M2) |
| B1 preload colado em `rewritten` | `echo x > pre.js && node --require=./pre.js ok.js` e `--import=` → opaque | Corrigido. Persiste a duplicação entre `files_run` e `preload_requests` |
| B2 `.SHELLFLAGS=` na linha | `make '.SHELLFLAGS=-c "git push origin main" x' a` → opaque | Corrigido |
| B3 `make CC=./x` | `make CC=./run.sh hello` e `make RM=./run.sh clean` → opaque | Corrigido |
| B4 fan-out de npm e make | `npm run` 40×40×40: 0,21 s; `$(MAKE)` 40×40×40: 1,34 s (antes 154 s e 27 s); 400 alvos com pré-requisitos densos: 0,02 s; ciclo `a: b`/`b: a` termina | Corrigido |
| B5 `source env/bin/activate` | read-only | Corrigido, mas por um caminho largo demais (N-M1) |
| B5 `source ~/.bashrc`, `. "$HOME/.cargo/env"` | opaque (ask), mesmo com o arquivo existindo: `~` e `$HOME` não são expandidos. Só o caminho absoluto fica read-only | Não corrigido. O ADR e o CHANGELOG afirmam o contrário (N-B3) |
| B5 `./gradlew build` commitado | filesystem-write, sem pergunta | Corrigido. Abriu N-M3 |
| B5 Makefile do Sphinx | `make html` → filesystem-write | Corrigido |
| B6 `bun publish` | external-write, ask | Corrigido |
| B6 `.husky/` | Write `.husky/pre-commit` e `.husky/_/husky.sh` → ask | Corrigido |
| Standards: duplicação `{"node","deno","bun"}` e preload | sem mudança | Mantido (julgamento) |
| Standards: testes faltando | há testes para fan-out de npm, preload colado e valores inofensivos. Falta fan-out de make | Quase todo corrigido |

## Achados novos

Nenhum é de severidade alta sob o modelo decidido, e nenhum trava o hook. Os três médios são regressões em relação à rodada 3, todos com correção pequena.

### MÉDIA

**N-M1. `env` em `INSTALLED_TOOLS` casa qualquer pasta `env` do caminho** (`python/aifw/indirect.py:21`, `:110-111`, `:263`, `:286`; `python/aifw/hooks.py:56`)
- `installed()` testa se algum componente do caminho está em `INSTALLED_TOOLS`. Com `env` na lista, qualquer script sob uma pasta `env` roda sem leitura.
- Exemplos, via `handle` num projeto AIFW:
  - `bash infra/env/deploy.sh` → read-only, sem pergunta. Na rodada 3 dava git-remote;
  - `source infra/env/deploy.sh` → read-only, sem pergunta;
  - `./config/env/prod.sh` → filesystem-write, sem pergunta.
- Também falta a compensação do ADR item 4: Write em `env/deploy.sh` e em `scripts/env/new.sh` não pergunta, porque `hooks.INSTALLED` cobre só `.venv`, `node_modules` e `.tox`. `venv/` já tinha essa lacuna na rodada 3, e `env` a amplia.
- Impacto: pastas `env/`, `infra/env/` e `deploy/env/` são comuns em repositórios de infraestrutura. Rodar o script de deploy existente é o vetor central de REQ-HOOK-SCRIPT-FILES e não exige intenção. Fica em média porque depende do nome da pasta.
- Correção barata: tratar `env` (e `venv`) como ferramenta instalada só quando a pasta tem `pyvenv.cfg`, ou só como primeiro componente do caminho, e incluir `venv`/`env` no `hooks.INSTALLED`.

**N-M2. A resolução de alvos do make perde alvos que o make roda** (`indirect.py:536`, `:546-549`)
- Na rodada 3 o superconjunto lia todas as receitas. Agora três formas comuns ficam de fora:
  - `.DEFAULT_GOAL := release` com `test:` como primeira regra: `make` → read-only. O make roda `release`, mas o reader pega a primeira regra (`:536`) e ignora a variável.
  - Pré-requisito montado por função: `PKGS = web`, `release: $(addprefix publish-,$(PKGS))` e `publish-web:` com push. `make release` → read-only. `expand` devolve `publish-,web` (todos os argumentos), que não casa nenhum alvo, e a regra que publica não é lida.
  - Pré-requisito com `$(wildcard ...)` ou variável indefinida vira `makevar` e também não chega a nenhuma regra.
- Impacto: `make` ou `make release` num Makefile de monorepo libera a publicação sem pergunta. Não exige intenção, mas depende de construções menos comuns que a regra explícita, então fica em média.
- Correção barata:
  - ler `.DEFAULT_GOAL` de `variables` quando não houver goals;
  - quando um pré-requisito expandido tiver `makevar`, `,` ou `$(` não resolvido, cair no superconjunto (todas as regras), como antes.

**N-M3. `./gradlew publish` e `./mvnw deploy` deixaram de perguntar** (`indirect.py:288-290`; `shell.py:79-81`)
- `BUILD_WRAPPERS` libera wrapper commitado com qualquer tarefa. Via `handle`, `./gradlew publish`, `./gradlew publishToMavenCentral`, `./mvnw deploy` e `./mvnw release:perform` → filesystem-write, sem pergunta. Na rodada 3 davam opaque, porque o `eval` do wrapper era lido.
- A causa de fundo é anterior à mudança: `PUBLISH` não tem `gradle`/`gradlew` `publish*` nem `mvn`/`mvnw` `deploy`, e `gradle publish` e `mvn deploy` diretos também não perguntam. É a mesma classe de `bun publish` (B6), que foi corrigido.
- Impacto: publicar um artefato é um caminho óbvio que o agente segue sem intenção. A pergunta que existia por acidente sumiu.
- Correção: incluir essas tarefas em `PUBLISH`, inclusive para o nome do wrapper, ou liberar o wrapper sem leitura só quando `is_test` ou a tarefa não publicar.

### BAIXA

**N-B1. O memo do make ignora a pasta em que as receitas rodam** (`indirect.py:579`)
- A chave tem os stamps do Makefile, os goals e o `cwd`, mas não `folder`. `make -C sub` e `make -f sub/Makefile` leem o mesmo arquivo, mas rodam `./deploy.sh` em pastas diferentes.
- Exemplo: `make -f sub/Makefile` sozinho → git-remote (o `./deploy.sh` da raiz publica). `make -C sub && make -f sub/Makefile` → read-only, porque reaproveita o resultado de `sub/deploy.sh`.
- Exige as duas formas no mesmo comando, então não é um caminho óbvio. Correção: pôr `folder` na chave.

**N-B2. Outras lacunas da resolução de alvos** (`indirect.py:390`, `:407`, `:508`, `:543`)

| Caso | Rótulo | Causa |
| --- | --- | --- |
| Variável por alvo, `release: CMD = git push origin main` mais `release:` com `$(CMD)` | filesystem-write | A linha é descartada (`:508`), e `$(CMD)` vira vazio. Na rodada 3 era opaque |
| `.DEFAULT:` com push e um pré-requisito sem regra | read-only | `.DEFAULT` não é seguido |
| `deploy:` sem receita mais `%:` com push | read-only | Regra explícita sem receita não traz as regras com padrão (`:543`) |
| `--assume-new X`, `--what-if X`, `--new-file X`, `--old-file X`, `--assume-old X` com valor separado | — | Por leitura do código: o valor vira goal (`:407`) e o alvo padrão deixa de ser lido. São opções raras |

Todas são raras ou exigem intenção. Vale declarar as três primeiras como residuais ou tratá-las de forma conservadora, como opaque ou superconjunto.

**N-B3. `source ~/.bashrc` ainda pergunta, ao contrário do que a documentação diz**
- Afirmações: ADR-0034 item 13 (`source` "de um arquivo fora do projeto (`~/.bashrc`)"), a linha 14 do CHANGELOG e o residual do ADR (linha 109).
- Medido: `source ~/.bashrc` e `. "$HOME/.cargo/env"` → opaque e ask, mesmo com o arquivo existindo. `local_file` não expande `~` nem `$HOME`. O teste `test_shell_setup_and_build_wrappers_stay_quiet` usa caminho absoluto, então não pega isso.
- O erro é conservador. Corrigir o texto, ou expandir `~` com `Path.expanduser`.

**N-B4. `source` de qualquer arquivo fora do projeto roda sem leitura** (`indirect.py:263`)
- Vale para `source ../outro/x.sh` e `source /tmp/x.sh` → read-only, enquanto `bash ../outro/x.sh` e `bash /tmp/x.sh` são lidos (git-remote).
- Está declarado como residual, mas o texto cita só `~/.bashrc`. Vale restringir a isenção à home do usuário ou declarar o alcance real.

**N-B5. Caches entre comandos** (`indirect.py:357-361`, `:579-591`)
- Os memos de `package` e `make` guardam o resultado inteiro, inclusive o dos scripts chamados, mas a chave não inclui esses scripts.
- No mesmo processo, sem limpar `_READ`: depois de `step.sh` mudar para push, `make` e `npm run go` continuam read-only. `bash step.sh` relê certo (git-remote), porque `file_requests` usa os stamps do próprio arquivo.
- Hoje não tem impacto: o hook roda um processo por comando (`hooks.main`), e nada no código analisado muda arquivos durante a análise. As mudanças dentro do mesmo comando passam por `rewritten`. O risco aparece se `handle` passar a rodar num processo longo. O comentário de `_READ` ("a hook process reads one command") documenta a premissa.

**N-B6. Standards**
- `MAKE_BUILTINS` (`indirect.py:57`) ficou sem uso depois da mudança em `expand`: é código morto.
- `CONDITIONALS` foi definido entre funções (`:477`), fora do bloco de constantes. É um julgamento.

### Observação anterior ao delta (fora do escopo)

- `printf 'git push origin main' > step.sh; make`, com uma receita que chama `./step.sh` → filesystem-write. `rewritten` só compara os nomes do Makefile (`files_run`), não os scripts chamados pelas receitas ou pelo `package.json`.
- O residual T-003 cobre só "gerador que grava o script sem citar o nome", e aqui o nome é citado. `rewritten` não mudou nesta rodada. Vale avaliar num item próprio.

## Eixo Standards

- Duplicated Code (julgamento): a decisão de preload continua em `preload_requests` e em `files_run` (`:240-241` e `:625-626`). Agora as duas estão iguais, mas é a mesma lógica escrita duas vezes.
- Código morto: `MAKE_BUILTINS` (N-B6).
- Comentários `shortcut:` em `make_commands`: corretos. O docstring de `expand` declara o residual do `export`.
- Testes: os novos cobrem M1, M2, B1-B6 e as regressões principais (pré-requisito, padrão, `$(MAKE)`). Faltam testes para `.DEFAULT_GOAL`, pré-requisito montado por função, `env` fora da raiz, `source ~/...` literal e `./gradlew publish`.

## Eixo Spec

- REQ-HOOK-TASK-RUNNERS: pré-requisitos, order-only, pré-requisitos por variável, cadeias, `$(MAKE)`/`${MAKE}`/`+$(MAKE) -C`, regras com padrão, static pattern, `::`, `;` na linha da regra, condicionais e `$(shell)` continuam detectados. Falhas: N-M2 e N-B2.
- REQ-HOOK-SCRIPT-FILES: regressão para scripts sob pastas `env` (N-M1).
- Documentação divergente:
  - ADR item 13 e CHANGELOG sobre `source ~/.bashrc` (N-B3);
  - ADR item 4 e design sobre a compensação "editar pede confirmação", que não vale para `env/` e `venv/` (N-M1);
  - design.md:47 diz "`env/`", mas o código casa qualquer componente do caminho.
- Fora do pedido: `BUILD_WRAPPERS` com "qualquer tarefa" vai além do falso positivo apontado (`./gradlew build`) e libera tarefas de publicação (N-M3).

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python/test_indirect_code.py`: 173 passaram em 6,2 s.
- `python -m pytest -q -p no:cacheprovider tests_python`: 2348 passaram em 42,6 s.
- `scratchpad/review4_probe.py`:
  - fixtures em diretório temporário; `_READ`/`_READING` limpos antes de cada caso, exceto nos testes de cache;
  - M1 (10 valores inofensivos, 12 tentativas de contorno);
  - 44 casos de make (alvos, pré-requisitos, order-only, padrões, `$(MAKE)`, `.DEFAULT_GOAL`, `.DEFAULT`, `export`/`override`, variável por alvo, indefinida, inline, funções em pré-requisitos, condicionais, `-j`, `-k`, `-l`, `CC`/`RM`/`.SHELLFLAGS`, Sphinx);
  - B1, `env/`, `source` de fora, wrappers, `bun publish`;
  - caches: mudança de arquivo entre chamadas e no mesmo comando; `-C` contra `-f`;
  - tempos;
  - `handle` ponta a ponta num projeto criado por `test_workflows.init`.
- `scratchpad/review4_probe2.py`: decisão de `handle` para a regra de commit, wrappers gradle/maven commitados num repositório git temporário, `env/`, `~/.bashrc` e Write em `env/`, `venv/` e `.venv/`.
- Não verifiquei:
  - o comportamento real de make, gradle e maven (sem execução);
  - as opções `--assume-new` e afins, que só li no código.

Resultado: aprovado com ressalvas
