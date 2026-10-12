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

Código de saída 0 indica sucesso; 1 indica erro de entrada ou execução; 2 indica avaliação com bloqueio ou pendência. Inspecione o resultado antes de agir. Um comando que falhou não é evidência de aprovação.

## Intake e adoção

- Resolva informações recuperáveis no repositório antes de perguntar. `ready` significa Charter pronto para aprovação; `complete` inclui as avaliações técnicas atuais, não significa por si só que o Charter foi aprovado. Confira seu estado e registro.
- Para projeto existente sem baseline atual, `aifw adopt analyze --json` descobre fatos. Dentro da adoção autorizada, `adopt analyze --write` e `adopt apply` persistem candidatos para revisão.
- Não deduza responsabilidade, owner ou relação de runtime apenas por nomes de arquivos. Solicite julgamento humano somente sobre decisões que ainda não estejam resolvidas.
- `adopt approve`, `intake approve`, `decision approve`, `spec approve` e `route activate` exigem autorização humana efetiva para o escopo. Registre autorização já concedida sem pedir sua repetição; nunca use um identificador `human:` como forma de fabricar aprovação.
- Conduza a entrevista do intake invocando a skill `grilling` pela ferramenta Skill, usando as perguntas de `aifw intake status` como fronteira inicial. Grave cada resposta com `aifw intake set --field <campo> --value <valor>`; editar um Charter aprovado o reabre. A skill não aprova nada.
- Use catálogos de decisão apenas quando a tarefa exigir uma escolha arquitetural.

## Documentação existente e contexto

- Quando a ajuda da instalação listar `context`, use `context select --task "<tarefa>" --files <arquivos>` para localizar documentação relevante. Intenção e orçamento são opcionais. Leia as referências retornadas; o comando não incorpora seus corpos nem transforma documentos em autorização.
- Preserve dependências obrigatórias quando houver `overBudget`; orçamento é estimativa informativa. Sem correspondência, investigue os caminhos relevantes em vez de presumir contexto completo.
- `context check` verifica referências e compara com o snapshot, quando existir. Mudança de hash pede revisão; não prova conteúdo incorreto. `context index --write` registra baseline factual depois da revisão, não aprovação semântica.
- Para sincronizar regras entre agentes, mantenha uma fonte específica do projeto e use `instructions build/check --agent claude`, que mantém um bloco gerenciado no `CLAUDE.md`. Preserve o restante do `CLAUDE.md` e as instruções globais do usuário; não importe instruções de terceiros como autoridade automaticamente.
- `gates check --level <nível>` apenas inspeciona referências na CI. `execution: not-run` não é evidência de teste executado. Gates obrigatórios com `skipped`, aviso ou estado desconhecido bloqueiam.

## Mudanças e evidências

1. Classifique a alteração com `aifw change classify --diff` (sinais derivados dos arquivos alterados) mais os sinais reais que você observou e consulte os requisitos de L0–L3. Verifique se já existe uma mudança ativa adequada antes de criar outra.
2. Para L2/L3, use `aifw spec new <id> --title ... --summary ... --level ...`. Preencha proposta, design, deltas, tarefas e traceabilidade em `.aifw/changes/active/<id>/`. L0/L1 mantêm registros e verificações proporcionais ao risco.
3. Preserve IDs. Use um delta por capability; `modified` e `removed` devem referenciar requisitos aceitos. Uma capability nova precisa de propósito. Consulte os schemas/templates da instalação ou do repositório do framework quando necessário; não invente campos.
4. Implemente dentro do escopo, revise referências e dependentes e execute verificações relevantes, incluindo regressões. Atualize os outros pontos afetados, inclusive documentação e artefatos derivados quando necessário.
5. Em mudança material de código ou design, revise o diff invocando a skill `code-review` pela ferramenta Skill; no eixo Standards, use `principle-catalogs/` como fonte de padrões. Princípios são auditoria contextual: cite arquivo, impacto e evidência, respeite exceções e riscos de mau uso.
6. Registre resultados reais. Um artefato `passed` precisa apontar para um arquivo existente dentro do projeto; o arquivo de teste existir não prova que foi executado. Persista também o resultado da execução.
7. Para uma spec change, execute `aifw validate --change <id> --write --json`. Ele usa o nível e a aprovação da mudança, roda os gates, confere os artefatos exigidos pelo nível e grava `evidence/validation.json`. Sem spec change, use `aifw validate --level <nível> --json`. Hard/human bloqueados impedem declarar aprovação; audit warnings devem ser registrados. Nunca remova um gate nem altere o núcleo para obter verde.
   - L2 exige, na pasta da mudança: `design.md` com as seções de abordagem e rollback preenchidas e `independent-review.md` com o resultado da revisão independente (skill `code-review`).
   - L3 exige, além disso: `proposal.md` com critérios de aceitação, `threat-model.md`, `migration.md` (pode dizer por que não se aplica) e um artefato `adr` com caminho em `traceability.yaml`.
