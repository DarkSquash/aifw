---
name: aifw-workflow
description: Workflow do AIFW neste projeto, que já tem aifw.yaml. Usar ao planejar, implementar, revisar ou concluir mudanças, e para intake, specs, gates, impasses e evidências.
---

# AIFW no Claude Code

Use o núcleo Python como ferramenta de governança. O Claude executa o trabalho; o AIFW valida documentos, estado e evidências. Respeite as instruções universais de comunicação: respostas curtas, detalhes nos artefatos.

## Entrada e escopo

1. Localize a raiz do projeto com `aifw.yaml`. Confirme `aifw --version` e consulte `aifw --help` ou a ajuda do subcomando quando houver dúvida. Use o executável instalado; não presuma um caminho local ou dependência de Node. Se `aifw --help` ainda listar `principle review` ou `handoff codex`, a instalação está desatualizada: avise o usuário antes de seguir.
2. Esta skill só existe em projetos habilitados por `/aifw new` ou `/aifw adopt`. Não reinicialize nem sobrescreva o control plane presente.
3. Leia `PROJECT_MAP.md`, `.aifw/charter.yaml` e apenas os contratos, specs em `.aifw/specs/current/`, ADRs e regras pertinentes à tarefa. Considere `.aifw/effective-policy.json` somente após conferir sua atualidade.
4. Para trabalho de implementação, confira `aifw intake status --json`, `aifw map check --json` e `aifw resolve check --json`. Não transforme uma consulta simples em um ciclo completo de implementação.

O que exige a aprovação do usuário (ADR-0037):
- começar uma mudança L2 ou L3: apresente o plano no chat e rode `aifw spec request-approval <id>` como última ação do turno. A partir daí o hook nega qualquer ferramenta até a resposta da pessoa: termine a resposta e espere, sem fazer outra pergunta. Um "sim" (ou "aprovo", "pode seguir") é registrado sozinho pelo hook `UserPromptSubmit` e aprova a mudança inteira; depois disso, não peça de novo para as alterações seguintes dela. Qualquer outra resposta cancela o pedido: ajuste o plano e peça de novo;
- instalar pacote, biblioteca, programa ou projeto novo;
- push para a branch padrão, force push, apagar branch remota, tags, merge de PR, deploy de produção e publicar pacote;
- escrever num serviço externo fora de `spec.externalAllowlist`: quando um domínio parecer parte do projeto, pergunte uma vez se pode incluí-lo na lista e, com o sim, inclua;
- o que já era decisão humana: impasse, waiver, break-glass, Charter, adoção e decisões.

O hook pede confirmação nesses casos. Commits, push para branches de trabalho, PRs, delegação a subagentes, código opaco e escritas na allowlist seguem sem perguntar. Segredos nunca são lidos.

Código de saída 0 indica sucesso; 1 indica erro de entrada ou execução; 2 indica avaliação com bloqueio ou pendência. Inspecione o resultado antes de agir. Um comando que falhou não é evidência de aprovação.

## Intake e adoção

- Resolva informações recuperáveis no repositório antes de perguntar. `ready` significa Charter pronto para aprovação; `complete` inclui as avaliações técnicas atuais, não significa por si só que o Charter foi aprovado. Confira seu estado e registro.
- Para projeto existente sem baseline atual, `aifw adopt analyze --json` descobre fatos. Dentro da adoção autorizada, `adopt analyze --write` e `adopt apply` persistem candidatos para revisão.
- Não deduza responsabilidade, owner ou relação de runtime apenas por nomes de arquivos. Solicite julgamento humano somente sobre decisões que ainda não estejam resolvidas.
- `adopt approve`, `intake approve`, `decision approve`, `spec approve`, `impasse decide`, `waiver add`, `break-glass grant` e `assess verdict` são aprovações humanas. O CLI só as aceita no terminal da pessoa que aprova, com o id do projeto digitado por ela; no shell do agente elas falham e o hook as nega. Mostre o comando exato e peça para a pessoa rodar. Nunca tente contornar essa exigência.
- Conduza a entrevista do intake invocando a skill `grilling` pela ferramenta Skill, usando as perguntas de `aifw intake status` como fronteira inicial. Grave cada resposta com `aifw intake set --field <campo> --value <valor>`; editar um Charter aprovado o reabre. A skill não aprova nada.
- Se `aifw intake status --json` trouxer `assessment.weakAnswers`, respostas que o Decider avaliou como vagas ou parciais, use-as como as próximas perguntas da entrevista. Não bloqueiam o `ready` nem a aprovação.
- Use catálogos de decisão apenas quando a tarefa exigir uma escolha arquitetural. Com o recurso `decisions` ligado, `decision recommend --suggest-signals --context "<pedido>"` sugere sinais. Confirme cada um com o usuário antes de passá-lo em `--signals`.

