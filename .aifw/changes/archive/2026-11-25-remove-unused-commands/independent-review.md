# Revisão independente — remove-unused-commands

## Adversário

Perfil: completo (risco crítico: o diff mexe no núcleo do hook). Eixo Spec revisado contra `proposal.md`, `design.md`, `specs/*.delta.yaml`, `tasks.yaml` e `traceability.yaml`.

### Escopo revisado

- `python/aifw/hooks.py`, `python/aifw/shell.py`, `permissions.py`, `gates.py`, `routing.py`, `cli.py`, `schemas/permissions.schema.json`, `templates/project-scaffold.json`, `scripts/verify_wheel.py`, `.aifw/gates.yaml`, `.aifw/permissions.yaml`, `.aifw/catalog.yaml`, fixtures, testes alterados, docs, skill, CHANGELOG, `docs/migrations.md` e ADR-0047.
- Deltas: `REQ-CONTEXT-GATES` (modified) existe em `.aifw/specs/current/context-intelligence.yaml`; `REQ-AUTONOMY-LEGACY-BREAKGLASS` (added) não existe em `agent-autonomy.yaml`. Nenhuma spec aceita cita waiver, break-glass, `aifw eval` ou `gates check`, então não falta nenhum `removed`.

### Experimentos

1. **Hook antigo e novo comparados.** Extraí `HEAD` numa pasta temporária e rodei as mesmas 37 entradas com `handle()` e `analyze()` nas duas versões, num projeto do `init` com repositório git. Foram 31 comandos Bash (push com e sem branch, `--force`, `HEAD:main`, push encadeado, as aprovações restantes `intake approve`, `impasse decide`, `assess verdict`, `spec approve`, `decision approve`, `activate`, `record_chat` em código inline, `echo | aifw decide`, `false && aifw impasse decide || echo`, `aifw impasse decide || true`, curl, `rm -rf`, `npm publish`, `gh pr create`, `gh release create`, `kubectl`, `vercel --prod`, `git reset --hard` e commits) e 4 Writes (`.aifw/waivers/`, `.aifw/break-glass/`, `permissions.yaml`, `impasses/`).
   - Diferenças encontradas, todas previstas no design (Decisions 3 e 4): `aifw grant`, `aifw waiver add`, `aifw break-glass grant`, `bash -c "aifw waiver add"` e código inline com `aifw` mais `grant` ou `add_waiver` deixaram de ser aprovação. Escrever em `.aifw/waivers/` e `.aifw/break-glass/` não pede mais confirmação.
   - Todas as outras decisões e o flag `approval` saíram idênticos. Isso inclui a precedência `and`/`or` de `segment_requests`, que continua `(name == "aifw" and palavras) or forges_prompt`.
2. **Ramos `git-remote` e `else`.** Sem grant, o ramo `git-remote` com o walrus equivale ao antigo, e o `else` com `decide_action` mantém o fluxo. Quanto a `active_grants`: antes ele só rodava quando havia `reason` ou quando a decisão não era `allow`. A remoção dele só tira efeitos (liberação e log), sem mudar o resto.
3. **Compatibilidade de `breakGlass`.** `load_permission_policy` aceita o objeto antigo, o objeto com campo extra, `null`, string, lista e o objeto com `requiresIncidentId: false`. Também aceita o arquivo sem a chave (o teste novo cobre esse caso). Nada em `python/` lê `breakGlass`, `.aifw/waivers/` ou `.aifw/break-glass/`, e nenhum validador mapeia schema por pasta.
4. **CLI.** `aifw waiver`, `waiver add`, `break-glass`, `break-glass grant`, `eval`, `gates` e `gates check --help` saem com 1 (erro do argparse). `route eval` e `route eval --cases evals/routing/cases.yaml` dão 32/32, e `assess eval --help` está intacto. O corpo de `evaluate_routing_cases` em `routing.py` é idêntico ao de `HEAD:conformance.py` (diff vazio).
5. **Suíte.** `python -m pytest -q -p no:cacheprovider tests_python` passa, com total de 2846.
6. **Cobertura do commit com arquivo de controle.** O design manda apagar a única asserção de `test_commits_allowed_by_policy_still_ask_with_control_files_changed` que exercia um arquivo de controle (`.aifw/waivers/w.yaml`). Por isso fiz uma mutação em processo, com `dirty_control` devolvendo `""`. A suíte inteira ainda reprova, por `test_agent_autonomy.py::test_committing_after_the_chat_approval_runs`, então o comportamento continua coberto.
7. **Gerados e verificações.** `aifw map check` (current), `resolve check`, `claude check` (pass), `spec validate` e `spec analyze` (sem achados). `docs/cli-reference.generated.md` não lista os comandos removidos. Nenhuma receita de `profiles/`, nem `.github/`, nem `.claude/`, nem o scaffold usa `aifw eval`, o gate `conformance` ou `gates check`; só aparece `session-conformance`.