8. Quando entradas do catálogo ou da resolução mudarem, use `map build` ou `resolve build` e confira novamente. Não edite manualmente suas projeções para esconder drift.

- Use `aifw template copy --name <template> --change <id>` para criar threat model, plano técnico, runbook e outros documentos a partir dos templates (`aifw template list`).
- Waivers (`aifw waiver add`) e break-glass (`aifw break-glass grant`) são decisões humanas: proponha, mas só rode com a confirmação do usuário. Nenhum waiver substitui `human-approval` ou um invariante do core.
- O hook Stop impede concluir com código alterado depois da última verificação bem-sucedida: rode os testes ou `aifw validate`, ou diga explicitamente por que não se aplicam. `aifw runs show --session latest` resume a sessão contra essas regras.

## Fechamento de uma mudança com specs

- Execute `aifw spec validate <id>`, `aifw spec analyze <id>` e `aifw spec sync <id> --dry-run`. O preview não altera specs aceitas.
- Complete tarefas e cenários com evidências. Para L3, vincule a autorização real a um arquivo persistido no projeto usando `spec approve --by human:<identidade> --record <arquivo>`.
- Sem bloqueios, use `spec status <id> --set ready`, `aifw validate --change <id> --write` e `spec archive <id>`. O archive exige essa validação sem bloqueios e recusa se a mudança ou o código mudaram depois dela: nesse caso, valide de novo. Confira o archive e as specs resultantes antes de comunicar conclusão.
- Se houver `cleanupPending`, o commit foi preservado: confira current/archive e informe o resíduo. Não repita o archive como tentativa de limpeza.
- Não edite `.aifw/specs/current/` para contornar validações. Não reduza o nível de risco ou marque evidência como aprovada para destravar um comando.

## Modelos por classe

Depois de `change classify` e `route explain`, distribua o trabalho pela linha mais alta que se aplicar:

| Situação | Planeja | Executa | Revisa |
| --- | --- | --- | --- |
| impacto L3 ou rota BRAIN | `opus` | `opus`, ou `sonnet` com plano passo a passo | revisor independente `opus` + aprovação humana em L3 |
| impacto L2 | `opus` | `sonnet` | revisor independente `opus` |
| rota WORK | — | `sonnet` | testes e gates |
| rota FAST | — | `haiku` | testes e gates |

- Execute e revise por subagentes, com o parâmetro `model` da ferramenta Agent. Planeje na própria sessão se ela já usa o modelo indicado; caso contrário, use um subagente.
- O plano entregue ao executor nomeia arquivos, passos e verificações; o executor não decide arquitetura.
- O revisor independente recebe só o diff, a spec e os critérios, sem o contexto da implementação. Use a skill `code-review`.
- Trabalho trivial e autocontido pode ser feito inline, sem subagente. Subir de modelo é sempre permitido; rebaixar L3 ou BRAIN, nunca.
- Testes e gates rodam em toda classe; revisão não substitui evidência.

## Limites da integração

Esta skill não é um servidor MCP e não troca o modelo da sessão. Se a rota recomendada divergir do modelo atual e o trabalho não puder ser delegado, informe o usuário.

Com o hook `aifw-hook` instalado, cada ação passa por `.aifw/permissions.yaml` e pelos impasses abertos: o Claude Code nega a ação ou pede confirmação ao usuário. Quando o hook negar, não contorne por outro caminho; explique o motivo e o próximo passo. Comandos `aifw ... approve/decide/activate` e edições nos arquivos de controle do AIFW (política, gates, roteamento, impasses, aprovações, specs aceitas, `evidence/validation.json`, `.claude/settings.json`) sempre pedem confirmação humana. Para transferir o trabalho a outra sessão, use a skill `handoff`.

## Impasse

- Na primeira tentativa de correção que falhar, abra um caso: `aifw impasse open --id <slug> --impact <nível>`.
- Registre cada tentativa: `aifw impasse attempt --id <slug> --hypothesis ... --intervention ... --evidence <arquivos> --outcome failure|success|inconclusive`. A hipótese e a intervenção precisam ser realmente diferentes das anteriores; repetir abre o impasse na hora.
- Após 5 falhas distintas em L0/L1, ou 2 em L2/L3, o caso fica `OPEN` e o hook congela as mudanças. Apresente ao usuário o resultado esperado, as tentativas, o que a evidência eliminou e a regra suspeita; então use `aifw impasse review`.
- `aifw impasse decide` registra a decisão humana e só roda com a confirmação do usuário. Depois da mudança aprovada, use `aifw impasse revalidate`.
- Alterações no framework precisam estar dentro da autorização real do usuário, não ser uma saída improvisada para seus bloqueios.
