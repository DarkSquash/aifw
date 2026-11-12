# Revisão independente — graphify-default

## Adversário

### Rodada 1

Escopo: `git diff main..HEAD` (claude.py, cli.py, common.py, conftest.py, test_graphify_default.py, docs, CHANGELOG, ADR-0045) contra o delta `specs/claude-graphify.delta.yaml`, `proposal.md`, `design.md`, `tasks.yaml` e as evidências. Rodei os 20 testes de `test_graphify_default.py` e fiz experimentos fora do repositório, com dublê do graphify.

Achados, todos corrigidos na rodada 2:

- A1 (média): com o graphify no PATH, um `.gitignore` somente leitura derrubava o `enable`. O `ignore_local_logs(root, ("graphify-out/",))` de `claude.py` não tinha proteção, e `cli.main(["claude","enable","--json"])` saía com código 1 e `[Errno 13] Permission denied`. Com `--no-graphify`, o mesmo projeto habilitava.
- A2 (baixa): o cenário SCN-GRAPHIFY-ENABLE-SKIPS dizia "com graphify-out/ existente, ... update não roda". O código e `test_existing_graphify_out_keeps_gitignore_but_still_updates` fazem o contrário.

### Rodada 2 (correção 1, `git diff HEAD~1..HEAD`)

Conferência dos achados:

- A1, corrigido. Repeti a prova (`scratchpad\adv\ro.py`, agora com o dublê num caminho absoluto fora do projeto) com o `.gitignore` somente leitura: código de saída 0, `status: enabled` e `"graphify": "could not update .gitignore: add `graphify-out/` yourself; graph built; no .git: git hooks skipped"`. O teste novo `test_gitignore_not_writable_is_a_note_not_a_crash` cobre o caso.
- A2, corrigido. O SCN-GRAPHIFY-ENABLE-SKIPS agora diz que o `.gitignore` não muda e que o update só é pulado com `graphify-out/graph.json`. Isso bate com o statement do REQ-GRAPHIFY-ENABLE, com o código e com o teste. O REQ-GRAPHIFY-NEVER-FAILS passou a citar o `.gitignore` não gravável, o que cobre o A1.
- R1, corrigido. Prova de ponta a ponta (`scratchpad\adv\r1.py`): sem `NoDefaultCurrentDirectoryInExePath`, num projeto git com um `graphify.cmd` plantado na raiz que gravaria um marcador. `shutil.which` devolve `.\graphify.CMD`, o `enable` sai com código 0 e a nota "graphify found inside the project: skipped". O marcador não foi criado e o `.gitignore` não mudou.

Procura de regressão na correção, sem achado:

- O guard roda antes de qualquer escrita, então um executável pulado não altera o `.gitignore`. O caso está no teste parametrizado (`inside`/`relative`).
- Um `graphify` numa `.venv` dentro do projeto passa a ser pulado. É efeito aceito, documentado no ADR-0045 (decisão 1) e em `docs/claude-code.md`.
- O mesmo vale quando a raiz do projeto contém a pasta do PATH (por exemplo, o home como projeto): o `enable` pula com nota, sem falhar.
- O dublê dos testes passou a usar um caminho absoluto (`os.path.abspath`). Sem isso, `"/fake/..."` não é absoluto no Windows e cairia no guard.
- `test_graphify_default.py`: 23 passed. Árvore de trabalho limpa depois dos testes.

Ressalvas mantidas por decisão: R2 (timeout no Windows com neto herdando os pipes, não verificado com o binário real), R3 (`core.hooksPath` global também pula o `hook install`) e R4 (segundo bloco de cabeçalho no `.gitignore`, só cosmético).

Não verificado: Linux e macOS; o graphify real (não rodei); worktree com o graphify real; o timeout com o binário real; `Path.resolve()` com caminhos de rede ou junctions; a suíte inteira (rodei só o arquivo de testes do graphify).

## QA