## Documentação existente e contexto

- Quando a ajuda da instalação listar `context`, use `context select --task "<tarefa>" --files <arquivos>` para localizar documentação relevante. Intenção e orçamento são opcionais. Leia as referências retornadas; o comando não incorpora seus corpos nem transforma documentos em autorização.
- Preserve dependências obrigatórias quando houver `overBudget`; orçamento é estimativa informativa. Sem correspondência, investigue os caminhos relevantes em vez de presumir contexto completo.
- `context check` verifica referências e compara com o snapshot, quando existir. Mudança de hash pede revisão; não prova conteúdo incorreto. `context index --write` registra baseline factual depois da revisão, não aprovação semântica.
- Para sincronizar regras entre agentes, mantenha uma fonte específica do projeto e use `instructions build/check --agent claude`, que mantém um bloco gerenciado no `CLAUDE.md`. Preserve o restante do `CLAUDE.md` e as instruções globais do usuário; não importe instruções de terceiros como autoridade automaticamente.
- `gates check --level <nível>` apenas inspeciona referências na CI. `execution: not-run` não é evidência de teste executado. Gates obrigatórios com `skipped`, aviso ou estado desconhecido bloqueiam.

## Mudanças e evidências

1. Classifique a alteração com `aifw change classify --diff` (sinais derivados dos arquivos alterados) mais os sinais reais que você observou e consulte os requisitos de L0–L3. Verifique se já existe uma mudança ativa adequada antes de criar outra.
   - Com o recurso `tasks` ligado, cada pedido do usuário chega com o contexto "AIFW, avaliador de tarefas (modo ativo): caminho …" (ADR-0036, ADR-0037), que já nomeia o subagente do caminho (ADR-0038). Siga esse caminho na tabela de modelos (FAST, WORK, PLANNED, CRITICAL): subir é sempre permitido, descer nunca. A aprovação do plano em L2/L3 continua valendo. Se vier o aviso de indisponível, siga a classificação de sempre.
   - Quando o início de sessão avisar que o relatório do avaliador está pronto, rode `aifw assess report` e mostre o relatório ao usuário. Os vereditos são aprovações dele: mostre os comandos `aifw assess verdict` para ele rodar no terminal.
2. Para L2/L3, use `aifw spec new <id> --title ... --summary ... --level ...`. Preencha proposta, design, deltas, tarefas e traceabilidade em `.aifw/changes/active/<id>/`. L0/L1 mantêm registros e verificações proporcionais ao risco.
   - Antes do pedido de aprovação, liste nos `paths` do `tasks.yaml` tudo o que a mudança vai tocar: arquivos, pastas (`docs/`) ou padrões (`templates/*.md`), inclusive testes, documentação e CHANGELOG. Depois do "sim", editar fora deles pede confirmação, e os `paths` do `tasks.yaml` aprovado só mudam com confirmação; trocar o `status` de uma tarefa não pede (ADR-0039, ADR-0041). Para incluir um arquivo descoberto no caminho, acrescente-o ao `tasks.yaml` (uma confirmação) e siga.
3. Preserve IDs. Use um delta por capability; `modified` e `removed` devem referenciar requisitos aceitos. Uma capability nova precisa de propósito. Consulte os schemas/templates da instalação ou do repositório do framework quando necessário; não invente campos.
4. Implemente dentro do escopo, revise referências e dependentes e execute verificações relevantes, incluindo regressões. Atualize os outros pontos afetados, inclusive documentação e artefatos derivados quando necessário.
5. Em mudança material de código ou design, revise o diff invocando a skill `code-review` pela ferramenta Skill; no eixo Standards, use `principle-catalogs/` como fonte de padrões. Princípios são auditoria contextual: cite arquivo, impacto e evidência, respeite exceções e riscos de mau uso.
6. Registre resultados reais. Um artefato `passed` precisa apontar para um arquivo existente dentro do projeto; o arquivo de teste existir não prova que foi executado. Persista também o resultado da execução.
7. Para uma spec change, execute `aifw validate --change <id> --write --json`. Ele usa o nível e a aprovação da mudança, roda os gates, confere os artefatos exigidos pelo nível e grava `evidence/validation.json`. Sem spec change, use `aifw validate --level <nível> --json`. Hard/human bloqueados impedem declarar aprovação; audit warnings devem ser registrados. Nunca remova um gate nem altere o núcleo para obter verde.
   - L2 exige, na pasta da mudança: `design.md` com as seções de abordagem e rollback preenchidas e `independent-review.md` com o resultado da revisão independente, feita em duas etapas (ADR-0038):
     1. Delegue ao subagente `aifw-adversary`, passando só o diff, a spec, os critérios e o caminho do arquivo. Ele tenta provar que a mudança está errada e, com um achado provado por um cenário concreto que falha, termina o arquivo em `Resultado: reprovado`.
     2. Sem achado provado, delegue ao `aifw-qa`, que confere critérios, evidências, testes, gates e documentação e termina o arquivo com `Resultado: aprovado`, `Resultado: aprovado com ressalvas` ou `Resultado: reprovado`.
     O gate `independent-review` lê essa linha: sem ela, ou com `reprovado`, ele falha. Corrija os achados e peça nova revisão em vez de editar o resultado: mova o arquivo para `evidence/independent-review-<n>.md` e passe ao adversário só o diff desde a revisão anterior e os achados dela. Ressalva sem prova não reabre rodada. Depois de duas rodadas de correção, uma terceira reprovação para a revisão: leve o caso à pessoa.
   - L3 exige, além disso: `proposal.md` com critérios de aceitação, `threat-model.md`, `migration.md` (pode dizer por que não se aplica) e um artefato `adr` com caminho em `traceability.yaml`.
