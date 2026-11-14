# ADR-0046: Perfil de revisão pela natureza da mudança

- Status: accepted
- Date: 2026-11-14
- Impact: L2
- Change: `review-profile`
- Amends: ADR-0038 (revisão em duas etapas) e ADR-0042 (revisores nas cascatas L2/L3)

## Contexto

A revisão independente de L2/L3 tem duas etapas: `aifw-adversary` (eixo Spec, Opus) e depois `aifw-qa` (eixo Standards e entrega, Sonnet). A pessoa quer um revisor só quando a mudança é só de interface ou só de texto.

O gate `independent-review` lê só a linha `Resultado:` do `independent-review.md` e não exige a seção do adversário. A guarda de revisor do hook decide pelo `agent_type` e pelo alvo da escrita; não olha se o adversário rodou. O `aifw-qa` tem a ferramenta `Skill` e o `aifw-adversary` não. L2/L3 de risco baixo ou médio em regra não criam pasta de mudança, então o registro do perfil não pode depender de `change.yaml`.

## Decisão

1. Dois perfis leves, com um revisor só (`aifw-qa`): `interface` e `texto`. O resto é `completo`, com os dois revisores. O `aifw-qa` fica com o papel por ter a ferramenta `Skill` e custar menos que o adversário.
2. Risco alto ou crítico é sempre `completo`. O aviso do avaliador só cita a exceção com risco baixo ou médio, para não contradizer a skill.
3. O agente principal declara no chat, antes de delegar, a linha `Perfil de revisão: completo`, `interface` ou `texto`, e segue sem pedir aprovação; a pessoa pode barrar. O perfil leve só vale em risco baixo ou médio, que não pede `request-approval`, então não há plano a aprovar. Na dúvida, `completo`.
4. O registro é a linha no chat, repetida no brief do `aifw-qa` e na primeira linha da seção `## QA`. Sem campo em `change.yaml`, sem campo no avaliador, sem código de classificação.
5. O `aifw-qa` faz também o eixo Spec, por uma seção curta que aponta para o `code-review`, sem copiar a lista do adversário (uma só fonte de verdade).
6. O `aifw-qa` confere primeiro se o diff cabe no perfil. Se não couber, não escreve `Resultado:` e devolve; o agente principal chama o `aifw-adversary` e depois o `aifw-qa` de novo. Sem `Resultado:`, o gate falha e a rodada de correção não é gasta.
7. `texto` exclui o que agente ou hook lê como regra (skill, subagente, política, spec): é comportamento do framework e fica em `completo`. Julgamento fora do pedido literal; a pessoa pode ampliar.
8. As skills de front end são nomeadas pelo agente principal no brief; os templates não fixam nomes. A checagem visual só é pedida quando há como rodar a tela.
9. O aviso do avaliador (`path_context`) cita a exceção, numa frase, em PLANNED e CRITICAL com risco baixo ou médio. Não entra em `PATH_RULE` nem nos caminhos FAST/WORK.
10. Gate, hook (`hooks.py`, `shell.py`, `indirect.py`) e os subagentes planner, lead, executor, senior e adversary não mudam; seus textos continuam verdadeiros.
11. Sem defesa contra orquestrador de má-fé: o hook protege contra erro do agente, não contra má-fé (ADR-0034, ADR-0037). O `aifw-qa` pega o erro honesto e a linha no chat registra a declaração.
12. Esta mudança é perfil `completo`: toca skill, subagente e código.

## Alternativas descartadas

- Perguntar antes de usar o perfil leve: voltaria a interromper a pessoa em toda mudança de tela ou de texto, que é o atrito que a mudança quer tirar. Declarar e seguir mantém a pessoa informada, com poder de barrar, e a guarda é o `aifw-qa`.
- Campo em `change.yaml`: não existiria no caso comum (sem pasta) e custaria esquema e código novos.
- Campo `reviewProfile` no avaliador: a pessoa decidiu não criar campo novo no avaliador.
- Fixar nomes de skill de front end nos templates: o repositório é público e cada pessoa tem as suas.
- Regra por extensão de arquivo: não distingue estilo de lógica nem texto lido por pessoas de texto lido por agentes.
- Incluir skill, subagente, política e spec em `texto`: o perfil leve revisaria sozinho a mudança de maior risco do repositório.

## Consequências

- Classificação errada do agente principal: o `aifw-qa` confere o diff e devolve, ao custo de uma rodada de QA. Se ele falhar em notar, a mudança passa sem adversário: risco aceito, mitigado pelo ônus da prova do `Resultado:` e pela suíte e gates, que rodam sempre.
- O comportamento do `aifw-qa` em perfil leve só é provado em uso real: os testes travam as frases, não o comportamento do agente.
- O `aifw-qa` não tem navegador nem captura de tela. A checagem visual depende do que o `Bash` rodar (por exemplo uma skill de Playwright nomeada no brief) e da trava dos revisores; não verificada. Sem como rodar a tela, a revisão de `interface` é só de diff.
- `texto` fica mais estreito que o pedido: mudança só de skill, ADR ou spec continua com os dois revisores.
- Pode haver duas seções `## QA` no mesmo arquivo quando o `aifw-qa` devolve e roda de novo; o gate lê a primeira linha `Resultado:` e só a segunda rodada a escreve.
- Rollback: reverter a mudança e rodar `aifw claude enable --no-graphify` para regenerar as cópias; volta a revisão em duas etapas. Nenhum formato persistido muda; um `independent-review.md` de perfil leve já gravado continua válido para o gate.
