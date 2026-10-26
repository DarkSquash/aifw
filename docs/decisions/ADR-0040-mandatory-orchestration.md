# ADR-0040: orquestração obrigatória em L2/L3

- Status: accepted
- Date: 2026-10-26
- Impact: L2
- Change: `mandatory-orchestration`
- Amends: ADR-0038 (subagentes por papel), ADR-0039 (edição restrita ao plano aprovado)

## Contexto

Desde o ADR-0038 a skill manda delegar execução e revisão a subagentes, mas a sessão principal podia editar sozinha: trabalho trivial ficava inline e, em L3, o Opus editava. Na prática a sessão executava o que devia delegar, gastando o modelo mais caro e perdendo a separação entre quem planeja e quem executa.

## Decisão

1. Em L2 e L3 a sessão planeja e delega: execução ao `aifw-executor`, subtarefas rápidas ao `aifw-quick` ou ao `aifw-explorer`, revisão ao `aifw-adversary` e ao `aifw-qa`. Inline só em L0 e L1; L3 e BRAIN nunca são rebaixados.
2. Enquanto houver uma mudança ativa com `approval`, o hook nega (`deny`) Edit, Write, MultiEdit e NotebookEdit feitos pela sessão principal, isto é, sem `agent_id` no payload, em arquivo do projeto. O motivo cita a mudança e manda delegar ao `aifw-executor` ou, numa tarefa rápida, ao `aifw-quick`.
3. Seguem livres: chamadas com `agent_id` (subagentes), a pasta `.aifw/changes/active/`, arquivos fora do projeto e os caminhos de `orchestration.sessionPaths` no `permissions.yaml`, com o mesmo casamento do ADR-0039 (arquivo, pasta ou padrão, com `./` e `\`).
4. `orchestration.mode` no `permissions.yaml`: `required` (padrão) ou `off`. Neste repositório `sessionPaths` lista os arquivos do núcleo do hook (`hooks.py`, `shell.py`, `indirect.py`), que a sessão edita porque o hook em uso depende deles.
5. Os caminhos do avaliador citam o `aifw-executor` e o `aifw-quick` em PLANNED e CRITICAL; na tabela de modelos, o L3 passa a ser executado pelo `aifw-executor` com plano passo a passo.
6. Para corrigir um arquivo que o executor errou, a sessão melhora o plano ou delega de novo; subir de modelo com `model` continua permitido.

## Consequências

- O que a pessoa aprova no plano é executado por subagentes, e a sessão fica com planejamento, decisão e revisão.
- Comandos de shell que escrevem ficam fora da regra, como no ADR-0039: o hook protege contra erro do agente, não contra um agente decidido a contornar.
- Um `change.yaml` ou `tasks.yaml` ilegível deixa aquela mudança fora da regra, sem travar o hook.
- Rollback: `orchestration.mode: off`, ou reverter a mudança.
