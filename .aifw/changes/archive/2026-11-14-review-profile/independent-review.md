## Adversário

### Rodada de correção 1

Escopo: `git diff HEAD~1..HEAD`, o commit `ee579b8` sobre `507c032`. Conferi o achado 1 da rodada anterior e as ressalvas, e procurei contradição nova entre a "Saída" e o item 1 do `aifw-qa`, a skill, o delta, o design, o ADR-0046 e `docs/routing.md` / `docs/claude-code.md`.

Rodado:
- `pytest tests_python/test_review_profile.py test_cascade.py test_reviewer_guardrails.py`: 188 passed.
- `aifw claude check`: status pass. `aifw spec validate review-profile`: sem achados.
- Comparei templates e cópias em `.claude/` (`agents/aifw-qa.md` e `skills/aifw-workflow/SKILL.md`) sem as linhas de carimbo: a única diferença é a linha em branco antes do carimbo, como na rodada anterior. `git diff HEAD~1..HEAD --stat -- .claude` mostra só esses dois arquivos.

Achado 1 (contradição entre a "Saída" e o item 1 de "Perfil leve" do `aifw-qa`): **corrigido**. A "Saída" (`templates/claude/agents/aifw-qa.md:33`) traz a exceção junto da regra, nos dois ramos: com arquivo ("salvo na devolução por diff fora do perfil leve (item 1 de "Perfil leve"), que fica sem linha `Resultado:`") e sem pasta ("a resposta traz só a seção `## QA`"). Agora concorda com o item 1 (linha 22), com o REQ-SUBAGENTS-REVIEW-PROFILE (delta, linha 11), com o SCN-SUBAGENTS-REVIEW-PROFILE-TEXT ("exceção expressa na Saída") e com a decisão 6 do ADR-0046. O teste `test_qa_output_excepts_the_diff_return_from_the_result_line` lê só o trecho depois de `## Saída`; sem a correção, ele falha.

Ressalvas da rodada anterior:
- R1 (laço na devolução): fechada. A skill (linha 109) diz "o perfil passa a `completo` e você chama o `aifw-adversary` e depois o `aifw-qa`, este com `Perfil de revisão: completo` no brief". Com esse brief, a seção "Perfil leve" do QA não se aplica, porque ela vale só para `interface` ou `texto`. O QA segue o fluxo normal e escreve o `Resultado:` final. Delta (REQ e SCN-TEXT), design (decisão 6) e ADR-0046 (decisão 6) dizem o mesmo.
- R3 (âmbito da declaração): fechada. O bullet começa com "em mudança L2 ou L3 (complexidade) de risco baixo ou médio", como no REQ.
- R4 (exceção longe da tabela): fechada. Há um parágrafo logo abaixo do parágrafo "Exceção de risco" da skill, e `docs/routing.md` traz a frase nos dois lugares (linhas 24 e 45).
- R5 (definição de `texto` em dois formatos): fechada. O item 1 do QA usa a mesma cláusula geral da skill.
- R2 (gate aceita perfil leve com `change.yaml` em L2/L3) e R6 (rastreio de `SCN-SUBAGENTS-REVIEW-FLOW`): mantidas por decisão, continuam ressalvas e não reprovam.

Contradição nova: não achei.
- A frase "A rodada de correção de um perfil leve volta ao `aifw-qa`" continua certa: depois da devolução o perfil já é `completo`, então a rodada de correção desse caso segue o item 7 e vai ao adversário.
- O "Na dúvida, e com risco alto ou crítico, o perfil é `completo`" não conflita com o novo âmbito da declaração: com risco alto não se declara, e as regras de revisores e de governança já mandam os dois revisores.
- O `docs/claude-code.md`, que não mudou nesta rodada ("o agente principal chama os dois revisores"), está de acordo.

Ressalva menor nova: `test_routing_doc_states_the_single_reviewer_twice` exige `count >= 2`, mas `docs/routing.md` já tinha uma ocorrência da frase (linha 26) e agora tem três. O teste continuaria passando se só uma das duas remissões novas fosse removida.

