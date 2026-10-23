# Revisão independente 2 — agent-autonomy (L3)

## Escopo

- `git diff HEAD` do working tree e os arquivos não rastreados (`.aifw/changes/active/agent-autonomy/`, `docs/decisions/ADR-0037-agent-autonomy.md`, `tests_python/test_agent_autonomy.py`).
- Critérios: `proposal.md`, `design.md`, `threat-model.md`, `migration.md`, `specs/*.delta.yaml`, ADR-0037 e o modelo de ameaças aceito (ADR-0034: o hook protege contra erros e caminhos óbvios; código opaco liberado e nomes montados em variáveis são risco residual).
- Base: a revisão anterior (`evidence/independent-review-1.md`).
- Verificação: suíte inteira (`python -m pytest -q -p no:cacheprovider`: 2461 passed). Sondas do hook com `aifw.hooks.handle` num projeto temporário com `remoteMutation: branches`, `externalServices.writes: allowlist`, `opaqueCode: allow`, `github` na allowlist, branch `feat/x` e `refs/remotes/origin/HEAD -> main`. A falsificação do achado 1 foi reproduzida de ponta a ponta: o comando rodou de verdade e depois `assert_approval` passou. Tempo do glob medido no próprio repositório (Python 3.14.8).
- A skill `code-review` não foi usada: ela dispara subagentes. A revisão foi feita direto, com leitura e sondas.

## Situação dos achados da revisão anterior

| # | Situação | Observação |
| --- | --- | --- |
| 1 (alta) autoaprovação via `aifw-hook` | Corrigido nos caminhos diretos | `aifw-hook`, `aifw-hook.exe`, `.venv/Scripts/aifw-hook.exe`, `python/py -m aifw.hooks`, `uv run`, `env`, `timeout`, `nohup`, `sh -c`, `bash -c`, `cmd /c`, `claude -p` e `python -c` com `aifw.hooks` são negados. Além disso, o pedido só vale na sessão que o fez. Sobra: o hook chamado por um programa intermediário (novo achado 4). |
| 2 (alta) `change.yaml`/`approval.md` graváveis por shell | Corrigido em parte | Padrões com `?`, `[]`, `{a,b}` e `*` agora pedem confirmação. Mas cópia de diretório, `tar -C`, `git apply`/`patch` e nomes partidos por aspas passam. Além disso, `assert_approval` ainda aceita qualquer arquivo como registro (novos achados 1 e 2). |
| 3 (alta) push para a branch padrão | Corrigido | `heads/main`, `refs/heads/*`, `--branches`, `-c ...`, `remote.*.push`, `push.default=matching`, upstream na padrão, remoto por URL e remoto sem `HEAD` pedem confirmação. `@:main`, `--set-upstream origin main`, `--atomic`, `--repo origin main` e vários destinos também. `GIT_CONFIG_*`, `git config alias.*` e `git <alias>` são classificados como opacos, o que é risco declarado. |
| 4 (alta) `gh api`/`curl` na API do GitHub | Corrigido | Escritas fora de PR, issue ou comentário pedem confirmação, inclusive `graphql`. Sobram truques de baixa severidade (novo achado 6). |
| 5 (média) `-fu` | Corrigido | Grupos de flags curtas com `f` ou `d` contam como force/delete. |
| 6 (média) push de tag | Corrigido | `v1.0`, `refs/tags/...`, `tag v1.0` e `x:refs/tags/v2` pedem confirmação. |
| 7 (média) pedido não amarrado à sessão | Corrigido | `requested_here` só aceita o pedido que está no log da sessão (`.aifw/runs/<sessão>.jsonl`, que é arquivo de controle). Não há expiração, mas a mensagem seguinte da sessão consome o pedido. |
| 8 (baixa) respostas condicionais | Mantido de propósito | Decisão da pessoa. |
| 9 (baixa) falha parcial silenciosa | Corrigido | O registro é apagado se `approve_change` falhar, e o aviso vai no `additionalContext`. Resíduo pequeno: uma exceção que não seja `AifwError` (YAML ou OSError) ainda é engolida por `handle` e deixa `approval.md` gravado. |
| 10 (baixa) `.env.example` negado | Corrigido | `.example`, `.sample`, `.template` e `.dist` ficam fora do padrão. |
| 11 (baixa) `echo $VAR` | Mantido de propósito | Já existia antes da mudança. |
| 12 (baixa) `gh release upload/edit` | Corrigido | Agora são `publish`. Isso criou uma regressão pequena (novo achado 7). |

## Achados novos

### 1. Alta — aprovação forjada copiando um diretório por cima da pasta da mudança

- Local: `python/aifw/hooks.py:119-129` (`control_target`, ramo de shell: procura o nome do arquivo de controle no texto do comando ou num padrão), `python/aifw/specs.py:396-404` (`assert_approval` só exige `human:`, data e um arquivo existente qualquer em `record`).
- Cenário (reproduzido de ponta a ponta):
  1. O agente grava `forged/change.yaml` com a ferramenta Write. Não há objeção, porque fica fora de `.aifw/changes/`. O arquivo é cópia do `change.yaml` real mais `approval: {approvedBy: human:x, approvedAt: ..., record: aifw.yaml}`.
  2. O agente roda `cp -r forged/. .aifw/changes/active/big/`. O hook devolve `None` e o comando substitui `change.yaml`.
  3. `assert_approval` passa. `record` aponta para `aifw.yaml`, então nem precisa existir um `approval.md`.
