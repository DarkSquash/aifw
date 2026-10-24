# Design — Revisores sem alterar o projeto

## Context

O Claude Code envia `agent_id` e `agent_type` no PreToolUse quando a chamada vem de um subagente; `agent_type` é o `name` da definição. O hook hoje decide só pela ferramenta e pela política, sem saber quem chama. `CONTROL` em `python/aifw/hooks.py` protege `.claude/skills/aifw-workflow/`, mas não `.claude/agents/`. Os templates dos revisores estão em `templates/claude/agents/`.

## Approach

- Em `hooks.py`:
  - `REVIEWERS = {"aifw-adversary", "aifw-qa"}`.
  - Uma função `reviewer_change(root, payload)` devolve o motivo da negação, ou nada.
    - Ferramentas de edição: alvo dentro da raiz que não seja `.aifw/changes/active/<id>/independent-review.md` é negado. O caminho é resolvido como em `control_target`.
    - Shell: `analyze(command)` e negação se algum pedido não for `read-only`, `external-read`, `opaque` ou `secret-read`; o segredo continua com a regra de sempre.
  - `pre_tool_use` consulta essa função antes de `evaluate`, depois do congelamento da aprovação.
  - `CONTROL` ganha `.claude/agents/aifw-`. A comparação por prefixo e por trecho já cobre as ferramentas de edição e o shell.
- Templates:
  - O `aifw-adversary` sai com `tools: Read, Grep, Glob, Bash, Write` e o brief do eixo Spec no próprio texto.
  - O `aifw-qa` mantém `Skill` só para ler os critérios do eixo Standards do `code-review`, com a regra de fazer o eixo ele mesmo, sem lançar subagentes.
  - Nenhum dos dois tem `Agent`.
- A edição de `hooks.py` é feita numa cópia, conferida e testada antes de entrar, porque o hook roda esse código ao vivo.

## Decisions

- A trava vale por `agent_type`, não pelo texto do pedido: é estrutural e não depende de o revisor seguir a instrução.
- O código opaco do revisor continua liberado: o adversário precisa rodar experimentos para provar um achado. É a mesma fronteira do ADR-0037; o hook não persegue um agente decidido a contornar a regra.
- Os eixos do `code-review` viram as etapas, em vez de liberar `Agent`. Subagentes aninhados rodariam no modelo da sessão e com outro `agent_type`, fora da trava.
- A proteção cobre só as definições com prefixo `aifw-`, como a da skill cobre só a `aifw-workflow`.

## Risks and rollback

- Se o Claude Code deixar de enviar `agent_type`, a trava some sem aviso e as regras normais voltam. Os testes fixam o formato que a documentação descreve.
- Um revisor que precise de um arquivo auxiliar dentro do projeto será negado. A mensagem manda usar uma pasta temporária.
- Rollback: reverter a mudança tira a trava e a proteção. Apagar `agent_type` do payload não é possível ao agente.
