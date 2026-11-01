# Design — Métricas do avaliador e checagem de aninhamento

## Context

`assessment.report()` calcula `criticalDemoted` a partir dos vereditos da pessoa (valores são nomes de caminho) e `render_report` o mostra como "CRITICAL rebaixados". `assessment_eval.run_tasks` calcula `pathBelowExpected` comparando `path_for(...)` com o caminho esperado. Desde o ADR-0042, `path_for` usa só a complexidade. `claude.check_project` já confere hooks, skill, subagentes e comando global, sem olhar o aninhamento. O Claude Code limita subagentes a camadas abaixo da conversa por `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (padrão 3).

## Approach

- Métricas: nenhuma lógica muda. Rótulo do relatório, comentários e uma frase em `docs/routing.md`. O teste existente de `criticalDemoted` ganha a asserção do texto novo.
- Checagem: função pequena em `python/aifw/claude.py` que lê a variável de `os.environ` e do bloco `env` dos três `settings`. Só conta valor em dígitos, positivo e menor que 2. Arquivo ausente, JSON ilegível ou sem `env` são ignorados. `check_project` acrescenta um achado por fonte que tenha o valor, dizendo onde está e que o planner e o lead não lançam workers. Os testes usam `monkeypatch.delenv` para não depender do ambiente da máquina.
- Plano B: uma linha em `aifw-planner.md` e `aifw-lead.md`, e ajuste na skill e em `docs/claude-code.md`. As cópias instaladas em `.claude/` são regeneradas por `aifw claude enable` na própria branch e commitadas junto; ninguém as edita à mão, porque o `aifw claude check` só confere o carimbo da versão e não acusaria uma cópia velha.
- ADR-0043 (impacto L2, altera ADR-0036 e ADR-0042) registra as decisões, a fonte e a consequência do critério de ativação.

## Decisions

- Não renomear: as chaves são JSON público e os nomes falam de caminho, não de risco.
- Avisar se qualquer fonte tiver valor menor que 2, porque a documentação não diz a precedência entre ambiente e `settings`.
- O planner e o lead implementam eles mesmos no plano B, porque o agente principal nunca implementa e o hook só restringe a sessão principal.
- Sem checagem de versão do Claude Code.

## Risks and rollback

- O aviso pode incomodar quem limita o aninhamento de propósito; é só aviso, não bloqueia.
- No plano B o planner (Sonnet) pode implementar partes grandes; o resumo avisa e os dois revisores continuam.
- Comportamento do Claude Code antes da 2.1.217 não verificado.
- Rollback: reverter o commit da branch. Sem migração nem dado persistido; as chaves JSON não mudam; o aviso é só leitura.
