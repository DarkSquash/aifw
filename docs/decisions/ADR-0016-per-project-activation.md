# ADR-0016 — Ativação do AIFW por projeto no Claude Code

- Status: accepted
- Date: 2026-10-11
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

A skill `aifw` e o hook `aifw-hook` estavam instalados no escopo do usuário: a skill podia ser acionada pelo modelo em qualquer sessão e o hook rodava em toda ação, mesmo sem efeito fora de projetos AIFW. O AIFW é configurado por projeto e deve ficar desligado até o usuário habilitá-lo.

## Decisão

1. `aifw claude install` instala só o comando `/aifw` em `~/.claude/skills/aifw/`, com `disable-model-invocation: true`.
2. `/aifw new` (projeto do zero) e `/aifw adopt` (projeto existente) inicializam o control plane e rodam `aifw claude enable`.
3. `aifw claude enable` grava no projeto o hook em `.claude/settings.json`, mesclado e idempotente, e a skill `aifw-workflow` em `.claude/skills/`. Um `settings.json` malformado nunca é sobrescrito.
4. O hook global e o complemento manual de `CLAUDE.md` deixam de existir.

## Consequências

- Projetos sem AIFW não carregam skill nem hook.
- Versionar `.claude/` leva a configuração junto com o projeto.
- A skill do projeto é uma cópia do template; atualizar o AIFW exige rodar `aifw claude enable` de novo em cada projeto.
- O hook e a skill valem a partir da sessão seguinte à habilitação.

## Rollback

Desfazer as mudanças listadas na decisão e executar `aifw resolve build` e `aifw map build`. Os checkpoints locais desta mudança foram descartados em 2026-10-11.