- Outros caminhos com o mesmo resultado, todos com hook `None`: `cp -r forged/ .aifw/changes/active/big/../big`, `tar -xf f.tar -C .aifw/changes/active/big`, `git apply p.diff`, `patch -p1 < p.diff` (com o patch gravado antes pela ferramenta Write). `rsync` pede confirmação só porque é visto como serviço externo.
- São comandos comuns, sem código opaco e sem variável, e contornam T-002 e o aceite "o agente não escreve `approval.md`". Sem a exigência de commit assinado, não há outra barreira: a aprovação só é conferida no working tree (`specs.py:513,528`). O commit desses arquivos ainda pede confirmação, mas o gate e o archive não exigem commit.
- Correção sugerida, duas partes:
  - (a) Em `assert_approval`, exigir `record == <pasta da mudança>/approval.md`. Amarrar a aprovação a algo que só o hook grava: por exemplo, o hook anota `changeId`, `approvedAt` e o sha256 de `approval.md` no log da sessão (`.aifw/runs/`, controle) ou num `.aifw/approvals.jsonl` novo (controle), e `assert_approval` confere essa entrada.
  - (b) No shell, para cada palavra de um comando mutante que resolva para um diretório existente do projeto, pedir confirmação se esse diretório contiver um caminho de controle (`change.yaml`, `approval.md`, `.aifw/runs/` etc.). Tratar `git apply`, `git am` e `patch` como pedido sempre, ou ler o patch e procurar caminhos de controle nele.

### 2. Média — nome de controle partido por aspas, barra invertida ou intervalo de chaves não é visto

- Local: `python/aifw/hooks.py:119-129` (substring no texto cru), `python/aifw/hooks.py:67-74` (`BRACES` só expande listas com vírgula, até 64 palavras).
- Cenário (hook `None`):
  - `sed -i s/a/b/ .aifw/changes/active/big/chang''e.yaml` e `.../chang"e".yaml`: o shell junta as partes em `change.yaml`.
  - `echo x > .aifw/changes/active/big/approval.m\d`: o shell lê `\d` como `d`.
  - `.../chang{e..e}.yaml`: intervalo de chaves, sem vírgula, não é expandido pelo hook.
  - `{a,b}{a,b}{a,b}{a,b}{a,b}{a,b}.../chang{e,x}.yaml`: o limite de 64 palavras para antes da última chave.
- É um truque deliberado, parecido com montar o nome numa variável (risco declarado), mas não usa variável nem código opaco. Com o achado 1, o efeito é o mesmo: aprovação forjada.
- Correção sugerida: comparar os nomes de controle também com as palavras já analisadas pelo parser de `shell.py`, sem aspas nem escapes. Expandir `{x..y}`. Quando o limite de expansão for atingido, pedir confirmação em vez de seguir com a palavra literal.

### 3. Média — `forges_prompt` nega comandos comuns de leitura e de commit

- Local: `python/aifw/shell.py:644-649`, no trecho `("UserPromptSubmit" in text and "aifw" in text)` e na regra `claude` com qualquer argumento.
- Cenário (todos `deny`, sem opção de confirmar):
  - `grep -rn UserPromptSubmit python/aifw`
  - `git log -S UserPromptSubmit -- python/aifw`
  - `git commit -m "aifw: UserPromptSubmit grava aprovação"`
  - `claude mcp list` e `claude doctor`
- Neste repositório isso atrapalha o trabalho de rotina, e nesta revisão a própria sonda `python -c` que listava classificações foi negada pelo hook. Só `--version`/`--help` escapam da regra `claude`.
- Correção sugerida: aplicar a regra de `UserPromptSubmit` só a código inline e a entrada redirecionada para um programa que lê payload, não ao texto inteiro de qualquer comando. Restringir `claude` a `-p`/`--print`, ao prompt posicional e a `--resume`/`-c` com prompt, deixando subcomandos como `mcp`, `config`, `doctor` e `update`, no máximo, em `ask`.

### 4. Baixa — o hook chamado por um programa intermediário

- Local: `python/aifw/shell.py:644-649` (só olha o programa do segmento) e `shell.py:36-49` (`xargs` e `find -exec` são opacos).
- Cenário (hook `None`, com `opaqueCode: allow`):
  - `xargs -a /dev/null aifw-hook < p.json`: o GNU xargs mantém o stdin do comando com `-a`, então o payload chega ao hook.
  - `find . -maxdepth 0 -exec aifw-hook \; < p.json`
  - `busybox sh -c 'aifw-hook < p.json'`: programa desconhecido, classificado como `filesystem-write`.
