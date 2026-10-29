# Revisão independente — quiet-enable-and-status

## Adversário

Rodada 1. Escopo: `git diff main...HEAD` (bdcfbf2) contra `specs/agent-autonomy.delta.yaml` (REQ-AUTONOMY-APPROVED-SCOPE), `specs/claude-subagents.delta.yaml` (REQ-SUBAGENTS-EDITED-BACKUP), Acceptance, design, Non-goals e ADR-0041. Os experimentos rodaram num projeto temporário (`init` de `tests_python/test_workflows.py`, `add_change` de `test_approved_scope.py`, `aifw.hooks.handle`, `aifw.claude.enable_project`/`check_project`), por scripts em pasta temporária. `tests_python/test_approved_scope.py` e `tests_python/test_role_subagents.py` passam (34 testes).

### Achado 1 (alta): uma chave duplicada no `tasks.yaml` aprovado passa sem pedir e desliga o plano, a orquestração e a proteção do `tasks.yaml`

- Onde: `python/aifw/hooks.py:181` (`widens_plan` lê com `yaml.safe_load`) e `python/aifw/hooks.py:111-122` (`approved_plans` lê com `read_yaml`/`CoreLoader`, que trata chave duplicada como erro e pula a mudança: "a broken change leaves the rule").
- Spec: proposal.md:16 ("se o resultado não é YAML legível, continua pedindo"), ADR-0041 item 4 ("um YAML ilegível [...] continua pedindo"), REQ-AUTONOMY-APPROVED-SCOPE (o `tasks.yaml` aprovado pede confirmação quando muda os paths, e os arquivos fora do plano pedem).
- Cenário (erro de agente comum: inserir uma linha em vez de trocá-la): um subagente faz um Edit no `tasks.yaml` aprovado com `old_string="  status: pending\n"` e `new_string="  status: pending\n  status: done\n"`. Para `safe_load` o YAML é válido (a última chave vence) e os `paths` não mudam, então o hook deixa passar. Para o leitor do AIFW o arquivo fica ilegível, e a mudança some de `approved_plans`.
- Evidência (probe `probe_dupkey.py`):
  - antes: Edit de `python/aifw/hooks.py` por subagente → `ask` (fora do plano); pela sessão → `deny` (ADR-0040);
  - o Edit da chave duplicada → `None` (não pede);
  - `approved_plans` depois → `{}`;
  - depois: Edit de `python/aifw/hooks.py` por subagente → `None`; pela sessão principal → `None`; incluir `src/` nos `paths` do `tasks.yaml` → `None`.
- Regressão: antes desta mudança, qualquer Edit no `tasks.yaml` aprovado pedia confirmação, então não havia como chegar a esse estado sem a pessoa ver. Agora um engano silencioso tira todo o escopo e a orquestração da mudança.
- Correção sugerida: em `widens_plan`, ler o antes e o depois com o mesmo leitor de `approved_plans` (`read_yaml`/`CoreLoader`). Assim chave duplicada e as diferenças de booleano e data contam como "ilegível" e pedem. Falta um teste com chave duplicada.

### Achado 2 (média): copiar uma tarefa sem trocar o `id` amplia o plano sem pedir

- Onde: `python/aifw/hooks.py:182`, `{task.get("id"): ...}`. Com `id` repetido (ou ausente), o dicionário guarda só a última tarefa, e uma tarefa nova acima dela some da comparação. `approved_plans` (hooks.py:119) junta os `paths` de todas as tarefas.
- Spec: REQ-AUTONOMY-APPROVED-SCOPE ("editar o tasks.yaml aprovado deve pedir confirmação quando muda os paths de alguma tarefa") e Acceptance ("incluir um path [...] pede").
- Cenário: o `tasks.yaml` tem `TASK-A` com `paths: [docs/]`. O agente duplica o bloco acima dele, esquece de trocar o `id` e põe `python/aifw/hooks.py` nos `paths`, por Edit (inserindo depois de `tasks:\n`) ou por Write.
- Evidência (probe `probe_plan.py`): `dup-id Write None`, `dup-id Edit None`; `approved_plans` passa de `{'plan': ['docs/']}` para `{'plan': ['python/aifw/hooks.py', 'docs/']}`. O mesmo vale para tarefas sem `id` (`no-id Write None`).
- Correção sugerida: comparar uma lista de pares `(id, paths)` na ordem, ou o multiconjunto. Outra saída é tratar `id` repetido ou ausente como mudança.

### Achado 3 (baixa): o CHANGELOG contradiz o código e o ADR

- Onde: `CHANGELOG.md:7`, "mudar os `paths` ou outro campo continua pedindo".
- O ADR-0041 (item 4) libera título e qualquer campo que não seja `paths`, e o código faz isso. Evidência (`probe_plan.py`): os Edits de `title`, `dependsOn` e `requirementIds` voltam `None` (não pedem). Só a troca de `id` pede, porque muda a chave do mapa.
- Correção: no CHANGELOG, trocar por "mudar os `paths` de alguma tarefa continua pedindo; `status`, título e os outros campos ficam livres".

### Conferido sem quebra

- Hash da cópia (`python/aifw/claude.py:69-87`), com o template mudado e `enable` de novo:
  - cópia CRLF intacta: troca sem `.bak` (o `read_text` normaliza o fim de linha);
  - cópia CRLF com o template igual: sem `.bak`;
  - texto acrescentado depois da linha de hash: `.bak`;
  - carimbo de outra versão com hash válido: sem `.bak`, como pede o ADR-0041 item 2;
  - template igual: sem `.bak`;
  - corpo editado: `.bak`;
  - `check_project` sem achados de skill ou subagente depois do `enable`.
- `widens_plan`:
  - Edit com `replace_all` de `status`: não pede;
  - MultiEdit de `status`: não pede;
  - MultiEdit que muda `paths`: pede;
  - Write que muda `paths`: pede;
  - Write que não é YAML válido: pede;
  - `old_string` vazio ou ausente: pede;
  - arquivo CRLF no disco: `status` não pede, incluir path pede;
  - troca de `id`: pede;
  - mover um path entre tarefas: pede;
  - reordenar `paths`: pede;
  - trocar `dependsOn`: não pede;
  - `sed -i`: pede;
  - NotebookEdit: pede, porque não há `old_string` e a exceção conta como mudança.
- A skill (template e cópia) e `docs/claude-code.md` batem com o código.

### Ressalvas

- Uma linha em branco a mais no fim da cópia, que alguns editores acrescentam, já faz a cópia contar como editada e gera `.bak`. É conservador e está dentro do ADR ("nada depois"), mas pode trazer de volta o atrito que a mudança quer tirar.
- Reordenar os `paths` de uma tarefa pede confirmação, e o design diz que "mudar status, título ou ordem não amplia o plano". Leio "ordem" como a ordem das tarefas, que não pede. É conservador e não reprova.
- O design cita `widens_plan(root, path, ...)`, mas o código não recebe `root`. Diferença sem efeito.

Resultado: reprovado
