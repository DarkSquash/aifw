# Proposal — Orquestração obrigatória em L2/L3

## Intent

A tabela de modelos manda o Opus planejar e o Sonnet executar em L2, mas a skill deixava a sessão principal implementar sozinha ("trabalho trivial pode ser feito inline", "em pontos críticos, prefira que o opus edite"), e isso aconteceu em mudanças L2. A pessoa decidiu que a orquestração é obrigatória em L2 e L3, que o executor também trabalha em L3, e que o Haiku pega as tarefas rápidas dentro delas.

## Scope

- **Hook:** enquanto houver uma mudança aprovada ativa, uma edição (Edit, Write, MultiEdit, NotebookEdit) feita pela sessão principal (chamada sem `agent_id`) num arquivo do projeto é negada, com o motivo "delegue ao aifw-executor ou ao aifw-quick (ADR-0040)".
  - Seguem livres: subagentes (qualquer chamada com `agent_id`), a pasta `.aifw/changes/active/`, arquivos fora do projeto e os caminhos em `orchestration.sessionPaths` do `permissions.yaml`.
  - `orchestration.mode`: `required` (padrão) ou `off`.
  - Neste repositório, `sessionPaths` reserva à sessão o núcleo vivo do hook (`python/aifw/hooks.py`, `python/aifw/shell.py`, `python/aifw/indirect.py`), que é editado numa cópia e testado antes de entrar.
- **Avaliador:** o caminho CRITICAL passa a dizer "Opus planeja, aifw-executor (Sonnet) executa", e PLANNED e CRITICAL citam o `aifw-quick` (Haiku) para as tarefas rápidas.
- **Skill:** em L2/L3 a orquestração é obrigatória. A sessão planeja, delega a execução ao `aifw-executor` e as subtarefas rápidas e mecânicas (renomear, ajuste pequeno de texto, busca) ao `aifw-quick` ou ao `aifw-explorer`, e manda revisar pelo `aifw-adversary` e pelo `aifw-qa`. Saem "trabalho trivial inline" e "prefira que o opus edite" para L2/L3; L0/L1 continuam podendo ser feitos inline.
- Testes, `docs/claude-code.md`, `docs/routing.md`, CHANGELOG e ADR-0040.

## Non-goals

- Comandos de shell que escrevem, pela mesma razão do ADR-0039: o hook não sabe com segurança o arquivo alterado.
- Mudanças L0/L1, sem aprovação.
- Escolher qual subagente pega cada tarefa: o hook só exige que não seja a sessão principal.

## Acceptance

- Com uma mudança aprovada ativa, a sessão principal editando `python/aifw/claude.py` é negada com o motivo; a mesma edição com `agent_id` (o `aifw-executor`) segue; a pasta da mudança, um arquivo fora do projeto e um caminho de `sessionPaths` seguem para a sessão.
- Sem mudança aprovada ativa, ou com `orchestration.mode: off`, a sessão edita como antes.
- O contexto do avaliador cita o `aifw-executor` no CRITICAL e o `aifw-quick` no PLANNED e no CRITICAL.
- A skill descreve a orquestração obrigatória em L2/L3 e o Haiku nas tarefas rápidas.
- Suíte inteira passando e revisão em duas etapas aprovada; esta mudança executada pelo `aifw-executor`, salvo o núcleo do hook.
