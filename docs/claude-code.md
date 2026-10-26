# AIFW no Claude Code

O AIFW fica desligado até você habilitá-lo num projeto. Nada roda nas sessões de projetos que não o usam.

## Instalação (uma vez por máquina)

Requisitos: Python 3.11 ou superior, [uv](https://docs.astral.sh/uv/), [Git](https://git-scm.com/) e Claude Code.

```powershell
uv tool install C:\caminho\para\aifw
aifw claude install
```

- O primeiro comando instala os executáveis `aifw` e `aifw-hook` no PATH (`~/.local/bin`). Com `--editable`, mudanças na pasta do AIFW valem na hora, sem reinstalar.
- O segundo copia o comando `/aifw` para `~/.claude/skills/aifw/`. Esse comando só roda quando você o digita; o Claude não o aciona sozinho.

Confira com `aifw --version`. Se o uv avisar que a pasta de executáveis não está no PATH, rode `uv tool update-shell` e abra um terminal novo.

## Habilitar num projeto

Abra o Claude Code na pasta do projeto e digite:

- `/aifw new` — projeto do zero: inicializa o control plane e conduz a entrevista do intake.
- `/aifw adopt` — projeto que já existe: inicializa com `--existing`, faz o discovery e pede sua aprovação do que foi encontrado.

Os dois rodam `aifw claude enable`, que grava no próprio projeto:

- `.claude/settings.json`: o hook `aifw-hook`, mesclado com o que já existir no arquivo;
- `.claude/skills/aifw-workflow/SKILL.md`: o fluxo do AIFW para o Claude seguir neste projeto;
- `.claude/agents/aifw-*.md`: os subagentes por papel, com modelo e esforço fixos (veja [Modelos](#modelos)).

Se você editou a skill ou um subagente, o `enable` guarda a sua versão em `<arquivo>.bak` antes de substituí-la. Abra uma nova sessão depois de habilitar, para o hook e a skill carregarem. Se o projeto usa git, versione a pasta `.claude/`: quem clonar o projeto recebe a mesma configuração.

Para desabilitar, remova a entrada `aifw-hook` de `.claude/settings.json`, a pasta `.claude/skills/aifw-workflow/` e os arquivos `.claude/agents/aifw-*.md`.

## O que os hooks fazem

| Evento | Ação |
| --- | --- |
| PreToolUse | cobre Bash, PowerShell, edições, Read, Grep, Glob, web, subagentes e MCP; aplica permissões, impasses, arquivos de controle, MCP, delegação, classificação dos dados e break-glass (detalhes abaixo); se o `aifw-hook` não puder rodar, a ação é bloqueada (`onFailure: block`) |
| PostToolUse | registra comandos e edições em `.aifw/runs/<sessão>.jsonl`, em segundo plano; `aifw init` e `aifw claude enable` colocam `.aifw/runs/` e `.aifw/assessments/` no `.gitignore` |
| PostToolUseFailure | registra a falha; se o mesmo comando de teste falhar duas vezes sem impasse aberto, sugere `aifw impasse open` |
| Stop | é um aviso, não uma trava: o Claude Code repassa o bloqueio uma vez por resposta. Impede concluir com código alterado depois da última verificação bem-sucedida, uma vez por resposta. Compara o estado do git, então pega edições feitas por qualquer caminho (scripts, `sed -i`, geradores). Só conta como verificação o próprio executor de testes ou `aifw validate`, não um `echo pytest`. Se o agente parar de novo sem verificar, o AIFW registra o ocorrido e `aifw runs show` (gate `session-conformance`) reprova a sessão |
| UserPromptSubmit | roda antes do agente ler a mensagem. Se uma mudança aguarda aprovação (`aifw spec request-approval`), registra a resposta da pessoa como aprovação (veja Aprovações). Com o recurso `tasks` ligado, avalia cada pedido e entrega o caminho de execução (ADR-0036, ADR-0037); se o serviço falhar, só avisa. Mensagens automáticas, como relatórios de subagentes e avisos de outras sessões, não aprovam nem são avaliadas |
| SessionStart | informa intake incompleto, mudanças ativas e impasses abertos; guarda o estado inicial do git e apaga registros de sessão com mais de 30 dias |

Como o PreToolUse bloqueia quando falha, quem clonar um projeto habilitado precisa instalar o AIFW antes de usar o Claude Code nele. `aifw claude check` mostra o que falta: hooks, skill do projeto, `aifw-hook` no PATH, comando `/aifw` e skills obrigatórias.

### PreToolUse

`aifw-hook` aplica `.aifw/permissions.yaml` e os impasses abertos a cada ação do Claude Code. Ele nunca aprova sozinho: quando o AIFW não tem objeção, as regras de permissão do próprio Claude Code continuam valendo. Ele retorna:

- `deny` quando a política diz `denied`, quando um impasse congela edições e comandos destrutivos, para leitura de arquivos que costumam guardar segredos (`.env`, `*.pem`, `*.key`, `id_rsa`) pela ferramenta Read ou por um comando que mostra o conteúdo (`cat`, `grep`, `git diff`...), para publicação com dados `confidential` ou `restricted`, ou para comandos de aprovação, que só rodam no terminal da pessoa (veja Aprovações);
- `ask` quando a política exige aprovação humana, para um comando que só cita um arquivo de segredo sem mostrar o conteúdo (`echo .env >> .gitignore`, `cp .env.example .env`, `source .env`), para leitura ou escrita em serviço fora da allowlist, para publicação de pacote, para comandos que o hook não consegue ler (exceto com `opaqueCode: allow`), para comandos de shell durante um impasse `OPEN` e para edições nos arquivos de controle e de decisão do AIFW (`aifw.yaml`, Charter, `change.yaml`, `approval.md` das mudanças, o `tasks.yaml` de uma mudança aprovada, permissões, gates, roteamento, impasses, waivers, break-glass, registro de sessões, decisões, aprovação da adoção, specs aceitas, `evidence/validation.json`, `policies/`, a skill `.claude/skills/aifw-workflow/` e os subagentes `.claude/agents/aifw-*`, a pasta `.git/`, `.venv/` e `node_modules/` e qualquer `.claude/settings*.json`, inclusive o global);
- `ask` também quando a política não pode ser lida, para que a falha chegue ao humano em vez de liberar a ação.

Controles adicionais:

- **Serviços externos:** a allowlist vem de `spec.externalAllowlist` em `aifw.yaml`. Com `externalServices.writes: allowlist` (ADR-0037), escrever num serviço dela (um `POST` para a API do projeto, por exemplo) roda sem perguntar; fora dela, pede confirmação. O agente pergunta uma vez antes de incluir um domínio novo na lista. Com `dataClassification: confidential`, leitura de serviço fora dela é negada; com `restricted`, escrita externa também é negada.
- **MCP:** `mcpServers.deny` e `mcpServers.ask` em `.aifw/permissions.yaml` listam servidores (o trecho entre `mcp__` e `__` no nome da ferramenta). Servidores fora das listas seguem as regras do Claude Code.
- **Plano aprovado:** enquanto houver uma mudança aprovada ativa, editar pelas ferramentas de edição um arquivo do projeto fora dos `paths` do `tasks.yaml` dela pede confirmação, citando a mudança (ADR-0039). Um path casa com o arquivo, com tudo dentro de uma pasta ou com um padrão (`templates/*.md`); a pasta `.aifw/changes/active/` fica livre, e o `tasks.yaml` aprovado vira arquivo de controle. Comandos de shell que escrevem não entram na regra. `changeScope: off` no `permissions.yaml` desliga a regra.
- **Orquestração:** com uma mudança aprovada ativa, a sessão principal não edita arquivos do projeto: o hook nega Edit, Write, MultiEdit e NotebookEdit sem `agent_id` no payload e manda delegar ao `aifw-executor`, ou ao `aifw-quick` numa tarefa rápida (ADR-0040). Subagentes (payload com `agent_id`), a pasta `.aifw/changes/active/` e arquivos fora do projeto seguem livres, assim como os caminhos de `orchestration.sessionPaths` no `permissions.yaml` (mesmo casamento do plano aprovado: arquivo, pasta ou padrão). `orchestration.mode: off` desliga a regra; o padrão é `required`.
- **Subagentes:** os hooks valem dentro deles, então nenhum subagente local passa do teto do agente pai. A escolha do modelo fica a critério do agente, seguindo a tabela de modelos da skill e os subagentes por papel (ADR-0037, ADR-0038). O hook reconhece o subagente pelo `agent_type` da chamada: aos revisores `aifw-adversary` e `aifw-qa` ele nega editar arquivos do projeto além do `independent-review.md` da mudança e rodar comando que escreve, commita ou muda o repositório; leitura, testes, `aifw`, código opaco e arquivos fora do projeto seguem. Delegar a uma sessão na nuvem (`isolation: remote`) pede confirmação, porque ela roda fora destes hooks.
- **Break-glass:** `aifw break-glass grant --incident <id> --scope git-remote,deploy --reason ... --by human:<nome> --hours 4` libera esses tipos de ação até expirar, se `breakGlass.enabled` estiver ativo. Não libera arquivos de controle, impasses nem aprovações.

O hook lê o comando como um shell leria: respeita aspas, separa as partes ligadas por `&&`, `;` e `|`, ignora as opções globais do git (`git -C . push` é um push) e analisa o conteúdo de `bash -c "..."`. Texto entre aspas não conta como comando, então `grep "git push" notas.txt` é só uma leitura. `cmd /c` e `powershell -Command` são analisados até o fim da linha, assim como o conteúdo de `$(...)`, crases e blocos `{ }`. Programa vindo de variável (`$G push`), `Invoke-Command` e blocos do PowerShell pedem confirmação. `printenv`, `env`, `set` e `env:` contam como leitura de segredo, e `git commit -S` pede confirmação, porque commit assinado é a prova de aprovação. Código que o hook não consegue ler pede confirmação, a menos que `permissions.yaml` tenha `opaqueCode: allow` (ADR-0025): `eval`, `Start-Process`, `xargs`, comandos codificados, texto enviado para um shell por pipe, subcomandos desconhecidos do git (que podem ser aliases) e programas que dirigem um terminal falso (`expect`, `unbuffer`, `socat`, `winpty`, `script` sem comando). O comando de `script -c` é analisado. Em `python -c` e `node -e`, o hook lê o código: cálculo e leitura passam, escrita em arquivo conta como escrita, rede como escrita externa, e executar outros programas (`subprocess`, `child_process`, `eval`) pede confirmação; Perl e Ruby sempre pedem. O conteúdo de blocos `{ }` é analisado como comando comum. Publicação (`npm publish`, `docker push`, `twine upload`, `uv publish`, `poetry publish`, `dotnet nuget push`, `gh release create`, `gradle publish`, `mvn deploy` e afins) sempre pede confirmação, mesmo com o registro na allowlist, e é negada com dados `confidential` ou `restricted`. Acesso remoto (`ssh`, `scp`, `rsync`, `Invoke-Command -ComputerName`) é escrita externa, que fora da allowlist pede confirmação (é negada com dados `restricted`); instalação de pacote, programa ou projeto novo (`pip install`, `npm install`, `uv add`, `uv tool install`, `npx`, `uvx`, `winget`, `choco`, `brew`, `npm create`, `git clone`) sempre pede confirmação, mesmo com o serviço na allowlist, exceto pacotes listados em `trustedPackages` no `permissions.yaml`, como o `ctx7`; `uv sync`, que só instala o que o `uv.lock` já fixou, é liberado. Criar ou reescrever commits (`git commit`, `merge`, `rebase`, `cherry-pick`, `revert`, `am`) também pede confirmação (ADR-0025), a menos que `permissions.yaml` tenha `commits: allow` (ADR-0030); mesmo assim, o commit pede confirmação quando estiver alterado um arquivo que, assinado, valeria como aprovação (Charter, adoção, impasses, waivers, break-glass) ou a própria política (`aifw.yaml`, `permissions.yaml`, `routing.yaml`, `gates.yaml`, `project-rules.yaml`, `.claude/settings*.json`). O resto não entra nessa conta: o `change.yaml` aprovado, a evidência de `aifw validate --write`, as specs gravadas pelo archive e arquivos gerados. A aprovação de mudança não depende de assinatura (ADR-0037). Com `remoteMutation: branches` (ADR-0037), push para uma branch de trabalho, PR e comentário em PR rodam sem perguntar, mesmo sem `github` em `spec.externalAllowlist` (com dados `confidential`, o GitHub precisa estar na allowlist; com `restricted`, escrita externa é sempre negada); pedem confirmação:
- push para a branch padrão, que é a do `refs/remotes/<remoto>/HEAD`; sem ela (remoto por URL ou adicionado à mão), todo push pede, e `git remote set-head origin --auto` resolve;
- push sem destino quando a configuração o leva à branch padrão (`remote.*.push`, `push.default=matching`, upstream na branch padrão) ou saindo dela;
- padrões (`refs/heads/*`), `--all`, `--branches`, `--mirror`, `--prune`, tags (`--tags`, `v1.0`, `refs/tags/...`, `tag v1.0`) e `git -c ... push`;
- force push (inclusive `-fu`), `git send-pack`, apagar branch remota, `gh pr merge` e escritas na API do GitHub (`gh api`, `curl api.github.com`) fora de PR, issue, revisão e comentário.

Rodar o `aifw-hook` ou `python -m aifw.hooks` à mão, abrir outra sessão com `claude -p`, ou código que monta uma mensagem `UserPromptSubmit` é negado: seria o agente respondendo no lugar da pessoa. Para liberar acesso remoto, inclua `remote-host` em `spec.externalAllowlist`. A allowlist casa por domínio, não por pedaço do nome: `github` vale para `github.com`, `githubusercontent.com` e `githubassets.com`, nunca para `github.attacker.example`. Um nome com ponto é o próprio domínio; outros nomes são definidos em `serviceDomains` no `permissions.yaml`. Em `python publicar.py` ou `node script.js`, o hook lê o arquivo do script com as mesmas regras do código inline. O código rodado de forma indireta também é lido (ADR-0034):
- scripts de shell, PowerShell e `.bat` (`bash x.sh`, o próprio `x.sh` executado pelo caminho, `source x.sh`, `pwsh -File x.ps1`, `cmd /c call x.bat`) são analisados como comandos, e os scripts que eles chamam também;
- `uv run x.py`, `x.py` executado pelo caminho, `python x` (sem extensão) e módulos do projeto em `python -m <módulo>`;
- os scripts do `package.json` rodados por `npm`, `pnpm`, `yarn` ou `bun` (`run X`, `test`, `start`, `yarn X`, `bun X`, `npm version`), com `preX` e `postX`, inclusive com `--prefix`;
- os comandos do `Makefile` rodados por `make`: as receitas dos alvos pedidos e de seus pré-requisitos, comandos depois de `;`, `$(shell ...)` e `!=`, com as variáveis expandidas;
- `git config`, `git -c` e `git --config-env` com uma configuração que faz o git rodar outro programa (`alias.*`, `core.hooksPath`, `core.sshCommand`, `diff.external`, `hook.*`, `credential.*`, `filter.*` e afins) pedem confirmação. A leitura (`--get`, `--list`) continua livre.

O hook falha fechado: pede confirmação, como código que ele não lê, para:
- arquivo do projeto executado em Perl ou Ruby, binário, ou sem linguagem reconhecível pela extensão ou pelo `#!`;
- script que ainda não existe, ou que outra parte do mesmo comando altera (`printf ... > x.sh && bash x.sh`), porque o hook lê o arquivo antes de o comando rodar;
- código vindo da entrada padrão (`echo ... | python -`), `env -S` e `package.json` que não se lê;
- Makefile com `include`, `define`, `SHELL` ou funções como `eval` e `call`;
- variáveis que fazem um programa executar outro, na linha ou em `export` (`GIT_SSH_COMMAND`, `GIT_CONFIG_*`, `NODE_OPTIONS`, `BASH_ENV`, `npm_config_*`), `--script-shell` ou `script-shell` no `.npmrc`, e `make SHELL=`, `--eval` ou `-e`. Módulos de `node -r ./x.js` são lidos.

Ferramentas em `.venv/`, `node_modules/` e `.tox/` e programas fora da pasta do projeto rodam sem leitura. Editar essas pastas com as ferramentas de edição pede confirmação. Um wrapper de teste (`./gradlew test`) só roda sem leitura quando está no git e inalterado. Scripts do PowerShell que usam variáveis (`$x = ...`) quase sempre pedem confirmação.

O hook protege contra erros do agente e caminhos óbvios, não é um sandbox contra um agente determinado a contorná-lo: a contenção de verdade é o sandbox do sistema operacional do Claude Code (ADR-0034). Continuam invisíveis, como risco aceito:
- o código de teste que os executores de teste rodam;
- os módulos que um script importa;
- scripts rodados depois de um `cd`;
- variáveis de ambiente exportadas antes (`GIT_SSH_COMMAND`, `export CC=...`).

Consulte o [ADR-0019](decisions/ADR-0019-hook-hardening.md) e o [ADR-0034](decisions/ADR-0034-hook-indirect-code.md).

### Aprovações

Mudanças L2 e L3 são aprovadas no chat (ADR-0037). O agente apresenta o plano e roda `aifw spec request-approval <id>`. Na mensagem seguinte da pessoa, o hook `UserPromptSubmit` decide:
- uma resposta que começa com "sim", "aprovo", "ok", "pode", "pode sim" ou "pode seguir" (também depois de "Perfeito,", "Beleza," ou "Ótimo,"), sem pergunta e sem ressalva ("mas", "porém", "antes", "espera", "ainda não", "não faça", "só depois"), aprova a mudança inteira; um "não" solto, como em "sim, não tenho objeções", não é ressalva. O hook grava `approval.md` com a mensagem citada e a identidade do `git config user.name`;
- qualquer outra resposta cancela o pedido, e o hook avisa o agente para ajustar o plano e pedir de novo;
- com dois pedidos pendentes, nenhum é aprovado;
- só conta o pedido feito na mesma sessão do chat: o hook anota em `.aifw/runs/approvals/<id>.session` a sessão que rodou o comando; uma resposta em outra sessão não o aprova nem o cancela;
- enquanto o pedido espera, o agente daquela sessão fica congelado: o hook nega qualquer ferramenta até a resposta, então a mensagem seguinte da pessoa é sempre a resposta ao plano.

O agente não consegue escrever `approval.md` nem o `change.yaml` sem confirmação, e mensagens automáticas não contam. Isso protege contra erro do agente, não contra um agente decidido a forjar a aprovação (ADR-0034, ADR-0037). Depois de aprovada, a mudança não pede novas aprovações, salvo as ações que já pedem confirmação por conta própria.

Os outros comandos de aprovação (`intake approve`, `adopt approve`, `decision approve`, `spec approve`, `impasse decide`, `waiver add`, `break-glass grant`) só funcionam no terminal da pessoa que aprova:

- o CLI recusa quando roda no shell do agente: sem janela de console no Windows, sem `/dev/tty` nos outros sistemas, ou com `CLAUDECODE=1`;
- antes de gravar, pede que a pessoa digite o id do projeto.

O agente mostra o comando, e você o roda no seu terminal; no app desktop, serve o painel Terminal.

Para uma prova mais forte, ative `approvals.requireSignedCommit: true` em `.aifw/permissions.yaml`. A partir daí, Charter, waivers e break-glass só valem se o arquivo estiver num commit assinado (`git commit -S`) e inalterado desde então. O agente consegue escrever arquivos, mas não consegue assinar um commit com uma chave cuja senha só você conhece. Para isso valer, o gpg-agent não pode guardar a senha em cache: use `default-cache-ttl 0` e `max-cache-ttl 0` em `gpg-agent.conf`. O modo cobre Charter, adoção, waivers, break-glass e decisões de impasse; a aprovação de mudança pelo chat não depende dele (ADR-0037). Decisões de arquitetura são registros: o AIFW não as usa para liberar nenhuma ação.

### Caminhos protegidos e break-glass

`protectedPaths` no `permissions.yaml` lista pastas ou arquivos que o hook trata como arquivos de controle; cada alteração pede confirmação. No repositório do próprio AIFW, `python/aifw/` deixou de ser protegido em 2026-10-18 (ADR-0025): as mudanças nesse código ficam registradas nos commits, que a pessoa revisa. Cada ação liberada por um break-glass é registrada em `.aifw/break-glass/<incidente>.log`.

### Projeto clonado sem o AIFW

Se o `aifw-hook` não estiver instalado, o hook de antes de cada ação bloqueia e explica como instalar. O de início de sessão avisa o Claude, que repassa a instrução. Os demais hooks ficam em silêncio. No Windows, os hooks rodam no Git Bash, que vem com o Git.

## Skills auxiliares

A skill `aifw-workflow` delega duas etapas a skills do host ([ADR-0013](decisions/ADR-0013-skill-delegation.md)):

- `grilling` (ou `grill-me`) conduz a entrevista do intake;
- `code-review` revisa o diff, usando `principle-catalogs/` como fonte de padrões.

Sem essas skills instaladas, o agente segue o mesmo método manualmente.

## Modelos

O Claude Code não troca o modelo da sessão por comando do AIFW. `aifw route explain` recomenda FAST/WORK/BRAIN (haiku/sonnet/opus), e a skill usa essa recomendação ao delegar trabalho a subagentes. Consulte [Roteamento](routing.md).

O `aifw claude enable` instala subagentes por papel (ADR-0038). O modelo e o esforço ficam na definição, então o agente delega pelo nome sem precisar lembrar de passá-los:

| Subagente | Modelo | Esforço | Papel |
| --- | --- | --- | --- |
| `aifw-explorer` | haiku | low | busca só de leitura no código |
| `aifw-quick` | haiku | low | tarefas do caminho FAST |
| `aifw-executor` | sonnet | medium | caminho WORK e planos do Opus |
| `aifw-adversary` | opus | high | revisão: tenta provar que a mudança está errada |
| `aifw-qa` | sonnet | high | revisão: confere critérios, evidências e documentação |

O caminho do avaliador de tarefas já nomeia o subagente. A revisão independente de L2/L3 tem duas etapas, que são os dois eixos do `code-review`, cada uma no próprio contexto: o `aifw-adversary` faz o eixo Spec e só reprova com um cenário concreto que falha, dentro da spec e do modelo de ameaça; sem achado provado, o `aifw-qa` faz o eixo Standards, confere a entrega e escreve o `Resultado:`. Nenhum dos dois tem a ferramenta `Agent`, então não lançam subagentes, que rodariam no modelo da sessão e fora da trava dos revisores. Depois de duas rodadas de correção, uma terceira reprovação para a revisão e leva o caso à pessoa. Passar `model` na chamada sobrepõe a definição, por isso a skill só o usa para subir de modelo.