### Achados

Nenhum achado provado.

### Ressalvas (não provadas como defeito, não reprovam)

1. **Grep de aceitação (proposal.md, Acceptance, item 2).** O critério diz que o grep "não acha nada que não seja `session-conformance`, a propriedade `breakGlass` tolerada [...] ou o teste de compatibilidade". Mas `templates/technical-plan.md:37` ("performance e conformance selecionados pelo risco") e `policies/core.yaml:70` ("routing table whose conformance eval passes") também casam, e estão em `evidence/acceptance-grep.txt`. Os dois são anteriores à mudança, genéricos ou falam do `route eval`, e `policies/` é non-goal. É uma divergência do texto do critério, não um defeito.
2. **`docs/migrations.md:25` ("permanece project rule ou waiver local").** Fica na seção de regras gerais, não numa seção de versão, e ainda recomenda o waiver, que deixou de existir. O design (TASK-DOCS-SECURITY) declarou essa linha como histórico, então fica dentro do que foi aprovado. Vale alinhar numa mudança de texto.
3. **`test_hooks.py::test_commits_allowed_by_policy_still_ask_with_control_files_changed`.** Ficou sem nenhuma asserção de arquivo de controle, embora o nome prometa isso. O comportamento segue coberto por `test_agent_autonomy` (experimento 6). Trocar `.aifw/waivers/w.yaml` por `.aifw/impasses/x.yaml` devolveria ao teste o que o nome diz.
4. **`docs/migrations.md:86`.** "Saem o gate `conformance`" tem erro de concordância ("Sai o gate").
5. **Não verificado.** Não rodei `python -m build`, `scripts/verify_wheel.py`, `generate_cli_reference.py --check` nem `ruff`: o hook do revisor bloqueou os comandos que gravam ou que ele lê como escrita. Para esses itens existem só as evidências registradas em `evidence/`. Também não rodei `aifw validate --level L2`, que executa os gates; conferi pelo diff que o gate `conformance` saiu.

## QA

Perfil de revisão: completo (risco crítico: o diff mexe no núcleo do hook). Eixos Standards e entrega, depois do adversário. Fontes de padrão: `AGENTS.md`, `principle-catalogs/`, o ADR-0046 como formato do ADR e a lista de smells do `code-review`.

### Critérios de aceitação (`proposal.md`, Acceptance)

