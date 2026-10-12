<!-- aifw:project-map digest=a16b86a9c523e6ba7f5998701fd8e22b8dfdc07bac848750cbbe31e4d56c8d00 -->
# PROJECT_MAP — AI Software Engineering Framework

> Compiled entrypoint. Edit authoritative sources, then regenerate this file.

## Project

| Field | Value |
| --- | --- |
| Project ID | aifw |
| Framework | 0.4.0 |
| Verified revision | discovery:84eda1c386f6 |

## Purpose

Tornar desenvolvimento com agentes reproduzível, seguro e independente de fornecedor por meio de decisões e evidências versionadas.

## Sources of truth

| Topic | Source |
| --- | --- |
| Arquitetura | docs/architecture.md |
| Brownfield discovery | .aifw/adoption/discovery.json |
| Capacidades aceitas | .aifw/specs/current/ |
| Catálogo de princípios de engenharia | principle-catalogs/ |
| Catálogos de decisão | decision-catalogs/ |
| Comportamento verificado | tests_python/ |
| Constituição | CONSTITUTION.md |
| Contexto por tarefa | docs/context-intelligence.md |
| Contract templates/asyncapi.yaml | templates/asyncapi.yaml |
| Contract templates/openapi.yaml | templates/openapi.yaml |
| Contrato do pacote | pyproject.toml |
| Contratos de documento | schemas/ |
| Decision docs/decisions/ADR-0001-typescript-cli.md | docs/decisions/ADR-0001-typescript-cli.md |
| Decision docs/decisions/ADR-0002-agent-independent-core.md | docs/decisions/ADR-0002-agent-independent-core.md |
| Decision docs/decisions/ADR-0003-routing-disabled-default.md | docs/decisions/ADR-0003-routing-disabled-default.md |
| Decision docs/decisions/ADR-0004-flutter-mobile-profile.md | docs/decisions/ADR-0004-flutter-mobile-profile.md |
| Decision docs/decisions/ADR-0005-global-decision-catalogs.md | docs/decisions/ADR-0005-global-decision-catalogs.md |
| Decision docs/decisions/ADR-0006-short-stack-flags.md | docs/decisions/ADR-0006-short-stack-flags.md |
| Decision docs/decisions/ADR-0007-contextual-engineering-principles.md | docs/decisions/ADR-0007-contextual-engineering-principles.md |
| Decision docs/decisions/ADR-0008-pi-routing-and-codex-fallback.md | docs/decisions/ADR-0008-pi-routing-and-codex-fallback.md |
| Decision docs/decisions/ADR-0009-executable-spec-core-and-brownfield-adoption.md | docs/decisions/ADR-0009-executable-spec-core-and-brownfield-adoption.md |
| Decision docs/decisions/ADR-0010-spec-archive-integrity.md | docs/decisions/ADR-0010-spec-archive-integrity.md |
| Decision docs/decisions/ADR-0011-python-runtime.md | docs/decisions/ADR-0011-python-runtime.md |
| Decision docs/decisions/ADR-0012-context-intelligence.md | docs/decisions/ADR-0012-context-intelligence.md |
| Decision docs/decisions/ADR-0013-skill-delegation.md | docs/decisions/ADR-0013-skill-delegation.md |
| Decision docs/decisions/ADR-0014-claude-code-host.md | docs/decisions/ADR-0014-claude-code-host.md |
| Decisões | docs/decisions/ |
| Guia operacional | HOW_TO_USE.md |
| Intenção do produto | .aifw/charter.yaml |
| Regras core | policies/core.yaml |

## Catalog

