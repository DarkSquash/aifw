# Changelog

## Não lançado

### Alterado

- Orquestração em cascata pela complexidade (ADR-0042):
  - O caminho vem da complexidade (trivial L0 FAST, simples L1 WORK, moderada L2 PLANNED, alta L3 CRITICAL); a importância deixa de mudá-lo, e os nomes dos caminhos ficam.
  - L0: `aifw-quick` e L1: `aifw-executor` planejam e executam sozinhos; L2: `aifw-planner` planeja e distribui a `aifw-worker`; L3: o agente principal planeja e divide entre `aifw-lead`, que usam `aifw-worker`. Em L2 e L3 os dois revisores rodam depois.
  - Exceção de risco: risco alto ou crítico em L0 vai a um `aifw-executor` sozinho, e em L1 a um `aifw-senior` (Opus), seguidos dos dois revisores. A governança (plano aprovado no chat, spec, ADR e revisores) segue o risco.
  - O agente principal só orquestra, em todos os níveis. Novos subagentes: `aifw-planner`, `aifw-lead`, `aifw-worker` e `aifw-senior`.
  - Os níveis de impacto do resto do framework (`--level`, `change.yaml`) não foram renomeados; o avaliador e a skill mostram o risco por extenso (baixo, médio, alto, crítico).
  - Sem pasta de mudança (L2/L3 de risco baixo ou médio), os revisores não têm `independent-review.md`: devolvem a seção `## Adversário` / `## QA` e a linha `Resultado:` na resposta, e o agente principal relata à pessoa. A skill e a documentação deixam claro que "sem revisor" em L0 e L1 vale só para risco baixo ou médio.
- Backup só de cópia editada e status livre no plano aprovado (ADR-0041): a skill e os subagentes instalados trazem o sha256 do corpo, e o `aifw claude enable` só cria `.bak` quando a cópia foi editada ou não tem o hash. Editar o `tasks.yaml` aprovado sem mudar os `paths` de nenhuma tarefa (trocar `status` ou título, por exemplo) deixa de pedir confirmação; mudar os `paths`, acrescentar ou duplicar uma tarefa com paths, uma edição que o hook não aplica, um YAML ilegível ou com chave duplicada, e o shell continuam pedindo.
- Orquestração obrigatória em L2/L3 (ADR-0040): com uma mudança aprovada ativa, o hook nega à sessão principal editar arquivos do projeto e manda delegar ao `aifw-executor` (ou ao `aifw-quick` numa tarefa rápida). Subagentes, a pasta das mudanças ativas e os caminhos de `orchestration.sessionPaths` seguem livres; `orchestration.mode: off` desliga. O L3 passa a ser executado pelo `aifw-executor` com plano do Opus, e os caminhos PLANNED e CRITICAL do avaliador citam o `aifw-quick`.
- Edição restrita ao plano aprovado (ADR-0039): com uma mudança aprovada ativa, editar arquivo fora dos `paths` do `tasks.yaml` dela pede confirmação, e o `tasks.yaml` aprovado vira arquivo de controle. A pasta das mudanças ativas fica livre, e comandos de shell que escrevem não entram na regra. `changeScope: off` no `permissions.yaml` desliga a regra e a proteção do `tasks.yaml`.
- Subagentes por papel (ADR-0038):
  - `aifw claude enable` instala em `.claude/agents/` os subagentes `aifw-explorer` (haiku, low, só leitura), `aifw-quick` (haiku, low), `aifw-executor` (sonnet, medium), `aifw-adversary` (opus, high) e `aifw-qa` (sonnet, high), guardando uma cópia editada em `.bak`. `aifw claude check` acusa subagente ausente ou desatualizado.
  - O caminho do avaliador de tarefas nomeia o subagente, e a skill delega pelo nome, sem passar `model`, para valer o modelo da definição.
  - A revisão independente de L2/L3 tem duas etapas: o adversário tenta provar que a mudança está errada e só reprova com um cenário concreto; sem achado provado, o QA confere a entrega e escreve o `Resultado:`. Uma terceira reprovação para a revisão e leva o caso à pessoa.
  - O adversário faz o eixo Spec e o QA o eixo Standards do `code-review`, sem lançar subagentes.
  - O hook reconhece o subagente pelo `agent_type`: aos revisores nega editar o projeto além do `independent-review.md` e rodar comando que escreve, commita ou muda o repositório. `git stash` sem argumentos ou com `-a`, `git tag -a` e `git reflog expire`/`delete` deixam de contar como leitura: as opções que só listam passam a ser definidas por subcomando.
  - Os revisores rodam programas que o hook não conhece (`python --version`, `python -m ruff check`, `cmp`), como o código opaco; programas que gravam ou apagam arquivos por natureza (`cp`, `mv`, `touch`, `mkdir`/`md`, `tee`, `rm`, `del`, `Remove-Item`, `xcopy`, `robocopy`...) e todo `find -exec` continuam negados a eles. A trava roda antes da política, então nega mesmo se a avaliação falhar.
  - `git config get` e `git remote get-url` contam como leitura; `git branch` e `git tag` com uma opção que altera (`-d`, `-m`, `-u`, `-a`...) em qualquer posição deixam de contar.
  - Editar `.claude/agents/aifw-*.md` pede confirmação, como a skill do AIFW; `aifw claude enable` continua instalando sem perguntar.
