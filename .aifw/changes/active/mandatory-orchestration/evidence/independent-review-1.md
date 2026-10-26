# Revisão independente — mandatory-orchestration

## Adversário

Rodada 1. Eixo Spec sobre `git diff main...HEAD` (commit 2257b56), contra `specs/claude-subagents.delta.yaml`, a seção Acceptance e os Non-goals de `proposal.md`, o `design.md` e o ADR-0040. Modelo de ameaça: erro do agente (ADR-0034, ADR-0037).

### Escopo revisado

- `python/aifw/hooks.py`: `edited_file`, `in_paths`, `session_edit`, a refatoração de `outside_plan` e a ordem em `pre_tool_use`.
- `schemas/permissions.schema.json`, `.aifw/permissions.yaml`, `python/aifw/assessment.py`.
- As duas cópias da skill `aifw-workflow` (iguais, fora o carimbo de versão), `docs/claude-code.md`, `docs/routing.md`, CHANGELOG, ADR-0040, os testes e a evidência.

### O que tentei quebrar e resistiu

Rodei os testes num projeto temporário criado com `init` de `tests_python/test_workflows.py` e `add_change` de `test_approved_scope.py`, chamando `handle` direto. Os resultados:

- **Ferramentas.** `MultiEdit` (`file_path`) e `NotebookEdit` (`notebook_path`) da sessão são negados, e `Read` segue.
- **Casamento de `sessionPaths`.** `./Python/AIFW/hooks.py` casa com `python/aifw/hooks.py` e com `PYTHON/aifw/HOOKS.py`. A pasta `docs\guide` cobre `docs/guide/a.md`, mas não `docs/guidex.md`, que é negado. O padrão `templates/*.md` e a pasta `src/` (para `src/a/b.py`) também casam. As entradas `./` e `/` não liberam o projeto inteiro, e `sessionPaths: []` nega até o `hooks.py`.
- **Caminhos.** Um `file_path` relativo (`README.md`) é negado. `.aifw/changes/active/plan/../../../permissions.yaml` é resolvido e negado. Pathlib resolve maiúsculas e nomes 8.3 do Windows, então o alvo continua dentro do projeto.
- **Sessão e subagentes.** Um `agent_id` vazio conta como sessão e é negado. Um subagente editando `README.md` segue. Fora do plano, o subagente recebe o `ask` do ADR-0039 e a sessão recebe `deny` (a negação vence). Num control file, o subagente recebe `ask`. O `tasks.yaml` aprovado, editado pela sessão, sai da orquestração e cai no `ask` de control file.
- **Trava dos revisores.** O `aifw-adversary` editando `README.md` é negado com o motivo do revisor. No `independent-review.md` ele segue.
- **Modo e schema.** Sem a chave `orchestration`, ou com `orchestration: {}`, vale `required`. `mode: off` libera. O schema recusa `mode: OFF`, `sessionPaths` como texto, `sessionPaths: [""]`, chave extra, `null` e escalar. Nesses casos a política fica inválida e a edição pede confirmação, que é o comportamento anterior.
- **Sem mudança aprovada.** Nada é negado. O mesmo acontece quando o `tasks.yaml` da mudança aprovada some, pela regra "mudança quebrada fica fora" do ADR-0040. O `aifw spec new` sempre cria o `tasks.yaml`.
- **Verificações.** A suíte inteira passa (`python -m pytest tests_python -q -p no:cacheprovider`: 2733 passed). `aifw claude check` e `aifw spec validate mandatory-orchestration` passam. `aifw validate --change` só bloqueia por falta deste arquivo.

### Achados

**A1. A tabela de modelos da skill não põe o `aifw-quick` nas tarefas rápidas de L2/L3 e ainda o limita ao caminho FAST** (severidade baixa)

