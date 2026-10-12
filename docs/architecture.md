# Arquitetura do framework

## Objetivo

Separar governança durável de executores temporários. O core recebe documentos portáveis, toma decisões determinísticas e produz planos/evidências. Adapters convertem esse resultado para o agente disponível.

```text
Humano + Project Charter + ADRs + contratos
                    │
                    ▼
        Core independente de agente
  ┌──────────────────────────────────────┐
  │ config authority lifecycle decisions│
  │ specs trace adoption map gates evals │
  └──────────────────────────────────────┘
            │ planos tipados
    ┌───────┼──────────┬──────────┐
    ▼       ▼          ▼          ▼
  Claude Code (skill)   futuro adapter
```

## Componentes

| Componente | Responsabilidade | Fonte principal |
| --- | --- | --- |
| Config | versão, projeto, ambientes, profiles, dados, allowlist | `aifw.yaml` |
| Intake | decisões humanas e unknowns | `.aifw/charter.yaml` |
| Resolution | autoridade, conflitos, lock e effective policy | `policies/`, `profiles/`, project rules |
| Decision Engine | comparação contextual, incerteza, aprovação e ADR | `decision-catalogs/`, profiles, `.aifw/decisions/` |
| Lifecycle | L0–L3, artefatos e aprovação | Change Case |
| Spec Lifecycle | current specs, deltas, tarefas, trace e archive atômico | `.aifw/specs/`, `.aifw/changes/` |
| Traceability | grafo requisito–tarefa–cenário–teste/evidência | `traceability.yaml` |
| Brownfield Adoption | discovery factual, candidatos e aprovação do baseline | `.aifw/adoption/` |
| Project Map | catálogo, relações e fontes de verdade | `.aifw/catalog.yaml` |
| Gates | comandos, auditorias e evidência | `.aifw/gates.yaml` |
| Impasse | tentativas, estados e escalada | Impasse Case |
| Permissions | efeitos externos e capability ceiling | `.aifw/permissions.yaml` |
| Routing | recomendação/ativação FAST–WORK–BRAIN | `.aifw/routing.yaml` |
| Conformance | comportamento observável do agente | `evals/` + traces reais |
| Adapters | tradução para o host do agente | `templates/claude/` |

## Fronteiras

- `python/aifw` não importa adapters nem SDKs de agentes.
- Um adapter consome tipos do core e do adapter SDK; não altera regras.
- Arquivos YAML/JSON são API pública e possuem JSON Schema.
- Markdown compilado é apresentação; YAML/JSON/ADRs são fontes.
- `PROJECT_MAP.md` e `docs/architecture/discovered.md` são projeções; catálogo, specs, contratos e ADRs preservam a autoridade.
- Comandos de gate usam execução direta de processo, sem shell implícito.

## Estado e determinismo

Locks e mapas são ordenados e possuem digest SHA-256. Dado o mesmo conjunto de entradas, o resultado deve ser byte a byte equivalente. Timestamps só entram quando representam aprovação ou evento real; geradores determinísticos não inventam `generatedAt`.

No ciclo de specs, `sync` calcula a próxima verdade sem escrever. `archive` valida antes de staging e troca a árvore atual somente depois de todo o plano estar materializado. Na adoção brownfield, o digest liga relatório, candidatos aplicados e aprovação humana; uma nova análise estrutural exige nova revisão.

## Extensibilidade

Um novo stack profile declara capabilities, requisitos, conflitos, regras e catálogos próprios. O motor de decisões continua global: profiles só acrescentam alternativas específicas da stack. Um novo agent adapter implementa `AgentAdapter`. Nenhum deles modifica a Constitution silenciosamente.
