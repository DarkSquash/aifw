# Revisão independente — role-subagents

## Adversário

Rodada 2, de correção. Escopo revisado: `git diff 2118386..HEAD` (commit d2c1bfb), que muda `docs/routing.md`, `HOW_TO_USE.md` e `tests_python/test_role_subagents.py` e acrescenta `evidence/independent-review-1.md`. A conferência foi feita contra os achados da rodada 1, `specs/claude-subagents.delta.yaml`, `templates/claude/skills/aifw-workflow/SKILL.md` e `PATH_RULE` em `python/aifw/assessment.py:138-149`, dentro do modelo de ameaça aceito (ADR-0034, ADR-0037). O código já revisado na rodada 1 não foi reexaminado.

Verificações rodadas:

- `python -m pytest tests_python/test_role_subagents.py -q`: 10 passed.
- `python -m pytest -q -x`: 2574 passed (eram 2573 na rodada 1; a diferença é o teste novo).
- Nenhum teste lê `docs/routing.md` (`grep -rn routing.md tests_python` não acha nada), então a mudança de texto não quebra teste algum.

### Achado 1 da rodada 1 (`docs/routing.md` com o fluxo antigo): corrigido

- `docs/routing.md:15`: a frase "parâmetro `model` da ferramenta Agent" saiu. O texto agora diz que a skill `aifw-workflow` delega pelo nome aos subagentes que o `aifw claude enable` instala, sem passar `model`. Isso bate com `SKILL.md:95` e com REQ-SUBAGENTS-DELEGATION. O nome antigo, skill `aifw`, também foi trocado por `aifw-workflow`, que é a skill que de fato tem a tabela.
- `docs/routing.md:17-22`: a tabela por classe nomeia `aifw-executor`, `aifw-quick`, `aifw-adversary` e `aifw-qa`, com os mesmos modelos de `SKILL.md:87-93`. A revisão de L2/L3 tem duas etapas, adversário e depois QA, como em `SKILL.md:58-59,82-83`. A expressão "revisor independente opus" não aparece mais.
- `docs/routing.md:36-41`: as linhas FAST, WORK, PLANNED e CRITICAL da tabela do avaliador batem com cada entrada de `PATH_RULE`: executor por caminho, Opus planejando em PLANNED e CRITICAL, Opus executando em CRITICAL, `aifw-adversary` e depois `aifw-qa` revisando, e aprovação humana em CRITICAL.
- O link `claude-code.md#modelos` aponta para a seção `## Modelos` de `docs/claude-code.md:131`, que existe.

Nenhum achado novo provado.

### Ressalvas da rodada 1 tratadas

- Ressalva 5: `HOW_TO_USE.md:31` agora cita os subagentes em `.claude/agents/aifw-*.md`.
- Ressalva 6: `test_check_reports_a_subagent_from_another_version` cobre o caso da versão antiga. Com o carimbo `0.0.1`, o `check` acusa a mensagem esperada, o `enable` devolve `agentBackups == [".claude/agents/aifw-qa.md.bak"]` e o `check` seguinte volta limpo. O teste passa.

### Ressalvas (sem prova de falha, não reprovam)

1. A outra metade da ressalva 5 ficou como estava. `templates/claude/skills/aifw/SKILL.md:45` ainda diz que, na nova sessão, valem "o hook de permissões e impasses (`.claude/settings.json`) e a skill `aifw-workflow`", sem citar os subagentes. A frase está incompleta, mas não errada.
2. O teste novo confere o `.bak` só pelo valor que o `enable` devolve (`agentBackups`), sem checar se o arquivo `.bak` existe no disco. A rodada 1 conferiu isso à mão e viu o arquivo gravado.
3. As ressalvas 1 a 4 da rodada 1 continuam valendo, porque o diff não mexeu nelas: revisores com `Write`/`Bash`, `code-review` sem `Agent` em `tools`, `.claude/agents/` fora de `CONTROL` e o `check` que só olha o carimbo.

## QA

Etapa 2, depois de o adversário não achar defeito provado na rodada 2. Escopo: `git diff main...HEAD`, `specs/claude-subagents.delta.yaml`, a seção Acceptance de `proposal.md` e ADR-0038.

### Gates e suíte (rodados por mim, cada um sozinho)

- `python -m pytest tests_python -q`: 2574 passed in 86.54s.
- `aifw spec validate role-subagents`: `pass: true`, sem achados.
- `aifw spec analyze role-subagents`: `pass: true`, sem achados; requisitos 3/3 ligados a tarefa, cenários 3/3 verificados, tarefas 4/4 concluídas.
- `aifw claude check`: `status: pass`, sem achados.

### Critérios de aceitação (proposal.md)