8. Quando entradas do catálogo ou da resolução mudarem, use `map build` ou `resolve build` e confira novamente. Não edite manualmente suas projeções para esconder drift.

- Use `aifw template copy --name <template> --change <id>` para criar threat model, plano técnico, runbook e outros documentos a partir dos templates (`aifw template list`).
- Waivers (`aifw waiver add`) e break-glass (`aifw break-glass grant`) são decisões humanas: proponha, mas só rode com a confirmação do usuário. Nenhum waiver substitui `human-approval` ou um invariante do core.
- O hook Stop impede concluir com código alterado depois da última verificação bem-sucedida: rode os testes ou `aifw validate`, ou diga explicitamente por que não se aplicam. `aifw runs show --session latest` resume a sessão contra essas regras.

## Fechamento de uma mudança com specs

- Execute `aifw spec validate <id>`, `aifw spec analyze <id>` e `aifw spec sync <id> --dry-run`. O preview não altera specs aceitas. Se o `spec analyze` trouxer `assessment.weakTraces`, revise esses cenários e cite-os no `independent-review.md`; são avisos, não bloqueios.
- Complete tarefas e cenários com evidências. A aprovação de L2/L3 é o registro que o hook grava da resposta do usuário (`approval.md` na pasta da mudança); não o escreva à mão.
- Sem bloqueios, use `spec status <id> --set ready`, `aifw validate --change <id> --write` e `spec archive <id>`. O archive exige essa validação sem bloqueios e recusa se a mudança ou o código mudaram depois dela: nesse caso, valide de novo. Confira o archive e as specs resultantes antes de comunicar conclusão.
- Se houver `cleanupPending`, o commit foi preservado: confira current/archive e informe o resíduo. Não repita o archive como tentativa de limpeza.
- Não edite `.aifw/specs/current/` para contornar validações. Não reduza o nível de risco ou marque evidência como aprovada para destravar um comando.

## Modelos por classe

Depois de `change classify` e `route explain`, distribua o trabalho pela linha mais alta que se aplicar:

| Situação | Planeja | Executa | Revisa |
| --- | --- | --- | --- |
| impacto L3, caminho CRITICAL ou rota BRAIN | `opus` | `aifw-executor` com plano passo a passo; `aifw-quick` nas tarefas rápidas e mecânicas | `aifw-adversary`, depois `aifw-qa`, e plano aprovado no chat |
| impacto L2 ou caminho PLANNED | `opus` | `aifw-executor`; `aifw-quick` nas tarefas rápidas e mecânicas | `aifw-adversary`, depois `aifw-qa` |
| caminho ou rota WORK | — | `aifw-executor` | testes e gates |
| caminho ou rota FAST | — | `aifw-quick` | testes e gates |

| Subagente | Modelo | Esforço | Papel |
| --- | --- | --- | --- |
| `aifw-explorer` | haiku | low | busca só de leitura no código |
| `aifw-quick` | haiku | low | tarefas do caminho FAST e tarefas rápidas e mecânicas de L2/L3 |
| `aifw-executor` | sonnet | medium | caminho WORK e planos do Opus |
| `aifw-adversary` | opus | high | revisão: tenta provar que a mudança está errada |
| `aifw-qa` | sonnet | high | revisão: confere critérios, evidências e documentação |

