# Proposal — Métricas do avaliador e checagem de aninhamento

## Intent

Duas pendências da revisão do PR #7 (ADR-0042). Primeira: `criticalDemoted` e `pathBelowExpected` foram definidos quando o caminho vinha do risco; hoje medem a complexidade, e o texto não diz isso. Segunda: `aifw-planner` e `aifw-lead` dependem de lançar `aifw-worker` pela ferramenta Agent, e o limite de aninhamento de subagentes do Claude Code só estava documentado, sem checagem nem plano B.

## Scope

- **Métricas, só redescrever.** `criticalDemoted` (relatório da sombra, `python/aifw/assessment.py`) e `pathBelowExpected` (eval, `python/aifw/assessment_eval.py`) medem o caminho pela complexidade. Os nomes das chaves JSON não mudam: são saída pública de `aifw assess report --json` e `aifw assess eval`, e o ADR-0042 §6 já manteve os nomes de caminho pelo mesmo motivo. Mudam o rótulo do relatório ("caminho CRITICAL (complexidade alta) rebaixado"), os comentários nas duas funções e uma frase em `docs/routing.md`.
- **Checagem de aninhamento.** Fonte: https://code.claude.com/docs/en/sub-agents (seção "Let subagents spawn their own subagents") e https://code.claude.com/docs/en/env-vars. O padrão é 3 camadas abaixo da conversa (desde a 2.1.219), configurável por `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` no ambiente ou no `env` do `settings.json`; `1` desliga o aninhamento. A cascata precisa de 2. `aifw claude check` avisa quando essa variável é um número menor que 2 no ambiente, em `.claude/settings.local.json`, `.claude/settings.json` ou `~/.claude/settings.json`.
- **Plano B documentado.** Se o planner ou o lead não tiver a ferramenta Agent, ou o lançamento falhar, ele implementa a parte ele mesmo, uma tarefa por vez, e avisa no resumo. Não devolve a implementação ao agente principal, que só orquestra (ADR-0042). Vale nos templates `aifw-planner` e `aifw-lead`, na skill `aifw-workflow` e em `docs/claude-code.md`.
- ADR-0043.

## Non-goals

- Renomear as chaves `criticalDemoted` e `pathBelowExpected`.
- Medir erro de risco no relatório da sombra: o veredito da pessoa é só de caminho. O critério "nenhum CRITICAL rebaixado" (ADR-0023, ADR-0036) passa a proteger contra complexidade subestimada; o risco segue protegido pelo piso do diff e por `exactByStage.risk` no eval. Registrado no ADR como decisão futura.
- Checar a versão do Claude Code: exigiria subprocesso, e a documentação não diz o comportamento antes da 2.1.217.
- Alterar `aifw-adversary`, `aifw-qa`, `aifw-worker`, `aifw-senior` ou o hook.

## Acceptance

- O relatório da sombra e o `assess eval` mantêm as chaves e passam a descrever o caminho pela complexidade; teste cobre o texto e as chaves.
- `aifw claude check` não avisa com o padrão nem com valores 2 ou 3; avisa com 1 no ambiente ou em qualquer um dos três `settings`; ignora valores que não sejam inteiros positivos em dígitos (`abc`, `0`) e arquivos ausentes ou ilegíveis.
- Os templates do planner e do lead e a skill trazem o plano B; `docs/claude-code.md` cita a variável, o padrão 3, o mínimo 2 e as fontes.
- ADR-0043 aceito; suíte inteira e `ruff` passando; revisão em duas etapas aprovada.
