# Catálogos de decisões arquiteturais

O AIFW oferece um mecanismo global para comparar padrões arquiteturais, organização de código, topologia e escolhas específicas de stack. Ele não impõe uma arquitetura universal: transforma o contexto real do projeto em uma recomendação explicável, que o humano revisa e aprova.

## O que é global e o que pertence à stack

O contrato `DecisionCatalog`, o motor de pontuação, os registros e os comandos da CLI pertencem ao core independente de stack. Catálogos em `decision-catalogs/` estão disponíveis para todos os projetos. Um profile pode acrescentar alternativas em `profiles/<profile>/decisions/`, como opções de gerenciamento de estado do Flutter, sem redefinir o processo nem a hierarquia de autoridade.

Os catálogos iniciais globais cobrem:

- arquitetura da aplicação: layered pragmática, ports and adapters, Clean Architecture e vertical slice;
- organização de código: layer-first, feature-first e híbrida;
- topologia: monólito, monólito modular e microsserviços.

Essas opções são um ponto de partida curado, não uma lista imutável. Um padrão novo entra por mudança versionada, com fontes, critérios, trade-offs, schemas e testes.

## Processo de decisão

1. O agente descobre o projeto sem alterar código e reúne sinais explícitos.
2. `decision list` mostra categorias, perguntas e alternativas disponíveis.
3. `decision recommend` pontua cada alternativa, elimina requisitos ausentes e conflitos e expõe dúvidas ainda não respondidas.
4. O agente apresenta os motivos, custos e incerteza ao usuário; não trata a primeira colocada como decisão automática.
5. A recomendação é persistida como `DecisionCase` em `.aifw/decision-cases/`.
6. O humano escolhe uma alternativa e registra a justificativa e consequências em um ADR dentro de `docs/adr/`.
7. `decision approve` valida o caso, exige identidade `human:*` e ADR existente e grava o `DecisionRecord` em `.aifw/decisions/`.
8. `PROJECT_MAP.md`, policies, specs e gates afetados são atualizados e revalidados.

Uma conversa com IA nunca é o registro da decisão. O artefato aceito é a combinação versionada de ADR e `DecisionRecord`.

## Exemplo

```powershell
aifw decision list --category application-architecture

aifw decision recommend `
  --category application-architecture `
  --signals domain:complex,integrations:many,testability:high `
  --write

aifw decision approve `
  --category application-architecture `
  --option ports-and-adapters `
  --by human:owner `
  --adr docs/adr/ADR-0001-architecture.md
```

Sinais são fatos ou preferências confirmadas do projeto, não palavras escolhidas para forçar o resultado. Se faltarem drivers, a confiança cai e o agente deve perguntar antes de recomendar com certeza artificial.

Com `decisions` em `spec.assessment.features` (modo sombra, ADR-0029), `decision recommend --suggest-signals [--context "<pedido>"]` pede ao Decider para responder cada direcionador da categoria a partir do Charter e do pedido.
- **O que mostra:** o campo `assessment` traz os sinais sugeridos (resposta diferente de "não diz", com confiança de 0,6 ou mais) e o ranking que eles dariam.
- **O que não faz:** o ranking oficial do comando continua usando só os sinais passados em `--signals`. A sugestão serve para o agente perguntar à pessoa e confirmar antes de usar.
- **Revisão:** o relatório sai com `aifw assess report --feature decisions`.

## Critérios de segurança

- Pontuação sempre inclui o motivo e o peso aplicado.
- Requisitos ausentes e conflitos tornam a opção inelegível.
- Empates são determinísticos, mas continuam visíveis para julgamento humano.
- Aprovação de agente (`agent:*`) é rejeitada.
- O digest protege o caso persistido contra alteração silenciosa entre recomendação e aprovação.
- O ADR precisa estar dentro do repositório e seu conteúdo também recebe digest.
- Uma mudança de decisão arquitetural segue o lifecycle L0-L3; escolhas globais ou de topologia normalmente são L2 ou L3.

## Como expandir

Um catálogo deve declarar categoria, impacto, drivers, alternativas, sinais positivos e negativos, requisitos, conflitos, trade-offs e fontes. O arquivo precisa validar contra `schemas/decision-catalog.schema.json`. Alternativas muito específicas devem ficar em profiles ou regras do projeto, evitando poluir o core e enviesar todo projeto para uma biblioteca ou moda passageira.