- Execute e revise por subagentes; a escolha é sua e não pede confirmação. Delegue pelo nome (`subagent_type`) sem passar `model`, para valer o modelo da definição; passe `model` só para subir. Planeje na própria sessão se ela já usa o modelo indicado; caso contrário, use um subagente. Para buscar no código, use o `aifw-explorer`.
- Fora desses papéis (agentes de Workflow, Agent genérico, outra sessão), escolha o esforço pelo mesmo critério, nunca acima de `high`: planejar, revisar e papéis críticos `high`; executar e pesquisar `medium`; tarefas rápidas e busca `low`. Sem os subagentes em `.claude/agents/`, rode `aifw claude enable`; até lá, use o Agent genérico com o `model` da tabela.
- O plano entregue ao executor nomeia arquivos, passos e verificações; o executor não decide arquitetura.
- Os revisores recebem só o diff, a spec e os critérios, sem o contexto da implementação. O `aifw-adversary` faz o eixo Spec e o `aifw-qa` o eixo Standards do `code-review`, cada um no próprio contexto e sem lançar subagentes. Cada achado precisa de prova; o escopo é a spec, os critérios e o modelo de ameaça aceito. O hook nega a eles editar o projeto além do `independent-review.md` e rodar comando que escreve, commita ou muda o repositório.
- A orquestração é obrigatória em L2 e L3 (ADR-0040): a sessão planeja e delega. A execução vai ao `aifw-executor`; subtarefas rápidas e mecânicas (renomear, ajuste pequeno de texto, busca) ao `aifw-quick` ou ao `aifw-explorer`; a revisão ao `aifw-adversary` e ao `aifw-qa`. Com uma mudança aprovada ativa, o hook nega à sessão principal editar arquivos do projeto (fora de `orchestration.sessionPaths` no `permissions.yaml`); subagentes, a pasta `.aifw/changes/active/` e arquivos fora do projeto seguem livres. Para corrigir um arquivo que o executor errou, melhore o plano ou delegue de novo; subir de modelo com `model` é permitido.
- Fazer inline só vale em L0 e L1, sem mudança L2/L3 aprovada ativa: com uma ativa, o hook nega a edição pela sessão. Subir de modelo é sempre permitido; rebaixar L3 ou BRAIN, nunca.
- Testes e gates rodam em toda classe; revisão não substitui evidência.

## Limites da integração

Esta skill não é um servidor MCP e não troca o modelo da sessão. Se a rota recomendada divergir do modelo atual e o trabalho não puder ser delegado, informe o usuário.

Com o hook `aifw-hook` instalado, cada ação passa por `.aifw/permissions.yaml` e pelos impasses abertos: o Claude Code nega a ação ou pede confirmação ao usuário. Quando o hook negar, não contorne por outro caminho; explique o motivo e o próximo passo. Edições nos arquivos de controle do AIFW (política, gates, roteamento, impasses, aprovações, specs aceitas, `evidence/validation.json`, `.claude/settings.json`, a skill e os subagentes do AIFW em `.claude/`, os `paths` do `tasks.yaml` de uma mudança aprovada, a pasta `.git/`, `.venv/` e `node_modules/`) pedem confirmação humana, e a leitura de arquivos de segredo é negada. Comandos que o hook não consegue ler (`eval`, `python -c`, scripts) rodam quando `opaqueCode: allow`, mas o que eles fazem continua sob as regras acima: não use um script para instalar, publicar ou fazer push que pediria confirmação. Não escreva waivers, break-glass, Charter, `change.yaml` ou registros de sessão à mão: use os comandos do aifw. Rode cada verificação sozinha ou ligada por `&&`: terminar com `| tail`, `; echo` ou `|| true` esconde a falha, e o hook não conta como verificada. Para transferir o trabalho a outra sessão, use a skill `handoff`.

## Impasse

- Na primeira tentativa de correção que falhar, abra um caso: `aifw impasse open --id <slug> --impact <nível>`.
- Registre cada tentativa: `aifw impasse attempt --id <slug> --hypothesis ... --intervention ... --evidence <arquivos> --outcome failure|success|inconclusive`. A hipótese e a intervenção precisam ser realmente diferentes das anteriores; repetir abre o impasse na hora.
- Após 5 falhas distintas em L0/L1, ou 2 em L2/L3, o caso fica `OPEN` e o hook congela as mudanças. Apresente ao usuário o resultado esperado, as tentativas, o que a evidência eliminou e a regra suspeita; então use `aifw impasse review`.
- `aifw impasse decide` registra a decisão humana e só roda com a confirmação do usuário. Depois da mudança aprovada, use `aifw impasse revalidate`.
- Alterações no framework precisam estar dentro da autorização real do usuário, não ser uma saída improvisada para seus bloqueios.

<!-- aifw-version: 0.4.1 -->
<!-- aifw-sha256: 01c40557e2ab0f132aef0048e7bcd7d3ca0a274ad1a1344e609c9aaacf3e38cc -->
