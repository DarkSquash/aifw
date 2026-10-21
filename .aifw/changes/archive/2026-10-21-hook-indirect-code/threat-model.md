# Threat model: código indireto no hook PreToolUse

## Modelo decidido (impasse hook-indirect-code, 2026-10-20)

Duas revisões independentes mostraram que ler e entender código indireto não tem fim: cada ferramenta tem variáveis, configurações e opções que executam outro programa. A pessoa decidiu (`.aifw/impasses/hook-indirect-code.yaml`, commit assinado `cb82caf`):

- O hook protege contra **erros do agente e caminhos óbvios**: um agente que, sem intenção de burlar, publica, instala, apaga ou envia dados por um script, `npm run`, `make` ou configuração do git.
- O hook **não é um sandbox** contra um agente determinado a contorná-lo. A contenção de verdade é o sandbox do sistema operacional do Claude Code e as permissões da própria ferramenta.
- Vale a regra "quanto menos aprovações, melhor": os casos baratos e comuns são fechados; o resto vira risco residual declarado, sem pedir confirmação para todo código indireto.

A revisão independente julga a mudança contra este modelo: um bypass só reprova quando é um caminho que um agente seguiria sem intenção de burlar e não está na lista de residuais abaixo.

## Escopo e assets

- A decisão do hook sobre cada comando: publicar, instalar, apagar, enviar dados, commitar, aprovar.
- O repositório remoto, os segredos locais e as aprovações humanas assinadas.
- A disponibilidade da sessão: um hook que falha bloqueia todas as ferramentas (`onFailure: block`), e uma exceção na avaliação vira `ask`.

## Diagrama e trust boundaries

Agente (não confiável quanto a intenção) → texto do comando → `aifw-hook` (fronteira) → shell da máquina.

Arquivos que o próprio agente pode escrever são entrada não confiável, lida pelo hook antes da execução: scripts, `package.json`, `Makefile`, `.git/`, `.venv/` e `node_modules/`.

## Actors

- O agente, inclusive sob prompt injection vinda de páginas, documentos ou saídas de ferramentas.
- A pessoa que aprova.
- Um colaborador que commita scripts maliciosos no repositório.

## STRIDE

