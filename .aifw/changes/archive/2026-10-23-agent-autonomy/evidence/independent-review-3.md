# Revisão independente 3 — agent-autonomy (L3)

## Escopo

- `git diff HEAD` do working tree e os arquivos não rastreados (`.aifw/changes/active/agent-autonomy/`, `docs/decisions/ADR-0037-agent-autonomy.md`, `tests_python/test_agent_autonomy.py`).
- Critérios: `proposal.md`, `design.md`, `threat-model.md`, `migration.md`, `specs/*.delta.yaml` e ADR-0037. Modelo de ameaças aceito (ADR-0034): o hook protege contra erros e caminhos óbvios, código opaco liberado e nomes montados em variáveis são risco residual.
- Base: `evidence/independent-review-1.md` e `evidence/independent-review-2.md`.
- Foco: o selo HMAC (`approval_key`, `seal`, `assert_approval`, `approve_change` em `python/aifw/specs.py`, proteção da chave em `control_target` de `python/aifw/hooks.py`) e as correções `forges_prompt`, `CLAUDE_SUBCOMMANDS`, `gh_api` e `pattern_files`.
- Verificação:
  - Suíte inteira com `AIFW_HOME` temporário: `python -m pytest -q -p no:cacheprovider` deu 2475 passed.
  - Sondas do hook com `aifw.hooks.handle` num projeto temporário criado como em `test_agent_autonomy.py`. A política era a do scaffold (`remoteMutation: branches`, `writes: allowlist`, `opaqueCode: allow`, `commits: allow`), com `github` na allowlist e `AIFW_HOME` temporário.
  - As duas falsificações dos achados 1 e 2 foram reproduzidas de ponta a ponta. Os comandos rodaram de verdade no Git Bash (`cp`, `xxd`, `openssl` de `/mingw64/bin`), o hook devolveu `None` para cada um, e depois `specs.assert_approval` passou.
  - Scripts em `C:\Users\DARKSQ~1\AppData\Local\Temp\claude\C--Users-DarkSquash-Documents-Projetos-aifw\31451809-735d-4dd2-985a-991c20809a6a\scratchpad\review3\` (`p1.py` a `p4.py`).

## Situação dos achados anteriores

### Revisão 1

| # | Situação |
| --- | --- |
| 1 (alta) autoaprovação via `aifw-hook` | Corrigido. `aifw-hook` direto, com caminho, `.exe/.cmd/.bat`, maiúsculas, wrappers (`env`, `nice`, `time`, `sudo`, `nohup`, `strace`, `start`, `exec`, `command`), `xargs`, `find -exec`, `cmd /c`, `powershell -c`, `python/py -m aifw.hooks`, `uv run`, `node -e` e `claude -p` são negados. `python python/aifw/hooks.py` passa, mas falha no import relativo. |
| 2 (alta) `change.yaml`/`approval.md` por shell com glob | Tratado em parte. Os padrões pedem confirmação, mas a escrita por cópia de diretório continua aberta e o selo não cobre o nível (novo achado 1). |
| 3 (alta) push para a branch padrão | Corrigido (conferido na rev. 2, sem regressão). |
| 4 (alta) `gh api`/`curl` | Corrigido. Sobra `user@` na URL (novo achado 5). |
| 5, 6, 7, 10, 12 | Corrigidos. |
| 8 respostas condicionais | Deixado de propósito. |
| 9 falha parcial silenciosa | Corrigido para `AifwError`. Uma exceção de outro tipo (YAML, `OSError`) em `approve_change` ainda é engolida por `handle` e deixa `approval.md` (`specs.py:517`). Com o selo, o resíduo é inofensivo. |
| 11 `echo $VAR` | Deixado de propósito. |

### Revisão 2

| # | Situação |
| --- | --- |
| 1 (alta) aprovação forjada copiando um diretório | Parte (a): o selo HMAC impede `change.yaml` com aprovação inventada sem a chave. Parte (b) não foi feita: `cp -r forged/. <pasta>`, `cp -r forged/ .../big/../big`, `tar -C`, `unzip -d`, `git apply`, `patch`, `git am`, `git merge`, `git cherry-pick` e `git stash pop` continuam sem objeção. `assert_approval` também não exige `record == <pasta>/approval.md`: o selo aceita `record: aifw.yaml`. Os dois caminhos que sobram estão nos novos achados 1 e 2. |
| 2 nomes partidos por aspas | Deixado de propósito para os outros arquivos de controle. Para `change.yaml`, `sed -i s/L3/L2/ .../chang''e.yaml` ainda passa e alimenta o novo achado 1. |
| 3 `forges_prompt` amplo demais | Corrigido. `grep UserPromptSubmit`, `git log -S aifw-hook`, `git commit -m "... aifw-hook"`, `claude mcp/doctor/update/plugin/config/agents` e `which/where/Get-Command aifw-hook` passam. Falsos positivos menores no novo achado 6. |
| 4 hook por intermediário | `xargs` e `find -exec` corrigidos. `busybox sh -c 'aifw-hook < p.json'` ainda passa (baixa, programa desconhecido). |
| 5 `sendPrompt` | Deixado de propósito, não verificado. |
| 6 truques na API do GitHub | `-q/--jq` e `:443` corrigidos. `gh pr review --approve` continua como discussão. O GitHub não deixa o autor aprovar o próprio PR, então o risco é baixo. |
| 7 `release download`/`pr checkout` | Corrigido (agora leitura). |
| 8 `git -C` | Deixado de propósito. |
| 9 desempenho | Padrões com `**` deixaram de ser expandidos (`hooks.py:82`). `protected_push` ainda roda duas vezes quando não há grant (`hooks.py:303-305`). |

## Achados novos

### 1. Alta — rebaixar o nível para L2 dispensa o selo, e a cópia de diretório ainda escreve `change.yaml`

- Local: `python/aifw/specs.py:415-416` (`assert_approval` retorna sem checar nada quando `level != "L3"`). `python/aifw/specs.py:408-411`: o selo cobre mudança, pessoa, instante e registro, mas não o nível. `python/aifw/hooks.py:124-131`: no shell, só o texto e os padrões são conferidos.
- Cenário (reproduzido, `p3.py` parte A):
  1. O agente grava `forged/change.yaml` com a ferramenta Write, sem objeção. O conteúdo é a cópia do `change.yaml` real com `level: L2`.
  2. O agente roda `cp -r forged/. .aifw/changes/active/big/`. O hook devolve `None`.
  3. `assert_approval` passa sem aprovação e sem selo. Logo `spec ready` e `spec archive` aceitam a mudança, e L2 ainda exige menos artefatos.
- Também passam, sem objeção, o mesmo efeito por `sed -i s/L3/L2/ .aifw/changes/active/big/chang''e.yaml` e por `tar`, `unzip`, `git apply`, `patch` (ver a rev. 2, achado 1).
- São comandos comuns, sem código opaco e sem variável. O resultado contradiz o ADR-0037 §2 ("`ready` e `archive` recusam aprovação sem selo válido, então um `change.yaml` escrito ou copiado à mão não passa") e T-002. A lacuna do nível já existia, mas antes do selo o ponto central era o commit assinado. Agora o desenho declara o selo como a barreira, e ela é contornada sem tocar no selo.
- Correção sugerida:
  - Incluir o nível no selo, gravado em `create_change` ou na aprovação.
  - Em `ready`/`archive`, recusar um nível abaixo do piso que o avaliador calcula (`assessment.classify_change`), ou abaixo do nível registrado num lugar que o agente não edita (por exemplo, um campo selado na criação).
  - Fazer a parte (b) da correção da rev. 2: um comando de shell mutante cujo argumento resolva para um diretório que contenha `change.yaml` ou `approval.md` pede confirmação. `git apply`, `git am` e `patch` pedem confirmação sempre, ou o hook confere os caminhos do patch.

### 2. Alta — a chave do selo é lida com um glob comum, e o selo é calculado com `openssl`

- Local: `python/aifw/shell.py:784` (`secret-read` só olha a palavra literal contra `SECRET_FILE`). `python/aifw/hooks.py:85-86` (`pattern_files` ignora padrões fora do projeto). `python/aifw/hooks.py:124-131` (o controle no shell exige a substring `approval.key`).
- Cenário (reproduzido, `p3.py` parte B). Todas as etapas devolvem hook `None`:
  1. `xxd -p ~/.aifw/approval.ke?`, `od -An -tx1 ~/.aifw/*` ou `base64 ~/.aifw/approval.ke[y]` imprimem a chave real. Só a forma literal `cat ~/.aifw/approval.key` é negada.
  2. `openssl dgst -sha256 -mac HMAC -macopt hexkey:<chave> m.txt`, com `m.txt` contendo `big\nhuman:x\n<instante>\naifw.yaml`, dá o selo. O `openssl` vem com o Git for Windows e não é código opaco.
  3. A aprovação com esse selo entra pela cópia de diretório do achado 1. `assert_approval` aceita, com `record: aifw.yaml`.
- Variante sem ler a chave real: `AIFW_HOME` muda a pasta da chave (`specs.py:401`), e definir a variável no comando não gera objeção. Com `AIFW_HOME=/tmp/k aifw spec ready big`, o `aifw` cria uma chave nova em `/tmp/k`, que se lê com `xxd -p /tmp/k/*`. O agente forja o selo com essa chave e roda `AIFW_HOME=/tmp/k aifw spec ready big` ou `spec archive big`. Os quatro comandos devolvem `None`, assim como `env AIFW_HOME=...` e `$env:AIFW_HOME=...` no PowerShell.
- Contradiz o ADR-0037 §2 ("o agente não lê a chave"). O passo do `openssl` é deliberado, mas cada comando é comum e legível. O que o ADR-0034 aceita como residual é o código opaco e os nomes em variáveis, não globs nem uma variável de ambiente de configuração do próprio AIFW.
- Correção sugerida:
  - Tratar como `secret-read` qualquer palavra do shell que nomeie a pasta da chave: `~/.aifw`, `$HOME/.aifw`, `%USERPROFILE%\.aifw`, o caminho absoluto resolvido ou o `AIFW_HOME` atual, com ou sem curinga. Também expandir padrões fora do projeto para conferir os resultados contra `SECRET_FILE`.
  - Ignorar `AIFW_HOME` fora dos testes, ou tratar como controle (pedir confirmação) qualquer comando que o defina. Por exemplo, só aceitar a variável quando `AIFW_TESTING` estiver definido no conftest.
  - Exigir em `assert_approval` que `record` seja `<pasta da mudança>/approval.md`.
  - Registrar no T-002 que, contra um shell do mesmo usuário, a chave é um segredo de arquivo como qualquer outro. A proteção vale até onde vale o detector de `secret-read`.

### 3. Média — `aifw validate --change` dá a aprovação humana como válida sem conferir o selo

- Local: `python/aifw/gates.py:398-407` (`validate_change_workspace` só exige `human:` e um registro existente).
- Cenário: com um `change.yaml` forjado sem selo, entrado pelo achado 1, `aifw validate --change big` mostra o gate `human-approval` como aprovado por `human:x` e grava isso em `evidence/validation.json`. `ready` e `archive` recusam, mas o relatório e quem o lê (pessoa, CI ou revisor) veem uma aprovação válida. O código é anterior à mudança, mas antes a prova era o commit assinado, que o relatório também não conferia.
- Correção sugerida: chamar `specs.assert_approval` (ou conferir o selo) antes de montar `approval` em `validate_change_workspace`.

### 4. Baixa — padrões recursivos `**` deixaram de ser vistos

- Local: `python/aifw/hooks.py:82-83`.
- Cenário: `sed -i x .aifw/**/chang?.yaml` devolve `None`. Antes da correção de desempenho, o padrão era expandido e pedia confirmação. `.../**/change.yaml` ainda pede, pela substring. Com o selo, o efeito restante é o mesmo do achado 1.
- Correção sugerida: expandir `**` só quando o prefixo literal estiver dentro de `.aifw/`, `.claude/`, `.git/`, `.husky/` ou `policies/`, como a rev. 2 sugeriu.

### 5. Baixa — merge pela API do GitHub com usuário na URL

- Local: `python/aifw/shell.py:523-526` (a regex exige `https?://api.github.com`, sem `user@`).
- Cenário: `curl -X PUT -H 'Authorization: token x' https://user@api.github.com/repos/o/r/pulls/1/merge` devolve `None`. Vira escrita externa no `github` da allowlist, sem a proteção de `git-remote`. `gh auth token` também passa, então o agente tem o token.
- Correção sugerida: aceitar `[^/@]*@` antes do host na regex, ou extrair o host com `urllib.parse.urlsplit`.

