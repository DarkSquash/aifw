# Changelog

## Não lançado

### Alterado

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
  - delegar para o `haiku` só pede confirmação com mudança L3 ativa;
  - a mensagem sobre código ilegível sugere gravá-lo num arquivo `.py` ou `.js`, que o hook lê.
- `aifw assess eval --feature <recurso>` roda as suítes de `evals/assessment/` contra o modelo de decisão, com acertos, divergências e acertos por corte (ADR-0033). As perguntas são as mesmas do modo sombra.
- Gate `independent-review` (ADR-0033): lê a linha `Resultado:` do `independent-review.md` e falha sem ela ou com `reprovado`; no `validate --level`, sem mudança, aponta as mudanças L2/L3 ativas em vez de avisar que não há comando. Neste repositório o gate passou a ser hard.
- Avaliação automática das tarefas (ADR-0031): com o recurso `tasks` ligado, o hook `UserPromptSubmit` avalia em segundo plano cada pedido com 5 palavras ou mais, sem atrasar a sessão; o registro marca `source: prompt`. `aifw claude enable` instala o novo hook.
- `aifw init` e `aifw claude enable` colocam `.aifw/runs/` e `.aifw/assessments/` no `.gitignore` do projeto. Antes, os registros de sessão, com os comandos rodados, podiam ir para o git.
- Menos confirmações falsas: `cut`, `tr`, `nl`, `basename`, `dirname` e `realpath` são leitura, e uma linha só com atribuição de variável (`L=x`) também. Cada confirmação pedida pelo hook fica registrada em `.aifw/runs/` (`tool: Ask`), para achar as que podem sair. Os registros de sessão e de avaliação não contam mais como arquivo de controle alterado num commit.
- Os testes deixam de falhar ao acaso no Windows com WinError 6: o pytest troca a entrada padrão e o identificador do Windows ficava apontando para a antiga, já fechada (`tests_python/conftest.py`).
- O hook trata o conteúdo de um heredoc como dado. Ele só é analisado como código quando alimenta um interpretador ou um shell, ou quando, sem aspas, expande `$(...)`.

### Adicionado

- Juiz do código opaco em modo sombra (ADR-0035): com o recurso `judge` ligado, um segundo hook `PreToolUse`, assíncrono (`aifw assess judge --hook`), pede ao Claude da assinatura, via `claude -p`, que julgue os comandos que o hook não consegue ler. Ele só registra, sem mudar nenhuma decisão do hook.
  - O registro vai para `.aifw/assessments/judge.jsonl`, com veredito, a intenção provável em uma frase, a divergência entre a descrição do agente e o código, a decisão da regra fixa e a latência. A pessoa o revisa com `aifw assess report` e `aifw assess verdict --feature judge`.
  - Haiku responde primeiro e o Sonnet entra quando a confiança fica baixa. O `claude -p` roda sem ferramentas, hooks, MCP, skills nem `CLAUDE.md`. Comando e código vão mascarados, entre marcadores com nonce, e arquivos de segredo, de dados, binários ou grandes ficam na máquina.
  - `aifw assess eval --feature judge` mede Haiku, Sonnet e a escalada: acertos, liberações indevidas, latência e custo. `aifw claude enable` instala o novo hook.
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
