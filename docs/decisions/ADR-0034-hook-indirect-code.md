# ADR-0034: o hook lê código executado indiretamente

- Status: accepted
- Date: 2026-10-19
- Impact: L3
- Change: `hook-indirect-code`

## Contexto

O hook `PreToolUse` lê o texto do comando, e desde o ADR-0022 também o arquivo de `python x.py` e `node x.js`. A auditoria de 2026-10-19 mostrou que bastava pôr o comando em outro lugar para que nada fosse lido. Com um script que fazia `git push`, todos estes passavam sem pergunta:
- `bash x.sh`, `x.sh` executado pelo caminho, `pwsh -File x.ps1`, `source x.sh`;
- `python x` sem extensão, `python -m <módulo do projeto>`, `uv run x.py`;
- `npm run X`, `make X`.

Também passavam a edição de `.git/hooks/*` e configurações como `alias.p=push`. Como `commits: allow` (ADR-0030) libera commits, um hook do git rodava código não lido a cada commit.

A primeira revisão independente reprovou a primeira versão desta mudança (`evidence/independent-review-1.md`). Ela achou outras formas que continuavam passando: variáveis e `include` no Makefile, scripts sem extensão escritos no mesmo comando, `diff.external`, opções do `git config`, wrappers como `timeout` e falha aberta quando o `package.json` não era lido.

A segunda revisão (`evidence/independent-review-2.md`) também reprovou: achou novas formas (`node -r`, `make SHELL=`, variáveis como `GIT_SSH_COMMAND` e `NODE_OPTIONS`, `script-shell` do npm) e duas regressões da correção. Com duas tentativas falhas numa mudança L3, abriu-se o impasse `hook-indirect-code`.

## Modelo de ameaças (decisão do impasse, 2026-10-20)

Ler e entender código indireto não tem fim: cada ferramenta tem variáveis, configurações e opções que executam outro programa. A pessoa decidiu, em commit assinado:
- o hook protege contra erros do agente e caminhos óbvios, não contra um agente determinado a contorná-lo;
- a contenção de verdade é o sandbox do sistema operacional do Claude Code;
- quanto menos aprovações, melhor: os casos baratos e comuns são fechados, e o resto vira risco residual declarado.

As revisões seguintes julgam a mudança contra esse modelo.

## Decisão

O código indireto fica em `python/aifw/indirect.py`. Dentro do que ele lê, a regra é falhar fechado: o que não se lê com segurança é código ilegível e pede confirmação (`opaqueCode: allow` continua liberando, ADR-0025).

1. **Arquivo executado** por um shell, um interpretador, `source`, `.`, `call` ou pela própria linha (`./x`, `uv run x.py`):
   - a linguagem vem do programa, senão da extensão, senão do `#!`;
   - shell, PowerShell e `.bat` são analisados como comandos;
   - Python e JavaScript seguem as regras do código inline;
   - o resto é ilegível: Perl, Ruby, binário, script de shell com mais de 100 mil caracteres.

   O argumento que é o script é achado pulando as opções e seus valores (`bash -o pipefail x.sh`, `pwsh -ExecutionPolicy Bypass -File x.ps1`, `python < x.py`). Código vindo da entrada padrão (`echo ... | python -`) é ilegível. Um script que se chama de novo é lido uma vez só.
2. **Script inexistente ou alterado no mesmo comando.** O hook lê antes de o comando rodar, então são ilegíveis:
   - o script que ainda não existe;
   - o arquivo lido que outra parte do comando altera. Valem as partes anteriores; nos laços, pipelines e jobs em segundo plano valem também as posteriores; e o conteúdo de `$(...)` sempre conta.

   `chmod`, `attrib` e `git add` não contam como alteração.
3. **`python -m X`:** lê `X.py` ou `X/__main__.py` quando existem no projeto. Isso vale também para um `pytest.py` local, que sombreia o pacote. Módulos instalados não são lidos.
4. **Ferramentas instaladas:** os arquivos em `.venv`, `venv`, `node_modules` e `.tox`, e os programas fora da pasta do projeto, rodam sem leitura. Em compensação, editar essas pastas com as ferramentas de edição pede confirmação (veja o item 12). Um wrapper de teste executado pelo caminho (`./gradlew test`) só roda sem leitura quando está no git e inalterado.
5. **`package.json`:**
   - `npm`, `pnpm`, `yarn` e `bun` têm lidos os scripts de `run X`, `test`, `start`, `stop`, `yarn X`, `pnpm X` e `bun X`, com `pre` e `post`, e os de ciclo de vida de `npm version`, `pack` e `restart`;
   - `--prefix`, `-C`, `--dir` e `--cwd` mudam a pasta lida;
   - workspaces (`--filter`, `-w`, `-r`) e `bun exec` são ilegíveis;
   - um `package.json` que não se lê também é ilegível. O BOM é aceito, como o npm faz.