### 6. Baixa — falsos positivos de `forges_prompt`

- Local: `python/aifw/shell.py:657-689`.
- Cenário: `claude --model haiku` é negado, porque o valor da opção é lido como prompt. `pip show aifw-hook` também é negado. Por outro lado, `echo sim | claude -c` passa e `claude -c < p.txt` é negado. Não verifiquei se o `claude` sem `-p`, com stdin em pipe e sem TTY, envia o texto como prompt.
- Correção sugerida: pular os valores das opções conhecidas do `claude` (`--model`, `--agent`, `--settings`, `--add-dir`, `-r/--resume` com id). Tratar `claude` com stdin em pipe como o redirecionamento, ou verificar que isso não dispara `UserPromptSubmit`.

## Sem achados

- O selo em si: HMAC-SHA256 com `compare_digest`, chave de 32 bytes, e `change_id` no texto, então um selo não serve para outra mudança. `approve_change` normaliza o `record` antes de selar. Write e Edit na chave pedem confirmação, e Read nela é negado.
- `gh_api`: o pulo de `-q/--jq`, `-H`, `--hostname`, `--input`, `-f/-F` e `--method=` funciona. `../`, `%2e%2e`, `//` e a barra final continuam protegidos. `#` e `?` no caminho só mudam a rota para PATCH/PUT em `pulls/1`, que é discussão.
- `CLAUDE_SUBCOMMANDS`: os subcomandos de gestão passam. Prompt posicional, `-p`, `--resume <id>` e `-- sim` são negados.

Resultado: reprovado