| ID | Kind | Name | Owner | Visibility | Origin | Confidence | Verified | Source | Description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| component:agent-instructions | Component | Shared agent instructions | framework:core | public | manual | confirmed | not-recorded | python/aifw/instructions.py | Generates bounded instruction blocks while preserving user content. |
| component:aifw-root | Component | aifw root module | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | pyproject.toml | Discovered module manifest at pyproject.toml; responsibility requires review. |
| component:brownfield-adoption | Component | Brownfield adoption | framework:core | public | manual | confirmed | not-recorded | python/aifw/brownfield.py | Descobre fatos, persiste candidatos revisáveis e exige confirmação humana antes do baseline aprovado. |
| component:claude-hooks | Component | Claude Code hook | framework:adapters | public | manual | confirmed | not-recorded | python/aifw/hooks.py | aifw-hook aplica a política em cada ação, registra a sessão, bloqueia conclusão sem verificação e informa o estado ao abrir a sessão (ADR-0015, ADR-0018). |
| component:claude-skill | Component | Claude Code skill | framework:adapters | public | manual | confirmed | not-recorded | templates/claude/skills/aifw/SKILL.md | Comando /aifw (new, adopt) que habilita o AIFW por projeto; a skill aifw-workflow do projeto guia o Claude (ADR-0016). |
| component:cli | Component | Control-plane CLI | framework:core | public | manual | confirmed | not-recorded | python/aifw/cli.py | Interface determinística usada por agentes, humanos e CI. |
| component:conformance | Component | Agent conformance evaluator | framework:quality | public | manual | confirmed | not-recorded | python/aifw/conformance.py | Avalia traces contra eventos, ordem, aprovações e evidência esperados. |
| component:context-intelligence | Component | Context intelligence | framework:core | public | manual | confirmed | not-recorded | python/aifw/context.py | Selects documentation, validates references and detects factual snapshot drift. |
| component:core | Component | Vendor-neutral core | framework:core | public | manual | confirmed | not-recorded | python/aifw/ | Intake, authority, lifecycle, gates, map, permissions, impasse, routing e conformance. |
| component:decision-engine | Component | Architecture decision engine | framework:core | public | manual | confirmed | not-recorded | python/aifw/catalogs.py | Classifica alternativas, expõe incerteza e exige aprovação humana com ADR antes de registrar uma escolha. |
| component:principle-review | Component | Engineering principle catalog | framework:quality | public | manual | confirmed | not-recorded | python/aifw/catalogs.py | Publica os princípios versionados; a revisão do diff é feita pela skill code-review (ADR-0013). |
| component:spec-lifecycle | Component | Executable spec lifecycle | framework:core | public | manual | confirmed | not-recorded | python/aifw/specs.py | Valida capability deltas, rastreabilidade e archive atômico contra a verdade comportamental atual. |
| contract:schemas | Contract | Framework document schemas | framework:core | public | manual | confirmed | not-recorded | schemas/ | JSON Schema 2020-12 para documentos públicos do AIFW. |
| contract:templates-asyncapi-yaml | Contract | templates/asyncapi.yaml | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | templates/asyncapi.yaml | Discovered machine-readable contract at templates/asyncapi.yaml. |
| contract:templates-openapi-yaml | Contract | templates/openapi.yaml | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | templates/openapi.yaml | Discovered machine-readable contract at templates/openapi.yaml. |
| decision:agent-independent-core | Decision | Core independente do agente | human:owner | public | manual | confirmed | not-recorded | docs/decisions/ADR-0002-agent-independent-core.md | Governança não depende do executor ou fornecedor. |
| decision:docs-decisions-adr-0001-typescript-cli-md | Decision | docs/decisions/ADR-0001-typescript-cli.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0001-typescript-cli.md | Discovered architecture decision reference at docs/decisions/ADR-0001-typescript-cli.md. |
| decision:docs-decisions-adr-0002-agent-independent-core-md | Decision | docs/decisions/ADR-0002-agent-independent-core.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0002-agent-independent-core.md | Discovered architecture decision reference at docs/decisions/ADR-0002-agent-independent-core.md. |
| decision:docs-decisions-adr-0003-routing-disabled-default-md | Decision | docs/decisions/ADR-0003-routing-disabled-default.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0003-routing-disabled-default.md | Discovered architecture decision reference at docs/decisions/ADR-0003-routing-disabled-default.md. |
| decision:docs-decisions-adr-0004-flutter-mobile-profile-md | Decision | docs/decisions/ADR-0004-flutter-mobile-profile.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0004-flutter-mobile-profile.md | Discovered architecture decision reference at docs/decisions/ADR-0004-flutter-mobile-profile.md. |
| decision:docs-decisions-adr-0005-global-decision-catalogs-md | Decision | docs/decisions/ADR-0005-global-decision-catalogs.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0005-global-decision-catalogs.md | Discovered architecture decision reference at docs/decisions/ADR-0005-global-decision-catalogs.md. |
| decision:docs-decisions-adr-0006-short-stack-flags-md | Decision | docs/decisions/ADR-0006-short-stack-flags.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0006-short-stack-flags.md | Discovered architecture decision reference at docs/decisions/ADR-0006-short-stack-flags.md. |
| decision:docs-decisions-adr-0007-contextual-engineering-principles-md | Decision | docs/decisions/ADR-0007-contextual-engineering-principles.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0007-contextual-engineering-principles.md | Discovered architecture decision reference at docs/decisions/ADR-0007-contextual-engineering-principles.md. |
| decision:docs-decisions-adr-0008-pi-routing-and-codex-fallback-md | Decision | docs/decisions/ADR-0008-pi-routing-and-codex-fallback.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0008-pi-routing-and-codex-fallback.md | Discovered architecture decision reference at docs/decisions/ADR-0008-pi-routing-and-codex-fallback.md. |
| decision:docs-decisions-adr-0009-executable-spec-core-and-brownfield-adoption-md | Decision | docs/decisions/ADR-0009-executable-spec-core-and-brownfield-adoption.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0009-executable-spec-core-and-brownfield-adoption.md | Discovered architecture decision reference at docs/decisions/ADR-0009-executable-spec-core-and-brownfield-adoption.md. |
| decision:docs-decisions-adr-0010-spec-archive-integrity-md | Decision | docs/decisions/ADR-0010-spec-archive-integrity.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0010-spec-archive-integrity.md | Discovered architecture decision reference at docs/decisions/ADR-0010-spec-archive-integrity.md. |
| decision:docs-decisions-adr-0011-python-runtime-md | Decision | docs/decisions/ADR-0011-python-runtime.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0011-python-runtime.md | Discovered architecture decision reference at docs/decisions/ADR-0011-python-runtime.md. |
| decision:docs-decisions-adr-0012-context-intelligence-md | Decision | docs/decisions/ADR-0012-context-intelligence.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0012-context-intelligence.md | Discovered architecture decision reference at docs/decisions/ADR-0012-context-intelligence.md. |
| decision:docs-decisions-adr-0013-skill-delegation-md | Decision | docs/decisions/ADR-0013-skill-delegation.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0013-skill-delegation.md | Discovered architecture decision reference at docs/decisions/ADR-0013-skill-delegation.md. |
| decision:docs-decisions-adr-0014-claude-code-host-md | Decision | docs/decisions/ADR-0014-claude-code-host.md | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | docs/decisions/ADR-0014-claude-code-host.md | Discovered architecture decision reference at docs/decisions/ADR-0014-claude-code-host.md. |
| decision:python-runtime | Decision | CLI e núcleo Python | human:DarkSquash | internal | manual | confirmed | not-recorded | docs/decisions/ADR-0011-python-runtime.md | Migração integral autorizada pelo usuário; ADR-0011. |
| decision:spec-archive-integrity | Decision | Integridade de archive e evidência | human:DarkSquash | internal | manual | confirmed | not-recorded | docs/decisions/ADR-0010-spec-archive-integrity.md | ADR-0010: separar commit de limpeza, revalidar aprovação L3 e impedir deltas/evidências inválidos. |
| profile:flutter-mobile | Resource | Flutter Mobile profile | framework:profiles | public | manual | confirmed | not-recorded | profiles/flutter-mobile/ | Regras e receitas de gates para Dart, Flutter, Android e iOS sem impor arquitetura de pastas ou biblioteca de estado. |
| profile:python | Resource | Python profile | framework:profiles | public | manual | confirmed | not-recorded | profiles/python/ | Regras portáveis de lint, formato, testes, dependências, segurança e observabilidade para projetos Python. |
| profile:web | Resource | Web profile | framework:profiles | public | manual | confirmed | not-recorded | profiles/web-ts/ | Regras de arquitetura, contratos, design, segurança e observabilidade para React, JavaScript, TypeScript e outras stacks Web. |
| resource:context-intelligence | Resource | Context guide | framework:core | public | manual | confirmed | not-recorded | docs/context-intelligence.md | Documents context commands, metadata, limits and opt-in gates. |
| resource:decision-catalogs | Resource | Global decision catalogs | framework:architecture | public | manual | confirmed | not-recorded | decision-catalogs/ | Alternativas arquiteturais comparáveis por sinais explícitos, com conflitos, trade-offs e fontes. |
| resource:evals | Resource | Conformance fixtures | framework:quality | public | manual | confirmed | not-recorded | evals/ | Casos e traces de fumaça para validar o evaluator. |
| resource:existing-project-adoption | Resource | Existing-project adoption guide | framework:docs | public | manual | confirmed | not-recorded | docs/existing-project-adoption.md | Fluxo factual de analyze, apply e human approval para projetos brownfield. |
| resource:github-workflows-ci-yml | Resource | .github/workflows/ci.yml | human:DarkSquash | internal | discovered | confirmed | 2026-10-11T22:15:58.585Z | .github/workflows/ci.yml | Discovered continuous-integration configuration at .github/workflows/ci.yml. |
| resource:how-to-use | Resource | AIFW operational guide | framework:docs | public | manual | confirmed | not-recorded | HOW_TO_USE.md | Instalação, fluxos recomendados, referência completa da CLI e comandos da extensão do Pi. |
| resource:policies | Resource | Core policies | framework:governance | public | manual | confirmed | not-recorded | policies/core.yaml | Invariantes executáveis alinhados à Constitution. |
| resource:principle-catalogs | Resource | Engineering principle catalogs | framework:quality | public | manual | confirmed | not-recorded | principle-catalogs/ | Clean Code, SOLID e princípios fundamentais aplicados por sinais, perguntas, evidências, exceções e riscos de mau uso. |
| resource:profiles | Resource | Optional profiles | framework:profiles | public | manual | confirmed | not-recorded | profiles/ | Capability e stack rules selecionadas após intake/discovery. |
| runtime:python | Runtime | Python | framework:runtime | public | manual | confirmed | not-recorded | pyproject.toml | Runtime do CLI e núcleo, Python 3.11 ou superior, independente de Node.js. |
| system:aifw | System | AIFW | human:owner | public | manual | confirmed | not-recorded | CONSTITUTION.md | Framework independente de agente para governança e execução verificável de engenharia de software. |

