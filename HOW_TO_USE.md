# Como usar o AIFW

Documentação existente e instruções para agentes: [contexto por tarefa](docs/context-intelligence.md).

Guia do AIFW v0.4.0. O núcleo e a CLI usam Python 3.11+, sem Node.js. O agente executa os comandos; o humano fornece contexto, revisa propostas e aprova decisões.

## Preparar o ambiente

Na pasta do AIFW, com uv instalado:

```powershell
uv sync --locked --extra dev
uv run --no-sync python -m pytest -q
uv run --no-sync aifw --version
```

Para ter `aifw` disponível fora dessa pasta:

```powershell
uv tool install .
aifw claude install
aifw --version
```

`aifw claude install` coloca o comando `/aifw` no Claude Code. Ele não liga nada sozinho: o AIFW só é habilitado num projeto quando você digita `/aifw new` ou `/aifw adopt`.

Também é possível instalar com `python -m pip install .`. No ambiente virtual deste checkout, o executável Windows é `.venv/Scripts/aifw.exe`. Ative o ambiente ou use o caminho absoluto ao trabalhar em outro projeto.

## Integração com Claude Code

Na pasta do projeto, abra o Claude Code e digite `/aifw new` (projeto do zero) ou `/aifw adopt` (projeto existente). O hook e a skill `aifw-workflow` ficam gravados em `.claude/` do próprio projeto. Veja [instalação e uso no Claude Code](docs/claude-code.md).

## Skills, plugins e MCPs

