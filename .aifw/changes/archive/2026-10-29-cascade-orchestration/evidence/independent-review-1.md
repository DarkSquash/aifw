# Revisão independente — cascade-orchestration

## Adversário

Rodada 1. Escopo: `git diff main...HEAD` (commit 9f65d6c), os deltas `specs/task-assessor.delta.yaml` (REQ-ASSESSOR-COMPLEXITY-PATH) e `specs/claude-subagents.delta.yaml` (REQ-SUBAGENTS-CASCADE), a seção Acceptance da proposta, o design, os Non-goals e o ADR-0042. Conferido:

- `assessment.path_for` e `path_context` em todas as combinações de complexidade, risco, importância e piso do diff, mais complexidade desconhecida e status não registrado (sonda em pasta temporária, `python -m pytest`);
- `evals/assessment/tasks-cases.yaml` contra `path_for`, e o uso em `assessment_eval.run_tasks` e em `assessment.report`;
- os quatro templates novos e as cópias em `.claude/agents/` (frontmatter, ferramentas, hash), `claude.AGENTS`, `aifw claude check` neste repositório;
- o limite de aninhamento de subagentes no Claude Code 2.1.303 instalado;
- o texto do avaliador, a skill (template e cópia), `docs/claude-code.md`, `docs/routing.md`, CHANGELOG, ADR-0042 e as specs aceitas em `.aifw/specs/current/`;
- a suíte inteira: `python -m pytest -q tests_python` deu 2791 passed.

O que resistiu às tentativas de quebra:

- `path_for` devolve FAST/WORK/PLANNED/CRITICAL só pela complexidade, qualquer que seja o risco ou a importância. Complexidade desconhecida (`None`, `""`, `"Trivial"`, `"xyz"`) cai em CRITICAL, ou seja, sobe e nunca desce. Em `assess`, `most_likely` sempre devolve um valor de `COMPLEXITY`.
- Nas 4×4×4×5 combinações (complexidade × risco × importância × piso), o contexto pede `aifw spec request-approval` se e somente se o risco final é L2/L3, e cita `aifw-adversary` e `aifw-qa` se e somente se o risco é alto/crítico ou o caminho é PLANNED/CRITICAL. A exceção aparece só em FAST/WORK com risco alto ou crítico. O piso do diff aparece como "elevado pelo diff". Com status diferente de `recorded`, o contexto continua sendo o aviso de indisponível.
- Os 24 casos de `tasks-cases.yaml` batem com `path_for`.
- `aifw-worker` e `aifw-senior` têm `disallowedTools: Agent`. `aifw-planner` e `aifw-lead` não têm `tools` nem `disallowedTools`, então herdam o Agent. O binário do Claude Code 2.1.303 tem limite padrão de aninhamento 3 (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, `var n=3`), o que basta para conversa → lead/planner → worker. `aifw claude check` passa. A skill instalada é igual ao template, tirando o carimbo.

### Achado 1: a spec aceita REQ-SUBAGENTS-DELEGATION fica contradita e não foi modificada no delta (severidade média)

- Onde: `.aifw/changes/active/cascade-orchestration/specs/claude-subagents.delta.yaml:21` (`modified: []`), diante de `.aifw/specs/current/claude-subagents.yaml:18-28`.
- Spec: o requisito aceito REQ-SUBAGENTS-DELEGATION diz: "O caminho entregue pelo avaliador e a tabela de modelos da skill devem nomear o subagente de cada papel, com o aifw-executor executando também em L3 e o aifw-quick nas tarefas rápidas de L2 e L3". O cenário SCN-SUBAGENTS-DELEGATION diz: "O contexto cita … aifw-executor, aifw-quick, aifw-adversary e aifw-qa (PLANNED e CRITICAL)". A mudança implementa o contrário, como pedem a proposta e o ADR-0042 item 2: em PLANNED e CRITICAL quem executa são `aifw-worker` e `aifw-lead`, e `PATH_RULE` (`python/aifw/assessment.py:138-150`) não cita mais `aifw-executor` nem `aifw-quick`. O delta só acrescenta REQ-SUBAGENTS-CASCADE, sem modificar REQ-SUBAGENTS-DELEGATION. O teste que verificava esse cenário (`tests_python/test_role_subagents.py::test_path_context_names_the_subagents`) foi reescrito para conferir a regra nova, e a spec aceita não acompanhou.
- Cenário: depois do archive, `.aifw/specs/current/claude-subagents.yaml` traz dois MUST incompatíveis, REQ-SUBAGENTS-DELEGATION (executor e quick em L2/L3) e REQ-SUBAGENTS-CASCADE (planner/lead + worker em L2/L3), e o código viola o primeiro.
- Evidência:
  - `aifw spec sync cascade-orchestration --dry-run --json` devolve `"modified": []` para `claude-subagents`, e o `outputs` mantém REQ-SUBAGENTS-DELEGATION com o texto antigo ao lado de REQ-SUBAGENTS-CASCADE.
  - A sonda `test_delegation_spec_still_holds`, que confere o "then" de SCN-SUBAGENTS-DELEGATION em `path_context` para PLANNED/L2 e CRITICAL/L3, falha: `AssertionError: ('PLANNED', ['aifw-executor', 'aifw-quick'], 'AIFW, avaliador de tarefas (modo ativo): caminho PLANNED. …')`.
  - `aifw spec analyze` não acusa o conflito (pass, sem findings). A contradição passa pelos gates sem aviso.
