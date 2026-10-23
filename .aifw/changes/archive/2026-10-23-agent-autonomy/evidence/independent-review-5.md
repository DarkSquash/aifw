# Revisão independente 5 — agent-autonomy (L3)

## Escopo

- Diff do working tree contra `HEAD` (branch `feat/agent-autonomy`), mudança `agent-autonomy`: `proposal.md`, `design.md`, `threat-model.md` (T-009), `migration.md`, `specs/*.delta.yaml`, ADR-0037 ("Risco aceito") e as revisões 1 a 4 em `evidence/`.
- Foco: correções da revisão 4. `diff_floor` e `assert_approval` (`python/aifw/specs.py:425-457`); `COPIES`, `PATCHES`, `TOP_TARGET`, `EXTRACTS` (`python/aifw/hooks.py:70-74, 136-145`); `KEY_HOME`, `HOME_VARIABLE`, `HOME_SET` (`python/aifw/shell.py:29-38, 803-815`); fixture de `tests_python/test_spec_integrity.py`.
- Verificação: `python -m pytest -q -p no:cacheprovider` deu 2502 passed. As sondas são testes pytest em projetos temporários com git: `scratchpad/review5/test_r5.py`, `test_r5b.py`, `test_r5c.py`, com saídas em `out.txt`, `merge.txt`, `merge2.txt`, `copy.txt`, `misc.txt`, `push.txt`, `floor.txt` e `floor2.txt`. Nenhum arquivo do repositório foi editado além deste.
- Fora da reprovação, por ser risco aceito (ADR-0037, T-009): código opaco, variáveis, `$(...)`, nomes partidos por aspas e mensagem enviada por ferramenta do agente.

## Situação dos achados da revisão 4

