# Project Intake: o que o usuário decide no começo

O usuário entrega contexto de negócio, risco e autoridade. O agente descobre e recomenda tecnologia. As perguntas são adaptativas: campos já conhecidos não são perguntados novamente.

## Decisões humanas obrigatórias

O intake precisa entender, nesta ordem aproximada:

1. **Problema:** qual dor ou oportunidade o projeto resolve.
2. **Público:** quem usa, administra ou é afetado.
3. **Resultado e sucesso:** mudança observável, métricas ou critérios de aceitação.
4. **Escopo:** o que entra agora e o que fica explicitamente fora.
5. **Restrições:** prazo, orçamento, legislação, acessibilidade, compatibilidade, infraestrutura ou política interna.
6. **Dados e risco:** classificação, dados pessoais/sensíveis, retenção e consequências de erro.
7. **Autonomia:** ações locais permitidas, Git remoto, serviços externos, previews e produção.
8. **Preferências e proibições:** tecnologias obrigatórias ou vetadas, quando realmente existirem.

Stack não é uma decisão obrigatória do usuário. Se não houver preferência, `technicalPreference.mode` permanece `agent-recommend`.

## O agente descobre

Em projeto existente, antes de perguntar detalhes técnicos, o agente faz descoberta somente leitura:

- package manager, scripts, dependências e runtimes;
- estrutura de módulos e boundaries;
- CI, testes, lint, typecheck e build;
- contratos OpenAPI/AsyncAPI/GraphQL/Protobuf;
- ADRs, diagramas, design system e Storybook;
- autenticação, dados, observabilidade e deployment já existentes;
- inconsistências e unknowns, sem tratá-los como autorização para mudança.

Em projeto novo, ele pesquisa opções compatíveis com as decisões humanas e apresenta recomendação com trade-offs.

## Entrevista

A entrevista é conduzida pela skill `grilling` (ou `grill-me`, que a invoca). As perguntas retornadas por `aifw intake status` formam a fronteira inicial: o agente pergunta em rodadas, recomenda uma resposta para cada pergunta, descobre sozinho os fatos que estão no repositório e só leva ao usuário as decisões. Cada resposta é gravada com `aifw intake set --field <campo> --value <valor>`, que valida o schema; a skill não substitui o Charter nem a aprovação humana. Em um host sem essa skill, siga o mesmo método manualmente.

`intake status` só confere se cada campo está preenchido: "a definir" passa. Com `intake` em `spec.assessment.features` (modo sombra, ADR-0027), o resultado ganha `assessment.weakAnswers`. São as respostas de problema, públicos, resultados e escopo que o Decider avaliou como vagas ou parciais, e elas viram as próximas perguntas da entrevista.
- **Não bloqueia:** o aviso não muda `ready`, `complete` nem a aprovação.
- **Cache:** a avaliação fica guardada pelo conteúdo do Charter e só roda de novo quando ele muda.
- **Revisão:** o relatório sai com `aifw assess report --feature intake`.

## Avaliações técnicas do agente

O intake também acompanha tarefas que pertencem ao agente, sem transformá-las em perguntas para o usuário. Em `projectType: existing`, `brownfield-mapping` é obrigatório: discovery factual, aplicação como candidatos e confirmação humana entram no mesmo `intake status`. A revisão de princípios não faz parte do intake; ela acontece sobre o código, pela skill `code-review` (consulte [Princípios de engenharia](engineering-principles.md)).

`aifw intake status` separa dois conceitos:

- `ready`: as decisões humanas estão suficientes para aprovar o Charter;
- `complete`: o Charter está aprovado e inalterado desde a aprovação (`charterApproved`), e todas as avaliações técnicas obrigatórias do intake estão atuais. Editar um Charter aprovado exige aprová-lo de novo.

Cada item em `agentAssessments` declara responsável, estado (`pending`, `current`, `stale` ou `invalid`), artefato e próxima ação. Uma avaliação técnica pendente não inventa uma nova decisão humana nem impede a aprovação do Charter; ela mantém o intake incompleto até o agente persistir evidência reproduzível.

## Estados

O Charter começa `draft`. `aifw intake status` retorna perguntas faltantes, unknowns bloqueantes e avaliações técnicas do agente. Aprovação só é possível quando as decisões humanas estão prontas; ela registra humano, instante e digest do conteúdo.

```text
draft → ready → human approval → approved ─┐
                                             ├→ intake complete
             agent assessments ─────────────┘
```

Alteração material depois da aprovação cria Change Case, reaprovação proporcional e novo digest. A aprovação do Charter não aprova automaticamente produção, custos ou mudanças futuras.

## Anti-padrões

- perguntar “qual framework você quer?” antes de entender o produto;
- preencher requisitos ausentes por suposição silenciosa;
- repetir um questionário fixo mesmo quando o repositório já responde;
- misturar preferência pessoal com necessidade do projeto;
- deixar a decisão apenas numa conversa.