Instale tudo no escopo do usuário (vale para todos os projetos). Skills usam o [CLI `skills`](https://github.com/vercel-labs/skills); plugins usam o comando `/plugin` dentro do Claude Code. Se `claude-plugins-official` não estiver disponível, rode antes `/plugin marketplace add anthropics/claude-plugins-official`.

### Obrigatórios

| Item | Para quê | Instalação |
| --- | --- | --- |
| Python 3.11+, [uv](https://docs.astral.sh/uv/), Claude Code | executar o CLI e o agente | instaladores oficiais |
| [Git](https://git-scm.com/) | o AIFW usa o git para saber quais arquivos fazem parte do projeto (respeitando o `.gitignore`) e para derivar sinais de risco do diff; o `/aifw` roda `git init` se o projeto ainda não tiver | instalador oficial |
| CLI do AIFW | `aifw`, `aifw-hook` e o comando `/aifw` | `uv tool install <pasta-do-aifw>` e `aifw claude install` |
| `grilling` e `grill-me` | entrevista do intake | ver comando abaixo |
| `code-review` | revisão de princípios contra `principle-catalogs/` | ver comando abaixo |
| `setup-matt-pocock-skills` | o `code-review` exige `docs/agents/issue-tracker.md`, criado por ela; rode `/setup-matt-pocock-skills` uma vez por projeto | ver comando abaixo |
| `handoff` | passar o trabalho para outra sessão | ver comando abaixo |

```bash
npx skills add mattpocock/skills --skill grilling --skill grill-me --skill code-review --skill setup-matt-pocock-skills --skill handoff -g -a claude-code -y
```

Sem essas skills o AIFW funciona, mas a entrevista e a revisão ficam manuais.

### Recomendados

**Fluxo e qualidade**

| Item | Para quê | Instalação |
| --- | --- | --- |
| superpowers | depuração sistemática, TDD, verificação antes de concluir, planos executados por subagentes; combina com impasse, evidência e a tabela de modelos | `npx skills add obra/superpowers -g -a claude-code -y` |
| ponytail | menor mudança completa, sem código especulativo | `/plugin marketplace add DietrichGebert/ponytail` e `/plugin install ponytail@ponytail` |
| mattpocock/skills (demais) | `domain-modeling`, `codebase-design`, `improve-codebase-architecture`, `to-spec`, `to-tickets`, `triage`, `prototype`, `research`, `pr`, `retro`, `git-guardrails-claude-code`, `setup-pre-commit` | `npx skills add mattpocock/skills --skill <nome> -g -a claude-code -y` |
| wshobson/agents | `architecture-decision-records` e `openapi-spec-generation`, para ADRs e contratos | `npx skills add wshobson/agents --skill architecture-decision-records --skill openapi-spec-generation -g -a claude-code -y` |
| claude-code-setup | recomenda hooks, skills e MCPs para o projeto | `/plugin install claude-code-setup@claude-plugins-official` |
| Instruções universais | regras de comunicação, fatos e verificação | copie [AGENTS.md](AGENTS.md) para `~/.claude/CLAUDE.md` |

**Segurança** (threat model e revisão independente em L2/L3)

| Item | Para quê | Instalação |
| --- | --- | --- |
| Trail of Bits | `static-analysis`, `insecure-defaults`, `supply-chain-risk-auditor`, `differential-review`, `sharp-edges` | `/plugin marketplace add trailofbits/skills` e `/plugin install <nome>@trailofbits` |
| security-guidance | avisos de segurança durante edições e revisão do diff | `/plugin install security-guidance@claude-plugins-official` |

**Pesquisa e documentação**

| Item | Para quê | Instalação |
| --- | --- | --- |
| Context7 | documentação atual de bibliotecas | `npx ctx7@latest library <nome> "<pergunta>"`; sem instalação |
| Firecrawl | pesquisa e extração na web; exige chave da Firecrawl | `npx skills add firecrawl/skills -g -a claude-code -y` |
| find-skills | descobrir novas skills | `npx skills add vercel-labs/skills --skill find-skills -g -a claude-code -y` |
| caveman | respostas curtas quando pedido | `npx skills add juliusbrussee/caveman -g -a claude-code -y` |

**Web, mobile e design** (profiles `web-ts` e `flutter-mobile`)

| Item | Instalação |
| --- | --- |
| `impeccable` | `npx skills add pbakaus/impeccable -g -a claude-code -y` |
| `ui-ux-pro-max` | `npx skills add nextlevelbuilder/ui-ux-pro-max-skill -g -a claude-code -y` |
| `frontend-design` | `npx skills add anthropics/skills --skill frontend-design -g -a claude-code -y` |
| `web-design-guidelines`, `vercel-react-best-practices` | `npx skills add vercel-labs/agent-skills --skill web-design-guidelines --skill vercel-react-best-practices -g -a claude-code -y` |
| `shadcn` | `npx skills add shadcn-ui/ui -g -a claude-code -y` |
| `design-motion-principles` | `npx skills add kylezantos/design-motion-principles -g -a claude-code -y` |
| `design-mobile-apps` | `npx skills add designed-by-ai/skills --skill design-mobile-apps -g -a claude-code -y` |
| Figma (plugin com MCP; exige autorização da conta) | diretório de plugins do Claude |

**Dados, documentos e produto**

| Item | Instalação |
| --- | --- |
| `supabase`, `supabase-postgres-best-practices` | `npx skills add supabase/agent-skills -g -a claude-code -y` |
| `docx`, `pdf`, `pptx`, `xlsx`, `skill-creator` | `npx skills add anthropics/skills --skill docx --skill pdf --skill pptx --skill xlsx --skill skill-creator -g -a claude-code -y` |
| `copywriting` | `npx skills add coreyhaines31/marketingskills --skill copywriting -g -a claude-code -y` |

### MCPs

| MCP | Para quê | Instalação |
| --- | --- | --- |
| markitdown | converter PDF, DOCX, XLSX e outros arquivos em Markdown | `claude mcp add markitdown -s user -- uvx markitdown-mcp` |
| Figma | arquivos de design e tokens | vem com o plugin Figma |

O navegador e o controle do computador já vêm no app desktop do Claude. Context7 e Firecrawl são usados por CLI, não por MCP.

## Atualizar o ambiente local

```powershell
uv sync --locked --extra dev
uv run --no-sync python -m pytest -q
uv run --no-sync python scripts/generate_cli_reference.py --check
uv run --no-sync python -m build --no-isolation
```

Se usar uma instalação separada, reinstale o wheel recém-gerado nela. A instalação local não publica o pacote em nenhum serviço.

## Primeiro uso em um projeto Flutter existente

Abra o PowerShell na raiz do projeto, onde está o `pubspec.yaml`:

```powershell
Set-Location "C:\caminho\para\meu_app"
aifw init --id meu-app --name "Meu App" --flutter --existing
aifw doctor
aifw audit --json
aifw adopt analyze --write
aifw adopt apply
aifw adopt approve --by "human:proprietario"
aifw intake status --json
```

Em seguida, peça ao Claude:

```text
Adote este projeto Flutter existente usando o AIFW. Faça discovery somente
 leitura, persista a proposta brownfield, aplique somente candidatos factuais e
 pare para revisão humana de responsabilidades, owners e relações. Depois
 conclua o intake, atualize PROJECT_MAP e effective policy e execute os gates
 proporcionais ao impacto. Não invente arquitetura a partir de nomes de pastas.
```

O `init` não reorganiza o código Flutter nem escolhe automaticamente Riverpod, Bloc, Clean Architecture ou outra arquitetura. Ele cria o plano de controle. O agente analisa o projeto e usa os catálogos de decisão para recomendar padrões conforme necessidade, trade-offs e evidências.

## Primeiro uso em outros projetos

Projeto Web/React/JavaScript/TypeScript existente:

```powershell
aifw init --id meu-site --name "Meu Site" --web --existing
```

Projeto Python existente:

```powershell
aifw init --id minha-api --name "Minha API" --python --existing
```

Projeto novo:

```powershell
aifw init --id novo-produto --name "Novo Produto" --web
```

Se a stack ainda não foi decidida, omita `--flutter`, `--web` e `--python`. O agente faz discovery/research e recomenda uma opção depois do intake. Use somente uma dessas flags por inicialização.

## Fluxo recomendado após o `init`

```text
1. doctor e audit
2. se existente: adopt analyze → apply → revisão → approve
3. intake status
4. respostas humanas registradas no Charter
5. avaliações técnicas do agente, incluindo princípios e baseline brownfield
6. aprovação humana do Charter
7. decisão arquitetural quando necessária
8. resolve build e map build
9. classificação L0-L3 da mudança
10. spec new → delta → tasks → trace para mudanças proporcionais ao risco
11. implementação, testes, spec validate/analyze e quality gates
12. spec ready/archive, map check, resolve check e documentação atualizada
```

Comandos típicos:

```powershell
aifw doctor
aifw audit --json
aifw adopt analyze --write
aifw adopt apply
aifw adopt approve --by "human:proprietario"
aifw intake status --json
aifw intake approve --by "human:proprietario"
aifw resolve build
aifw map build
aifw change classify --behavior-change --local-only --reversible
aifw spec new add-feature --title "Add feature" --summary "Resultado esperado" --level L2
aifw validate --level L1
aifw resolve check
aifw map check
```

O campo `ready` do intake significa “o Charter pode receber aprovação humana”. O campo `complete` significa “decisões humanas e avaliações técnicas do agente estão concluídas”. O agente conduz a entrevista com a skill `grilling`, usando as perguntas de `intake status`. Você não precisa escolher manualmente SOLID ou Clean Code; o agente revisa o diff com a skill `code-review` contra `principle-catalogs/` e apresenta findings concretos.

## Ajuda e saída JSON

Para descobrir a sintaxe atual:

```powershell
aifw --help
aifw init --help
aifw route activate --help
```

A referência literal gerada de todos os comandos e opções está em [docs/cli-reference.generated.md](docs/cli-reference.generated.md).

Quase todos os comandos aceitam `--json`. Use essa opção para agentes, scripts e CI, porque a saída é estável e estruturada.

| Código | Significado |
| --- | --- |
| `0` | comando concluído ou verificação aprovada |
| `2` | comando válido, mas estado ainda incompleto, desatualizado ou bloqueado |
| `1` | erro de entrada, contrato, configuração ou execução |

## Referência completa dos comandos

### `aifw init`

Inicializa o AIFW na pasta atual. Cria `aifw.yaml`, `.aifw/`, `PROJECT_MAP.md`, diretórios de documentação e contratos. Recusa sobrescrever um projeto já inicializado.

```powershell
aifw init --id app --name "Projeto" --flutter --existing `
  --locale pt-BR --primary windows --targets windows,wsl,linux-ci
```

Opções principais:

- `--id`: identificador estável, curto e sem espaços;
- `--name`: nome humano do projeto;
- `--existing`: informa que já existe uma base de código;
- `--flutter`, `--web` ou `--python`: profile primário, no máximo um;
- `--primary`: ambiente cotidiano (`windows`, `wsl` ou `linux`);
- `--targets`: ambientes que deverão ser validados;
- `--locale`: idioma dos artefatos do projeto.

### `aifw audit`

Faz discovery somente leitura. Detecta stack, scripts, dependências, CI, contratos, ADRs, estrutura Flutter e freshness do mapa. Não documenta automaticamente responsabilidades sem evidência.

```powershell
aifw audit --json
```

### `aifw adopt analyze`

Analisa um projeto marcado `--existing`. Sem `--write`, é totalmente read-only; com `--write`, persiste um relatório factual e seu digest sem alterar catálogo, mapa ou aplicação.

```powershell
aifw adopt analyze --json
aifw adopt analyze --write
```

### `aifw adopt apply`, `status` e `approve`

`apply` mescla candidatos factuais no catálogo, escreve `docs/architecture/discovered.md` e recompila o mapa. Eles permanecem `confidence: candidate` até revisão humana.

```powershell
aifw adopt apply
aifw adopt status
aifw adopt approve --by "human:proprietario"
```

`approve` confirma o digest revisado e não pode ser executado por uma identidade `agent:`. Edição posterior em candidato confirmado torna o status inválido; refaça `apply` + revisão. Refaça também a análise após mudanças estruturais importantes.

### `aifw spec`

Gerencia a verdade comportamental e o contexto completo de uma mudança:

```powershell
aifw spec new add-search --title "Adicionar busca" --summary "Busca autorizada" --level L2
aifw spec list
aifw spec show add-search
aifw spec validate add-search
aifw spec analyze add-search
aifw spec sync add-search --dry-run
aifw spec status add-search --set ready
aifw spec archive add-search
```

Edite os arquivos criados em `.aifw/changes/active/add-search/`. `validate` confere deltas contra `.aifw/specs/current/`; `analyze` confere a cadeia requisito–tarefa–cenário–teste/evidência; `sync` sempre é preview; `archive` revalida, atualiza current specs de forma atômica e preserva todo o contexto.

Use somente um delta por capability e títulos não vazios. Artefatos `passed` precisam apontar para arquivos existentes dentro do projeto; gates vinculados por `checkedBy` devem estar `passed`. A aprovação L3 e seu registro são conferidos novamente no archive. Se o resultado incluir `cleanupPending`, o commit foi preservado, mas restam arquivos de transação para limpeza após conferência; não repita o archive. Consulte [o lifecycle](docs/spec-lifecycle.md) para limites e recuperação.

Mudança L3 também exige:

```powershell
aifw spec approve change-core --by "human:proprietario" --record docs/adr/ADR-0042-core.md
```

### `aifw intake status`

Mostra perguntas humanas ainda ausentes, unknowns bloqueantes e avaliações pertencentes ao agente. As perguntas são a fronteira inicial da entrevista conduzida pela skill `grilling`.

```powershell
aifw intake status --json
```

Estados da avaliação técnica: `pending`, `current`, `stale` e `invalid`. Retorna código 2 enquanto `complete` for falso.

### `aifw intake approve`

Aprova o Project Charter quando as decisões humanas estão prontas. A identidade deve começar com `human:`. A aprovação não autoriza automaticamente deploy, gastos ou mudanças futuras.

```powershell
aifw intake approve --by "human:proprietario"
```

`--at` permite informar um timestamp ISO-8601; sem ele, a CLI usa o instante atual.

### `aifw map build`

Recompila `PROJECT_MAP.md` a partir de `.aifw/catalog.yaml`. Use após atualizar módulos, relações, contratos ou fontes de verdade.

```powershell
aifw map build
```

### `aifw map check`

Compara o mapa existente com o catálogo sem reescrevê-lo. Retorna código 2 se estiver desatualizado.

```powershell
aifw map check --json
```

### `aifw decision list`

Lista catálogos arquiteturais disponíveis, drivers e alternativas. Profiles ativos podem adicionar categorias.

```powershell
aifw decision list
aifw decision list --category application-architecture
```

### `aifw decision recommend`

Pontua alternativas usando sinais explícitos, mostra conflitos e dúvidas e, com `--write`, persiste um caso revisável.

```powershell
aifw decision recommend `
  --category application-architecture `
  --signals domain:complex,integrations:many,testability:high `
  --write
```

`--selected` informa decisões já adotadas para detectar incompatibilidades. Uma recomendação não equivale a aprovação.

### `aifw decision approve`

Registra a alternativa escolhida depois de revisão humana. Exige um ADR já existente dentro do projeto.

```powershell
aifw decision approve `
  --category application-architecture `
  --option clean-architecture `
  --by "human:proprietario" `
  --adr docs/adr/ADR-0001-architecture.md
```

Use os IDs realmente retornados por `decision list`; o exemplo não garante que uma opção com esse ID exista no profile atual.

### `aifw principle list`

Lista Clean Code, SOLID e princípios fundamentais, incluindo quando se aplicam, perguntas de revisão, evidências, exceções e riscos de mau uso.

```powershell
aifw principle list
aifw principle list --family solid
```

Famílias aceitas: `clean-code`, `solid` e `foundational`.

A revisão de princípios é feita pela skill `code-review` (eixo Standards), com `principle-catalogs/` como fonte de padrões.

### `aifw resolve build`

Resolve Constitution/core, defaults pessoais opcionais, profiles e regras do projeto. Grava `.aifw/effective-policy.json` e `.aifw/framework.lock.yaml`.

```powershell
aifw resolve build
aifw resolve build --personal "C:\caminho\para\personal-policy.yaml"
```

### `aifw resolve check`

Verifica sem escrever se a policy efetiva e o lock continuam atuais.

```powershell
aifw resolve check --json
```

### `aifw change classify`

Classifica impacto L0–L3 e informa artefatos, gates e rota cognitiva sugerida.

```powershell
aifw change classify --read-only
aifw change classify --docs-only --local-only --reversible
aifw change classify --behavior-change --local-only --reversible
aifw change classify --shared-contract --cross-module
aifw change classify --touches-auth --security-boundary
```

Sinais disponíveis:

- baixo impacto: `--read-only`, `--docs-only`, `--local-only`, `--reversible`;
- estrutural: `--behavior-change`, `--cross-module`, `--shared-contract`, `--global-design-system`;
- risco: `--sensitive-data`, `--external-cost`, `--production`, `--touches-auth`;
- crítico: `--framework-core`, `--constitution`, `--security-boundary`, `--destructive-migration`, `--breaking-contract`, `--irreversible-production`;
- complexidade independente do impacto: `--complexity fast|work|brain`.

### `aifw route explain`

Explica qual rota FAST/WORK/BRAIN é apropriada. O comando só recomenda; não troca o modelo da sessão. Consulte [Roteamento](docs/routing.md).

```powershell
aifw route explain `
  --impact L2 `
  --operation implementation `
  --uncertainty medium `
  --failed-attempts 0
```

Operações: `single-read`, `discovery`, `documentation`, `implementation`, `review`, `research`, `architecture-decision` e `incident-response`. Use `--cross-domain` quando a tarefa atravessar domínios relevantes.

### `aifw route status`

Mostra a policy persistida, aliases, modelos-alvo, modo e evidência de ativação do projeto atual.

```powershell
aifw route status --json
```

Projetos novos começam em `recommendation-only`.

### `aifw route eval`

Executa os casos determinísticos de roteamento e calcula se o relatório atende aos mínimos para ativação.

```powershell
aifw route eval --output .aifw/routing-report.json --json
```

`--cases` permite fornecer outra fixture revisável. Falhas retornam código 2.

### `aifw route activate`

Ativa o roteamento automático somente depois de relatório aprovado e registro humano persistido.

```powershell
aifw route activate `
  --report .aifw/routing-report.json `
  --by "human:proprietario" `
  --record docs/adr/ADR-0008-routing.md
```

Não execute isso apenas para “ligar uma opção”: a ativação exige pelo menos 30 casos, 95% de aprovação, nenhuma falha crítica e evidência humana.

### `aifw intake set`

Grava uma decisão no Charter, validando o schema. Editar um Charter aprovado o devolve a `draft`.

```powershell
aifw intake set --field problem --value "Reduzir o tempo de fechamento do caixa"
aifw intake set --field scope.out --value "[relatórios fiscais]"
```

### `aifw change classify --diff`

Acrescenta aos sinais informados os derivados dos arquivos alterados no git (contratos do catálogo, mais de um componente, autenticação, deploy, governança, só documentação). Os sinais derivados só elevam o nível.

```powershell
aifw change classify --diff
aifw change classify --diff --base main --behavior-change
```

### `aifw waiver` e `aifw break-glass`

Exceções humanas com prazo. Um waiver faz um gate reprovado passar como `waived` até expirar; `manifest`, `human-approval` e os invariantes do core não aceitam waiver. O break-glass libera tipos de ação no hook durante um incidente.

```powershell
aifw waiver add --rule tests --scope ci --reason "runner instável" --expires 2026-10-20T00:00:00Z --by "human:proprietario"
aifw waiver list
aifw break-glass grant --incident inc-42 --scope git-remote,deploy --reason "correção em produção" --hours 4 --by "human:proprietario"
```

### `aifw secrets scan`

Procura segredos nos arquivos do projeto: chaves privadas, tokens da AWS, do GitHub e do Slack, chaves de API e senhas atribuídas em código, além de arquivos como `.env` versionados. Mostra arquivo, linha e tipo, nunca o valor. Uma linha com o comentário `aifw:allow-secret` é ignorada (use em fixtures de teste). É o gate `secret-scan`, obrigatório a partir de L1.

```powershell
aifw secrets scan
```

### `aifw template`

```powershell
aifw template list
aifw template copy --name threat-model.md --change minha-mudanca
aifw template copy --name runbook.md --output docs/runbooks/pagamentos.md
```

### `aifw runs show`

Resume as sessões gravadas pelo hook em `.aifw/runs/`: edições, verificações, falhas e o que violou as regras do fluxo. Retorna código 2 se houver achados.

```powershell
aifw runs show --session latest
```

### `aifw claude check`

Mostra o que falta para o Claude Code operar o AIFW no projeto. `aifw doctor` inclui o mesmo resultado, sem alterar o código de saída.

### `aifw impasse`

Registra tentativas de correção e congela mudanças quando o limite é atingido. Consulte [Prevenção de impasse](docs/impasse-prevention.md).

```powershell
aifw impasse open --id login-radius --impact L2
aifw impasse attempt --id login-radius --hypothesis "..." --intervention "..." --evidence logs/run1.txt --outcome failure
aifw impasse status --json
```

`decide` exige identidade `human:` e um registro existente no projeto. Como todo comando de aprovação, só roda no seu próprio terminal e pede que você digite o id do projeto.

### `aifw doctor`

Verifica Python, Git, Windows e WSL. WSL é tratado como ambiente separado; indisponibilidade do WSL não é confundida com falha do Python no Windows.

```powershell
aifw doctor --json
```

### `aifw eval`

Executa casos de conformidade comportamental contra traces do agente. Serve para verificar se o agente respeita ordem, aprovações, evidências e comportamentos proibidos.

```powershell
aifw eval --json
aifw eval --cases evals/cases --traces evals/traces
```

Este comando é diferente de `route eval`: um testa comportamento geral do agente; o outro testa especificamente decisões de roteamento.

### `aifw validate`

Executa os quality gates selecionados para o nível de impacto.

```powershell
aifw validate --level L0
aifw validate --level L1
aifw validate --level L2
aifw validate --level L3
aifw validate --change <id> --write
```

Com `--change`, o nível e a aprovação vêm da spec change. Além dos gates, o comando confere os artefatos exigidos pelo nível (L2: plano técnico, rollback e revisão independente; L3: também RFC, threat model, migração e ADR) e, com `--write`, grava `evidence/validation.json` com o digest da mudança e do código. `aifw spec archive` exige essa validação sem bloqueios e atual.

- L0: verificações mecânicas proporcionais;
- L1: mudança local e reversível;
- L2: feature, módulo ou contrato compartilhado;
- L3: arquitetura, autenticação, segurança, framework ou mudança crítica.

Gate obrigatório ausente ou sem evidência bloqueia; não vira aprovação implícita.

## O que você precisa decidir e o que o agente decide

Você decide:

- problema, público e resultado esperado;
- o que entra e o que fica fora;
- restrições, dados, riscos e custos;
- autonomia para Git, serviços, preview e produção;
- preferências ou proibições técnicas que realmente existam;
- aprovação de Charter, ADRs e mudanças críticas.

O agente descobre ou recomenda:

- stack quando não foi determinada;
- arquitetura e padrões adequados ao contexto;
- quais princípios são aplicáveis;
- nível L0–L3 e rota FAST/WORK/BRAIN;
- testes, gates, documentação e evidências necessárias.

## Arquivos que você consultará com mais frequência

| Arquivo | Função |
| --- | --- |
| `PROJECT_MAP.md` | entrada rápida para humano ou IA |
| `.aifw/charter.yaml` | decisões do início do projeto |
| `aifw.yaml` | versão, ambientes e profiles |
| `.aifw/catalog.yaml` | fatos que geram o mapa |
| `.aifw/effective-policy.json` | regras efetivas compiladas |
| `.aifw/framework.lock.yaml` | versões e digests fixados |
| `.aifw/gates.yaml` | quality gates |
| `.aifw/permissions.yaml` | autonomia e efeitos colaterais |
| `.aifw/routing.yaml` | política de roteamento do projeto |
| `docs/adr/` | decisões arquiteturais persistidas |

## Manutenção deste guia

`python scripts/generate_cli_reference.py` gera a referência diretamente do parser; use Python 3.13 ou mais novo, porque versões anteriores quebram as linhas de uso de outra forma. O mesmo comando com `--check` detecta divergências. Execute dentro do ambiente instalado, por exemplo com `uv run --no-sync python`.

```powershell
uv run --no-sync ruff check python tests_python scripts setup.py
uv run --no-sync python -m pytest -q
uv run --no-sync python -m build --no-isolation
uv run --no-sync aifw map check
```
