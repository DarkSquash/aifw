# ADR-0005 — Catálogos globais de decisões arquiteturais

- Estado: aceito
- Data: 2026-08-22
- Dono: human:owner
- Impacto: L3 (novo mecanismo de governança do core)

## Contexto

O AIFW preservava a arquitetura concreta como decisão de cada projeto, mas ainda não oferecia uma maneira uniforme de comparar padrões comuns. Isso deixava duas alternativas ruins: impor um único padrão a toda stack ou depender de uma recomendação transitória registrada apenas na conversa com o agente.

O mecanismo precisa servir a Flutter, Web, Python e stacks futuras, mantendo conhecimento específico fora do core quando necessário. Também precisa evitar que popularidade seja confundida com adequação e que o agente aprove sua própria recomendação.

## Decisão

1. Criar `DecisionCatalog` como contrato global, independente de stack e fornecedor de agente.
2. Manter catálogos aplicáveis a qualquer projeto em `decision-catalogs/`.
3. Permitir que profiles acrescentem catálogos em `profiles/<id>/decisions/`, sem substituir o motor ou a autoridade global.
4. Classificar alternativas somente a partir de sinais explícitos, com pesos, justificativas, requisitos e conflitos visíveis.
5. Expor drivers não respondidos e reduzir a confiança em vez de inventar certeza.
6. Persistir a análise em `.aifw/decision-cases/<categoria>.json` com digest determinístico.
7. Exigir aprovação `human:*` e ADR existente dentro do repositório antes de gravar `.aifw/decisions/<categoria>.yaml`.
8. Incluir digest do ADR no registro aceito, impedindo que a decisão dependa apenas de uma conversa com IA.
9. Distribuir os catálogos, schemas, documentação e testes como parte do pacote AIFW.

## Consequências

- Todos os projetos ganham o mesmo processo para comparar arquiteturas sem receber a mesma arquitetura.
- Flutter e outras stacks podem oferecer alternativas especializadas sem contaminar o core.
- O agente economiza pesquisa repetitiva em escolhas comuns, mas precisa perguntar quando sinais essenciais faltarem.
- A pontuação auxilia a decisão; não substitui julgamento, protótipo, benchmark ou aprovação humana.
- Alterações em critérios e pesos são mudanças de governança versionadas e testadas.

## Alternativas rejeitadas

- Definir Clean Architecture como padrão universal: ignora complexidade, tamanho, equipe e custos de abstração.
- Manter catálogos apenas em Flutter/Web: repetiria o processo e excluiria stacks futuras.
- Deixar o agente escolher automaticamente a opção mais pontuada: mistura recomendação com autoridade.
- Salvar a escolha apenas no histórico da IA ou Obsidian: não fornece contrato versionado e verificável no projeto.