- Mais autonomia para o agente (ADR-0037):
  - Mudanças L2/L3 são aprovadas no chat: o agente apresenta o plano e roda `aifw spec request-approval <id>`, e o hook `UserPromptSubmit` grava a resposta "sim" da pessoa em `approval.md`. Qualquer outra resposta cancela o pedido, e só vale o pedido da mesma sessão. A aprovação de mudança não exige mais commit assinado. Enquanto o pedido está pendente, o agente fica congelado: o hook nega qualquer ferramenta até a resposta da pessoa.
  - O hook nega rodar `aifw-hook`, `python -m aifw.hooks` ou `claude -p` pelo shell, e editar `change.yaml`/`approval.md` (também por padrão de shell ou em outra árvore) pede confirmação. A proteção mira erro do agente, não um agente decidido a forjar a aprovação.
  - Publicação com `uv`, `poetry`, `hatch`, `flit`, `pdm`, `deno`, `dotnet nuget push`, `vsce` e `docker buildx build --push` passa a pedir confirmação, e `git send-pack` conta como push protegido.
  - Uma resposta com ressalva ("ok, mas não faça nada ainda") cancela o pedido de aprovação, e o hook avisa o agente; um "não" solto ("sim, não tenho objeções") não é ressalva, e "Pode sim" ou "Perfeito, pode seguir" aprovam. O pedido aceita opções antes do id (`--json`), outros lançadores (`py -m aifw`, `uv run`) e linhas novas; só o comando de verdade, não um `grep` que o cite, marca a sessão que pediu.
  - O commit só pede confirmação com um arquivo que, assinado, valeria como aprovação (Charter, adoção, impasse, waiver, break-glass) ou com a política alterada; o `change.yaml` aprovado, a evidência de `validate --write` e as specs do archive não pedem. `git commit && git push` de uma branch de trabalho roda numa linha só.
  - PR e comentário em PR, e ver o PR e os checks, rodam mesmo sem `github` na allowlist (com dados confidential o GitHub precisa estar nela; com restricted a escrita é negada). `gh api graphql` de leitura roda; uma mutation pede. Sem o HEAD do remoto, o motivo do pedido diz para rodar `git remote set-head origin --auto`.
  - Só ler o conteúdo de um arquivo de segredo é negado (inclusive `git --no-pager diff .env` e `git show HEAD:.env`); um comando que apenas cita ou escreve o arquivo (`echo .env >> .gitignore`, `cat .env.example > .env`) pede confirmação, e procurar o nome (`grep .env .gitignore`) roda.
  - `aifw secrets scan` deixa de apontar `.env.sample`, `.env.template` e `.env.dist`, que são modelos.
  - Roteamento e avaliador de tarefas sempre ligados: saem `aifw route activate`, `aifw assess activate` e `.aifw/assessor.yaml`.
  - `remoteMutation: branches`: push para branch de trabalho e PR sem confirmação; branch padrão, tags, force push, apagar branch remota e merge de PR pedem.
  - `externalServices.writes: allowlist`: escrita em serviço da allowlist sem confirmação.
  - Publicação de pacote sempre pede e é negada com dados confidential/restricted; leitura de segredos é negada; delegação a subagentes locais não pede.
  - O juiz do código opaco (ADR-0035) foi removido: `aifw assess judge`, o recurso `judge` e o hook assíncrono. Rode `aifw claude enable` para limpar o hook.
  - `spec archive` apaga a spec de uma capability que perde todos os requisitos.
  - Neste repositório: `opaqueCode: allow`, `remoteMutation: branches`, `writes: allowlist`.
