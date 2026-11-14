# Design — Perfil de revisão pela natureza da mudança

## Context

A revisão independente de L2/L3 tem duas etapas (ADR-0038, ADR-0042): `aifw-adversary` (eixo Spec, Opus) e depois `aifw-qa` (eixo Standards e entrega, Sonnet). A pessoa quer um revisor só quando a mudança é só de interface ou só de texto.

Fatos conferidos no código:

- O gate `independent-review` (`python/aifw/gates.py`, `review_result`) lê só a linha `Resultado:` do `independent-review.md`; não exige a seção do adversário. `specs.missing_artifacts` só exige o arquivo não vazio. Nenhum gate muda. Já existe teste de arquivo só com `Resultado: aprovado com ressalvas` (`tests_python/test_spec_integrity.py`, por volta da linha 370).
- A guarda de revisor do hook (`reviewer_change` e `REVIEWERS` em `hooks.py`) decide pelo `agent_type` e pelo alvo da escrita; não olha se o adversário rodou. O `aifw-qa` sozinho continua podendo escrever só o `independent-review.md`. O núcleo do hook não muda, e não há tarefa da sessão principal.
- Os textos de `aifw-planner`, `aifw-lead`, `aifw-executor` e `aifw-senior` dizem "o agente principal chama `aifw-adversary` e `aifw-qa`" ou "não chame revisores". Continuam verdadeiros: os dois primeiros não chamam revisor; os dois últimos só aparecem com risco alto ou crítico, que é sempre perfil completo. Não mudam.
- `aifw-qa` tem a ferramenta `Skill` e o `aifw-adversary` não; os dois são negados pelo hook de editar o projeto além do `independent-review.md`.
- L2/L3 de risco baixo ou médio não criam pasta de mudança; nesse caso os revisores devolvem a seção e o `Resultado:` na resposta. O perfil leve só vale em risco baixo ou médio, então o caso comum é sem pasta, e o registro não pode depender de `change.yaml`.

## Approach

Texto, uma frase de código e testes. Nenhum código de classificação.

Arquivos: `templates/claude/skills/aifw-workflow/SKILL.md`, `templates/claude/agents/aifw-qa.md`, `python/aifw/assessment.py`, as duas cópias regeneradas em `.claude/`, `docs/claude-code.md`, `docs/routing.md`, `CHANGELOG.md`, `docs/decisions/ADR-0046-review-profile.md`, `tests_python/test_review_profile.py`.

### Texto da skill (`aifw-workflow/SKILL.md`)

Três edições. Quem escreve o texto usa a skill `writing-for-agents`: palavra-guia `perfil`, instrução no positivo, uma fonte de verdade (o bullet novo; os outros dois pontos só apontam para ele).

1. No item 7 de "Mudanças e evidências", trocar `feita em duas etapas (ADR-0038):` por `feita em duas etapas (ADR-0038), ou em uma só nos perfis leves de "Modelos por classe" (ADR-0046):`.
2. Em "Modelos por classe", logo depois do bullet `- Revisores (...)`, acrescentar este bullet, sem alterar o bullet de revisores:

   > - Perfil de revisão (ADR-0046): antes de delegar, escreva no chat a linha `Perfil de revisão: completo`, `interface` ou `texto` e siga sem perguntar; a pessoa pode barrar se discordar. `interface` é mudança só de estilo, layout ou componente visual, sem lógica, dados nem autenticação. `texto` é mudança só de docs, mensagens e comentários que pessoas leem; o que um agente ou o hook lê como regra (skill, subagente, política, spec) é comportamento e fica em `completo`. Em `interface` e `texto`, com risco baixo ou médio, chame só o `aifw-qa`; no brief, diga o perfil e passe o plano. Em `interface`, nomeie também as skills de front end que ele deve carregar e, havendo como rodar a tela, peça a checagem visual. Na dúvida, e com risco alto ou crítico, o perfil é `completo`: os dois revisores. O `aifw-qa` confere primeiro se o diff cabe no perfil; se não couber, devolve sem `Resultado:` e você chama o `aifw-adversary` e depois o `aifw-qa` de novo. A rodada de correção de um perfil leve volta ao `aifw-qa`.

