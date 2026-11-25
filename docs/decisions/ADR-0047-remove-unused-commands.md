# ADR-0047: Remover waiver, break-glass, eval e gates check

- Status: accepted
- Date: 2026-11-15
- Impact: L2
- Change: `remove-unused-commands`
- Amends: ADR-0037 (break-glass e waiver nos arquivos de controle e na assinatura), ADR-0018 (comandos `waiver add/list` e `break-glass grant/list`), ADR-0020 (`.aifw/waivers/` e `.aifw/break-glass/` como arquivos de controle) e ADR-0021 (registro de uso do break-glass)

## Contexto

Os recursos `aifw waiver`, `aifw break-glass`, `aifw eval` e `aifw gates check` nunca foram usados no fluxo de trabalho. O repositório usa `approvals.requireSignedCommit: true`, e a aprovação de mudanças deixou de depender de assinatura (ADR-0037). Sem uso real, os quatro recursos só aumentam a superfície de código, de testes e de documentação.

O schema `schemas/permissions.schema.json` tinha `additionalProperties: false` com `breakGlass` em `required`. Sem mudança no schema, um `permissions.yaml` novo sem a chave falha; removendo a propriedade, um `permissions.yaml` antigo falha. Os dois casos precisam de tratamento explícito.

A contagem de ocorrências das palavras-chave no código é muito maior que o uso real: parte é histórico, parte é o `eval` do shell, parte é `session-conformance` e parte é o status `waived` da rastreabilidade, que não depende do recurso waiver.

## Decisão

1. Remover os quatro recursos: os comandos `aifw waiver` e `aifw break-glass` (CLI e lista `APPROVALS`), o hook (caminhos de controle e grants no `item_findings`), o módulo `waiver.py`, as funções de break-glass em `permissions.py`, `evaluate_trace` e `run_conformance` em `conformance.py`, `gates.inspect_gate_wiring` e o comando `gates check`, o gate `conformance` e os schemas, templates, casos e traces de `aifw eval`.
2. `breakGlass` fica no schema como propriedade sem tipo, descrita como ignorada, e sai de `required`, para que um `permissions.yaml` antigo continue carregando. Fica o requisito `REQ-AUTONOMY-LEGACY-BREAKGLASS` em `agent-autonomy`, com teste de compatibilidade. Nenhuma migração apaga a chave: `permissions.yaml` é arquivo de controle e a decisão é da pessoa.
3. `evaluate_routing_cases` passa de `conformance.py` para `routing.py`, porque `aifw route eval` a usa e continua na CLI.
4. `.aifw/waivers/` e `.aifw/break-glass/` saem de `CONTROL` e de `SIGNED_OR_POLICY` no hook. `grant` e `waiver add` saem da detecção de aprovação do shell. Nada lê esses caminhos depois do corte, e proteger caminho morto só gera confirmação falsa.
5. `CONSTITUTION.md` fica sem edição. Os §9 ("Break-glass exige...") e §13 ("Exceções devem ter...") são condições normativas pendentes de revisão, porque editar a Constituição é mudança L3 (§15). `docs/authority.md`, que não é normativo, é ajustado.
6. `REQ-CONTEXT-GATES` é modificado para retirar a inspeção de CI. Nenhum requisito aceito é removido, porque nenhum cita waiver, break-glass ou eval.
7. Não há substituto para a exceção temporária. Para um gate que não passa, a saída é corrigir o gate, mudar `.aifw/gates.yaml` (com confirmação humana) ou registrar uma ADR. Push na branch padrão e demais ações `ask` continuam pedindo confirmação a cada vez.

## Alternativas descartadas

- Comando "deprecated" que apenas avisa: mantém o código e os testes que a mudança quer remover, sem ganho de uso.
- Flag de compatibilidade nos comandos: reintroduz a superfície removida com outro nome.
- Apagar a chave `breakGlass` de `permissions.yaml` por migração: altera arquivo de controle sem decisão da pessoa, e o schema novo já aceita a chave antiga.
- Manter `conformance.py` reduzido, só com `evaluate_routing_cases`: deixa um módulo chamado "conformance" com uma função de roteamento e uma entidade falsa no catálogo.

## Consequências

- Um agente que escreva em `.aifw/waivers/` ou `.aifw/break-glass/` deixa de pedir confirmação. Risco aceito: nada lê esses arquivos, então a escrita não muda o comportamento.
- Projetos que copiaram o gate `conformance` das receitas falham em `aifw validate` até removê-lo. A nota de migração em `docs/migrations.md` e no CHANGELOG descreve o passo.
- Grants de break-glass ativos deixam de valer no mesmo instante. Ações `ask` passam a pedir confirmação em todo incidente, como antes de existirem.
- Um gate que um waiver cobria passa a reprovar de verdade.
- Pendência: `CONSTITUTION.md` §9 e §13 continuam citando break-glass e exceções. Precisa de revisão L3.

## Rollback

Reverter o commit (ou commits) da mudança e rodar `aifw claude enable --no-graphify` para regenerar a skill. Nenhum formato persistido muda: os arquivos de waiver e de break-glass nunca foram apagados, então o código antigo volta a lê-los, e o `permissions.yaml` antigo continua válido para o schema antigo. `docs/cli-reference.generated.md` e `PROJECT_MAP.md` voltam com o revert ou são regenerados com `scripts/generate_cli_reference.py` e `aifw map build`.