- Modo ativo do avaliador de tarefas (ADR-0036; a ativação e a confirmação para Haiku saíram no ADR-0037): cada pedido chega ao agente com o caminho de execução, e se o serviço falhar o agente só recebe um aviso. `aifw claude enable` instala o hook de pedidos em primeiro plano.
- O avaliador de tarefas ignora mensagens automáticas da sessão (relatórios de subagentes, avisos de outras sessões, notificações): elas não são avaliadas nem enviadas ao serviço, e o relatório deixa de contá-las.

- O hook lê o código que um comando executa indiretamente, em `python/aifw/indirect.py` (ADR-0034). Antes, pôr um `git push` dentro de um script bastava para ele passar sem pergunta.
  - Scripts de shell, PowerShell e `.bat` (`bash x.sh`, `./x.sh`, `source x.sh`, `pwsh -File x.ps1`, `call x.bat`) são analisados como comandos; `uv run x.py`, `./x.py`, `python x` sem extensão e módulos do projeto em `python -m` seguem as regras do código inline.
  - Os scripts do `package.json` (`npm`, `pnpm`, `yarn`, `bun`, com `pre`, `post` e `--prefix`) e os comandos do `Makefile` (receitas, `;`, `$(shell ...)`, `!=`, variáveis expandidas, `-C` e `-f`) também são lidos.
  - Falha fechada: pedem confirmação, como código ilegível, arquivos em Perl, Ruby ou binários; scripts que ainda não existem ou que o mesmo comando altera; código da entrada padrão; `env -S`; `package.json` que não se lê; Makefile com `include`, funções do make ou variáveis do ambiente; e configurações do git que executam programas (`alias.*`, `core.hooksPath`, `diff.external`, `hook.*` e afins), por `git config`, `-c` ou `--config-env`.
  - Toda a pasta `.git/` é arquivo de controle, sem diferenciar maiúsculas; editar `.venv/`, `node_modules/` ou `.tox/` com as ferramentas de edição pede confirmação.
  - `timeout`, `nice -n`, `sudo -u` e `uv run --with` pulam os próprios valores antes de achar o programa.
  - Código carregado por opção ou variável também conta: `node -r ./x.js` lê o módulo; variáveis como `GIT_SSH_COMMAND`, `NODE_OPTIONS`, `BASH_ENV` e `npm_config_*` na linha ou em `export`, `--script-shell`, `script-shell` no `.npmrc` e `make SHELL=`, `--eval` ou `-e` pedem confirmação.
  - Para pedir menos confirmações: `make` lê só os alvos pedidos e seus pré-requisitos; valores comuns como `GIT_EDITOR=true` e `NODE_OPTIONS=--experimental-vm-modules` não perguntam; `source ~/.bashrc`, scripts `activate` e wrappers `./gradlew`/`./mvnw` commitados rodam sem leitura. `bun publish`, `gradle publish` e `mvn deploy` contam como publicação e `.husky/` como arquivo de controle.
  - Modelo de ameaças decidido no impasse `hook-indirect-code`: o hook protege contra erros do agente e caminhos óbvios, não é um sandbox; o resto fica como risco residual declarado no ADR.