Não verificado: o comportamento real dos agentes, porque só o texto foi lido. A suíte inteira e o ruff não foram rodados de novo nesta rodada; a contagem de 2859 testes vem de `evidence/tests.txt`. O "4 failed antes das edições" é relato do worker e não foi reproduzido.

### Rodada inicial (resumo)

Achado 1 (média): o template do `aifw-qa` mandava, para a mesma devolução por diff fora do perfil sem pasta, não escrever `Resultado:` (item 1) e devolver a linha `Resultado:` na resposta ("Saída"). A exceção ficava longe da regra. Corrigido na rodada 1.

Ressalvas: R1 laço na devolução; R2 o gate aceita perfil leve com `change.yaml` em L2/L3 (gates.py:410), onde o risco exige `completo`; R3 âmbito da declaração; R4 exceção longe das tabelas; R5 duas definições de `texto`; R6 rastreio de `SCN-SUBAGENTS-REVIEW-FLOW` em `evidence/tests.txt`. R1, R3, R4 e R5 foram fechadas na rodada 1; R2 e R6 ficaram por decisão.

## QA

Perfil de revisão: completo (declarado no brief). Escopo: `git diff main..HEAD` (507c032 e ee579b8), delta `specs/claude-subagents.delta.yaml` contra `.aifw/specs/current/claude-subagents.yaml`, `proposal.md`, `design.md`, `tasks.yaml`, `traceability.yaml`, ADR-0046, CHANGELOG, `docs/claude-code.md`, `docs/routing.md`, `evidence/tests.txt`. Skills carregadas: `code-review` (fontes de padrão e lista de smells) e `writing-for-agents` (texto lido por agentes).

### Gates e suíte (rodados agora, no HEAD com o working tree atual)

- `python -m pytest -q -p no:cacheprovider tests_python`: 2859 passed (148s). Bate com `evidence/tests.txt`.
- `python -m ruff check .`: All checks passed. `ruff format --check .`: 324 files already formatted.
- `aifw claude check`: status pass, sem achados. Templates e cópias em `.claude/` diferem só pela linha em branco antes do carimbo (conferido por `diff` sem as linhas `aifw-version`/`aifw-sha256`).
- `aifw spec validate review-profile`: pass, sem achados. `aifw spec analyze review-profile`: pass; requisitos 2/2 ligados a tarefa, cenários 4/4 verificados, tarefas 7/7 concluídas.
- `aifw validate --change review-profile --json` (sem `--write`; o hook nega escrita a revisor): build, cli-docs, conformance, context-integrity, lint, manifest, project-map, secret-scan, session-conformance, tests e typecheck em pass; `missingArtifacts` vazio; sem warnings. Único bloqueio: `independent-review`, por falta da linha de veredito, que esta seção escreve.

### Critérios de aceitação (proposal.md)

