# Revisão independente — cascade-orchestration

## Adversário

Rodada 2, de correção. Escopo: `git diff 9f65d6c..HEAD` (commit 5781381), conferido contra o achado 1 e as ressalvas 1, 3, 4 e 6 de `evidence/independent-review-1.md`. O código já revisado na rodada 1 não foi caçado de novo.

### Achado 1 da rodada 1 (REQ-SUBAGENTS-DELEGATION): corrigido

- `specs/claude-subagents.delta.yaml` agora põe REQ-SUBAGENTS-DELEGATION em `modified`, com o texto da cascata (quick em L0, executor em L1, planner com worker em L2, lead com worker em L3, executor ou senior na exceção).
- `aifw spec sync cascade-orchestration --dry-run` devolve `added: [REQ-SUBAGENTS-CASCADE]` e `modified: [REQ-SUBAGENTS-DELEGATION]`. Na spec resultante de claude-subagents, REQ-SUBAGENTS-DELEGATION e REQ-SUBAGENTS-CASCADE descrevem a mesma cascata, e o texto antigo ("aifw-executor executando também em L3 e o aifw-quick nas tarefas rápidas de L2 e L3") sumiu. Não sobra nenhum par de MUST incompatíveis. REQ-SUBAGENTS-MANDATORY-ORCHESTRATION ("negada, citando o aifw-executor e o aifw-quick") continua valendo, porque a mensagem do hook cita os dois.
- Rodei uma sonda em pasta temporária (`python -m pytest`, 40 casos: 4 caminhos × risco final × risco do modelo, com o piso do diff). Ela confere o "then" novo de SCN-SUBAGENTS-DELEGATION em `path_context`, e os 40 passaram. Sem a exceção, cada caminho cita os seus papéis, com os revisores em PLANNED e CRITICAL. Com risco alto ou crítico em FAST ou WORK, o contexto cita `aifw-executor` ou `aifw-senior` sozinho e os dois revisores, e não cita mais `aifw-quick` ou `aifw-executor` da linha trocada. O pedido de aprovação aparece se e somente se o risco é alto ou crítico, e o texto não tem pontuação duplicada.
- `aifw spec analyze cascade-orchestration`: pass, sem findings. A rastreabilidade ganhou REQ-SUBAGENTS-DELEGATION na TASK-CASCADE-ASSESSOR e o link SCN-SUBAGENTS-DELEGATION → TEST-CASCADE-ORCHESTRATION.

### Ressalvas da rodada 1 que foram corrigidas

- Ressalva 1: o contexto da exceção troca a linha da cascata (`swapped`), em vez de somar as duas. Com risco alto ou crítico em L0 ou L1 não aparece mais "sem revisor", e "revisam" aparece uma vez só (conferido na sonda).
  - Contra a skill e `docs/routing.md`: os dois dizem "faz sozinho … Depois, os dois revisores" na exceção (SKILL.md:88; routing.md:24 e 45), e o contexto diz "planeja e executa sozinho, e depois aifw-adversary e aifw-qa revisam". É o mesmo conteúdo, sem contradição, e bate com os templates de `aifw-executor` e `aifw-senior` ("planeja e executa sozinho").
- Ressalva 3: `hooks.py` cita `aifw-senior`, `docs/claude-code.md` acompanhou e o design registra a mudança de texto do hook. Não sobrou "aifw-planner or aifw-lead" em código ou docs, fora a descrição do `aifw-worker`, que está correta. `test_orchestration.py` passa.
- Ressalva 4: `aifw-planner` e `aifw-lead` (template e cópia) dizem "aprovado (pela pessoa, quando o risco pede; com risco baixo ou médio, o plano que o agente principal entregar)". `aifw claude check` deu pass, sem findings.
- Ressalva 6: o README cita os nove papéis, e `README.md` entrou nos `paths` do `tasks.yaml`.

Testes: `python -m pytest tests_python/test_cascade.py tests_python/test_orchestration.py tests_python/test_role_subagents.py tests_python/test_assessor_active.py tests_python/test_assessment.py -q` deu 94 passed.

### Ressalvas (sem prova de falha; não reprovam)

1. Na skill, SKILL.md:103 diz "L0 e L1: delegue … ao `aifw-quick` ou ao `aifw-executor` … sem revisor", sem ressalvar a exceção que a linha 88 descreve logo acima. A linha não mudou nesta rodada e as linhas 88 e 107 cobrem o caso, mas um "salvo a exceção de risco" deixaria a skill alinhada ao contexto corrigido.
2. REQ-SUBAGENTS-INSTALL continua com "Os cinco arquivos ficam…". Não chega a ser incompatível, porque REQ-SUBAGENTS-CASCADE acrescenta os outros quatro, mas o texto ficou desatualizado diante dos nove papéis.
3. `evidence/tests.txt`, na parte de Cobertura, não lista SCN-SUBAGENTS-DELEGATION, embora a rastreabilidade agora ligue esse cenário a esse arquivo. Os testes que o cobrem (`test_cascade.py` e `test_role_subagents.py`) existem e passam.
4. As ressalvas 2, 5 e 7 da rodada 1 seguem como estavam (revisores sem pasta de mudança em L2/L3 de risco baixo; semântica de `criticalDemoted` e `pathBelowExpected`; limite de aninhamento remoto). Estão fora do escopo desta rodada.