- Escopo das aprovações (ADR-0025):
  - instalar pacote, programa ou projeto novo (inclusive `npx`, `uvx`, `winget` e `git clone`) e criar ou reescrever commits sempre pedem confirmação;
  - a allowlist não libera mais instalações;
  - neste repositório, `python/aifw/` deixou de ser caminho protegido.
- Opções `opaqueCode` (padrão `ask`) e `trustedPackages` em `permissions.yaml`. Neste repositório, `npx ctx7` roda sem perguntar.
- Uma aprovação do AIFW escondida em código que também roda programas passa a ser detectada.
- O cache de validação dos arquivos YAML inclui o hash do schema, então uma mudança de schema sempre valida de novo.
- Falhas repetidas contam só em sequência: um comando de teste que volta a passar zera a contagem. Isso vale para a sugestão de abrir impasse e para o gate `session-conformance`, que antes reprovava sessões longas por falhas de causas diferentes, já corrigidas.
- Os recursos de avaliação `context` e `intake` só acrescentam o campo `assessment` à saída quando estão ligados.
- Falhas aleatórias no Windows (WinError 6, "identificador inválido") corrigidas:
  - os subprocessos do AIFW recebem a própria entrada padrão. Antes, uma entrada herdada inválida fazia o `git` parecer ausente e zerava o piso de risco do diff;
  - os gates com `python` chamam o interpretador real por trás de atalhos como o `bin\python.exe` do instalador do Python. O atalho, rodando sem console, repassava entradas inválidas aos testes.
- Mais autonomia (ADR-0030):
  - opção `commits: allow` em `permissions.yaml`: criar e reescrever commits deixa de pedir confirmação, exceto com algum arquivo de controle alterado; push e commit com `-S` continuam pedindo. Ligada neste repositório;
  - delegar para o `haiku` só pede confirmação com mudança L3 ativa (depois, no ADR-0037, a delegação local deixou de pedir);
  - a mensagem sobre código ilegível sugere gravá-lo num arquivo `.py` ou `.js`, que o hook lê.
- `aifw assess eval --feature <recurso>` roda as suítes de `evals/assessment/` contra o modelo de decisão, com acertos, divergências e acertos por corte (ADR-0033). As perguntas são as mesmas do modo sombra.
- Gate `independent-review` (ADR-0033): lê a linha `Resultado:` do `independent-review.md` e falha sem ela ou com `reprovado`; no `validate --level`, sem mudança, aponta as mudanças L2/L3 ativas em vez de avisar que não há comando. Neste repositório o gate passou a ser hard.
- Avaliação automática das tarefas (ADR-0031): com o recurso `tasks` ligado, o hook `UserPromptSubmit` avalia cada pedido com 5 palavras ou mais (em segundo plano até o ADR-0037, que o pôs em primeiro plano); o registro marca `source: prompt`. `aifw claude enable` instala o novo hook.
- `aifw init` e `aifw claude enable` colocam `.aifw/runs/` e `.aifw/assessments/` no `.gitignore` do projeto. Antes, os registros de sessão, com os comandos rodados, podiam ir para o git.
- Menos confirmações falsas: `cut`, `tr`, `nl`, `basename`, `dirname` e `realpath` são leitura, e uma linha só com atribuição de variável (`L=x`) também. Cada confirmação pedida pelo hook fica registrada em `.aifw/runs/` (`tool: Ask`), para achar as que podem sair. Os registros de sessão e de avaliação não contam mais como arquivo de controle alterado num commit.
- Os testes deixam de falhar ao acaso no Windows com WinError 6: o pytest troca a entrada padrão e o identificador do Windows ficava apontando para a antiga, já fechada (`tests_python/conftest.py`).
- O hook trata o conteúdo de um heredoc como dado. Ele só é analisado como código quando alimenta um interpretador ou um shell, ou quando, sem aspas, expande `$(...)`.