Escopo: `git diff main..HEAD` (2f47b2a, 4aa3c06) contra proposal.md, design.md, tasks.yaml, traceability.yaml, o delta, ADR-0045, CHANGELOG e as evidências. Scripts de prova somente leitura em `scratchpad\qa\` (fora do repositório). Não rodei o graphify real.

### Gates (rodados agora, no HEAD 4aa3c06)

- `python -m pytest -q -p no:cacheprovider tests_python`: 2829 passed em 126 s. `git status --short` antes e depois: só ` M independent-review.md`.
- `python -m ruff check .`: All checks passed. `ruff format --check .`: 316 files already formatted.
- `aifw spec validate graphify-default --json`: pass, sem findings. `aifw spec analyze graphify-default --json`: pass, sem findings; 3/3 requisitos ligados a tarefa, 5/5 cenários verificados, 4/4 tarefas concluídas, `weakTraces: []` (o analyze grava uma avaliação em modo sombra em `.aifw/assessments/`, que é ignorada pelo git).
- Referência gerada da CLI: comparei `docs/cli-reference.generated.md` com `render()` de `scripts/generate_cli_reference.py` (`scratchpad\qa\cliref.py`): idênticos. Não rodei o `--check` do script porque o hook nega ao revisor um script que também escreve.

### Critérios de aceitação (proposal.md) e cenários

| Critério / cenário | Evidência |
|---|---|
| Sem graphify no PATH: mesmo resultado + chave `graphify`, sem subprocesso do graphify, `.gitignore` sem `graphify-out/` (SCN-GRAPHIFY-ENABLE-ABSENT) | `test_absent_from_path_skips_everything`; smoke cenário 5 (JSON igual ao do `--no-graphify` fora da chave `graphify`) |
| Com graphify: `.gitignore`, `update .` com cwd na raiz, `hook install`, nessa ordem; segunda execução sem `update` (SCN-GRAPHIFY-ENABLE) | `test_happy_path_in_git_project`, `test_second_run_skips_update_and_reinstalls_hook`; smoke cenários 1 e 2 |
| Pulos: `core.hooksPath`, sem `.git`, `graphify-out/` existente, `--no-graphify`, executável dentro do projeto (SCN-GRAPHIFY-ENABLE-SKIPS) | `test_core_hooks_path_skips_hook_install`, `test_no_git_dir_skips_hook_install`, `test_existing_graphify_out_keeps_gitignore_but_still_updates`, `test_no_graphify_option_in_process_cli`, `test_no_graphify_parameter`, `test_executable_found_inside_the_project_is_not_run[inside,relative]`; smoke cenários 4 e 6 |
| Falha, timeout, `OSError` e `.gitignore` não gravável não derrubam o `enable`; linha diz o que rodar (SCN-GRAPHIFY-NEVER-FAILS) | `test_failures_never_break_enable[update-exit-1,update-timeout,hook-oserror]`, `test_gitignore_not_writable_is_a_note_not_a_crash`; prova do adversário com `.gitignore` somente leitura real |
| `graphify claude install` nunca roda | `test_never_runs_graphify_claude_install[happy,failing,no-git,second-run]` |
| `aifw claude check` igual com e sem graphify | `test_check_is_the_same_with_and_without_graphify` |
| Hook sem regra nova para o graphify (SCN-GRAPHIFY-HOOK-UNCHANGED) | `test_hook_lets_graphify_through_with_opaque_code_allow`, `test_hook_without_opaque_code_key_documents_current_behavior`; `hooks.py`, `shell.py` e `indirect.py` fora do diff |
| Teste manual com graphify 0.9.107 real | `evidence/smoke-real-graphify.md`, 8 cenários (veja a ressalva Q1) |
| Suíte, lint, spec validate/analyze, revisores | Gates acima; seção do adversário |

### Pontos pedidos

- `paths` de tasks.yaml: cobrem todos os arquivos de código e documentação do diff, inclusive os da correção (`claude.py`, `test_graphify_default.py`, `CHANGELOG.md`, `docs/claude-code.md`, ADR-0045 e `evidence/tests.txt`, este por `evidence/`). Os arquivos da própria pasta da mudança (delta, design, proposal, review) não entram, o que segue a convenção das mudanças arquivadas.
- ADR-0045 acompanha o código final: a decisão 1 fala do executável dentro do projeto, e a decisão 7 do `.gitignore` não gravável. O design.md não foi atualizado na correção (ressalva Q2).
- Prova real antes da correção: a pasta `smoke-112443` é anterior ao commit 4aa3c06 (11:44). A correção só acrescentou o guard e o `try/except` do `.gitignore`. Apliquei o guard ao executável real sem executá-lo (`scratchpad\qa\guard.py`): `shutil.which` devolve `C:\Users\DarkSquash\.local\bin\graphify.EXE`, e o guard não pula nem para a raiz deste repositório nem para a pasta dos clones do smoke (o `DARKSQ~1` vira nome longo no `resolve()`). Logo o caminho exercido pelo smoke continua alcançável com o código final. Fica sem prova real de ponta a ponta o código pós-correção. Com o home (`C:\Users\DarkSquash`) como raiz, o guard pula, como o ADR documenta.
- `import subprocess` no topo de `claude.py`: não pesa no início do `aifw`. `cli.py` importa `claude` só dentro dos ramos `claude *` e `doctor` (linhas 665 e 725). `import aifw.cli` não carrega `subprocess` nem `aifw.claude`, e `aifw.hooks` já carregava `subprocess` antes (`scratchpad\qa\imports.py`). Sem achado.
- Cabeçalho do `.gitignore`: o cabeçalho repetido não acontece só em projetos antigos. Num projeto novo (`scratchpad\qa\header.py`: `ignore_local_logs` do init e depois a chamada do graphify), o arquivo fica com duas linhas idênticas `# AIFW local files (not versioned)`, uma antes de `.aifw/runs/` e outra antes de `graphify-out/`. Isso vale para todo projeto novo com graphify, não só para os antigos. É cosmético e não afeta o que é ignorado (ressalva Q3). Nenhum teste fixa o texto do cabeçalho.

