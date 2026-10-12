# ADR-0014 — Claude Code como host de referência

- Status: accepted
- Date: 2026-10-11
- Impact: L3
- Approved by: human:DarkSquash
- Supersedes: ADR-0008

## Contexto

O AIFW foi integrado primeiro ao Pi (extensão com troca de modelo Luna/Terra/Sol) e ao Codex (skill e complemento de `AGENTS.md`). O usuário deixou de usar esse fluxo e passou a usar o Claude Code.

## Decisão

1. Publicar a skill `aifw` e o complemento de `CLAUDE.md` em `templates/claude/`, adaptados do template do Codex.
2. Remover a integração Pi: `extensions/aifw.ts`, `aifw-pi-bridge`, o módulo de adapters (PiAdapter) e a documentação do Pi.
3. Remover a integração Codex: o template e o guia do Codex.
4. Trocar os aliases de roteamento para `haiku`/`sonnet`/`opus` e os alvos para modelos da Anthropic.
5. A ativação automática registrada para os modelos do Pi não vale para os novos alvos: a policy deste repositório volta a `recommendation-only` até nova avaliação e aprovação.

## Consequências

- O núcleo continua independente de agente (ADR-0002); só o host de referência mudou.
- O Claude Code não troca o modelo da sessão; a rota recomendada orienta a delegação a subagentes.
- `aifw instructions --agent codex|opencode` continua gerando `AGENTS.md` para outros hosts.
- Instalações fora do repositório (pacote Pi, `~/.pi/agent/aifw-routing.yaml`, skill em `~/.agents/skills/aifw`) não são alteradas por esta mudança.

## Rollback

Desfazer as mudanças listadas na decisão e executar `aifw resolve build` e `aifw map build`. Os checkpoints locais desta mudança foram descartados em 2026-10-11.