### Adicionado

- Avaliador de tarefas em modo sombra (ADR-0023):
  - `aifw change assess` avalia risco, importância e complexidade com o `perplexity/pplx-decider-v1.2`, pelo OpenRouter, com piso de risco vindo do diff;
  - `aifw assess report` mostra as avaliações e os vereditos;
  - `aifw assess verdict` é a aprovação humana que registra se você concorda;
  - o início de sessão avisa quando há 50 avaliações.
- `openrouter` na tabela de domínios da allowlist e `spec.assessment` no manifesto.
- Impasse em modo sombra (ADR-0024):
  - `spec.assessment.features` liga cada avaliação;
  - com `impasse`, cada tentativa nova é comparada pelo Decider com as anteriores, para detectar a mesma estratégia escrita com outras palavras;
  - relatório e vereditos com `--feature impasse`.
- Seleção de contexto em modo sombra (ADR-0026):
  - com `context`, o `context select` informa os documentos que o Decider considera relevantes e as palavras não acharam, e os escolhidos só por uma palavra em comum;
  - na suíte de 20 tarefas, a cobertura foi de 42% para 82%.
- Respostas do intake em modo sombra (ADR-0027):
  - com `intake`, o `intake status` aponta as respostas do Charter vagas ou parciais, que viram perguntas da entrevista, sem bloquear a aprovação;
  - na suíte de 20 respostas, acertou fraca ou não fraca em todas.
- Rastreabilidade da spec em modo sombra (ADR-0028):
  - com `traceability`, o `spec analyze` aponta pares de requisito e cenário em que o cenário provavelmente não verifica o requisito, sem bloquear;
  - na suíte de 18 pares reais, acertou todos.
- Sinais dos catálogos de decisão em modo sombra (ADR-0029):
  - `decision recommend --suggest-signals [--context]` sugere os sinais de cada direcionador a partir do Charter e do pedido, mostrando o ranking que eles dariam;
  - o ranking oficial continua usando só `--signals`, que deixou de ser obrigatório;
  - na suíte, nenhum sinal sugerido contrariou o texto.

## 0.4.1 — 2026-10-15

Fecha os itens em aberto das auditorias (ADR-0022).

### Adicionado

- `aifw secrets scan --history`, que lê as linhas adicionadas em todos os commits.
- O hook lê o arquivo de um script Python ou JavaScript chamado diretamente (`python publicar.py`).
- Delegação: o hook lê o modelo da definição do subagente e pede confirmação para sessões na nuvem.

### Alterado

- O Stop ignorado fica registrado. `runs show` separa achados de notas, e `session-conformance` passa a ser hard nas receitas.
- `route explain` usa a policy gravada; com assinatura exigida, a ativação de roteamento só vale assinada.
- O `init` ajusta a receita de gates ao gerenciador de pacotes e às ferramentas declaradas no projeto.
- O cache de validação fica em `~/.cache/aifw/`. Valores desconhecidos na política de permissões pedem confirmação.

### Removido

- `permissions.validate_delegation`, substituída pelos hooks, que valem dentro dos subagentes.

## 0.4.0 — 2026-10-11

Claude Code passa a ser o host de referência, ativado por projeto, e a validação deixa de poder parecer verde sem evidência.

### Adicionado

- `aifw claude install|enable|check`, comando `/aifw new|adopt` e skill de projeto `aifw-workflow` (ADR-0014, ADR-0016).
- Hook `aifw-hook` para PreToolUse, PostToolUse, PostToolUseFailure, Stop e SessionStart (ADR-0015, ADR-0018):
  - aplica permissões, impasses, arquivos de controle, MCP, delegação a subagentes, `dataClassification` e break-glass;
  - registra a sessão em `.aifw/runs/`, bloqueia a conclusão com código não verificado e sugere abrir impasse após falhas repetidas;
  - informa intake, mudanças ativas e impasses ao abrir a sessão.
