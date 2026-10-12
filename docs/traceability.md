# Rastreabilidade executável

O analisador da v0.2 monta um grafo determinístico para responder: qual requisito motivou esta tarefa, qual cenário verifica o comportamento e qual evidência prova que ele passou?

```text
Capability → Requirement → Scenario
                    ↓          ↓
                  Task       Test
                    ↓          ↓
                  Code     Gate/Evidence
                    ↘ ADR / Design
```

## O que é analisado

`aifw spec analyze <change-id>` lê somente a mudança ativa e os caminhos citados. Ele não executa testes e não inventa relações. O relatório contém:

- cobertura de requisitos ligados a tarefas;
- cobertura de cenários ligados a testes aprovados;
- tarefas concluídas versus total;
- nós e links do grafo;
- findings com código, severidade, IDs e localizações.

## Bloqueios detectados

| Finding | Significado |
| --- | --- |
| `ORPHAN_REQUIREMENT` | requisito sem tarefa responsável |
| `SCENARIO_WITHOUT_VERIFICATION` | cenário sem teste aprovado |
| `TASK_UNKNOWN_REQUIREMENT` | tarefa aponta para requisito inexistente |
| `DANGLING_TRACE_LINK` | link aponta para nó não declarado |
| `TRACE_ARTIFACT_MISSING` | arquivo de teste, gate ou evidência não existe |
| `TRACE_ARTIFACT_OUTSIDE_PROJECT` | evidência tenta escapar da raiz do projeto |
| `TRACE_GATE_NOT_PASSED` | gate obrigatório ligado por checkedBy ainda não possui verificação passed |

Todo artefato `passed` precisa de um `path` não vazio para um arquivo existente dentro da raiz real do projeto. A verificação resolve links simbólicos e rejeita diretórios. Um teste sem esse arquivo não satisfaz a cobertura do cenário.

Uma relação `checkedBy` com um gate declara um compromisso de verificação para a mudança: apenas `passed` o satisfaz. `planned`, `failed` e `waived` bloqueiam esse compromisso. Observações de auditoria sem essa relação permanecem não bloqueantes. A autoridade hard/audit/human e os waivers do avaliador de gates continuam seguindo seus próprios contratos; o analisador de trace não executa gates nem converte uma observação em aprovação.

Validação de delta acrescenta conflitos como adicionar requisito já vigente, alterar/remover requisito desconhecido, IDs duplicados e criação de capability sem propósito.

## Limite intencional

Um arquivo chamado `payment_service.dart` prova que o arquivo existe; não prova sozinho sua responsabilidade arquitetural. Relações semânticas precisam de contrato, importação, teste, documentação, ADR ou confirmação humana. Esse limite vale tanto para traceabilidade quanto para adoção brownfield.

## Uso em CI

Para cada mudança ativa relevante, a CI deve executar `spec validate` e `spec analyze`; failures retornam código diferente de zero. O archive continua sendo uma ação controlada, depois dos quality gates da stack e das aprovações aplicáveis.