## QA

Escopo: `git diff main...HEAD` (40 arquivos, 27 fora da pasta da mudança), conferido contra `proposal.md` (Acceptance e Non-goals), `design.md`, as duas specs delta, o ADR-0042, `tasks.yaml`, `traceability.yaml` e `evidence/tests.txt`. Comandos rodados cada um sozinho, sem escrever nada.

### Gates e suíte

| Comando | Resultado |
| --- | --- |
| `python -m pytest tests_python -q` | 2791 passed (127 s) |
| `aifw spec validate cascade-orchestration` | pass, sem findings; capabilities claude-subagents e task-assessor |
| `aifw spec analyze cascade-orchestration` | pass, sem findings; requisitos 3/3 ligados a tarefa, cenários 3/3 verificados, tarefas 3/3 concluídas; `weakTraces` vazio (probabilidades 0,991, 0,997 e 0,996) |
| `aifw spec sync cascade-orchestration --dry-run` | pass; claude-subagents: added REQ-SUBAGENTS-CASCADE, modified REQ-SUBAGENTS-DELEGATION; task-assessor: added REQ-ASSESSOR-COMPLEXITY-PATH |
| `aifw claude check` | `{"status": "pass", "findings": []}` |
| `aifw validate --change cascade-orchestration` (sem `--write`) | `blocked`, com um único bloqueio: o gate `independent-review`, porque este arquivo ainda não tinha a linha `Resultado:`. Passaram build, cli-docs, conformance, context-integrity, lint, manifest, project-map, secret-scan, session-conformance, tests e typecheck; sem warnings. Não reexecutei depois de escrever a linha final; a sessão deve rodá-lo (com `--write`, como a skill manda) para confirmar que o bloqueio some. |

### Critérios de aceitação da proposta

| Critério | Evidência |
| --- | --- |
| `path_for` devolve FAST, WORK, PLANNED e CRITICAL pela complexidade, qualquer que seja a importância | `python/aifw/assessment.py:228` (só a complexidade entra); `tests_python/test_assessment.py::test_path_rule`, parametrizado com risco L0/L3, importância baixa/crítica e as quatro complexidades; passa na suíte |
| O contexto cita a cascata de cada nível, a exceção com risco L2/L3 e o pedido de aprovação e dos revisores | `assessment.py` (`PATH_RULE`, `EXCEPTION`, `path_context`); `tests_python/test_cascade.py` (`test_each_path_names_its_cascade`, `test_high_risk_on_a_small_task_swaps_the_cascade`, `test_high_risk_keeps_the_cascade_on_larger_tasks`, `test_governance_follows_the_risk`, `test_diff_raised_risk_is_shown`); `test_role_subagents.py::test_path_context_names_the_subagents`; `test_assessor_active.py` |
| `aifw claude enable` instala os quatro papéis com modelo, esforço e ferramentas do template, e `aifw claude check` os confere | `python/aifw/claude.py` (`AGENTS` com nove nomes); `templates/claude/agents/aifw-{planner,lead,worker,senior}.md` e as cópias em `.claude/agents/`; `test_cascade.py::test_new_templates_and_enable` (modelo, esforço, `disallowedTools: Agent` só em worker e senior); `test_role_subagents.py::test_enable_installs_the_nine_subagents`; `aifw claude check` pass |
| A skill descreve a cascata, a exceção e a regra de que o Opus da conversa só orquestra | `templates/claude/skills/aifw-workflow/SKILL.md` (seção "Modelos por classe": tabela por nível, parágrafo "Exceção de risco", "Você só orquestra e nunca implementa, em nenhum nível"); a cópia `.claude/skills/aifw-workflow/SKILL.md` difere do template só pelo rodapé de versão e hash, e `aifw claude check` passa |
| Suíte inteira passando e revisão em duas etapas aprovada | 2791 passed acima; a primeira etapa é a seção "Adversário" (rodada 1 reprovou o achado de REQ-SUBAGENTS-DELEGATION, `evidence/independent-review-1.md`; rodada 2 confirmou a correção, sem achado novo); a segunda é esta seção |

### Cenários da spec

| Cenário | Evidência |
| --- | --- |
| SCN-ASSESSOR-COMPLEXITY-PATH | `test_assessment.py::test_path_rule`, `test_cascade.py`, `test_assessor_active.py`; `evidence/tests.txt` lista a cobertura; `traceability.yaml` liga o cenário a TEST-CASCADE-ORCHESTRATION |
| SCN-SUBAGENTS-CASCADE | `test_cascade.py::test_new_templates_and_enable`, `test_role_subagents.py`; a skill cita os nove papéis (`test_role_subagents.py`) |
| SCN-SUBAGENTS-DELEGATION | `test_cascade.py` e `test_role_subagents.py::test_path_context_names_the_subagents` (quick, executor, planner e worker, lead e worker, revisores em PLANNED e CRITICAL, executor ou senior sozinho com risco alto); `evidence/tests.txt` agora lista este cenário em "Cobertura acrescentada na rodada 2" (ressalva 3 do adversário resolvida) |

