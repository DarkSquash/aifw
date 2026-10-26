# Design — Orquestração obrigatória em L2/L3

## Context

O Claude Code envia `agent_id` no PreToolUse só quando a chamada vem de um subagente. O ADR-0039 já lê as mudanças aprovadas ativas (`approved_plans` em `python/aifw/hooks.py`). O caminho do avaliador vem de `assessment.PATH_RULE`.

## Approach

- `hooks.py`: `session_edit(root, policy, payload)` devolve o motivo da negação quando:
  - `policy["orchestration"]["mode"]` é `required` (padrão);
  - a ferramenta é de edição e não há `agent_id`;
  - há mudança aprovada ativa;
  - o alvo está dentro do projeto, fora de `.aifw/changes/active/` e fora de `sessionPaths`, com o mesmo casamento de paths do ADR-0039.
- `pre_tool_use` consulta essa função junto com a trava dos revisores, antes da política, e nega com o motivo.
- `schemas/permissions.schema.json`: `orchestration` como objeto com `mode` (`required` ou `off`) e `sessionPaths` (lista de strings).
- `.aifw/permissions.yaml` deste repositório ganha os `sessionPaths` do núcleo do hook. É arquivo de controle: a pessoa confirma a edição.
- `assessment.PATH_RULE`: PLANNED e CRITICAL com o `aifw-quick`, e CRITICAL com o `aifw-executor`.
- Skill, `docs/claude-code.md` e `docs/routing.md` com a tabela nova.
- `hooks.py` editado pela sessão numa cópia (ele está em `sessionPaths`); testes e documentação pelo `aifw-executor`.

## Decisions

- Nega em vez de pedir: a orquestração é obrigatória e a resposta certa é delegar, sem incomodar a pessoa.
- A distinção é por `agent_id`, que existe para qualquer subagente: o hook exige delegar, não escolhe o subagente.
- `sessionPaths` é decisão da pessoa, no arquivo de controle, para os pontos em que um erro trava o próprio hook.

## Risks and rollback

- Se o Claude Code deixar de enviar `agent_id`, os subagentes também seriam negados; os testes fixam o formato documentado.
- Se o executor falhar várias vezes num arquivo, a sessão não o corrige direto. O caminho é um plano melhor, um subagente de modelo maior (passando `model`) ou incluir o caminho em `sessionPaths`.
- Rollback: `orchestration.mode: off`, ou reverter a mudança.
