# AIFW — AI Software Engineering Framework

O AIFW é um plano de controle versionado para desenvolvimento de software com agentes. Ele transforma decisões, limites de autonomia, contratos, evidências e qualidade em arquivos e regras executáveis dentro do repositório.

O núcleo é independente do agente. O host de referência é o Claude Code, integrado por skill; outro executor pode entrar da mesma forma, e nenhum fornecedor define a Constitution, o lifecycle L0–L3 ou as fontes de verdade do projeto.

> Estado: `v0.4.1` mais as mudanças em [Não lançado](CHANGELOG.md), control plane funcional. O agente trabalha com autonomia dentro de uma mudança aprovada no chat e só para nas ações que saem do projeto ou não voltam atrás ([ADR-0037](docs/decisions/ADR-0037-agent-autonomy.md)).

## Quando o agente pede sua aprovação

| Pede | Não pede |
| --- | --- |
| plano de uma mudança L2/L3, uma vez, respondido no chat ("sim") | commits |
| instalar pacote, biblioteca, programa ou projeto | push para branch de trabalho, PR e comentário em PR |
| push para a branch padrão, tags, force push, apagar branch remota, merge de PR | escrita em serviço da allowlist do projeto |
| escrever em serviço fora da allowlist (e incluir um domínio novo nela) | delegar trabalho a subagentes (haiku/sonnet/opus) |
| publicar pacote ou release, deploy de produção, ação destrutiva | código opaco (`python -c`, scripts), se o projeto liberar |
| impasse, waiver, break-glass, Charter, adoção e decisões de arquitetura | deploy de preview |

Ler segredos (`.env`, chaves, `printenv`) é sempre negado.

## O que já funciona

- Project Intake adaptativo e Project Charter aprovado por humano;
- manifesto com versão do framework fixada por projeto;
- hierarquia executável de Constitution/core, preferências pessoais, capability profiles, stack profiles e regras do projeto;
- lock determinístico de perfis e effective policy compilada;
- classificação de impacto L0–L3 separada da complexidade FAST/WORK/BRAIN;
- `PROJECT_MAP.md` compilado a partir de catálogo e fontes de verdade;
- contexto por tarefa com dependências, checagem de referências e snapshots documentais;
- blocos de instruções comuns para agentes, preservando o AGENTS universal;
- inspeção estática da ligação entre gates e GitHub Actions, separada da execução;
- ciclo executável de capability specs, deltas, tarefas, evidências e archive atômico;
- analisador de rastreabilidade requisito → cenário → tarefa → teste/gate;
- adoção brownfield em duas fases, com discovery factual, candidatos revisáveis e confirmação humana;
- catálogos globais de decisões que comparam padrões por necessidades, conflitos e trade-offs, com aprovação humana e ADR;
- catálogo global contextual de Clean Code, SOLID, KISS, YAGNI, DRY e separação de responsabilidades, incluindo riscos de uso dogmático;
- quality gates progressivos, distinguindo hard gate, auditoria e aprovação humana;
- máquina de estados para prevenção de impasse e loops de correção;
- política de permissões para Git local/remoto (branches de trabalho livres, branch padrão protegida), deploy, serviços externos com allowlist, publicação, delegação e break-glass;
- integração com o Claude Code ativada por projeto (`/aifw new|adopt`), com skill de fluxo e tabela de modelos FAST/WORK/BRAIN (haiku/sonnet/opus) sempre ligada, e subagentes por papel com modelo e esforço fixos: cascata pela complexidade (rápido, executor, planner, worker, lead; sênior para risco alto em L1), mais explorador e a revisão em duas etapas, adversário e QA (nove papéis);
- hooks que aplicam permissões, impasses e arquivos de controle a cada ação, leem os comandos de shell como um shell (inclusive scripts, `package.json` e `Makefile` que o comando executa), gravam a aprovação do plano a partir da sua resposta no chat e impedem concluir com código não verificado;
- avaliador de tarefas que classifica cada pedido (risco, importância, complexidade) e entrega ao agente o caminho FAST, WORK, PLANNED ou CRITICAL, com piso de risco vindo do diff;
- avaliações em modo sombra por modelo de decisão para impasse, contexto, intake, rastreabilidade e sinais de decisão, com relatório e vereditos humanos;
- validação por mudança (`validate --change`) exigida pelo archive, waivers e break-glass com prazo, secret scan e resumo das sessões (`runs show`);
- testes de conformidade comportamental do agente;
- profile oficial `flutter-mobile`, com descoberta de `pubspec.yaml`, targets Android/iOS e receitas de gates para Windows e macOS;
- seleção direta de stack no `init` por `--flutter`, `--web` ou `--python`, validada antes de qualquer arquivo ser criado;
- diagnóstico Windows/WSL;
- schemas JSON 2020-12, templates de specs/ADRs/C4/OpenAPI/AsyncAPI, segurança, observabilidade e runbooks;
- CI em Windows e Linux.