1. `enable` cria os cinco arquivos com modelo, esforço e ferramentas do template; segunda execução não muda nada; cópia editada vai para `.md.bak`. Coberto por `tests_python/test_role_subagents.py`: `test_enable_installs_the_five_subagents`, `test_second_enable_changes_nothing`, `test_edited_copy_is_backed_up_and_restored`. A implementação está em `python/aifw/claude.py` (`install_template`, `AGENTS`). Os modelos e esforços dos templates (`templates/claude/agents/*.md`) batem com a proposta: explorer haiku/low, quick haiku/low, executor sonnet/medium, adversary opus/high, qa sonnet/high.
2. `check` acusa ausência ou versão antiga e passa depois do `enable`. Coberto por `test_check_reports_missing_subagents_until_enable` e `test_check_reports_a_subagent_from_another_version`; `aifw claude check` neste repositório devolve `pass`.
3. O contexto do avaliador cita o subagente de cada caminho. Coberto por `test_path_context_names_the_subagents` (FAST, WORK, PLANNED, CRITICAL), contra `PATH_RULE` em `python/aifw/assessment.py`.
4. A skill descreve as duas etapas, o ônus da prova e o limite de rodadas: `templates/claude/skills/aifw-workflow/SKILL.md` (passo 7, "Delegue ao subagente `aifw-adversary`", "`aifw-qa`", "Ressalva sem prova não reabre rodada", "terceira reprovação"). `test_workflow_skill_documents_the_subagents` confere os cinco nomes, `subagent_type` e "terceira reprovação".
5. Suíte inteira, `spec validate`/`analyze` limpos e esta mudança revisada pelo fluxo novo: suíte e specs acima; revisão em `evidence/independent-review-1.md` (rodada 1, reprovada), seção Adversário (rodada 2) e esta seção.

### Cenários da spec

- SCN-SUBAGENTS-INSTALL: os testes do critério 1 e 2.
- SCN-SUBAGENTS-DELEGATION: `test_path_context_names_the_subagents` e `test_workflow_skill_documents_the_subagents`. A instrução "sem `model`, só para subir" está em `SKILL.md` (bullet "Delegue pelo nome (`subagent_type`) sem passar `model`") e em `docs/routing.md:15`.
- SCN-SUBAGENTS-REVIEW-FLOW: o texto está nos templates `aifw-adversary.md` (ônus da prova, `Resultado: reprovado`, sem linha `Resultado` quando não acha) e `aifw-qa.md` (seção `## QA`, `Resultado:` final) e na skill. É instrução, sem teste automatizado do conteúdo dos templates (ressalva 1).

### Documentação e artefatos derivados

- `docs/claude-code.md` (lista do que o `enable` grava, `.bak`, como desabilitar, tabela de subagentes em Modelos), `docs/routing.md` (corrigido na rodada 2, bate com `PATH_RULE`), `HOW_TO_USE.md:31`, `README.md`, `CHANGELOG.md` e `docs/decisions/ADR-0038-role-subagents.md`: todos refletem a mudança.
- A cópia `.claude/skills/aifw-workflow/SKILL.md` é igual ao template, salvo o carimbo de versão; os cinco `.claude/agents/aifw-*.md` são iguais aos templates, salvo o carimbo (`diff` conferido).
- `design.md` tem abordagem e riscos/rollback preenchidos; `approval.md` registra a aprovação; `tasks.yaml` com as quatro tarefas `done` e `traceability.yaml` ligando os três cenários a `evidence/tests.txt`.
- Eixo Standards (`code-review`, `principle-catalogs/`): `install_template` extrai a lógica antes duplicada da skill sem perder o tratamento do `.bak`; o `PATH_RULE` ganhou um comentário só com o motivo; sem duplicação nem acoplamento novo. Nada a apontar.

### Ressalvas (sem prova de falha, não reprovam)

1. `evidence/tests.txt` está defasado em relação à rodada 2: registra `9 passed` de `test_role_subagents.py` e `2573 passed` da suíte, e hoje são 10 e 2574 (o teste da versão antiga foi acrescentado depois). Ele também afirma que "os templates do adversário e do QA trazem o ônus da prova e o Resultado" como coberto, mas nenhum teste lê esses templates; o conteúdo existe (conferido por leitura), só não é verificado automaticamente. Convém regravar o `tests.txt` com os números atuais.
2. `docs/plans/2026-10-17-avaliador-de-tarefas.md:50` ainda traz "revisor independente e humano" para CRITICAL. É um plano histórico e não entra no escopo da mudança.
3. As ressalvas do adversário continuam valendo: `templates/claude/skills/aifw/SKILL.md:45` sem os subagentes, o teste do `.bak` que confere só o valor devolvido, revisores com `Write`/`Bash`, `code-review` sem `Agent` em `tools`, `.claude/agents/` fora de `CONTROL` e o `check` que só olha o carimbo.

Resultado: aprovado com ressalvas
