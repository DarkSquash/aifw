# Design — Backup só de cópia editada e status livre no plano aprovado

## Context

`install_template` em `python/aifw/claude.py` monta o conteúdo como template + carimbo `<!-- aifw-version: X -->` e grava `.bak` sempre que a cópia existente é diferente. `control_target` em `python/aifw/hooks.py` trata o `tasks.yaml` de uma mudança aprovada como arquivo de controle para qualquer edição.

## Approach

- `claude.py`:
  - `HASH = "<!-- aifw-sha256: {} -->"`. O conteúdo instalado vira `template.rstrip() + "\n\n" + STAMP + "\n" + HASH(sha256 do template.rstrip()) + "\n"`.
  - Antes de trocar uma cópia diferente do conteúdo novo, `install_template` procura a linha `aifw-sha256` e o corpo antes do carimbo. Se o hash do corpo bate com o gravado, a cópia não foi editada e não há `.bak`; senão, `.bak` como hoje.
  - `check_project` continua procurando o carimbo de versão, que não muda.
- `hooks.py`:
  - `widens_plan(root, path, tool_name, tool_input)`: lê o `tasks.yaml` atual e monta o texto novo. No Write, o `content`; no Edit, a troca de `old_string` por `new_string` (todas, com `replace_all`); no MultiEdit, as trocas em ordem. Devolve se o mapa `{id da tarefa: paths}` mudou. Edição que não se aplica, ou YAML ilegível, conta como mudança.
  - Em `control_target`, para as ferramentas de edição, o `tasks.yaml` aprovado só entra como controle quando `widens_plan` é verdadeiro. O shell continua como hoje.
- `hooks.py` é editado pela sessão numa cópia, testado antes de entrar (está em `sessionPaths`). `claude.py`, os testes e a documentação vão para o `aifw-executor`, como exige o ADR-0040.

## Decisions

- Hash no próprio arquivo, sem registro à parte: a cópia carrega a prova de que não foi editada.
- Comparar o mapa de `paths` por tarefa, não o texto: mudar `status`, título ou ordem não amplia o plano.
- Na dúvida, pede: edição que não se aplica ou YAML quebrado continuam pedindo confirmação.

## Risks and rollback

- Cópias instaladas antes desta mudança não têm hash: a primeira atualização ainda cria `.bak` se o template mudou. Depois disso, não.
- Rollback: reverter a mudança volta ao `.bak` sempre e ao `tasks.yaml` inteiro como controle.