Non-goals respeitados no diff: `route explain` não mudou, o nível `--level` e `change.yaml` não foram renomeados, e nenhuma configuração de esforço da sessão principal foi tocada. `python/aifw/hooks.py` mudou só a mensagem de negação (ADR-0040), como o design registra.

### Documentação e artefatos derivados

- `tasks.yaml` lista todos os 27 arquivos do diff fora da pasta da mudança: `python/aifw/assessment.py`, `claude.py`, `hooks.py`, `evals/assessment/tasks-cases.yaml`, os quatro testes, `templates/claude/agents/` e `.claude/agents/` (pastas, cobrindo os seis arquivos de cada lado), as duas skills, `docs/claude-code.md`, `docs/routing.md`, o ADR-0042, `CHANGELOG.md` e `README.md`. Os registros em `.aifw/changes/active/cascade-orchestration/` ficam livres pela regra do plano aprovado.
- Coerência da cascata entre as fontes: contexto do avaliador (`assessment.py`), skill (template e cópia), `docs/claude-code.md` (tabela de subagentes e bullets L0 a L3, exceção e governança), `docs/routing.md` (as duas tabelas e a nota de exceção), README (nove papéis), CHANGELOG e ADR-0042 dizem a mesma coisa: L0 `aifw-quick`, L1 `aifw-executor`, L2 `aifw-planner` com `aifw-worker`, L3 Opus com `aifw-lead` e `aifw-worker`, exceção `aifw-executor` em L0 e `aifw-senior` em L1, revisores depois, governança pelo risco. Não achei contradição de modelo, esforço, ferramenta Agent ou revisor.
- `docs/routing.md` não ficou com a regra antiga: a tabela "Avaliador de tarefas" e a de "No Claude Code" já estão pela complexidade. Busca por "Opus planeja" e por "cinco papéis/arquivos/subagentes" em `docs/`, README, templates, `python/` e `.aifw/specs` só acha o rollback do ADR-0042 (que descreve o estado anterior, corretamente) e a spec aceita REQ-SUBAGENTS-INSTALL.
- ADR-0042 segue o formato dos ADR-0040 e ADR-0041 (Status, Date, Impact, Change, Amends) e registra decisão, consequências e rollback.

### Eixo Standards

Fontes: `AGENTS.md` (sem regra de estilo de código), `pyproject.toml` (ruff, linha de 110, `E4,E7,E9,F`; o gate `lint` passou), `principle-catalogs/engineering-principles.yaml` e a lista de smells. Nenhum padrão documentado do repositório é violado no diff.

Julgamentos, não violações:

1. `path_for(risk, importance, complexity)` ignora `risk` e `importance` e cai em `"CRITICAL"` para qualquer complexidade fora das três primeiras. Possível Speculative Generality (parâmetros sem uso); o design registra que a assinatura fica igual para `assessment_eval` e os testes, e `COMPLEXITY` (assessment.py:57) restringe o valor a quatro nomes, então o `CRITICAL` por omissão só ocorre com "alta". Fica como está.
2. `test_cascade.py` repete a lista de papéis, modelos e esforços que `test_role_subagents.py::EXPECTED` já tem para os quatro novos. Possível Duplicated Code em testes, pequeno e sem custo real.
3. `LEVEL_OF_PATH`, `RISK_WORD`, `EXCEPTION` e `PATH_RULE` são mapas por caminho; não há cascata de `if` repetida sobre o mesmo tipo. Nada a apontar em Repeated Switches.

### Ressalvas (sem prova de falha; não reprovam)

1. A skill (bullet "L0 e L1: delegue a tarefa inteira … sem revisor") e o bullet equivalente de `docs/claude-code.md` não ressalvam a exceção no mesmo item; ela vem no parágrafo e no bullet seguintes, e o contexto do avaliador, que o agente lê a cada pedido, já a diz certa. Um "salvo a exceção de risco" no bullet fecharia a leitura isolada. É a ressalva 1 do adversário, ainda aberta.
2. REQ-SUBAGENTS-INSTALL, na spec aceita, mantém "Os cinco arquivos…" e a lista de cinco subagentes. REQ-SUBAGENTS-CASCADE acrescenta os outros quatro e `spec sync` não gera conflito, mas o texto antigo fica desatualizado até uma mudança de spec o corrigir. É a ressalva 2 do adversário.
3. O `aifw validate --change` só fica sem bloqueio depois desta linha final; o único bloqueio que vi foi o gate `independent-review`.
4. Seguem fora do escopo, como o adversário já registrou: revisores sem pasta de mudança em L2/L3 de risco baixo; semântica de `criticalDemoted` e `pathBelowExpected`; limite de aninhamento remoto.

Resultado: aprovado com ressalvas