6. **Makefile:**
   - Lidos e expandidos:
     - as receitas com TAB, inclusive as continuadas com `\`;
     - os comandos depois de `;` na linha do alvo;
     - os `$(shell ...)` de qualquer linha;
     - as atribuições com `!=`;
     - as variáveis, inclusive as passadas na linha de comando ou antes de `make`.
   - `-C`, `-f`, `--directory=` e `--file=` são seguidos, juntos ou separados. `$(MAKE)` relê como um `make`.
   - São ilegíveis:
     - `include`, `define`, `.RECIPEPREFIX`, `SHELL` e `.SHELLFLAGS`;
     - as funções `eval`, `call`, `foreach`, `value`, `file`, `subst` e `patsubst`;
     - `make -e`.
7. **git:** pedem confirmação, como código ilegível:
   - definir, por `git config`, `git -c` ou `git --config-env`, uma configuração que faz o git executar outro programa: `alias.*`, `core.hooksPath`, `core.fsmonitor`, `core.sshCommand`, `core.pager`, `core.editor`, `core.askpass`, `credential.*`, `filter.*`, `include.*`, `hook.*`, `protocol.*`, `pager.*`, `gpg.program`, `diff.external`, `diff.*.command|textconv`, `merge.*.driver`, `difftool/mergetool/browser/man/trailer.*.cmd`, `submodule.*.update`, `remote.*.receivepack|uploadpack` e `uploadpack.packObjectsHook`;
   - `git config --edit`.

   As opções com valor (`--file`, `--type`) são puladas antes de achar a chave.
8. **Arquivos de controle:** toda a pasta `.git/` é arquivo de controle, inclusive a de repositórios aninhados e submódulos. A comparação ignora maiúsculas (`.GIT/hooks`), porque Windows e macOS também ignoram.
9. **Wrappers:** `timeout`, `nice -n`, `sudo -u`, `env -C` e `uv run --with` pulam os próprios valores antes de achar o programa. `env -S` é ilegível. `python3.12` é tratado como `python3`.
10. **Código carregado por opção ou variável:**
    - `node -r`, `--require`, `--import` e `--loader` com um caminho leem o módulo; pacotes por nome são código instalado.
    - Variáveis que fazem um programa executar outro, definidas na linha ou com `export`/`set`, são ilegíveis: `GIT_SSH_COMMAND`, `GIT_EXTERNAL_DIFF`, `GIT_CONFIG_*`, `GIT_PAGER`, `NODE_OPTIONS`, `BASH_ENV`, `LD_PRELOAD`, `EDITOR`, `PAGER`, `SHELL`, `MAKEFLAGS`, `npm_config_*` e afins (lista `EXEC_ENVIRONMENT` em `shell.py`).
11. **Gerenciadores de pacotes:**
    - `--script-shell` e um `.npmrc` ou `.yarnrc` do projeto com `script-shell` tornam os scripts ilegíveis.
    - `yarn workspace` e `yarn workspaces` são ilegíveis.
    - Builtins de yarn e pnpm (`publish`, `pack`, `why`) seguem a própria regra, mesmo com um script de mesmo nome.
12. **make:** `SHELL=`, `.SHELLFLAGS=`, `MAKEFILES=` e `MAKEFLAGS=` na linha, `--eval`/`-E` e `-e` são ilegíveis. Vários `-f` são lidos juntos, na ordem.

13. **Menos falsos positivos (terceira revisão):**
    - `make` lê só os alvos pedidos (ou o `.DEFAULT_GOAL`, ou o primeiro alvo), seus pré-requisitos, as regras com padrão quando o alvo não tem regra explícita e as regras com variável no nome. Referências de substituição (`$(SRCS:.c=.o)`, `$(PKGS:%=publish-%)`) são expandidas como no make. Pré-requisitos ou `.DEFAULT_GOAL` montados por função ou por variável indefinida, direto ou numa variável, fazem ler todas as regras. Isso não vale para funções de caminho como `wildcard` nem para as variáveis do próprio make (`CURDIR`, `CC`). Cada variável é seguida e expandida uma vez. É ilegível uma expansão maior que 100 mil caracteres, o total das receitas expandidas acima disso e um Makefile desse tamanho (o que inclui Makefiles grandes gerados pelo automake). Assim, camadas e ciclos de variáveis não pesam no hook. Uma variável que o Makefile não define fica vazia, como no make.
    - Valores comuns das variáveis vigiadas não perguntam: `GIT_EDITOR=true`, `GIT_PAGER=cat`, `GIT_CONFIG_NOSYSTEM=1`, `NODE_OPTIONS` sem `-r`/`--import`.
    - `source` (ou `.`) de um arquivo fora do projeto (`~/.bashrc`, `$HOME/.cargo/env`, com `~` e `$HOME` expandidos) e de um script `activate` de ambiente virtual roda sem leitura.
    - `./gradlew` e `./mvnw` commitados e inalterados rodam sem leitura. Contam como publicação, em qualquer posição: tarefas do Gradle com `publish` no nome (`:lib:publish`, `publishToMavenCentral`), exceto `publishToMavenLocal` e os valores de opções como `-x` e `--task`; e os goals do Maven `deploy`, `deploy:deploy-file`, `release:prepare` e `release:perform`, sem contar valores de opções como `-pl`. As opções com valor são conferidas por ferramenta e respeitando maiúsculas, então flags como `mvn -B` e `gradle -s` não escondem a tarefa seguinte.
    - `bun publish` é publicação, e `.husky/` é arquivo de controle.
    - Sobrescrever na linha os programas das regras embutidas do make (`CC`, `RM`, `LD` e afins) é ilegível.

Alterar `.venv/`, `node_modules/` ou `.tox/` pede confirmação só pelas ferramentas de edição. Pelo shell, `.venv/bin/ruff format .` cita a pasta sem alterá-la, então não pergunta.

## Consequências

- Scripts que publicam, instalam, apagam ou enviam dados pedem confirmação como o comando direto pediria; scripts inofensivos continuam livres.
- Pedem confirmação a mais, sempre a favor da segurança:
  - scripts PowerShell com variáveis (`$x = ...`);
  - Makefiles que usam `include` ou funções do make que o leitor não segue;
  - wrappers de teste ainda não commitados.
- Riscos residuais aceitos, registrados no threat model:
  - Executores de teste rodam o código de teste do projeto (`conftest.py`, testes, plugins) sem leitura. Exigir confirmação a cada teste inviabilizaria a verificação que o Stop cobra. Esse código fica nos commits que a pessoa revisa.
  - Também ficam invisíveis, por exigirem intenção de contornar o hook ou custarem aprovações demais:
    - imports de um script e scripts rodados depois de um `cd`;
    - variáveis de ambiente fora de `EXEC_ENVIRONMENT`, exportadas em comandos anteriores, e as configurações globais do usuário (`~/.npmrc`, `~/.gitconfig`);
    - `just`, `task`, `php`, `tsx`, `ts-node` e wrappers não listados (`stdbuf`, `wsl`);
    - um gerador que grava um script sem citar o nome dele no mesmo comando;
    - programas sem extensão gravados fora da pasta do projeto e executados pelo caminho;
    - código Python que chama funções de execução importadas por nome (`from os import system`);
    - variável de Makefile vinda do ambiente, que o reader expande como vazia, inclusive dentro do padrão de uma substituição (`$(PKGS:%=$(X)-%)`);
    - Makefiles montados para consumir memória ou tempo do leitor (substituições gigantes, grafos densos de variáveis): falham fechado, com confirmação ou bloqueio por timeout, e não liberam a ação;
    - qualquer arquivo de fora do projeto carregado com `source` ou `.` (o mesmo arquivo rodado com `bash` é lido);
    - variáveis por alvo, `.DEFAULT:`, uma regra explícita sem receita junto de uma regra com padrão no Makefile, e opções do make com valor separado pouco usadas (`--assume-new X`), cujo valor é lido como alvo;
    - escrita em `.venv/` ou `node_modules/` por comando de shell;
    - o `.git` de uma worktree, que fica fora do projeto.

## Rollback

Reverter o commit da mudança: o hook só lê mais arquivos e não grava estado. `opaqueCode: allow` em `permissions.yaml` reduz as confirmações sem reverter.
