# ADR-0007 — Catálogo contextual de princípios de engenharia

## Status

Aceito em 2026-08-23 por `human:owner`. Itens 3 e 4 da decisão substituídos pelo [ADR-0013](ADR-0013-skill-delegation.md).

## Contexto

O AIFW já comparava alternativas arquiteturais, incluindo Clean Architecture, mas não formalizava Clean Code, SOLID ou princípios complementares. Colocá-los no `DecisionCatalog` seria semanticamente incorreto: um projeto não escolhe SRP contra legibilidade ou KISS contra tratamento de erros. Também seria perigoso convertê-los em hard gates universais, pois heurísticas aplicadas mecanicamente geram fragmentação, abstração prematura e falsa simplicidade.

## Drivers

- Tornar revisões de manutenção reproduzíveis e independentes do agente.
- Distinguir princípios de design de decisões arquiteturais mutuamente comparáveis.
- Exigir perguntas e evidência, não apenas citar siglas.
- Preservar exceções e riscos de mau uso.
- Permitir evolução versionada e schemas públicos.

## Opções consideradas

1. Adicionar frases SOLID às core policies como hard gates.
2. Modelar princípios como opções do `DecisionCatalog`.
3. Criar um `PrincipleCatalog` e uma revisão contextual separada.

## Decisão

Adotar a opção 3.

1. Criar o contrato versionado `PrincipleCatalog` para Clean Code, SOLID e fundamentos complementares.
2. Cada princípio declara aplicabilidade, perguntas, evidência, riscos de mau uso, exceções e fontes.
3. Princípios universais permanecem aplicáveis; princípios dependentes de contexto ficam `deferred` sem o sinal necessário.
4. `aifw principle review` gera um `PrincipleReview` determinístico e opcionalmente o persiste em `.aifw/reviews/engineering-principles.json`.
5. A core policy exige revisão como auditoria contextual (`SHOULD`), não como hard gate universal.
6. Findings precisam referenciar evidência concreta; o checklist não aprova código automaticamente.

## Consequências positivas

- Diferentes agentes aplicam a mesma base e enxergam as mesmas salvaguardas.
- Clean Code e os cinco princípios SOLID ficam explícitos sem impor uma arquitetura.
- DRY, OCP e SRP deixam documentado quando não devem ser aplicados mecanicamente.
- Reviews podem ser persistidos, comparados e usados como evidência de quality gate.

## Consequências negativas

- O catálogo acrescenta tokens e tempo quando uma revisão material é solicitada.
- Sinais incorretos produzem checklist inadequado; discovery continua essencial.
- A avaliação final ainda exige julgamento técnico e não é totalmente automatizável.

## Riscos e mitigação

- Risco: agente citar princípios sem apontar defeito real. Mitigação: perguntas e evidências obrigatórias no catálogo.
- Risco: transformar preferências em dogma. Mitigação: `misuseRisks`, `exceptions`, aplicabilidade por sinais e enforcement de auditoria.
- Risco: catálogo ficar desatualizado. Mitigação: versionamento, schemas, testes e fontes registradas.

## Referências

- Robert C. Martin, Clean Code e artigos sobre SOLID.
- Barbara Liskov e Jeannette Wing, Behavioral Subtyping.
- Martin Fowler, YAGNI e Test Pyramid.
- Edsger W. Dijkstra, Separation of Concerns.