## Relationships

| Source | Relation | Target |
| --- | --- | --- |
| component:agent-instructions | partOf | system:aifw |
| component:aifw-root | partOf | system:aifw |
| component:brownfield-adoption | documentedBy | resource:existing-project-adoption |
| component:brownfield-adoption | partOf | component:core |
| component:claude-hooks | dependsOn | component:core |
| component:claude-hooks | partOf | system:aifw |
| component:claude-skill | dependsOn | component:cli |
| component:claude-skill | partOf | system:aifw |
| component:cli | dependsOn | component:core |
| component:cli | documentedBy | resource:how-to-use |
| component:cli | partOf | system:aifw |
| component:conformance | consumes | resource:evals |
| component:conformance | partOf | component:core |
| component:context-intelligence | partOf | system:aifw |
| component:core | partOf | system:aifw |
| component:core | provides | contract:schemas |
| component:decision-engine | consumes | resource:decision-catalogs |
| component:decision-engine | partOf | component:core |
| component:principle-review | consumes | resource:principle-catalogs |
| component:principle-review | partOf | component:core |
| component:spec-lifecycle | consumes | contract:schemas |
| component:spec-lifecycle | partOf | component:core |
| contract:schemas | partOf | system:aifw |
| contract:templates-asyncapi-yaml | partOf | system:aifw |
| contract:templates-openapi-yaml | partOf | system:aifw |
| decision:agent-independent-core | partOf | system:aifw |
| decision:docs-decisions-adr-0001-typescript-cli-md | partOf | system:aifw |
| decision:docs-decisions-adr-0002-agent-independent-core-md | partOf | system:aifw |
| decision:docs-decisions-adr-0003-routing-disabled-default-md | partOf | system:aifw |
| decision:docs-decisions-adr-0004-flutter-mobile-profile-md | partOf | system:aifw |
| decision:docs-decisions-adr-0005-global-decision-catalogs-md | partOf | system:aifw |
| decision:docs-decisions-adr-0006-short-stack-flags-md | partOf | system:aifw |
| decision:docs-decisions-adr-0007-contextual-engineering-principles-md | partOf | system:aifw |
| decision:docs-decisions-adr-0008-pi-routing-and-codex-fallback-md | partOf | system:aifw |
| decision:docs-decisions-adr-0009-executable-spec-core-and-brownfield-adoption-md | partOf | system:aifw |
| decision:docs-decisions-adr-0010-spec-archive-integrity-md | partOf | system:aifw |
| decision:docs-decisions-adr-0011-python-runtime-md | partOf | system:aifw |
| decision:docs-decisions-adr-0012-context-intelligence-md | partOf | system:aifw |
| decision:docs-decisions-adr-0013-skill-delegation-md | partOf | system:aifw |
| decision:docs-decisions-adr-0014-claude-code-host-md | partOf | system:aifw |
| decision:python-runtime | partOf | system:aifw |
| decision:spec-archive-integrity | partOf | system:aifw |
| profile:flutter-mobile | dependsOn | component:core |
| profile:flutter-mobile | partOf | resource:profiles |
| profile:python | dependsOn | component:core |
| profile:python | partOf | resource:profiles |
| profile:web | dependsOn | component:core |
| profile:web | partOf | resource:profiles |
| resource:context-intelligence | partOf | system:aifw |
| resource:decision-catalogs | partOf | system:aifw |
| resource:evals | partOf | system:aifw |
| resource:existing-project-adoption | partOf | system:aifw |
| resource:github-workflows-ci-yml | partOf | system:aifw |
| resource:how-to-use | partOf | system:aifw |
| resource:policies | partOf | system:aifw |
| resource:principle-catalogs | partOf | system:aifw |
| resource:profiles | dependsOn | resource:policies |
| resource:profiles | partOf | system:aifw |
| system:aifw | documentedBy | decision:agent-independent-core |
| system:aifw | runsOn | runtime:python |