## Fluxo de um projeto

```text
DISCOVERY (somente leitura) → BASELINE BROWNFIELD, se existente
        ↓
PROJECT INTAKE → PROJECT CHARTER → aprovação humana
        ↓
RESOLUTION → effective-policy + profile lock
        ↓
RESEARCH → SPEC CHANGE + DELTAS → TECHNICAL PLAN
        ↓
CHANGE CASE L0–L3 → plano aprovado no chat (L2/L3)
        ↓
IMPLEMENTAÇÃO → TRACE → TESTES → AUDITORIAS → QUALITY GATES
        ↓
ARCHIVE ATÔMICO → CURRENT SPECS + PROJECT_MAP + ADRs + docs
```

O agente pode descobrir tecnologia e recomendar a stack. O usuário não precisa saber escolher React, Python, banco de dados ou hosting no primeiro contato. O que precisa vir do humano é intenção, limites, risco e autoridade; consulte [Project Intake](docs/project-intake.md).

## Início rápido

Para aproveitar documentação existente, consulte
[Contexto por tarefa e consistência das instruções](docs/context-intelligence.md).

Requisitos: Python 3.11 ou superior. Com uv instalado, prepare o ambiente local:

```powershell
uv sync --locked --extra dev
uv run --no-sync python -m pytest -q
uv run --no-sync aifw --version
```

Para usar em qualquer projeto com o Claude Code:

```powershell
uv tool install .
aifw claude install
```