- **Spec.** `claude-subagents.delta.yaml`, linha 24 (REQ-SUBAGENTS-DELEGATION, modificado): "a tabela de modelos da skill devem nomear o subagente de cada papel, com o aifw-executor executando também em L3 e o aifw-quick nas tarefas rápidas de L2 e L3".
- **Onde.** `.claude/skills/aifw-workflow/SKILL.md` e `templates/claude/skills/aifw-workflow/SKILL.md`, linhas 83-84 e 91. A mesma linha da tabela de subagentes está em `docs/claude-code.md:141`.
- **Cenário.** O agente consulta a tabela "Modelos por classe" para uma subtarefa rápida dentro de uma mudança L2.
  - A linha `impacto L2 ou caminho PLANNED` traz em Executa só `aifw-executor`. A linha L3 também traz só `aifw-executor`, então a parte "executor em L3" foi feita.
  - A tabela de subagentes, logo abaixo, descreve o papel do `aifw-quick` como "tarefas do caminho FAST", o que exclui L2 e L3.
  - O `aifw-quick` nas tarefas rápidas aparece só no bullet da linha 100, contradito pela tabela da mesma seção.
- **Contraste.** O próprio diff fez isso direito na tabela do avaliador de `docs/routing.md`, que nas linhas PLANNED e CRITICAL passou a dizer "`aifw-executor` (sonnet), `aifw-quick` (haiku) nas tarefas rápidas". Já a tabela por classe do mesmo arquivo (linhas 19-20) e a da skill ficaram como estavam.
- **Evidência.** `sed -n 82,95p .claude/skills/aifw-workflow/SKILL.md` mostra as três linhas citadas.
- **Correção sugerida.** Nas linhas L3 e L2 da tabela da skill (e da tabela por classe do `routing.md`), escrever "`aifw-executor`; `aifw-quick` nas tarefas rápidas". No papel do `aifw-quick` (skill e `docs/claude-code.md`), escrever "tarefas do caminho FAST e tarefas rápidas de L2/L3".

### Ressalvas (sem reprovação)

- **R1. A sessão não edita o `permissions.yaml`.** Com uma mudança aprovada ativa, a sessão recebe `deny`, não `ask`, ao editar `.aifw/permissions.yaml`, como em qualquer arquivo do projeto fora de `sessionPaths` (provado: sessão `deny`, subagente `ask`). Isso bate com a spec (linha 11). Só que o design (linha 92) e o ADR-0040 apontam "incluir o caminho em `sessionPaths`" e "`orchestration.mode: off`" como saída e rollback, e isso só funciona delegando a um subagente, com confirmação, ou editando à mão. O motivo da negação não diz isso.
- **R2. L0/L1 durante uma mudança aprovada.** A skill diz "Fazer inline só vale em L0 e L1". Mas uma edição L0/L1 feita enquanto uma mudança L2 aprovada está ativa é negada, porque a regra depende só de existir uma mudança aprovada. Isso segue a spec literal e a documentação ("com uma mudança aprovada ativa"). Fica a tensão de leitura.
- **R3. Processo.**
  - O `tasks.yaml` não lista `tests_python/test_approved_scope.py`, que está no diff, e lista `.aifw/effective-policy.json`, que não está.
  - Segundo a evidência, a sessão editou `schemas/permissions.schema.json`, que não está em `sessionPaths`. Pela Acceptance (linha 62), só o núcleo do hook fica com a sessão. A edição foi antes de o hook novo entrar, e o schema pode ser lido como parte do núcleo, porque uma política inválida trava as edições.
- **R4. Cobertura de testes.** `test_orchestration.py` cobre só Edit e Write. MultiEdit e NotebookEdit funcionam (provado acima), mas não têm teste. Também não há teste para `sessionPaths` com pasta, padrão, `./` e maiúsculas, que vêm do ADR-0039 via `in_paths`.
- **R5. `*` nos padrões.** O `*` de `fnmatch` atravessa `/`: `python/aifw/*.py` em `sessionPaths` também libera `python/aifw/sub/x.py`. Herdado do ADR-0039.

Resultado: reprovado