1. Skill instalada declara `Perfil de revisão: completo|interface|texto` antes de delegar, sem pedir aprovação, define os perfis, chama só o `aifw-qa` com risco baixo ou médio, `completo` na dúvida e com risco alto: entregue em `templates/claude/skills/aifw-workflow/SKILL.md` (bullet "Perfil de revisão", parágrafo após "Exceção de risco", item 7) e na cópia `.claude/skills/aifw-workflow/SKILL.md`. Evidência: `test_skill_template_declares_the_profile`, `test_skill_sends_the_complete_profile_back_to_the_qa`, `test_text_profile_names_what_is_read_as_rule`, `test_installed_copies_carry_the_profile`.
2. `aifw-qa` confere o diff contra o perfil, devolve sem veredito, faz o eixo Spec, carrega as skills do brief, ferramentas sem `Agent` e com `Skill`: entregue em `templates/claude/agents/aifw-qa.md` (seção "Perfil leve" e "Saída") e cópia. Evidência: `test_qa_template_covers_the_light_profile`, `test_qa_output_excepts_the_diff_return_from_the_result_line`, `test_installed_copies_carry_the_profile`.
3. Aviso do avaliador em PLANNED/CRITICAL com risco L0/L1 e ausente em L2/L3 e em FAST/WORK: `python/aifw/assessment.py` (`LIGHT_REVIEW`, `path_context`). Evidência: 16 casos parametrizados em `test_notice_on_larger_tasks_with_low_or_medium_risk`, `test_no_notice_on_high_risk`, `test_no_notice_on_small_tasks`. A frase não contém `revisam` (restrição de `test_governance_follows_the_risk`, que passa na suíte).
4. Gate aceita arquivo só com `## QA` e veredito aprovado, falha sem a linha: `test_gate_accepts_a_single_qa_section`. Gate não mudou (`gates.py` fora do diff).
5. Nenhum template nomeia skill de front end: `test_templates_do_not_name_front_end_skills` (4 nomes).
6. Suíte, lint, `claude check`, spec validate/analyze e os dois revisores: ver "Gates e suíte" e a seção do adversário.

### Cenários da spec

- SCN-SUBAGENTS-REVIEW-PROFILE-TEXT, -MESSAGE, -GATE: ligados a `evidence/tests.txt` em `traceability.yaml`; cobertos pelos testes acima. A segunda cláusula de -GATE (guardas do hook iguais para o `aifw-qa` sem o adversário) é coberta por `tests_python/test_reviewer_guardrails.py` (já existente, passa na suíte), e o hook não está no diff.
- SCN-SUBAGENTS-REVIEW-FLOW: cenário inalterado; o REQ ganhou "Salvo no perfil leve". Rastreio para a evidência do perfil mantido por decisão (R6).

### Pontos pedidos no brief

- `paths` de `tasks.yaml`: cobrem todo arquivo do diff, inclusive a rodada de correção (design.md, delta, evidence e independent-review em TASK-EVIDENCE pela pasta da mudança; ADR e `docs/routing.md` em TASK-DOCS; templates, cópias e teste nas tarefas próprias). TASK-INSTALL declara também `.claude/settings.json` e `.gitignore`, que o diff não toca: sobra inofensiva.
- design.md, delta e ADR-0046 acompanham o texto final: o bullet da skill e a seção "Perfil leve" em design.md são iguais ao template; a "Saída", a troca para `completo` no brief da devolução e a definição de `texto` aparecem no delta (REQ e SCN-TEXT), no design (decisão 6, seção do `aifw-qa`) e no ADR-0046 (decisões 6 e 7). Divergência só no teste: design.md diz que "passa só pelo `aifw-qa`" aparece "duas vezes em `docs/routing.md`", e o arquivo tem três (linhas 24, 26 e 45).
- Teste de `docs/routing.md` (ressalva do adversário): confirmada. Contei 3 ocorrências; `>= 2` não trava a remoção de uma das duas remissões novas. Ressalva: o teste fica mais forte com `== 3` ou checando cada parágrafo.
- Desvio de processo (arquivo não movido para `evidence/independent-review-1.md`): não fere gate nem critério. O gate (`gates.py:356-373`) lê só a primeira linha de veredito do `independent-review.md`, e nenhum gate, critério ou cenário lê `evidence/independent-review-<n>.md`; `aifw validate --change` não acusou artefato faltando. O risco que o item 7 evita, um `Resultado: reprovado` antigo vencer o veredito novo por ser o primeiro, não ocorre: a reescrita removeu essa linha. Duas observações: (a) a ordem de mover é do agente principal (item 7 da skill fala com ele), e o hook não deixaria o revisor criar arquivo em `evidence/`; (b) o texto integral da rodada inicial existe só no commit `ee579b8` (`git show ee579b8:.aifw/changes/active/review-profile/independent-review.md`); no arquivo fica um resumo. Ressalva: antes do commit, gravar esse conteúdo em `evidence/independent-review-1.md` restaura o rastro na pasta que será arquivada.