3. No bullet "Os revisores recebem só o diff...", depois de `o eixo Standards do \`code-review\``, acrescentar ` (no perfil leve, o \`aifw-qa\` faz os dois)`.

### Texto do `aifw-qa.md`

- `description`: trocar `Segunda etapa da revisão independente de mudanças L2/L3 do AIFW, só depois de o aifw-adversary não achar defeito provado.` por `Revisão independente de mudanças L2/L3 do AIFW, como segunda etapa depois de o aifw-adversary não achar defeito provado ou como etapa única nos perfis de revisão interface e texto.` (sem dois-pontos nem aspas: um `: ` quebra o frontmatter YAML sem aspas) O resto da descrição fica.
- Primeiro parágrafo: acrescentar no fim `Nos perfis leves o adversário não roda; veja "Perfil leve".`
- Nova seção entre "O que conferir" e "Regras":

  ```
  ## Perfil leve (um revisor só)

  Quando o brief declarar `Perfil de revisão: interface` ou `texto`, o adversário não rodou. Além de "O que conferir", faça o eixo Spec do `code-review`: requisito ou critério que falta ou está parcial, e comportamento que ninguém pediu. A regra de prova é a mesma.

  1. Confira primeiro se o diff cabe no perfil. `interface` é só estilo, layout ou componente visual, sem lógica, dados nem autenticação; `texto` é só docs, mensagens e comentários que pessoas leem, sem skill, subagente, política nem spec. Se algo do diff está fora do perfil, não aprove: na seção `## QA`, aponte arquivo e trecho fora do perfil, não escreva a linha `Resultado:` e devolva ao agente principal, que chama o `aifw-adversary`.
  2. Em `interface`, carregue pela ferramenta Skill as skills de front end que o brief nomear e aplique-as ao diff. Se o brief disser como rodar a tela, rode e registre o que viu.
  3. Abra a seção `## QA` com a linha `Perfil de revisão: <perfil>, declarado no chat.`
  ```

  `tools` e `model` não mudam.

### Aviso do avaliador (`assessment.py`, `path_context`)

Constante `LIGHT_REVIEW = "Perfil de revisão interface ou texto declarado no chat: só o aifw-qa revisa; sem declaração, os dois."` e, em `path_context`, depois do bloco `parts = [...]` e antes do `if high:`, `if path in {"PLANNED", "CRITICAL"} and not high: parts.append(LIGHT_REVIEW)`. Não pode conter a palavra `revisam` (o teste `test_governance_follows_the_risk` proíbe `revisam` em risco baixo e médio). `PATH_RULE` não muda: ele também alimenta o relatório do avaliador, e com risco alto a frase seria falsa.

### Documentação

- `docs/claude-code.md`: um bullet novo "Perfil de revisão (ADR-0046)", com a declaração no chat sem pedido de aprovação, na lista da cascata, depois do bullet "Exceção de risco", e `(uma só nos perfis leves, acima)` depois de `tem duas etapas` no parágrafo da revisão independente.
- `docs/routing.md`: uma frase no fim do parágrafo "A revisão independente tem duas etapas...".
- `CHANGELOG.md`: entrada no topo de "Não lançado / Alterado".
- ADR-0046 (skill `architecture-decision-records`): decisões abaixo, no formato do ADR-0045. Status accepted, Impact L2, Amends ADR-0038 e ADR-0042.

### Regenerar as cópias instaladas

`aifw claude enable --no-graphify` na raiz, depois de os templates prontos. O `--no-graphify` evita rodar o graphify real neste repositório. Nunca editar `.claude/skills/aifw-workflow/SKILL.md` nem `.claude/agents/aifw-qa.md` à mão. Conferir `aifw claude check` e `git diff --stat`: só essas duas cópias mudam (nenhum `.bak`, nenhum outro arquivo).

### Testes (`tests_python/test_review_profile.py`, novo, vermelhos antes da implementação)

- `path_context` em PLANNED e CRITICAL com risco L0 e L1 traz `Perfil de revisão interface ou texto`; com L2 e L3, e em FAST e WORK com qualquer risco, não traz.
- Os templates da skill e do `aifw-qa` trazem as frases fixas: skill com `Perfil de revisão: completo`, `Na dúvida`, `risco alto ou crítico` e `devolve sem`; `aifw-qa` com `Perfil de revisão: interface`, `eixo Spec`, `não escreva a linha` e `ferramenta Skill`; `aifw-qa` mantém `Skill` sem `Agent` nas ferramentas; o `aifw-adversary` não ganha a palavra `Perfil`.
- Depois de `enable_project`, as cópias em `.claude/` trazem o texto novo.
- `review_result` com um arquivo só com `## QA`, a linha de perfil e `Resultado: aprovado` dá `pass`; sem a linha `Resultado:` dá `fail`.
- O `aifw-qa` escreve o `independent-review.md` e continua negado em `python/aifw/claude.py` (já coberto por `test_reviewer_guardrails.py`; só conferir que passa).

