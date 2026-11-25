# Proposal — Remove waiver, break-glass, eval e gates check

## Intent

Remove do CLI e do hook os recursos waiver e break-glass inteiros e os subcomandos eval e gates check, nunca usados no fluxo, mantendo legiveis os projetos que ja tem breakGlass no permissions.yaml.

A pessoa decidiu cortar quatro coisas que nunca entraram no fluxo de trabalho: elas custam código, testes, texto de skill e superfície de ataque do hook sem produzir evidência. Só remoção: nada de abstração nova, flag de compatibilidade nem comando "deprecated". Um comando removido deixa de existir no argparse.

## Scope

1. **waiver:** `aifw waiver add|list`, `python/aifw/waiver.py`, `apply_waivers` em `gates.py`, `schemas/waiver.schema.json`, `templates/waiver.yaml`, o campo `waived` que só ele escreve no resultado do gate, e os caminhos `.aifw/waivers/` como arquivo de controle no hook.
2. **break-glass:** `aifw break-glass grant|list`, `validate_break_glass`, `BREAK_GLASS_SCOPES`, `grant_break_glass`, `list_break_glass` em `permissions.py`, `active_grants` e `log_break_glass` no hook, o ramo "break-glass" nas decisões do hook, `.aifw/break-glass/` como arquivo de controle, e a chave `breakGlass` do `permissions.yaml` do repositório e do scaffold.
3. **eval:** `aifw eval`, o gate `conformance` de `.aifw/gates.yaml` (que roda `aifw eval`), `conformance.py` (menos `evaluate_routing_cases`, que o `route eval` usa e que passa para `routing.py`), `schemas/conformance-case.schema.json`, `schemas/agent-trace.schema.json`, `templates/agent-trace.yaml`, `evals/cases/`, `evals/traces/`, a entrada `component:conformance` do catálogo, e o texto do `docs/agent-conformance.md` que só descreve o `aifw eval`.
4. **gates check:** `aifw gates check` e `gates.inspect_gate_wiring`.
5. **Compatibilidade:** `schemas/permissions.schema.json` deixa de exigir `breakGlass` e continua aceitando a chave com qualquer valor, que o código ignora. Um `permissions.yaml` antigo com `breakGlass` carrega; um novo sem ela também. Pastas `.aifw/waivers/` e `.aifw/break-glass/` que sobrarem em projetos adotados ficam inertes: nada lê nem protege.
6. **Texto e artefatos derivados:** skill `aifw-workflow` (template e cópia regenerada), README, HOW_TO_USE, docs, CHANGELOG, `docs/migrations.md` (nota de migração), ADR-0047, `docs/cli-reference.generated.md` e `PROJECT_MAP.md` regenerados.
7. **Spec aceita:** `REQ-CONTEXT-GATES` (capability `context-intelligence`) deixa de falar de inspeção de CI; nova `REQ-AUTONOMY-LEGACY-BREAKGLASS` (capability `agent-autonomy`) trava a compatibilidade da chave antiga.

## Non-goals

- `audit`, `instructions build|check`, `principle list`, `context index|select|check`, `decision *`, `spec list`, `route eval`, `assess eval` e qualquer outro recurso.
- `CONSTITUTION.md` (seções 9 e 13 citam break-glass e waivers como regra; qualquer edição nela é L3, §15): fica como está. Se a pessoa quiser alinhá-la, é outra mudança L3.
- `policies/core.yaml`, `profiles/`, `aifw.yaml`: sem edição. O campo `overridable` das regras e o status `waived` de artefato de rastreabilidade (`traceability.schema.json`, `specs.py`) não dependem do recurso waiver e ficam.
- Histórico: ADRs antigos, `docs/audits/`, `docs/plans/`, `docs/gap-audit-*`, entradas antigas do CHANGELOG e `.aifw/changes/archive/` não se reescrevem.
- `python/aifw/indirect.py`: não muda (sem referência a nenhum dos quatro itens).
- Migração automática que apague `.aifw/waivers/`, `.aifw/break-glass/` ou a chave `breakGlass` de projetos existentes: a nota de migração diz como limpar à mão.

## Acceptance

- `aifw waiver`, `aifw break-glass`, `aifw eval` e `aifw gates check` não existem mais no parser (`aifw <cmd> --help` falha com erro de argparse) e `docs/cli-reference.generated.md` não os cita.
- `grep -rn -i -E "waiver|break-?glass|conformance|inspect_gate_wiring|apply_waivers" python scripts schemas templates policies profiles tests_python` não acha nada que não seja `session-conformance`, a propriedade `breakGlass` tolerada em `schemas/permissions.schema.json` ou o teste de compatibilidade da chave `breakGlass`. O status `waived` de rastreabilidade não casa com o padrão e fica.
- O gate `conformance` saiu de `.aifw/gates.yaml`; `aifw validate --level L2` não chama mais `aifw eval`.
- Teste de compatibilidade (`tests_python/test_audit_features.py`): um `permissions.yaml` com o bloco `breakGlass` antigo e um `.aifw/break-glass/<id>.yaml` antigo carrega e o hook trata `git push` como antes (pede confirmação); um `permissions.yaml` sem `breakGlass` valida pelo schema.
- `route eval` continua dando 32/32 (`tests_python/fixtures/cli-parity.json`, `test_workflows`, `scripts/verify_wheel.py`).
- Suíte: `python -m pytest -q -p no:cacheprovider tests_python` passa (base 2859; esperado 2846, a diferença é só dos testes removidos e dos dois de compatibilidade acrescentados). `ruff check` e `ruff format --check` passam; `python scripts/generate_cli_reference.py --check`, `aifw map check`, `aifw resolve check`, `aifw claude check` passam.
- `aifw spec validate remove-unused-commands` sem erro e `aifw spec analyze remove-unused-commands` sem achado de erro depois da evidência de teste registrada.
- Nota de migração em `docs/migrations.md` e no CHANGELOG; ADR-0047 registrado e ligado em `traceability.yaml`.