### Standards (CONSTITUTION.md, docs/engineering-principles.md, principle-catalogs/engineering-principles.yaml, smells)

Não há violação dura de padrão documentado. A ajuda `--no-graphify  no graphify` sai do helper `option()` de `cli.py` (linha 84), que gera o texto a partir da flag; segue a convenção do repositório. Pontos de juízo:

- Q4 (clean-code-tests): o `no_real_graphify` do `conftest.py` usa `monkeypatch.setattr(..., raising=False)`. Isso era necessário na fase vermelha, quando `GRAPHIFY` ainda não existia. Hoje, se a constante for renomeada, o fixture deixa de proteger sem avisar, e a suíte passaria a rodar o graphify real da máquina, o risco que o próprio design.md aponta. Com `raising=True`, o teste quebraria na hora.
- Q5 (clean-code-tests): `test_happy_path_in_git_project` verifica `"hook" in result["graphify"]`, o que também passa com "git hooks failed: ...". E `test_second_run_...` só verifica que a linha não está vazia. As chamadas, essas sim, são conferidas com exatidão.
- Q6 (clean-code-comments): o comentário de `test_hook_without_opaque_code_key_documents_current_behavior` cita "the design.md claim that it asks without the key", mas o design.md atual já traz a correção ("Correção do plano"). O comentário ficou velho.
- Q7 (Mysterious Name, juízo): `ignore_local_logs` agora também ignora `graphify-out/`, que não é log. Já o módulo ganhou um `run` genérico (`claude.run`). As docstrings explicam as duas, e o custo é baixo.

### Ressalvas

- Q1: não há prova com o graphify real depois da correção. O guard foi conferido contra o caminho real sem executá-lo, e o resto do caminho exercido não mudou.
- Q2: o design.md (Approach, passos 2, 4 e 5) não descreve o guard do executável dentro do projeto nem a nota do `.gitignore` não gravável, e não lista os 3 testes novos. Diz ainda que o helper "devolve verdadeiro só com código de saída 0", mas `run` devolve o `CompletedProcess` ou `None`, e diz que o resultado do smoke vai para `evidence/tests.txt`, quando está em `smoke-real-graphify.md`. O ADR-0045 e o delta estão corretos.
- Q3: o cabeçalho duplicado (R4) também aparece em todo projeto novo com graphify, não só nos antigos. Além disso, o SCN-GRAPHIFY-ENABLE-ABSENT diz "o .gitignore fica igual ao que o enable já gravava", mas o texto do cabeçalho mudou para todos. A mudança está declarada no CHANGELOG e no design.md.
- Q4 a Q7: ressalvas de padrão, acima.
- R2, R3 e R4: mantidas por decisão.

Não verificado: o graphify real (não rodei); Linux e macOS; o `--check` do gerador da referência rodado diretamente (comparei por `render()`); `Path.resolve()` com caminho de rede ou junction.

Resultado: aprovado com ressalvas