- O `session_id` aparece em `ls .aifw/runs/`. `xargs` e `find -exec` caem no risco declarado do código opaco, mas o nome do hook está escrito no comando, sem disfarce.
- Correção sugerida: marcar como aprovação qualquer palavra do comando cujo `name_of` seja `aifw-hook`, ou que comece por `aifw.hooks`, em qualquer posição. Isso não pega `grep UserPromptSubmit` e ajuda no achado 3.

### 5. Baixa (hipótese não verificada) — mensagens enviadas pelo próprio agente como se fossem da pessoa

- Local: `python/aifw/hooks.py` (`user_prompt`), `python/aifw/assessment.py:41` (`AUTOMATIC_PROMPT`).
- Cenário: no app desktop, o agente tem ferramentas que mandam texto ao chat "como se a pessoa tivesse digitado". Exemplos: `sendPrompt()` num widget de `show_widget`, que pode rodar ao carregar, e o envio de mensagem a uma sessão. Depois de `request-approval`, um `sendPrompt("sim")` dispararia `UserPromptSubmit` na mesma sessão, sem o prefixo `<...>`, e aprovaria. Não verifiquei se esses caminhos disparam o hook nem com que texto.
- Correção sugerida: verificar. Se dispararem, pedir confirmação no `PreToolUse` para essas ferramentas enquanto houver `approval-request.yaml` pendente na sessão.

### 6. Baixa — truques residuais na API do GitHub

- Local: `python/aifw/shell.py:545-555` (`gh_api` usa o primeiro argumento com `/` que não começa por `-`) e `shell.py:523` (a URL precisa ter `/` logo depois de `github.com`).
- Cenário (hook `None`):
  - `gh api -q repos/o/r/issues/1 -X PUT repos/o/r/pulls/1/merge`: o valor de `-q` é lido como endpoint de discussão. O jq só roda depois da requisição.
  - `curl -X PUT https://api.github.com:443/repos/o/r/pulls/1/merge`
  - `gh pr review 1 --approve` é tratado como discussão, embora uma aprovação de PR possa liberar merge por regra de proteção.
- Correção sugerida: pular os valores das opções conhecidas de `gh api` (`-q/--jq`, `-t/--template`, `-H`, `--hostname`, `--input`, `-p`, `--cache`, `-f/-F`). Aceitar `:porta` na regex. Tratar `review --approve` como protegido.

### 7. Baixa — `gh release download` e `gh pr checkout` pedem confirmação com motivo errado

- Local: `python/aifw/shell.py:707-717`.
- Cenário: `gh release download v1` cai em `publish` ("publishes a package to a registry"). `gh pr checkout 12` cai em `git-remote` protegido ("changes the default branch"). Os dois são operações locais ou de leitura. Antes também pediam (`human-approval`), mas agora o motivo engana.
- Correção sugerida: incluir `download` nas leituras de `release` e `checkout` nas leituras de `pr`.

### 8. Baixa — `git -C <outro repo> push` é avaliado com a branch padrão do projeto

- Local: `python/aifw/hooks.py:185-222` (`protected_push` roda `git` em `root`).
- Cenário: `git -C ../other push origin develop` devolve `None`, mesmo que `develop` seja a branch padrão de `../other`.
- Correção sugerida: com `-C`/`--git-dir`/`--work-tree`, pedir confirmação, ou rodar as consultas no diretório indicado.

### 9. Baixa (desempenho) — glob e consultas git

- Local: `python/aifw/hooks.py:67-90` (`pattern_files`) e `hooks.py:298-300`.
- Medido no repositório: `rm **/nothing.xyz`, `sed ... python/aifw/*.py`, `git add tests_python/test_*.py`, `mkdir -p a/{b,c}` e 7 níveis de chaves levam de 0,16 a 0,21 s por chamada inteira do hook, sem diferença perceptível. O `islice(200)` limita quantos resultados são lidos, mas não quantos diretórios são percorridos. Com um padrão `**/x` que não acha nada, a árvore inteira é varrida, incluindo `.git/`, `node_modules/` e `.venv/`, o que pode custar segundos em projetos grandes.
- `protected_push` é chamado duas vezes por item: são até 6 a 8 subprocessos `git`, cerca de 0,3 s por push.
- Correção sugerida: só fazer glob nas palavras que podem nomear um controle, isto é, cujo prefixo literal antes do primeiro curinga esteja vazio ou dentro de `.aifw/`, `.claude/`, `.git/`, `.husky/`, `policies/`, ou cujo último componente possa casar com `change.yaml`/`approval.md`. Também calcular `protected_push` uma vez só.

## Sem achados

- `requested_here`/`record_chat_approval`: um pedido de outra sessão não é consumido. Dois pedidos não aprovam nenhum. Mensagens automáticas não consomem o pedido. O log de sessão é controle (escrever nele pede confirmação).
- `protected_push`: os casos da revisão anterior, mais `@:main`, `--set-upstream origin main`, `feat/x main`, `--atomic`, `--repo origin main` e `upstream` sem `HEAD`, pedem confirmação. `git push origin HEAD`, `-n` e `-o ci.skip` em branch de trabalho passam, como pretendido.
- `publish`, delegação, `secret-read` como `deny`, `.env.example` liberado e `archive`/`preview_sync` com `remove` estão coerentes com a spec.

Resultado: reprovado