## Decisions

1. **Dois perfis leves, um revisor só (`aifw-qa`); o resto é `completo`.** Decisão da pessoa. Quem fica com o único revisor é o `aifw-qa` porque tem a ferramenta `Skill` (carrega as skills de front end) e custa menos que o adversário (Sonnet em vez de Opus).
2. **Risco alto ou crítico é sempre `completo`.** Decisão da pessoa; o texto repete na skill e o aviso do avaliador só cita a exceção com risco baixo ou médio, para o agente não ler duas instruções que se contradizem.
3. **Quem decide a natureza é o agente principal: declara no chat a linha `Perfil de revisão: ...` antes de delegar e segue, sem perguntar; a pessoa pode barrar.** Decisão da pessoa (revista: a primeira versão dizia que o "sim" ao plano aprovava o perfil, mas o perfil leve só vale em risco baixo ou médio, que não pede `request-approval`, então não havia plano a aprovar). Nenhum requisito ou cenário depende de aprovação do perfil. Sem código de classificação, sem campo no avaliador, sem regra por extensão. Na dúvida, `completo`.
4. **Onde fica o registro: a linha declarada no chat, repetida no brief do `aifw-qa` e na primeira linha da seção `## QA`.** Sem campo em `change.yaml` nem código. Motivo: o perfil leve vale em risco baixo ou médio, que em regra não cria pasta de mudança; um campo em `change.yaml` não existiria no caso comum. Com pasta, o `independent-review.md` carrega a linha `Perfil de revisão:` e a ausência da seção do adversário se explica por ela; para auditoria, a linha no chat e essa linha no arquivo bastam. Descartado: campo em `change.yaml` (código novo e esquema novo para o caso raro com pasta), campo `reviewProfile` no avaliador (decisão da pessoa: sem campo novo no avaliador).
5. **O `aifw-qa` responde também pelo eixo Spec, por uma seção curta que aponta para o `code-review`, sem copiar a lista do adversário.** O `aifw-qa` já carrega o `code-review`; a seção só liga o eixo Spec ao perfil leve e mantém a regra de prova. Duplicar a lista do `aifw-adversary` abriria duas fontes de verdade.
6. **Guarda barata: o `aifw-qa` confere o diff contra o perfil antes de tudo e, se não couber, devolve sem `Resultado:`.** O erro de classificação honesto é pego depois que o diff existe. Sem linha `Resultado:`, o gate falha (o arquivo não está pronto) e a rodada de correção não é gasta: o limite de duas rodadas continua valendo só para reprovação com achado. O agente principal chama o adversário e depois o `aifw-qa` de novo, que escreve o `Resultado:` final.
7. **`texto` exclui o que agente ou hook lê como regra (skill, subagente, política, spec).** Julgamento meu, fora do pedido literal ("docs, mensagens, comentários"): esses arquivos são texto, mas mudam o comportamento do framework (esta própria mudança é um exemplo). A pessoa pode ampliar. Sem a exclusão, o perfil leve revisaria sozinho a mudança de maior risco do repositório.
8. **Skills de front end: o agente principal as nomeia no brief; os templates não fixam nomes.** O repositório é público e cada pessoa tem as suas. A checagem visual é pedida só quando há como rodar a tela, e o `aifw-qa` só a faz se o brief disser como.
9. **A mensagem do avaliador cita a exceção em PLANNED e CRITICAL com risco baixo ou médio, numa frase.** Sem ela, o contexto entregue a cada pedido diria "chama aifw-adversary e depois aifw-qa" e contradiria a skill; o agente tende a seguir o aviso do pedido. Em CRITICAL também, porque complexidade alta não implica natureza de risco (uma reescrita grande de docs é texto). Não entra em `PATH_RULE` (alimenta o relatório e a frase falharia com risco alto) nem nas exceções FAST/WORK (risco alto, sempre completo).
10. **Nenhuma mudança no núcleo do hook, no gate nem nos outros subagentes.** Conferido nos fatos acima. Nenhuma tarefa da sessão principal.
11. **Alternativa descartada: perguntar antes de usar o perfil leve** (esperar o "sim" da pessoa). Voltaria a interromper a pessoa em toda mudança de tela ou de texto, que é o atrito que a mudança quer tirar. Declarar e seguir mantém a pessoa informada e com o poder de barrar, e a guarda é o `aifw-qa`, que confere o diff. O ADR-0046 registra esta alternativa, junto com campo em `change.yaml` e campo no avaliador (decisão 4).
12. **Sem defesa contra orquestrador de má-fé** (ADR-0034, ADR-0037): quem declara o perfil leve para fugir do adversário não é bloqueado; o `aifw-qa` pega o erro honesto e a linha no chat registra a declaração.

