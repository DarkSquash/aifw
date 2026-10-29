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