- `aifw validate --change <id> --write`, com artefatos exigidos por nível e relatório com digest; `spec archive` exige esse relatório atual (ADR-0017).
- `aifw impasse open|attempt|status|review|decide|revalidate`.
- `aifw waiver add|list`, `aifw break-glass grant|list`, `aifw intake set`, `aifw template list|copy`, `aifw runs show`, `aifw change classify --diff`.
- Receitas de gates aplicadas no `init` para os profiles Python, Web e Flutter (com detecção de FVM).
- `aifw doctor` informa a integração com o Claude Code quando roda num projeto.
- Leitura real de comandos de shell no hook (`aifw.shell`): aspas, separadores, wrappers, opções globais do git e `bash -c`; código ilegível pede confirmação (ADR-0019).

### Alterado

- `intake status` só é `complete` com o Charter aprovado e inalterado (`charterApproved`).
- A allowlist de serviços externos vem só de `aifw.yaml` (`spec.externalAllowlist`); `externalServices.allowlist` em `permissions.yaml` ficou obsoleta.
- Roteamento usa haiku/sonnet/opus; a policy volta a `recommendation-only` até nova avaliação.
- Gates com `python` ignoram o atalho da Microsoft Store e usam o interpretador do AIFW.
- Git passa a ser dependência obrigatória.
- Comandos de aprovação só rodam no terminal da pessoa que aprova, com o id do projeto digitado; o shell do agente é recusado (ADR-0019).
- Teste com saída escondida por `|`, `;`, `||` ou `&` não conta como verificação.
- Hooks de projeto rodam no bash e, sem o AIFW instalado, explicam como instalar em vez de falhar sem mensagem.
- Waivers, break-glass, Charter, `change.yaml`, registros de sessão e qualquer `.claude/settings*.json` passam a ser protegidos pelo hook (ADR-0020).
- O Stop compara o estado do git e só aceita o executor de testes de fato como verificação.
- O leitor de shell cobre `cmd /c`, `powershell -Command`, `Start-Process`, `xargs`, `python -c`, aliases do git, publicação, acesso remoto e instalação de pacotes.
- `aifw secrets scan` e gates `secret-scan` e `session-conformance` nos scaffolds; leitura de arquivos de segredo pede confirmação.
- Modo opcional `approvals.requireSignedCommit`: aprovações só valem em commit assinado.
- O leitor de shell analisa `$(...)`, crases e blocos `{ }`; programa vindo de variável, `Invoke-Command` e `.` pedem confirmação; `printenv`/`env`/`set` são leitura de segredo; `git commit -S` pede confirmação (ADR-0021).
- Menos confirmações sem reabrir brechas: blocos `{ }` têm o conteúdo analisado, `python -c`/`node -e` são lidos pelo que fazem, e escrita externa fora da allowlist pede confirmação em vez de ser negada (exceto dados `confidential`/`restricted`).
- `script -c` é analisado; `expect`, `unbuffer`, `socat`, `winpty` e `script` sem comando pedem confirmação, fechando aprovação por terminal falso no Linux.
- `uv sync` é liberado; `pip install`, `npm install` e `uv add` pedem confirmação.
- Allowlist casa por domínio, com `serviceDomains` editável; Grep e Glob passam pelo hook; `protectedPaths` no `permissions.yaml`.
- Modo de commit assinado cobre também adoção e decisões de impasse; uso de break-glass é registrado.
- O hook só carrega o validador de schemas para conteúdo ainda não validado (cerca de 300 ms em vez de 650 ms); `aifw claude enable` guarda backup de uma skill de projeto editada.
- Registros de sessão com mais de 30 dias são apagados; `aifw claude check` detecta o `/aifw` global desatualizado; schemas são carregados uma vez por processo.

### Removido

- Integração Pi (`extensions/aifw.ts`, `aifw-pi-bridge`, adapter) e Codex (templates e guia).
- `aifw handoff codex` e `aifw principle review`; a entrevista do intake usa a skill `grilling` e a revisão de princípios usa `code-review` (ADR-0013).
