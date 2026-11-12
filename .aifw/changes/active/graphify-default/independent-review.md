# Revisão independente — graphify-default

## Adversário

Escopo: `git diff main..HEAD` (claude.py, cli.py, common.py, conftest.py, test_graphify_default.py, docs, CHANGELOG, ADR-0045) contra o delta `specs/claude-graphify.delta.yaml`, `proposal.md`, `design.md`, `tasks.yaml` e as evidências. Rodei `tests_python/test_graphify_default.py` (20 passed) e dois experimentos fora do repositório (scratchpad), com dublê do graphify. Não rodei o graphify real.

### A1 — `.gitignore` sem permissão de escrita derruba o `enable` só quando o graphify está no PATH (severidade: média)

- Onde: `python/aifw/claude.py:123` (`ignore_local_logs(root, ("graphify-out/",))` fora de qualquer `try`), dentro de `enable_graphify`, cuja docstring (linha 117) diz "never raises".
- Spec e plano: delta linha 6 (purpose: "sem nunca derrubar o aifw claude enable"); delta linha 35 ("Em todos o enable termina com sucesso"); `design.md:26` ("Nenhuma exceção sai de `enable_graphify`"); ADR-0045 decisão 7 ("Nenhuma exceção sai do `enable`").
- Cenário: projeto já inicializado (`aifw init` gravou `.aifw/runs/` e `.aifw/assessments/` no `.gitignore`), `.gitignore` somente leitura, graphify no PATH, sem `graphify-out/`.
- Evidência (script em `scratchpad\adv\ro.py`, dublê de `subprocess.run`/`shutil.which`):
  - `enable_project(root, graphify=False)` → `enabled` (a primeira chamada de `ignore_local_logs` não escreve, porque nada falta);
  - `cli.main(["claude", "enable", "--json"])` → `[Errno 13] Permission denied: ...\.gitignore`, código de saída 1, nenhum JSON e nenhuma chamada ao graphify.
- Resultado: o mesmo projeto que habilita com `--no-graphify`, ou sem o graphify, falha quando o graphify está presente. Os hooks, a skill e os subagentes já tinham sido gravados, mas o resultado não sai. É regressão para quem tem o graphify instalado.

### A2 — O cenário SCN-GRAPHIFY-ENABLE-SKIPS contradiz o código e o teste que o verifica (severidade: baixa)

- Onde: delta linha 35 ("com graphify-out/ existente, o .gitignore não muda e update não roda").
- Código: `claude.py` roda o `update` sempre que falta `graphify-out/graph.json`, exista a pasta ou não. O teste `tests_python/test_graphify_default.py:121` (`test_existing_graphify_out_keeps_gitignore_but_still_updates`) garante o contrário do cenário: com `graphify-out/` vazio, `["update", "."]` está nas chamadas. Mesmo assim, `traceability.yaml` liga SCN-GRAPHIFY-ENABLE-SKIPS a TEST-GRAPHIFY-DEFAULT como "verifiedBy".
- O código segue o statement do REQ-GRAPHIFY-ENABLE ("rodar graphify update . uma vez quando não há graphify-out/graph.json"). O erro está no cenário: a spec se contradiz e a rastreabilidade declara verificado um cenário que o teste nega. Corrige-se trocando o texto do cenário por "com graphify-out/graph.json existente, update não roda; com graphify-out/ existente, o .gitignore não muda".

### Ressalvas (não reprovam)

- R1 — Busca no diretório corrente no Windows. Com o Python 3.14 desta máquina, `shutil.which("graphify")` procura primeiro no diretório corrente quando `NoDefaultCurrentDirectoryInExePath` não está definido (prova em `scratchpad\adv\cwd.py`: devolve `.\graphify-cwd-probe.CMD` dentro da pasta e `None` fora dela). Como o CLI usa `Path.cwd()` como raiz (`cli.py:757`), um `graphify.cmd`, `.bat` ou `.exe` na raiz do projeto é executado por `aifw claude enable` rodado num terminal comum, mesmo sem graphify no PATH. Isso contraria o "resolvido pelo PATH" do ADR-0045 e o "Com o graphify no PATH" do REQ-GRAPHIFY-ENABLE. Dentro do Claude Code a variável vem definida (`=1`), e o caminho de `/aifw` não é afetado. Exige um arquivo plantado no repositório, por isso fica como ressalva. Correção barata: ignorar resultado relativo ou passar `path=os.environ["PATH"]`.
- R2 — Timeout no Windows. `subprocess.run(..., capture_output=True, timeout=...)` mata só o processo direto e depois chama `communicate()`. Se um neto herdar os pipes, o `enable` espera além dos 300 s. Não verifiquei se o `graphify update` real deixa neto com handle herdado; o launcher `.exe` costuma usar job object.
- R3 — Um `core.hooksPath` global do git, fora do projeto, também faz o `enable` pular `hook install`. É conservador e a linha explica, mas a doc fala só do projeto.
- R4 — Num `.gitignore` antigo, a entrada do graphify ganha um segundo bloco de cabeçalho (`# AIFW local files (not versioned)`) abaixo do antigo. É só cosmético: não duplica entradas, e o smoke confirmou que os dois blocos não se repetem nas execuções seguintes.
- Conferido sem achado:
  - a suíte não roda o graphify real: só `test_cli.py` usa subprocesso, e para `claude enable` só com `--help`;
  - `hooks.py` não está no diff;
  - `--no-graphify` chega a `enable_project`;
  - sem graphify no PATH, nenhum subprocesso roda;
  - `git` ausente do PATH vira `None` e não vira exceção;
  - saída não UTF-8 é tratada como bytes, sem decodificação;
  - `.git` como arquivo segue para `hook install`, e uma falha ali é capturada.

Não verificado: Linux e macOS; o graphify real (não rodei); `.git` de worktree com o graphify real; o comportamento do timeout com o binário real.

Resultado: reprovado