### Standards (padrões do repositório, `principle-catalogs/`, smells)

- CONSTITUTION §8/§112: cópias em `.claude/` regeneradas por `aifw claude enable --no-graphify`, não editadas à mão (`claude check` pass, carimbos novos). Testes vermelhos antes da implementação registrados em `evidence/tests.txt` (os "7 failed" e "4 failed" são relato do worker; não reproduzi).
- `assessment.py`: constante e comentário de uma linha em inglês, no mesmo formato de `EXCEPTION` logo acima; condição no padrão de `high`/`swapped`. Sem smell relevante; nenhuma abstração nova.
- `test_review_profile.py`: reaproveita `init` de `test_workflows` e `enable_project`; sem duplicação relevante.
- Possível Shotgun Surgery (juízo): a mesma regra aparece em skill, template do QA, aviso do avaliador, `docs/claude-code.md`, `docs/routing.md` (3 vezes), CHANGELOG e ADR. É o padrão do repositório para regra de cascata (a skill é a fonte e as docs remetem), e a skill mantém uma fonte (o bullet) com dois ponteiros. Sem violação.

### Texto para agentes (writing-for-agents)

Instruções têm sujeito e ação ("escreva no chat", "chame só o `aifw-qa`", "confira primeiro", "aponte arquivo e trecho", "devolva"); proibições vêm pareadas com a ação positiva; a exceção do QA está junto da regra na abertura e na "Saída". Não achei contradição que eu possa provar. Ressalvas de juízo:

1. Eixo Spec parcial no QA. `templates/claude/agents/aifw-qa.md:20` resume o eixo Spec em "requisito ou critério que falta ou está parcial, e comportamento que ninguém pediu". O eixo Spec do `code-review` tem três itens; falta "requisito que parece implementado mas está errado", que o `aifw-adversary` (linha 13) traz. No perfil leve ninguém recebe esse item por escrito. Além disso, "O que conferir" diz "Carregue a skill `code-review` só para ler as fontes de padrão e a lista de smells", e o QA leve precisa do eixo Spec; o "Além de" resolve na prática, mas o "só" fica impreciso.
2. Exceção de rodada longe da regra. Item 7 da skill manda "passe ao adversário só o diff desde a revisão anterior"; a exceção "A rodada de correção de um perfil leve volta ao `aifw-qa`" está no bullet de "Modelos por classe". O item 7 aponta para "os perfis leves de 'Modelos por classe'" na frase de cabeçalho, o que mitiga. O template do `aifw-qa` não tem instrução para rodada de correção (o do adversário tem, linha 18).
3. Redundância no bullet da skill: o âmbito "de risco baixo ou médio" abre o bullet e reaparece em "Em `interface` e `texto`, com risco baixo ou médio" e "Na dúvida, e com risco alto ou crítico". Não contradiz; alonga um bullet de ~10 frases.

### Outras ressalvas

- Cobertura parcial de SCN-TEXT por teste: "sem pedir aprovação" / "siga sem perguntar" e "nomeie também as skills de front end" na skill não têm frase travada em `test_review_profile.py`. O texto existe (skill, linha 109); o ADR-0046 já registra que os testes travam frases, não comportamento.
- `README.md:41` ainda descreve "a revisão em duas etapas, adversário e QA" sem citar o perfil leve. Continua verdadeiro como padrão; fora do escopo listado na proposta.
- Ressalvas mantidas por decisão: R2 (gate não distingue perfil) e R6 (rastreio de SCN-FLOW).

### Não verificado

- Comportamento real do `aifw-qa` e do agente principal num perfil leve (só texto lido; esta mudança é `completo`).
- Checagem visual via `Bash` sob a trava dos revisores.
- Contagens "vermelho antes" dos testes (relato do worker).

Resultado: aprovado com ressalvas
