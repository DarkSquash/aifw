# ADR-0009: Núcleo executável de specs e adoção brownfield em duas fases

- Status: accepted
- Date: 2026-08-29
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

AIFW v0.1 já classificava mudanças, gerava o `PROJECT_MAP`, executava gates e fazia discovery somente leitura. Contudo, specs ainda eram templates Markdown sem merge verificável, a ligação requisito–tarefa–teste dependia de disciplina textual e a adoção de repositórios existentes exigia que o agente editasse manualmente catálogo e documentação. Isso permitia drift, perda de contexto entre sessões e conclusão sem prova estrutural suficiente.

## Drivers

- manter a verdade do produto no repositório, independente de Pi, Claude, Codex ou outro executor;
- impedir que uma proposta ativa altere silenciosamente o comportamento aceito;
- permitir validação mecânica de deltas e rastreabilidade;
- automatizar fatos brownfield sem transformar inferência incerta em arquitetura aprovada;
- preservar revisão humana para semântica, owners e mudanças críticas;
- permanecer local-first, auditável e compatível com Windows, WSL e CI Linux.

## Alternativas consideradas

1. Continuar apenas com convenções Markdown. Simples, mas sem contratos executáveis, detecção de órfãos ou sincronização segura.
2. Depender diretamente de uma ferramenta externa de spec-driven development. Acelera alguns fluxos, mas acopla o core a um fornecedor e não resolve as regras próprias de intake, L0–L3, gates e brownfield.
3. Implementar um núcleo YAML pequeno e agnóstico, com adapters opcionais. Exige manutenção de schemas e CLI, mas preserva portabilidade e permite integrar ferramentas externas depois.

## Decisão

1. Adotar `CapabilitySpec` em `.aifw/specs/current/` como verdade comportamental aceita.
2. Isolar mudanças em `.aifw/changes/active/<id>/`, contendo proposta, design, tarefas, deltas, grafo de traceabilidade e evidências.
3. Validar precondições de `added`, `modified` e `removed` antes de qualquer merge.
4. Exigir rastreabilidade de requisitos a tarefas e de cenários a testes aprovados, além da existência dos artefatos referenciados dentro do projeto.
5. Fazer `spec sync` somente como preview. A mutação da verdade ocorre em `spec archive`, depois de readiness, tarefas concluídas, análise limpa e aprovação humana para L3.
6. Construir a próxima árvore de specs em staging e efetuar a troca de diretórios apenas após toda a pré-validação.
7. Para projeto existente, usar duas fases: `adopt analyze --write` persiste descoberta factual; `adopt apply` grava candidatos revisáveis no catálogo/mapa; `adopt approve` exige identidade humana e confirma o digest.
8. Nunca inferir responsabilidade, owner ou relação sem evidência. Candidatos permanecem explicitamente não confirmados até revisão.
9. Integrar o estado brownfield ao `intake status` como avaliação técnica do agente, sem convertê-lo em pergunta de stack para o usuário.

## Consequências

- Features L2/L3 ganham mais artefatos, porém o contexto necessário deixa de ser reexplicado a cada sessão.
- CI e agentes podem bloquear requisitos órfãos, cenários sem verificação, links quebrados e deltas incompatíveis.
- O mapeamento inicial de repositórios existentes fica repetível e idempotente, mas compreensão semântica continua exigindo revisão.
- Specs descrevem comportamento e não substituem ADRs, contratos API, design system, threat models ou runbooks.
- Integrações futuras com outros formatos devem traduzir para estes contratos sem substituir a hierarquia de autoridade.

## Migração

Projetos v0.1 mantêm seus arquivos atuais. A atualização cria os diretórios de `specs`, `changes` e `adoption`, adiciona capability specs às fontes de verdade, executa o baseline brownfield quando `projectType: existing`, regenera policy lock e `PROJECT_MAP` e só então fixa `frameworkVersion: 0.2.0`.

## Rollback

Desabilitar os novos comandos no adapter/CI, preservar `.aifw/changes/` e `.aifw/adoption/` como evidência, restaurar o manifesto/lock v0.1 e o catálogo/mapa anteriores a partir do checkpoint. Capability specs já aceitas não devem ser apagadas; durante rollback elas permanecem documentação versionada até migração posterior.