| Critério | Evidência | Situação |
| --- | --- | --- |
| `waiver`, `break-glass`, `eval`, `gates check` fora do parser; `cli-reference.generated.md` sem eles | `evidence/removed-commands.txt` (argparse `invalid choice` para os quatro, `grep-exit=1` no cli-reference); `aifw --help` rodado por mim lista 21 comandos, sem `waiver`, `break-glass`, `eval` nem `gates` | cumprido |
| grep de aceitação só com `session-conformance`, `breakGlass` tolerada e teste de compatibilidade | `evidence/acceptance-grep.txt`; refeito por mim com o mesmo padrão: mesmos achados, inclusive os dois pré-existentes de `technical-plan.md` e `policies/core.yaml` | cumprido, com a ressalva 2 do adversário |
| Gate `conformance` fora de `.aifw/gates.yaml` | `git diff .aifw/gates.yaml`; nenhuma receita de `profiles/` o usa | cumprido |
| Compatibilidade de `breakGlass` (grant antigo e `git push` ainda em `ask`; arquivo sem a chave valida) | `tests_python/test_audit_features.py` (`test_legacy_break_glass_key_is_ignored`, `test_permissions_without_break_glass_validate`), `evidence/scenario-tests.txt` (6 passed) | cumprido |
| `route eval` 32/32 | `evidence/removed-commands.txt`, `evidence/verify-wheel.txt` (14 comandos, pass) | cumprido |
| Suíte, ruff, `generate --check`, `map check`, `resolve check`, `claude check` | `evidence/tests.txt` (2846 passed), `ruff-check.txt`, `ruff-format.txt`, `cli-reference-check.txt` (vazio), `map-check.txt`, `resolve-check.txt`, `claude-check.txt`; refeitos por mim: `map check` current, `resolve check` current, `claude check` pass | cumprido (ver "Gates") |
| `spec validate` sem erro e `spec analyze` sem achado | `evidence/spec-validate.txt`, `evidence/spec-analyze.txt`; refeitos por mim: `pass: true`, `findings: []`, requisitos 2/2, cenários 2/2, tarefas 12/12 | cumprido |
| Nota de migração em `docs/migrations.md` e no CHANGELOG; ADR-0047 ligado em `traceability.yaml` | `docs/migrations.md` seção "v0.4.1 → próxima versão" (7 passos); `CHANGELOG.md` (`### Alterado` e `### Removido`, ADR-0047); `traceability.yaml` (`ADR-0047` com `governedBy` nos dois requisitos) | cumprido |

### Tarefas e rastreabilidade

- As 12 tarefas estão `done`; `spec analyze` confirma 12/12 completas e cada requisito ligado a uma tarefa. Os arquivos que as tarefas mandam apagar (`conformance.py`, `waiver.py`, 3 schemas, 2 templates, `evals/cases`, `evals/traces`) aparecem como `D` no `git status`.
- Os 14 artefatos de `traceability.yaml` apontam para arquivos que existem em `evidence/`, no `design.md` e no ADR-0047. Os dois cenários (`SCN-CONTEXT-GATES`, `SCN-AUTONOMY-LEGACY-BREAKGLASS`) têm teste e `scenario-tests.txt`.
- Reexecutei `test_audit_features`, `test_context`, `test_hooks` e `test_shell`: 163 passed.

### Documentação e derivados

- Skill: `templates/claude/skills/aifw-workflow/SKILL.md` e `.claude/skills/aifw-workflow/SKILL.md` são iguais, salvo o rodapé `aifw-version`/`aifw-sha256` que a regeneração acrescenta; `claude check` passa. As cinco edições previstas (lista de decisões humanas, lista de aprovações, bullet `gates check`, bullet de waiver/break-glass, frase "Não escreva waivers...") estão feitas.
- `README.md`, `HOW_TO_USE.md`, `docs/cli.md`, `docs/cli-reference.generated.md`, `docs/agent-conformance.md`, `docs/architecture.md`, `docs/authority.md`, `docs/security.md`, `docs/claude-code.md`, `docs/context-intelligence.md`, `docs/observability-and-runbooks.md`, `docs/quality-gates.md`, `docs/traceability.md`: sem referência aos quatro recursos, salvo o histórico listado nas ressalvas. `docs/cli-reference.generated.md` não cita `waiver`, `break-glass` nem `gates check`.
- `docs/decisions/` só tem arquivos `ADR-*.md`: não há índice de ADR a atualizar.

### ADR-0047

Segue o formato do ADR-0046 (Status, Date, Impact, Change, Amends, Contexto, Decisão, Alternativas descartadas, Consequências, Rollback). Tem sete decisões, quatro alternativas com motivo, consequências honestas (escrita em `.aifw/waivers/` sem confirmação, projetos com o gate `conformance` falham até removê-lo, grants ativos deixam de valer, gate antes coberto por waiver reprova), rollback concreto sem formato persistido alterado e a pendência de `CONSTITUTION.md` §9 e §13 (revisão L3, §15). Ligado em `traceability.yaml` e no CHANGELOG.

### Standards

- `principle-catalogs/` e padrões do repositório: o diff é remoção, mais a mudança de `evaluate_routing_cases` de módulo (corpo idêntico, confirmado pelo adversário) e a tolerância no schema. Sem abstração nova, flag de compatibilidade ou comando "deprecated", o que respeita o "só remoção" da proposta.
- Smells: nenhum introduzido. A relocação para `routing.py` evita deixar um módulo "conformance" com uma função só (Middle Man), como diz a alternativa descartada do ADR.
- `ruff check` e `ruff format --check` limpos pela evidência registrada; não pude reexecutar.

