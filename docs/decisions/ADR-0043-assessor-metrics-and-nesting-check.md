# ADR-0043: Métricas do avaliador e checagem de aninhamento

- Status: accepted
- Date: 2026-11-01
- Impact: L2
- Change: `assessor-metrics-nesting-check`
- Amends: ADR-0036 (o critério "nenhum CRITICAL rebaixado" agora protege contra complexidade subestimada), ADR-0042 (checagem e plano B do aninhamento de subagentes)

## Contexto

Desde o ADR-0042 o caminho de execução vem só da complexidade, mas duas métricas do avaliador ainda foram definidas quando o caminho vinha do risco: `criticalDemoted` (relatório da sombra) e `pathBelowExpected` (eval). Os nomes e o texto do relatório não diziam isso.

Além disso, `aifw-planner` e `aifw-lead` dependem de lançar `aifw-worker` pela ferramenta Agent. O Claude Code limita o aninhamento de subagentes pela variável `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`. O ADR-0042 registrou o limite, mas nada o checava e não havia plano B quando o lançamento falha ou a ferramenta não existe.

## Decisão

1. `criticalDemoted` e `pathBelowExpected` medem o caminho pela complexidade desde o ADR-0042. Nenhuma lógica muda e as chaves JSON não são renomeadas: elas são saída pública de `aifw assess report --json` e `aifw assess eval`, pelo mesmo motivo do ADR-0042 §6. O rótulo do relatório passa a ser "Caminho CRITICAL (complexidade alta) rebaixado".
2. O critério de ativação "nenhum CRITICAL rebaixado" (ADR-0023, ADR-0036) passa a proteger contra complexidade subestimada. O risco segue protegido pelo piso do diff e por `exactByStage.risk` no eval. Medir erro de risco no relatório da sombra fica como decisão futura: o veredito da pessoa, nesse relatório, é só de caminho.
3. `aifw claude check` avisa quando `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` é um número menor que 2 no ambiente, em `.claude/settings.local.json`, `.claude/settings.json` ou `~/.claude/settings.json`. Há um achado por fonte e é só aviso, sem bloqueio.
   - Fontes: https://code.claude.com/docs/en/sub-agents (seção "Let subagents spawn their own subagents") e https://code.claude.com/docs/en/env-vars. O padrão é 3 camadas abaixo da conversa (desde a 2.1.219); `1` desliga o aninhamento; a cascata do ADR-0042 precisa de 2.
   - O aviso vale para qualquer fonte que tenha o valor, porque a documentação não diz a precedência entre ambiente e `settings`.
   - Valores que não são inteiros positivos em dígitos (`abc`, `0`) e arquivos ausentes ou ilegíveis são ignorados.
   - Não há checagem de versão do Claude Code: ela exigiria um subprocesso, e o comportamento antes da 2.1.217 não foi verificado.
4. Plano B: se `aifw-planner` ou `aifw-lead` não tiver a ferramenta Agent, ou o lançamento falhar, ele implementa a parte ele mesmo, uma tarefa por vez, e avisa no resumo. Não devolve a implementação ao agente principal, que só orquestra (ADR-0042). Vale nos templates `aifw-planner` e `aifw-lead`, na skill `aifw-workflow` e em `docs/claude-code.md`. O hook só restringe a sessão principal.

## Consequências

- O aviso pode incomodar quem limita o aninhamento de propósito; por isso ele não bloqueia.
- No plano B o planner (Sonnet) pode implementar partes grandes. O resumo avisa, e os dois revisores continuam rodando depois.
- Os nomes das métricas continuam falando de caminho e não de risco; quem ler o relatório precisa do rótulo novo para saber que o número é de complexidade.
- Rollback: reverter o commit da mudança. Não há migração nem dado persistido; as chaves JSON não mudam e o aviso só lê arquivos.