| ID | Categoria | Cenário | Impacto | Controle | Evidência | Risco residual | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | Elevation of privilege | `git push` dentro de script, `source`, `npm run`, `bun X`, `make` ou `python -m` | push, instalação ou envio sem aprovação | `indirect.py` lê o código (ADR-0034) | `test_indirect_code_that_pushes_asks`, `test_more_forms_that_run_scripts_are_read` | imports de scripts; `cd` antes do script | human:DarkSquash |
| T-002 | Tampering | Makefile esconde o comando em variável, `include`, `;`, `$(shell)` ou função | comando não lido | expansão de variáveis; construções não seguidas são `opaque` | `test_makefile_forms_that_hide_commands_ask`, `test_make_options_glued_or_overriding_are_followed` | variáveis exportadas antes do `make`, que o reader expande como vazias | human:DarkSquash |
| T-003 | Tampering | script escrito no mesmo comando que o executa, com ou sem extensão | o hook leu o conteúdo antigo | inexistente ou alterado no comando é `opaque` (`rewritten`) | `test_code_written_by_the_same_command_is_opaque`, `test_code_without_a_readable_file_is_opaque` | gerador que grava o script sem citar o nome | human:DarkSquash |
| T-004 | Tampering | `.git/hooks`, `.git/config` (inclusive `.GIT`, glob, submódulo) ou config do git que executa programa | código não lido em commit, diff ou fetch | `.git/` é controle sem diferenciar maiúsculas; `EXEC_CONFIG` ampliado, `--config-env`, opções com valor | `test_git_folder_and_installed_tools_ask_in_any_case`, `test_more_git_settings_that_run_programs_are_opaque` | `GIT_SSH_COMMAND` e afins exportados antes; `.git` de worktree fora do projeto | human:DarkSquash |
| T-005 | Elevation of privilege | executor de teste local (`./pytest`, `./gradlew`, `pytest.py` sombreando o pacote) | código não lido em cada verificação | só wrapper commitado e inalterado passa sem leitura; `python -m` lê o módulo local | `test_test_runners_written_in_the_project_are_read` | código de teste e `conftest.py` rodados pelo executor (aceito, ADR-0034) | human:DarkSquash |
| T-006 | Tampering | agente planta código em `.venv/` ou `node_modules/`, que o hook não lê | ferramenta adulterada | editá-las com as ferramentas de edição pede confirmação | `test_git_folder_and_installed_tools_ask_in_any_case` | escrita por comando de shell; instalação aprovada que traz pacote malicioso (cadeia de suprimentos) | human:DarkSquash |
| T-007 | Denial of service | script recursivo, enorme ou com aspas abertas, ou Makefile com camadas de variáveis, trava o hook | sessão lenta ou bloqueada | leitura única por arquivo e processo (cache por conteúdo), 1 MB, 100 mil caracteres por script, por expansão, pelo total das receitas e por Makefile, 200 linhas abertas, variáveis do make expandidas uma vez | `test_scripts_calling_scripts_many_times_stay_fast`, `test_layers_of_make_variables_stay_fast`, `test_cyclic_make_variables_stay_fast_and_ask`, `test_large_expanded_recipes_are_opaque_and_fast`, `test_a_quote_left_open_is_opaque_and_fast` | Makefiles montados para consumir memória ou tempo (substituições gigantes, grafos de 300 variáveis); como `onFailure: block`, o hook então pede confirmação ou bloqueia, nunca libera | human:DarkSquash |
| T-008 | Elevation of privilege | erro de leitura (BOM, JSON inválido, permissão) libera a ação | bypass | erro vira `opaque`; BOM é aceito como o npm faz | `test_a_package_json_the_hook_cannot_parse_is_opaque` | nenhum | human:DarkSquash |
| T-009 | Spoofing | wrapper ou opção desloca o programa (`timeout 10 bash x`, `env -S`, `uv run --with x f.py`) | programa errado analisado | valores dos wrappers pulados; `env -S` é `opaque` | `test_more_forms_that_run_scripts_are_read`, `test_env_split_string_is_opaque` | wrappers não listados (`stdbuf`, `ionice`) | human:DarkSquash |
| T-012 | Elevation of privilege | código carregado por opção ou variável: `node -r ./x.js`, `NODE_OPTIONS`, `BASH_ENV`, `GIT_SSH_COMMAND`, `GIT_CONFIG_*`, `npm_config_script_shell`, `--script-shell`, `.npmrc` com `script-shell`, `make SHELL=`, `--eval`, vários `-f` | código não lido | preloads de caminho lidos; variáveis da lista `EXEC_ENVIRONMENT` na linha ou em `export` são `opaque`; opções do make e do npm tratadas | `test_second_review_forms_ask`, `test_npmrc_script_shell_is_opaque` | variáveis fora da lista; `~/.npmrc` do usuário; pacotes pré-carregados por nome | human:DarkSquash |
| T-013 | Spoofing | builtin com o mesmo nome de um script (`yarn publish`) lido como script | publicação sem confirmação | builtins de yarn e pnpm seguem a regra própria | `test_publish_builtins_keep_their_rule_with_a_same_named_script` | builtins não listados | human:DarkSquash |
| T-010 | Repudiation | confirmação pedida sem registro | sem trilha | o hook registra cada `ask` em `.aifw/runs/` | `pre_tool_use` (já existente) | nenhum | human:DarkSquash |
| T-011 | Information disclosure | o hook lê um arquivo com segredo ao analisar um script | segredo exposto | o conteúdo só é analisado localmente, nunca enviado nem registrado | `record()` grava o comando mascarado | nenhum novo | human:DarkSquash |

## Abuse cases

- **Script que chama script:** coberto. Um arquivo já em leitura conta uma vez só.
- **`opaqueCode: allow`:** decisão do projeto, que libera todo código ilegível (ADR-0025).
- **Commit assinado com o código adulterado:** um wrapper de teste "commitado" pelo próprio agente com `commits: allow` passa a rodar sem leitura. O commit fica no histórico que a pessoa revisa, e qualquer arquivo de controle alterado faz o commit pedir confirmação.

## Riscos residuais aceitos (fora do modelo)

Caminhos que exigem intenção de contornar o hook, ou cobri-los custaria aprovações demais:

- código de teste rodado pelos executores (`conftest.py`, testes, plugins);
- imports de scripts e scripts rodados depois de um `cd`;
- variáveis de ambiente fora de `EXEC_ENVIRONMENT`, exportadas em comandos anteriores, ou configurações globais do usuário (`~/.npmrc`, `~/.gitconfig`);
- programas sem extensão gravados fora da pasta do projeto (`../t`) e executados pelo caminho;
- interpretadores não reconhecidos (`php`, `tsx`, `ts-node`) e wrappers não listados (`stdbuf`, `wsl`);
- código Python que importa funções de execução por nome indireto (`from os import system`);
- escrita em `.venv/` ou `node_modules/` por comando de shell (só as ferramentas de edição perguntam);
- workspaces e builtins de gerenciadores de pacotes não listados.

## Decisão e aprovação

- Os riscos residuais acima e da tabela são aceitos nesta mudança e registrados no ADR-0034 para revisão futura.
- Aprovação humana via `aifw spec approve hook-indirect-code`.
