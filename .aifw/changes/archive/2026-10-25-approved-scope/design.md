# Design — Edição restrita ao plano aprovado

## Context

`approve_change` grava `approval` no `change.yaml` da mudança; as tarefas ficam em `.aifw/changes/active/<id>/tasks.yaml`, cada uma com `paths`. O hook (`python/aifw/hooks.py`) decide cada chamada em `evaluate`, e `control_target` lista os arquivos de controle.

## Approach

- Em `hooks.py`, `outside_plan(root, policy, tool_name, tool_input)`:
  - só para ferramentas de edição e `policy.get("changeScope", "ask") == "ask"`;
  - lê as mudanças ativas com `approval` no `change.yaml`; sem nenhuma, devolve nada;
  - resolve o alvo como em `control_target`; fora da raiz, nada;
  - libera a pasta de qualquer mudança aprovada ativa;
  - casa o caminho relativo contra cada path: igual, prefixo de pasta (path terminado em `/` ou pasta existente) ou `fnmatch`;
  - sem casamento, devolve o motivo com os ids das mudanças.
- `evaluate` acrescenta esse motivo como `ask`.
- `control_target`: o `tasks.yaml` de uma mudança ativa cujo `change.yaml` tem `approval` conta como arquivo de controle, para as ferramentas de edição e para o shell que escreve.
- `schemas/permissions.schema.json`: `changeScope` com `ask` e `off`.
- Erro ao ler um `change.yaml` ou `tasks.yaml` quebrado: a mudança é ignorada para a regra, sem travar o hook.
- `hooks.py` editado numa cópia e testado antes de entrar.

## Decisions

- Pede, não nega: a pessoa decide o que fica fora do plano.
- Só as ferramentas de edição: são o caminho normal de escrita do agente, e o alvo é certo.
- A pasta da mudança é sempre liberada, para a evidência e a revisão não perguntarem.
- `changeScope` existe para desligar por projeto, como as outras opções do ADR-0037.

## Risks and rollback

- Um plano com `paths` incompletos faz o agente perguntar mais. A skill pede para listar tudo antes da aprovação, e ampliar o `tasks.yaml` custa uma confirmação.
- Rollback: `changeScope: off` no `permissions.yaml`, ou reverter a mudança.