- Correção esperada: pôr REQ-SUBAGENTS-DELEGATION em `modified` com o texto da cascata, ou em `removed` se REQ-SUBAGENTS-CASCADE o substitui. Vale avaliar o mesmo para REQ-SUBAGENTS-INSTALL (`claude-subagents.yaml:41-50`), que lista só os cinco papéis antigos e diz "Os cinco arquivos ficam…", enquanto o `enable` agora instala nove.

### Ressalvas (sem prova de falha; não reprovam)

1. Texto contraditório na mesma mensagem: com risco alto ou crítico em FAST ou WORK, o contexto diz primeiro "aifw-quick (Haiku, low) planeja e executa sozinho, sem revisor" (ou "aifw-executor … sem revisor") e só depois "Risco alto em L0: aifw-executor (Sonnet) faz sozinho, e depois aifw-adversary e aifw-qa revisam". A exceção vem por último e é explícita, mas um agente apressado pode seguir a primeira frase. Seria mais seguro trocar a linha da cascata pela exceção, em vez de somar as duas.
2. Revisores sem mudança: em PLANNED ou CRITICAL com risco baixo ou médio, o contexto manda chamar `aifw-adversary` e `aifw-qa`. Só que a governança desse risco não cria spec change, e os dois revisores escrevem, pelo template e pela trava do hook, apenas em `.aifw/changes/active/<id>/independent-review.md`. Não há pasta de mudança onde escrever, e a regex `REVIEW_FILE` aceitaria uma pasta qualquer criada só para isso. Nem a skill nem o design dizem onde fica essa revisão.
3. `aifw-senior` ausente da mensagem do hook: `python/aifw/hooks.py:170-171` e `docs/claude-code.md` (Orquestração) listam a cascata como "aifw-quick, aifw-executor, aifw-planner or aifw-lead", sem `aifw-senior`, que é o delegado direto da exceção em L1. Além disso, o design diz "nada no núcleo do hook muda", mas `hooks.py` mudou (só o texto, e estava nos `paths` do `tasks.yaml`).
4. `aifw-planner` e `aifw-lead` falam em plano "aprovado" ("Plano já aprovado", "já planejada e aprovada"), e em L2/L3 de risco baixo não há aprovação. A skill cobre o caso ("quando a governança pedir"), o template não.
5. Semântica de "CRITICAL rebaixados" (`assessment.report`, `criticalDemoted`) e de `pathBelowExpected` (`assessment_eval`): os dois mediam rebaixamento de risco L3 e agora medem complexidade. O risco só aparece em `exactByStage`. O impacto prático é baixo porque o recurso `tasks` já está sempre ativo (ADR-0037), mas o relatório e o eval perderam o sinal de risco crítico subavaliado.
6. Documentação periférica: `README.md:41` enumera os subagentes como "explorador, rápido, executor e a revisão em duas etapas, adversário e QA", sem os quatro novos. Fica fora da lista de docs do Scope, mas ficou para trás.
7. O Claude Code 2.1.303 lê o limite de aninhamento de `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` ou de uma flag remota (`maxSubagentSpawnDepthFromGrowthBook`), com padrão 3. Se o valor remoto baixar, a cascata L2/L3 quebra em "Subagent nesting limit reached". Não confirmei o valor efetivo nesta conta, nem que um subagente sem `tools` recebe o Agent na prática.

Resultado: reprovado
