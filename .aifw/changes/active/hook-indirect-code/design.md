# Design — Hook lê código indireto

## Context

`shell.segment_requests` classifica cada comando simples. O que não reconhecia caía em `filesystem-write` não destrutivo, que a política libera. Só `python x.py` e `node x.js` tinham o arquivo lido, e só com essas extensões. A primeira revisão independente (`evidence/independent-review-1.md`) reprovou a primeira versão desta mudança por formas que ainda passavam e por falhar aberto em erro de leitura.

## Approach

O código indireto fica num módulo próprio, `python/aifw/indirect.py`, chamado por `segment_requests` num só ponto (`indirect.requests`) depois dos ramos que já tratam código ilegível e `-c`. A regra do módulo é falhar fechado: o que ele não lê com segurança é `opaque`.

- `requests` tenta, em ordem:
  1. `package_requests`: os scripts do `package.json`, mais `pre`, `post` e ciclo de vida, com `--prefix`, `-C`, `--dir` e `--cwd`. Workspaces, `bun exec` e JSON ilegível são `opaque`.
  2. `make_requests`: `make_options` lê `-C`, `-f` (juntos ou separados), as variáveis passadas e `-e`; `make_commands` junta as continuações e coleta receitas, `;`, `$(shell)` e `!=`; `expand` expande as variáveis e devolve `None` (opaque) para o que não segue.
  3. `runner_requests`: interpretador, shell, `source`, `.` e `call`. `script_argument` acha o script pulando opções com valor por família (shell, python, node, pwsh) e trata `< arquivo`. Entrada padrão em pipe e script inexistente são `opaque`. O Windows PowerShell sem `-File` analisa o resto da linha como comando.
  4. `direct_requests`: execução pelo caminho e `python -m` local. Um wrapper de teste só passa sem leitura quando `committed` (no git e inalterado).
- `file_requests` lê até 1 MB e decide pela linguagem (`language`: programa, extensão, `#!`). Um arquivo já em leitura mais acima (`_READING`) conta como `read-only`, porque seus pedidos já foram contados. Isso evita explosão em scripts recursivos e mantém o `$(MAKE)` recursivo legível.
- `rewritten`, chamado por `shell.analyze`, compara `files_run` de cada parte (nomes de arquivos que ela rodaria, existindo ou não) com as palavras das partes que alteram arquivos:
  - valem as partes anteriores, e também as posteriores em laços, pipelines e `&`;
  - o conteúdo de `$(...)` sempre conta;
  - `chmod`, `attrib` e `git add/stage/commit` não contam.

Em `shell.py`:
- `program_at` pula os valores de `sudo`, `env`, `nice`, `time`, `timeout` e `uv run`;
- `env_splits` marca `env -S` como `opaque`;
- `.` deixa de ser `opaque` direto e passa a ter o script lido;
- `logical_lines` desiste depois de 200 linhas com aspas abertas;
- `git_requests` lê `--config-env`, pula as opções com valor do `git config`, trata `--edit` e usa o `EXEC_CONFIG` ampliado.

Em `hooks.py`:
- `.git/` inteiro entra em `CONTROL`;
- a comparação de arquivos de controle ignora maiúsculas;
- repositórios aninhados contam;
- `INSTALLED` pede confirmação para alterações em `.venv/`, `node_modules/` e `.tox/`.

Depois do impasse (opção 1, 2026-10-20):
- `preload_requests` lê os módulos de `node -r`;
- `shell.exec_environment` marca como `opaque` as variáveis de `EXEC_ENVIRONMENT`;
- `script_shell` procura `script-shell` no `.npmrc` e no `.yarnrc`;
- `make_options` aceita vários `-f` e marca `SHELL=`, `--eval`, `-E` e `-e` como ilegíveis;
- builtins de yarn e pnpm saem da leitura de scripts;
- `resolved` guarda em cache o `Path.resolve`, e `rewritten` só procura arquivos quando alguma parte do comando altera arquivos;
- `hooks.py` deixa de checar `.venv/` e `node_modules/` no texto do shell, que gerava falso positivo em `.venv/bin/ruff format .`.

Depois da terceira revisão (aprovada com ressalvas):
- `make_rules` separa as regras e `make_commands` segue só os alvos pedidos e seus pré-requisitos; `expand` trata variável não definida como vazia;
- `shell.harmless_setting` libera valores comuns das variáveis vigiadas;
- `source` de fora do projeto (com `~` e `$HOME` expandidos), scripts `activate` e `BUILD_WRAPPERS` commitados rodam sem leitura;
- `make_commands` respeita `.DEFAULT_GOAL` e lê todas as regras quando um pré-requisito é montado por função;
- `package_requests` e `make_requests` guardam o resultado por conteúdo.

## Decisions

- Modelo de ameaças (impasse `hook-indirect-code`): proteger contra erros do agente e caminhos óbvios, não contra um agente determinado; o resto é residual declarado no threat model.

- Make lê os alvos pedidos e seus pré-requisitos, e os dois lados de condicionais. Variável vinda do ambiente fica vazia, como no make (risco residual declarado).
- Ferramentas instaladas e programas fora do projeto não são lidos, para evitar falso positivo; em troca, alterar as pastas de ferramentas pede confirmação.
- Executores de teste rodam código do projeto sem leitura: é risco aceito, documentado no ADR-0034. Exigir confirmação a cada teste inviabilizaria a verificação do Stop.
- `.ps1` é analisado pelo leitor de shell. Variáveis do PowerShell viram `opaque`, o que pergunta a mais, nunca a menos.

## Risks and rollback

- Falsos positivos em scripts e Makefiles legítimos. Mitigados pelos testes de casos comuns (`test_common_commands_stay_quiet`, casos inofensivos) e por `opaqueCode: allow`.
- Tempo do hook: os limites são 1 MB por arquivo, 100 mil caracteres por script de shell, 200 linhas com aspas abertas e uma leitura por arquivo. Os testes medem o pior caso conhecido abaixo de 2 s.
- O hook roda a partir deste código: as edições foram aplicadas a partir de uma cópia que passou pela suíte inteira (`staged.py`) antes de substituir o código vivo.
- Rollback: `git revert` do commit da mudança. Nenhum estado persistido muda.
