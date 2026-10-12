# ADR-0013 — Delegar entrevista e revisão de princípios a skills do host

- Status: accepted
- Date: 2026-10-11
- Impact: L3
- Approved by: human:DarkSquash
- Supersedes: ADR-0007 (itens 3 e 4 da decisão); ADR-0008 (item 6, handoff Codex)

## Contexto

Três partes do núcleo duplicavam capacidades que o host do agente já oferece com mais qualidade:

- `aifw handoff codex` e `aifw_codex_handoff` produziam um documento de transferência manual Pi → Codex. A skill genérica `handoff` cobre o caso.
- O Project Intake listava perguntas, mas a entrevista em si ficava sem método. As skills `grilling`/`grill-me` conduzem entrevistas por rodadas, com recomendação por pergunta e sem perguntar fatos que o agente pode descobrir.
- `aifw principle review` gerava um checklist determinístico a partir de sinais declarados pelo próprio agente. Ele não lia código; a revisão real continuava fora do AIFW.

## Decisão

1. Remover `aifw handoff codex`, a ação `handoff` do `aifw-pi-bridge`, a ferramenta `aifw_codex_handoff`, o comando `/codex-handoff`, `schemas/codex-handoff.schema.json` e `templates/codex-handoff-input.json`. `redact` passa a viver em `context.py`, seu único usuário.
2. A entrevista do intake é conduzida pela skill `grilling` (ou `grill-me`). As perguntas de `aifw intake status` são a fronteira inicial da entrevista. O AIFW continua dono do Charter, de `ready`/`complete` e da aprovação humana.
3. Remover `aifw principle review`, `PrincipleReview`, `schemas/principle-review.schema.json` e a avaliação `engineering-principles` do intake. A revisão de princípios é feita pela skill `code-review`, eixo Standards, usando `principle-catalogs/` como fonte de padrões documentados.
4. `principle-catalogs/`, seu schema e `aifw principle list` permanecem como fonte versionada dos princípios, perguntas, exceções e riscos de mau uso.

## Consequências

- O intake fica `complete` sem artefato de princípios; em projetos existentes continua exigindo `brownfield-mapping`.
- A evidência da regra `quality.contextual-principle-review` passa a ser `code-review`.
- O núcleo passa a referenciar skills que dependem do host. Hosts sem essas skills seguem as mesmas regras manualmente: entrevista por rodadas e revisão do diff contra `principle-catalogs/`.
- Arquivos já gravados em `.aifw/handoffs/` e `.aifw/reviews/engineering-principles.json` deixam de ser lidos pelo AIFW.

## Rollback

Desfazer as mudanças listadas na decisão e executar `aifw resolve build` e `aifw map build`. Os checkpoints locais desta mudança foram descartados em 2026-10-11.
