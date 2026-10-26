# Proposal — Edição restrita ao plano aprovado

## Intent

Hoje o "sim" ao plano de uma mudança L2/L3 aprova a mudança, mas não limita o que o agente edita: os `paths` do `tasks.yaml` servem só à rastreabilidade. A pessoa pediu que, depois da aprovação, o agente mexa só nos arquivos do plano, e que o resto passe por ela.

## Scope

- Enquanto houver uma mudança ativa aprovada (com `approval` no `change.yaml`), editar pelas ferramentas de edição (Edit, Write, MultiEdit, NotebookEdit) um arquivo do projeto fora dos `paths` do `tasks.yaml` dessa mudança pede confirmação, com o motivo "fora do plano aprovado de <id>".
  - Um path casa com o arquivo exato, com tudo dentro de uma pasta (`docs/`, `tests_python`) ou com um padrão (`templates/claude/agents/*.md`).
  - Com mais de uma mudança aprovada ativa, vale a união dos paths.
  - A pasta da própria mudança (`.aifw/changes/active/<id>/`) fica sempre liberada: evidência, revisão e artefatos.
  - Arquivos fora do projeto, como experimentos numa pasta temporária, não entram na regra.
- O `tasks.yaml` de uma mudança aprovada vira arquivo de controle: o agente não amplia o plano sozinho. Para incluir um arquivo descoberto no caminho, ele edita o `tasks.yaml` (uma confirmação) e segue livre nesse arquivo.
- Nova opção `changeScope` no `permissions.yaml`: `ask` (padrão) ou `off`, para desligar por projeto sem mudar código.
- A skill `aifw-workflow` passa a pedir que o `tasks.yaml` liste, antes do pedido de aprovação, tudo o que a mudança vai tocar, inclusive testes, documentação e CHANGELOG.
- Testes, `docs/claude-code.md`, CHANGELOG e ADR-0039.

## Non-goals

- Comandos de shell que escrevem (`sed -i`, scripts, `cp`): o hook não sabe com segurança qual arquivo eles alteram. Ficam como hoje, pelo modelo de ameaça aceito (ADR-0034, ADR-0037).
- Mudanças L0/L1, sem aprovação: nada muda para elas.
- Comandos do `aifw` (`validate --write`, `spec archive`, `claude enable`), que gravam pelo próprio CLI.

## Acceptance

- Com uma mudança aprovada cujo `tasks.yaml` lista `python/aifw/claude.py` e `docs/`, editar `python/aifw/claude.py`, `docs/x.md` e `.aifw/changes/active/<id>/evidence/tests.txt` não pede; editar `python/aifw/hooks.py` pede, citando a mudança.
- Sem mudança aprovada ativa, ou com `changeScope: off`, a mesma edição de `python/aifw/hooks.py` não pede.
- Editar o `tasks.yaml` de uma mudança aprovada pede; o de uma mudança ainda não aprovada não pede.
- O padrão `templates/claude/agents/*.md` casa com `templates/claude/agents/aifw-qa.md`.
- Suíte inteira passando e revisão em duas etapas aprovada.