Depois, na pasta de um projeto, abra o Claude Code e digite `/aifw new` (do zero) ou `/aifw adopt` (projeto existente). O AIFW fica desligado nos demais projetos. Detalhes em [Claude Code](docs/claude-code.md). Skills, plugins e MCPs obrigatórios e recomendados: [HOW_TO_USE](HOW_TO_USE.md#skills-plugins-e-mcps).

Para inicializar um projeto:

```powershell
aifw init `
  --id meu-projeto `
  --name "Meu Projeto" `
  --flutter `
  --existing `
  --primary windows `
  --targets windows,wsl,linux-ci
```

Depois:

```powershell
aifw intake status
aifw adopt analyze --write
aifw adopt apply
aifw map check
aifw resolve build
aifw decision list
aifw decision recommend --category application-architecture --signals domain:complex,integrations:many,testability:high --write
aifw principle list
aifw audit
aifw change classify --behavior-change --local-only --reversible
aifw validate --level L1
aifw eval
aifw doctor
```

A CLI não é uma interface que o usuário final precisa operar diariamente. Ela é o **plano de controle** usado pelo agente, pela CI e por automações para produzir resultados determinísticos. Humanos definem intenção e limites, respondem ao plano e aprovam decisões; o agente executa os comandos por trás do fluxo.

No status do intake, `ready` significa que o Charter está pronto para aprovação humana e `complete` significa que o intake inteiro está concluído. Em projetos existentes, o baseline `brownfield-mapping` aparece em `agentAssessments`; o agente produz as evidências e o humano confirma apenas o que exige julgamento. A entrevista do intake usa a skill `grilling` e a revisão de princípios usa a skill `code-review` sobre o diff ([ADR-0013](docs/decisions/ADR-0013-skill-delegation.md)).

## Estrutura

```text
python/aifw/       regras independentes de fornecedor
schemas/           contratos JSON Schema 2020-12
policies/          invariantes do framework
profiles/          capacidades e stacks opcionais
decision-catalogs/ padrões globais comparáveis por contexto do projeto
principle-catalogs/ princípios globais para revisão contextual
templates/         ADR, spec, plano, contratos e operações
evals/             casos e traces de conformidade do agente
docs/              arquitetura, políticas e decisões
tests_python/      testes unitários e workflows ponta a ponta
```

Em um projeto inicializado:

```text
aifw.yaml                       versão, ambiente, perfis e allowlist
.aifw/charter.yaml              decisões humanas e aprovação
.aifw/catalog.yaml              fonte do PROJECT_MAP
.aifw/effective-policy.json     regras resolvidas, geradas
.aifw/framework.lock.yaml       versão e digests fixados
.aifw/gates.yaml                quality gates progressivos
.aifw/permissions.yaml          limites de efeitos colaterais
.aifw/routing.yaml              aliases e modelos da tabela de roteamento
.aifw/specs/current/             comportamento atualmente aceito
.aifw/changes/active/            propostas, deltas, tarefas e evidências
.aifw/changes/archive/           contexto completo de mudanças concluídas
.aifw/adoption/                  discovery e aprovação brownfield
.aifw/decision-cases/           análises e recomendações reproduzíveis
.aifw/decisions/                escolhas aprovadas por humano e ligadas a ADR
.aifw/project-rules.yaml        exceções/regras específicas, opcional
PROJECT_MAP.md                  entrada compilada para humano ou IA
docs/adr/                       decisões arquiteturais
docs/runbooks/                  operação e recuperação
contracts/                      OpenAPI, AsyncAPI e demais contratos
```

## Python, Flutter, Web e WSL

O núcleo e a CLI usam Python. Os projetos governados podem usar outras stacks: a distribuição mantém profiles Web, Flutter Mobile e Python. Os contratos persistidos continuam em YAML/JSON/Markdown.

O histórico TypeScript foi separado da implementação ativa. Consulte [ADR-0011](docs/decisions/ADR-0011-python-runtime.md) e [Windows e WSL](docs/windows-wsl.md).

## Princípios essenciais

1. Uma conversa com IA nunca é fonte de verdade arquitetural.
2. Descoberta precede recomendação; spec precede implementação quando o risco exige.
3. Impacto L0–L3 e potência cognitiva FAST/WORK/BRAIN são eixos diferentes.
4. Toda permissão delegada a um subagente é limitada pelo teto do agente pai.
5. Um gate obrigatório ausente é bloqueio, não aprovação implícita.
6. Exceções expiram, têm escopo, checkpoint e aprovação.
7. Um possível defeito do framework abre impasse; não autoriza o agente a mudar o framework sozinho.
8. Autonomia no que fica registrado e é reversível; decisão humana no que sai do projeto ou não volta atrás.

## Documentação principal

- [Como usar o AIFW](HOW_TO_USE.md)
- [Integração com Claude Code: instruções e skill](docs/claude-code.md)
- [Constitution](CONSTITUTION.md)
- [Arquitetura](docs/architecture.md)
- [Hierarquia de autoridade](docs/authority.md)
- [Project Intake](docs/project-intake.md)
- [Lifecycle L0–L3](docs/change-lifecycle.md)
- [Prevenção de impasse](docs/impasse-prevention.md)
- [PROJECT_MAP](docs/project-map.md)
- [Quality gates](docs/quality-gates.md)
- [Conformidade do agente](docs/agent-conformance.md)
- [Roteamento FAST/WORK/BRAIN](docs/routing.md)
- [MCPs, skills e extensões](docs/tooling-and-mcps.md)
- [CLI](docs/cli.md)
- [Catálogos de decisões arquiteturais](docs/decision-catalogs.md)
- [Princípios de engenharia](docs/engineering-principles.md)
- [Adoção de projeto existente](docs/existing-project-adoption.md)
- [Ciclo executável de specs](docs/spec-lifecycle.md)
- [Rastreabilidade](docs/traceability.md)
- [Flutter Mobile](docs/flutter-mobile.md)

## Limites deliberados

- O mapeamento brownfield automatiza fatos, não compreensão semântica incerta: responsabilidades, owners, boundaries e fluxos de negócio ainda exigem evidência e revisão.
- O framework não escolhe provedores de produção.
- O hook protege contra erros do agente e caminhos óbvios; não é um sandbox contra um agente determinado a contorná-lo. A contenção de verdade é o sandbox do sistema operacional do Claude Code ([ADR-0034](docs/decisions/ADR-0034-hook-indirect-code.md)).

## Licença

MIT. Consulte [LICENSE](LICENSE).