### Os cinco pontos conhecidos

1. **Frases perdidas da skill ("`execution: not-run` não é evidência", "obrigatórios com skipped, aviso ou desconhecido bloqueiam"):** a regra não depende dessas frases. Continua em `docs/quality-gates.md:35` (`not-run` hard/human bloqueia), em `REQ-CONTEXT-GATES` (modificado, com `SCN-CONTEXT-GATES` e os testes `test_missing_hard_gate_never_passes` e `test_unproven_hard_gate_blocks`, verdes) e no item 7 de "Mudanças e evidências" da skill ("Hard/human bloqueados impedem declarar aprovação"). Não quebra critério. Se a pessoa quiser a instrução de volta ao agente, uma frase no item 6 ou 7 da skill ("`not-run`, `skipped`, aviso ou estado desconhecido em gate obrigatório não é evidência") basta; fica como sugestão, fora desta spec.
2. **"conformance" em `templates/technical-plan.md:37` e `policies/core.yaml:70`:** pré-existentes e genéricos (o segundo fala do `route eval`, que continua). Não citam item removido. É o texto do critério de aceitação que deveria tê-los ressalvado, não a entrega.
3. **`docs/migrations.md:25` ("waiver local") e `:86` ("Saem o gate"):** ver ressalvas 2.
4. **`test_commits_allowed_by_policy_still_ask_with_control_files_changed` sem asserção de arquivo de controle:** confirmado em `tests_python/test_hooks.py:204-229`. As asserções que sobram cobrem `git push`, `-S`, `git add -A && git commit` e script antes do commit. O comportamento de arquivo de controle segue provado por `test_agent_autonomy` (mutação do adversário, experimento 6). O nome do teste promete mais do que ele cobre.
5. **Teste de `breakGlass` escrito depois do código:** a ordem não é verificável no artefato. O que o critério exige, teste que existe e passa, está provado (`scenario-tests.txt`), e o adversário exercitou seis formas do valor antigo (experimento 3). Sem impacto na entrega.

### Gates

- Rodei e passou: `aifw spec validate remove-unused-commands` (pass, sem achados), `aifw spec analyze remove-unused-commands` (pass, sem achados, 2/2, 2/2, 12/12), `aifw map check` (current), `aifw resolve check` (current), `aifw claude check` (pass), os quatro arquivos de teste acima (163 passed) e o grep de aceitação.
- O guard de revisor negou `python scripts/generate_cli_reference.py --check` e `ruff` (lidos como escrita). Para esses, só a evidência registrada. Também não reexecutei a suíte inteira (2846 passed em `evidence/tests.txt`, reexecutada pelo adversário) nem `build`/`verify_wheel`.
- `aifw validate --change remove-unused-commands --write` não foi rodado: grava `evidence/validation.json` e é passo do agente principal depois da revisão.

### Ressalvas (não reprovam)

1. `docs/migrations.md:71` (seção v0.3.0 → v0.4.0): "registre um waiver (`aifw waiver add`)" manda a pessoa a um comando que não existe mais. É passo histórico daquela versão, mas é o que o leitor de uma migração segue; cortar a alternativa ou marcá-la como removida.
2. `docs/migrations.md:25` ("project rule ou waiver local") e `:86` ("Saem o gate" para "Sai o gate"): alinhar o texto. A linha 13 ("conformance evals") é genérica e continua verdadeira por `route eval` e `assess eval`.
3. `docs/quality-gates.md:36-37`: ao tirar o trecho de waiver, o parágrafo perdeu a linha em branco antes de `## TDD por risco`. Renderiza (o cabeçalho interrompe o parágrafo), mas é regressão de formatação; restaurar a linha em branco.
4. `.aifw/charter.yaml:19` fala em "conformance evals" no escopo do projeto. Arquivo de controle, sem comando citado, fora do escopo.
5. Pendência registrada no ADR-0047: `CONSTITUTION.md` §9 e §13 ainda citam break-glass e exceções; precisa de mudança L3 própria.

Resultado: aprovado com ressalvas