## Risks and rollback

- **Classificação errada do agente principal** (declara `texto` e o diff mexe em lógica): o `aifw-qa` confere o diff e devolve; o custo é uma rodada de QA perdida. Se o `aifw-qa` falhar em notar, a mudança passa sem adversário: risco aceito, mitigado por `Resultado:` com ônus da prova e pela suíte e os gates, que rodam sempre.
- **O `aifw-qa` não tem ferramenta de navegador nem de captura de tela.** A checagem visual depende do que o `Bash` consegue rodar (por exemplo uma skill de Playwright que o brief nomeie) e da trava dos revisores, que nega comandos que gravam arquivos; não verificada neste plano. Sem como rodar a tela, a revisão de `interface` é só de diff.
- **O comportamento do `aifw-qa` num perfil leve só é provado em uso real**: os testes travam as frases, não o comportamento do agente. A primeira mudança leve de verdade é a prova; esta mudança, que é `completo`, não a exerce.
- **`texto` mais estreito que o pedido** (decisão 7): quem queria revisar sozinho uma mudança só de skill ou de ADR/spec continua com os dois revisores.
- **Duas seções `## QA` no mesmo arquivo** quando o `aifw-qa` devolve e roda de novo depois do adversário: aceito; a primeira registra por que o perfil não coube. O gate lê a primeira linha `Resultado:` e só a segunda rodada a escreve.
- **Windows/POSIX:** só texto e uma constante; nada depende de caminho ou shell.
- **Rollback:** reverter a mudança e rodar `aifw claude enable --no-graphify` para regenerar as cópias; volta a revisão em duas etapas. Nenhum formato persistido muda; um `independent-review.md` de perfil leve já gravado continua válido para o gate.
