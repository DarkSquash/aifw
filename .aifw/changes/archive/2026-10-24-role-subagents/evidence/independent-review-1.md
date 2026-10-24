# Revisão independente — role-subagents

## Adversário

Rodada 1. Escopo revisado: `git diff main...HEAD` (commit 2118386), `specs/claude-subagents.delta.yaml`, a seção Acceptance de `proposal.md` e ADR-0038, no modelo de ameaça aceito (ADR-0034, ADR-0037).

Verificações rodadas:

- `python -m pytest -q`: 2573 passed.
- `aifw claude check` neste repositório: `pass`, sem achados.
- Projeto temporário (`init` + `enable_project`), com o carimbo de `aifw-qa.md` trocado para `0.0.1`: o `check` acusa `subagent aifw-qa is not from aifw 0.4.1`, o `enable` seguinte devolve `agentBackups == ['.claude/agents/aifw-qa.md.bak']` e grava o `.bak`, e o `check` volta limpo. Esse caso de "versão antiga" do critério de aceitação não tem teste automatizado, mas funciona.
- Frontmatter conferido na documentação do Claude Code (code.claude.com/docs/en/sub-agents): `model`, `effort` (`low`/`medium`/`high`) e `tools` com `Skill` são campos e valores válidos.
- Empacotamento: `setup.py` copia `templates/` inteiro para `aifw/data`, então `templates/claude/agents/` entra no wheel.

### Achado 1 — `docs/routing.md` continua com o fluxo antigo (provado, severidade baixa)

- Arquivo: `docs/routing.md:15`, `:19-20` e `:40-41`.
- Cenário: quem segue o link "Consulte [Roteamento](routing.md)" da seção Modelos de `docs/claude-code.md` lê que a skill delega "entre subagentes (parâmetro `model` da ferramenta Agent)", que L2 é revisado por um "revisor independente opus" e, na tabela do avaliador, que PLANNED é executado por "sonnet" e revisado por "opus" e CRITICAL por "revisor independente e humano". A mudança diz o contrário: a skill delega por `subagent_type` sem `model` (REQ-SUBAGENTS-DELEGATION), a revisão tem duas etapas, `aifw-adversary` e depois `aifw-qa` (REQ-SUBAGENTS-REVIEW-FLOW, que é sonnet), e `PATH_RULE` em `python/aifw/assessment.py` nomeia os subagentes. O ADR-0038 diz que altera os ADR-0036 e ADR-0037 justamente nessas duas tabelas, e as mudanças desses dois ADRs atualizaram `docs/routing.md` (commits dd83463 e 75bcbcb). Esta mudança não o atualizou.
- Evidência: `grep -n "parâmetro \`model\`\|revisor independente" docs/routing.md` acha as linhas 15, 19, 20 e 41. `git diff main...HEAD -- docs/routing.md` sai vazio.
- Correção esperada: alinhar o parágrafo e as duas tabelas de `docs/routing.md` com a skill e com `PATH_RULE`.

### Ressalvas (sem prova de falha, não reprovam)

1. "Os revisores sem editar código" (REQ-SUBAGENTS-INSTALL) só vale por instrução. `aifw-adversary` e `aifw-qa` têm `Write` e `Bash`, que conseguem sobrescrever código, e o teste confere apenas que `Edit` não está na lista. Isso cabe no modelo de ameaça (erro do agente, guiado pela instrução), mas a garantia é menor do que o texto da spec sugere.
2. As duas definições mandam usar a skill `code-review`, cujo passo 4 lança dois sub-agentes em paralelo. Sem `Agent` em `tools`, o subagente não consegue lançar subagentes (documentação do Claude Code). Nesta rodada não havia ferramenta Agent, e os dois eixos foram feitos inline. A skill também espera um `docs/agents/issue-tracker.md`, que não existe no repositório. A revisão funciona assim, só que pior do que a skill descreve.
3. `.claude/skills/aifw-workflow/` está em `CONTROL` (`python/aifw/hooks.py:49`), mas `.claude/agents/aifw-*.md` não está. Assim, um agente pode alterar por engano o modelo ou as instruções do revisor sem que o hook peça confirmação. Mexer no hook está nos Non-goals, então fica só registrado.
4. `aifw claude check` só confere o carimbo da versão. Uma cópia editada que mantém o carimbo passa como atual. É o mesmo comportamento da skill, e a spec diz "ausente ou desatualizado".
5. `HOW_TO_USE.md:31` e `templates/claude/skills/aifw/SKILL.md:45` descrevem o que fica em `.claude/` como só o hook e a skill, sem os subagentes. As frases estão incompletas, não erradas.
6. O cenário "versão antiga" do `check` e do `.bak` não tem teste automatizado. Ele foi verificado só à mão, como descrito acima.

Resultado: reprovado