| # | Situação |
| --- | --- |
| 1 (alta) cópia de árvore por cima da raiz rebaixa para L2 | Parcial. L2 agora exige aprovação selada, e há o piso do diff. `cp -r forged/. .`, `cp -rT forged .`, `rsync ... ../aifw/` e `cd forged && cp -r . ../` pedem. Seguem abertos: o destino com o nome da raiz (`../aifw`, caminho absoluto com `/` no fim, `Copy-Item ..\aifw\`), o rebaixamento para L1 e o piso, que some quando o trabalho é commitado (achados novos 1, 2 e 3). |
| 2 (média) `HOME`/`USERPROFILE` | Corrigido: `USERPROFILE=... aifw`, `python -m aifw`, `env USERPROFILE=... aifw`, `HOME=... uv run aifw` e `export HOME=` são negados. `HOME=/tmp/h npm test` passa. |
| 3 (média) a palavra `patch` | Corrigido: `PATCHES` só casa no início de um segmento. `npm version patch` passa. `curl -X PATCH` e `gh api --method PATCH` não casam mais com `PATCHES`. |
| 4 (média) menção a `approval.key`/`AIFW_HOME=` | Parcial. `AIFW_HOME=` em argumentos e a ferramenta Grep com `pattern: approval.key` passam. `grep -rn approval.key python/aifw`, `git log -S approval.key` e `git commit -m "doc: explica approval.key"` continuam negados, agora por `SECRET_FILE` (`shell.py:803`, qualquer argumento terminado em `.key`). Ver novo achado 6. A correção de `KEY_HOME` abriu uma regressão (novo achado 3). |
| 5 (baixa) cópia para `evidence/` pede | Aberto, sem mudança. Baixa. |
| 6 (baixa) `claude --model haiku` negado | Aberto, sem mudança. Baixa. |
| 7 (baixa) mensagem enviada por ferramenta do agente | Declarado no ADR-0037 como não verificado. Risco aceito. |

## Achados novos

### 1. Alta — commit num worktree mais `git merge` rebaixa a mudança L3 para L1 sem aprovação

- Local: `python/aifw/hooks.py:105-145` (`control_target`: a ferramenta Write só protege caminhos que começam por `.aifw/changes/`); `hooks.py:300-307` (`dirty_control(root)` olha só a árvore da raiz, não a do `git -C`); `merge`, `cherry-pick`, `rebase`, `pull` e `switch` não são vistos como entrada de arquivo de controle; `specs.py:444` (L1 dispensa aprovação).
- Cenário, reproduzido em `test_r5b.py::test_inner_worktree_merge` (todos os passos com hook `None`, sem código opaco, variável nem aspas):
  1. A mudança `big` (L3) já está commitada, como no fluxo normal antes do archive.
  2. `git worktree add .wt -b forged`
  3. Ferramenta Write ou Edit em `.wt/.aifw/changes/active/big/change.yaml`, com `level: L1`.
  4. `git -C .wt commit -am f` (ou `cd .wt && git commit -am f`).
  5. `git merge forged` (ou `git cherry-pick forged`, `git rebase forged`, `git pull . forged`).
  6. Resultado: `level=L1 floor=L1`, e `assert_approval` passa sem aprovação nem selo. `ready` e `archive` seguem, e `validate --change` não cobra mais `human-approval`, porque L1 não tem esse gate. Sobre o worktree, a variante `../w` também passa, mas a escrita fora do projeto depende da permissão do próprio Claude Code.
- Isso não é a classe aceita no T-009: são comandos git diretos e comuns.
- Correção: gravar o nível da criação num lugar de controle (o log do hook ou `.aifw/runs/`) e recusar `ready`/`archive` com nível menor. Outra saída é exigir aprovação sempre que já existiu `approval-request.yaml` ou o nível guardado foi L2/L3. No hook, tratar Write/Edit em qualquer `*/.aifw/changes/*/change.yaml` como controle e fazer `dirty_control` respeitar `-C`/`cd`.

### 2. Alta — copiar a árvore para a raiz pelo nome dela não pede confirmação

- Local: `python/aifw/hooks.py:73` e `:139`. `TOP_TARGET` só reconhece `.` e `..`. A comparação com o caminho absoluto exige a raiz seguida de espaço, então `/` no fim já escapa, e `../<nome>` não é resolvido.
- Cenário, em `copy.txt` e `misc.txt` (hook `None`):
  - `cp -r forged/. ../aifw`
  - `cp -r forged/. ../aifw/`
  - `cp -r forged/. C:/.../aifw/`
  - `Copy-Item -Recurse forged\* ..\aifw\`
- Com `forged/.aifw/changes/active/big/change.yaml` em `level: L1`, gravado pela ferramenta Write (hook `None`), a mudança cai para L1. Depois da cópia, o piso fica em L1 sempre que os arquivos de código já estão commitados (achado 4) ou não tocam caminhos que levam a L2/L3. É o achado 1 da revisão 4 com outra grafia do destino.
- Correção: resolver cada argumento de `cp`/`mv`/`rsync`/`Copy-Item`/`robocopy` contra o cwd e pedir quando o destino for a raiz ou um ancestral de `.aifw/`. Melhor ainda: verificar se a origem contém `.aifw/`. A correção do achado 1 (nível guardado) também fecha este caminho.

### 3. Alta — regressão: a chave volta a ser lida por glob ou por caminho relativo

- Local: `python/aifw/shell.py:29-33` e `:803`. Ao estreitar `KEY_HOME` (achado 4 da revisão 4), saiu o casamento de `approval\.ke` em qualquer lugar. Agora `KEY_HOME` exige um prefixo de pasta pessoal colado em `/.aifw`, e os globs de leitura não são expandidos (`pattern_files` só roda para mutação, `hooks.py:132`).
- Cenário, em `out.txt` e `misc.txt` (hook `None`, leitura liberada):
  - `cd ~ && cat .aifw/approval.ke?`
  - `cd ~/ && xxd -p .aifw/approval.ke?` (sonda da revisão 4, que antes era negada)
  - `xxd -p ../../../.aifw/*` (da raiz do projeto até a pasta pessoal)
  - `cat ~/../DarkSquash/.aifw/*`
- `cd ~ && xxd -p .aifw/*` só pede confirmação. Com a chave, o agente sela a própria aprovação L3 e escreve o `change.yaml` pelos achados 1 ou 2. O T-009 declara fechada a leitura por menção à pasta da chave e por globs, e o caminho relativo direto não está na lista aceita.
- Correção: para leitura, expandir os globs (`pattern_files`, também a partir do destino de `cd`) e negar quando a expansão alcançar `approval.key`. Resolver os argumentos relativos e negar quando caírem em `Path.home()/.aifw`. Repor `approval\.ke` para argumentos que sejam caminho ou glob, sem valer para o texto de `-m` nem para o padrão de busca.

### 4. Média — o piso do diff é medido contra `HEAD`: some com um commit e trava mudanças L0

- Local: `python/aifw/specs.py:425-432` com `routing.changed_files` (`routing.py:122-138`, `git diff HEAD` mais arquivos não rastreados).
- Cenário A, em `floor2.txt`: `CONSTITUTION.md` alterado dá piso L3. Depois de `git commit`, o piso cai para L0. No fluxo normal o trabalho é commitado antes do archive, então o piso quase nunca protege. Isso é o que torna os achados 1 e 2 efetivos em mudanças com arquivos de núcleo.
- Cenário B, em `floor.txt`, uma regressão de rotina: uma mudança L0 só de documentação é recusada ("Change level L0 is below L1"). Os próprios `change.yaml`, `tasks.yaml` e `traceability.yaml` da mudança, ainda não rastreados, contam como `behaviorChange`. Pelo mesmo motivo, qualquer trabalho não relacionado e não commitado no working tree sobe o piso de outra mudança.
- Correção: medir contra o merge-base com a branch padrão (ou o commit em que a mudança nasceu), ignorar `.aifw/changes/` no cálculo e restringir o cálculo aos arquivos da mudança quando houver como saber quais são.

### 5. Média — `TOP_TARGET` e `EXTRACTS` pedem confirmação em cópias e extrações de rotina

- Local: `python/aifw/hooks.py:73-74` e `:139-145`.
- Cenário (pedem com o motivo enganoso "changes the AIFW control file .aifw/"): `cp ../shared/config.json .`, `mv build/out.js .` e `unzip pkg.zip -d vendor`. Este último pede porque só `-C`/`--directory` são aceitos como destino, e `-d` do `unzip` e `-o` do `7z` não.
- Correção: pedir só quando a origem for um diretório, ou quando contiver `.aifw/`. Aceitar `-d` e `-o<dir>` como destino de extração.

### 6. Média — citar `approval.key` num argumento nega `grep`, `git log -S` e mensagens de commit

- Local: `python/aifw/shell.py:803` (`SECRET_FILE` em qualquer argumento terminado em `.key`).
- Cenário (negados, sem opção de confirmar): `grep -rn approval.key python/aifw`, `git log -S approval.key --oneline` e `git commit -m "doc: explica approval.key"`. Neste repositório, que documenta a chave, isso trava buscas e commits comuns. É o resto do achado 4 da revisão 4.
- Correção: não aplicar `SECRET_FILE` ao padrão de `grep`/`git log -S`/`-G` nem ao valor de `-m`. Ou rebaixar para `ask` quando o argumento não for um arquivo existente.

### 7. Baixa — achados 5 e 6 da revisão 4 seguem abertos

- `cp out.txt .aifw/changes/active/big/evidence/tests.txt` pede (`hooks.py:144`).
- `claude --model haiku -p "x"` é negado (`shell.py`, `forges_prompt`).

## Sem achados

- Push: `git push` e `git push origin feat/x` rodam numa branch de trabalho. Pedem confirmação: `origin main`, `HEAD:main`, `feat/x:main`, `feat/x:heads/main`, `HEAD~0:main`, `refs/heads/...:refs/heads/main`, `-- main`, `--set-upstream origin feat/x:main`, `--all`, `-f`, `:main` e, já na branch padrão, `git push`/`origin HEAD`. `npm publish`, `gh release create`, `twine upload` e `gh pr merge` pedem.
- Selo, `approve`, `HOME`/`USERPROFILE` com `aifw`, `cat ~/.aifw/approval.key`, `cp -r ~/.aifw ./k` e `cat /c/Users/.../.aifw/approval.key` estão corretos.
- O fixture de `test_spec_integrity.py` aprova a mudança L2 pelo caminho real (`approve_change`). Sem git, o piso cai para L0 por exceção, o que é aceitável fora de um repositório.

Resultado: reprovado
