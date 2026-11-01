# Revisão independente — assessor-metrics-nesting-check

## Adversário

Escopo: `git diff feat/cascade-orchestration..2e519e8`, conferido contra `specs/claude-subagents.delta.yaml` (REQ-SUBAGENTS-NESTING, SCN-SUBAGENTS-NESTING-CHECK, SCN-SUBAGENTS-NESTING-FALLBACK), `specs/task-assessor.delta.yaml` (REQ-ASSESSOR-SHADOW-METRICS, SCN-ASSESSOR-SHADOW-METRICS), `tasks.yaml`, `design.md`, `proposal.md` (Acceptance) e ADR-0043. Modelo de ameaça: o check protege contra erro do agente (ADR-0034, ADR-0037).

### O que verifiquei

- **REQ-SUBAGENTS-NESTING, aviso (claude-subagents.delta.yaml:11, SCN-SUBAGENTS-NESTING-CHECK:16-19).** Testei `nesting_findings` direto, num diretório temporário fora do projeto. O ambiente e cada um dos três settings com `1` (string ou inteiro JSON) e com `01` geram um achado que diz a fonte. Não geram achado: ausente, `2`, `0`, `-1`, `abc`, `""`, `" 1"`, `True`, `1.0`, lista, objeto, JSON que é lista, bytes inválidos, JSON quebrado e `settings.json` que é um diretório (o `OSError` é capturado). Isso bate com a documentação primária, que consultei: https://code.claude.com/docs/en/env-vars diz "Accepts a positive whole number in plain digits; anything else is ignored".
- **Cenário com a variável no ambiente da máquina.** Rodei `test_cascade`, `test_role_subagents`, `test_audit_features`, `test_hardening`, `test_assessor_active` e `test_cli` com `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` no ambiente: 181 passaram. Nenhum teste antigo afirma `status == "pass"` em `check_project`, e as asserções `"subagent" in f` não pegam a mensagem nova, que só tem `SUBAGENT` em maiúsculas.
- **Só aviso.** `aifw claude check` sai com 2 em qualquer `warning`, o que já acontecia antes. `aifw doctor` só informa o resultado (cli.py:718-721). Nenhum gate nem hook chama `check_project`.
- **SCN-SUBAGENTS-NESTING-FALLBACK (claude-subagents.delta.yaml:20-27).** Os templates `aifw-planner`, `aifw-lead` e `aifw-workflow/SKILL.md` trazem o plano B (sem a ferramenta Agent ou com falha no lançamento: implementa a parte, uma tarefa por vez, e avisa no resumo, sem devolver a implementação ao agente principal). As cópias em `.claude/` têm o mesmo corpo dos templates: comparei o `git show` do template com o da cópia sem o carimbo, e os três arquivos são idênticos. Nenhum texto que ficou para trás contradiz o plano B (tabelas de papéis, descrições no frontmatter, `docs/routing.md:26`).
- **REQ-ASSESSOR-SHADOW-METRICS (task-assessor.delta.yaml:11-21).** As chaves `criticalDemoted` e `pathBelowExpected` não mudaram. O rótulo novo é coberto por `test_assessment.py:89`. `pathBelowExpected == 1` com a complexidade subestimada já era coberto por `test_assessment_eval.py:71`. Os arquivos afetados passaram: 154 testes.

### Achados

Nenhum achado provado.

### Ressalvas

1. **O padrão era 1 na 2.1.217 e na 2.1.218.** A mesma página da documentação diz: "In v2.1.217 through v2.1.218, the default was 1, so a subagent couldn't spawn its own unless you raised the limit". Nessas versões, com a variável ausente, a cascata não tem aninhamento e o check não avisa. Isso está dentro da spec, porque "Ausente ... não gera aviso" e o design dispensa a checagem de versão. Só o plano B cobre esse caso. `docs/claude-code.md` e o ADR dizem "desde a 2.1.219" e "antes da 2.1.217 não verificado", mas não dizem que nas duas versões anteriores o padrão desligava o aninhamento. Fica como sugestão de documentação, sem reprovar.
2. **Teste fraco do plano B.** `test_planner_lead_and_skill_carry_the_fallback` procura "agente principal" no planner e no lead, mas esse texto já existia antes ("o agente principal chama"). Na prática, o teste só prova "sem worker". O conteúdo está correto, conforme lido acima.
3. **Fontes de settings fora da spec.** O check não lê os managed settings nem `~/.claude/settings.local.json`. A spec lista só as três fontes, então isso fica fora do escopo.

## QA

Eixo Standards feito por mim, sem subagentes. Fontes lidas: `AGENTS.md`, ADR-0042 (convenções da cascata) e a lista de smells da skill `code-review`. O diff não toca regra de `principle-catalogs/`.

### Critérios de aceitação (proposal.md) e evidência

| Critério | Evidência |
|---|---|
| Relatório da sombra e `assess eval` mantêm as chaves e descrevem o caminho pela complexidade; teste cobre texto e chaves | `python/aifw/assessment.py` (rótulo "Caminho CRITICAL (complexidade alta) rebaixado" e comentário), `python/aifw/assessment_eval.py` (comentário), `docs/routing.md:56`. `tests_python/test_assessment.py:89` afirma o texto, e a linha anterior afirma `criticalDemoted == [3]`. `pathBelowExpected == 1` já coberto por `tests_python/test_assessment_eval.py:71`. |
| `claude check` não avisa com padrão, 2 ou 3 | `test_spawn_depth_ok_in_environment[None/2/3]` em `tests_python/test_cascade.py`. |
| Avisa com 1 no ambiente e em cada um dos três settings | `test_spawn_depth_one_in_environment` e `test_spawn_depth_one_in_settings` (3 caminhos); afirmam um achado que cita a fonte. |
| Ignora `abc`, `0`, arquivos ausentes ou ilegíveis | `test_spawn_depth_ignored_values[abc/0/""]` e `test_spawn_depth_unreadable_settings_ignored`. Arquivos ausentes estão implícitos em todos os testes (home e arquivos não existem). |
| Plano B nos templates do planner e do lead, na skill e em `docs/claude-code.md` | `templates/claude/agents/aifw-planner.md`, `aifw-lead.md`, `templates/claude/skills/aifw-workflow/SKILL.md`; `docs/claude-code.md:158-162` cita a variável, o padrão 3, o mínimo 2 e as duas fontes. Cópias em `.claude/` regeneradas e commitadas (carimbo sha256 novo no diff). Teste: `test_planner_lead_and_skill_carry_the_fallback` (fraco, ver ressalva 2). |
| ADR-0043 aceito | `docs/decisions/ADR-0043-assessor-metrics-and-nesting-check.md`: `Status: accepted`, `Impact: L2`, `Amends` ADR-0036 e ADR-0042, contexto, decisão, consequências e rollback. |
| Suíte inteira e `ruff` passando | Rodei eu mesmo: `python -m pytest -q` = 2803 passed (108,85 s), igual ao `evidence/tests.txt`; `ruff check` = All checks passed; `ruff format --check` = 58 files already formatted. `aifw claude check` = `pass`, sem achados. |
| Revisão em duas etapas aprovada | Etapa 1 (`## Adversário`): nenhum achado provado. Etapa 2: esta seção. |

### Cenários da spec

- `SCN-SUBAGENTS-NESTING-CHECK`: testes `test_spawn_depth_*` em `tests_python/test_cascade.py` (11 casos parametrizados).
- `SCN-SUBAGENTS-NESTING-FALLBACK`: `test_planner_lead_and_skill_carry_the_fallback`, mais leitura direta dos três textos no diff.
- `SCN-ASSESSOR-SHADOW-METRICS`: `tests_python/test_assessment.py:89` e `tests_python/test_assessment_eval.py:71`.

### Gates

`aifw validate --change assessor-metrics-nesting-check --json` (sem `--write`), rodado antes desta seção, deu `blocked` por um único bloqueio: `independent-review`, que exige a linha `Resultado:` (escrita abaixo). `build`, `cli-docs`, `conformance`, `context-integrity` e `lint` passaram; li só o começo da saída (truncada), então a reexecução final fica com o agente principal.

### Artefatos derivados e documentação

- Spec deltas, `tasks.yaml` (4 tarefas, todas `done`, caminhos batem com o diff), `traceability.yaml` (os três cenários e os dois requisitos ligados a teste, design e ADR), `design.md`, `approval.md` (humana, gravada pelo hook) e `evidence/tests.txt`: presentes e coerentes com o diff.
- `CHANGELOG.md` (entrada em "Alterado"), `docs/claude-code.md`, `docs/routing.md` e ADR-0043 atualizados.

### Standards (padrões do repositório e smells)

- `AGENTS.md`: efeitos relacionados tratados (cópias em `.claude/`, docs, testes, CHANGELOG); sem refatoração extra; os non-goals do proposal não foram tocados.
- `python/aifw/claude.py`: função pequena, erros de leitura capturados nos tipos certos, sem dependência nova. Smell menor, questão de juízo: `SPAWN_DEPTH` ficou entre as constantes `STAMP` e `HASH`, que formam um par. Não afeta o comportamento.
- Os testes isolam o ambiente com `monkeypatch.delenv`, como o design previa.

### Ressalvas

1. (herdada do adversário) `docs/claude-code.md` e o ADR dizem "desde a 2.1.219" e "antes da 2.1.217 não verificado", mas a documentação primária diz que na 2.1.217-2.1.218 o padrão era 1; nessas versões, com a variável ausente, o check não avisa. Sugestão de texto, não bloqueia.
2. (herdada) `test_planner_lead_and_skill_carry_the_fallback` prova só "sem worker"; a asserção de "agente principal" já passava antes. O conteúdo está correto pela leitura.
3. Não verifiquei por execução o comportamento do Claude Code com a variável em 1, só a documentação e os testes do check.

Resultado: aprovado com ressalvas
