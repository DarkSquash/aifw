# Aprovação L3 — hook-indirect-code

O que a pessoa aprova ao rodar `aifw spec approve hook-indirect-code`:

- O hook passa a ler o código executado indiretamente: scripts, `source`, módulos de `python -m`, scripts do `package.json`, alvos do `Makefile`, módulos de `node -r`, configurações e variáveis que fazem o git ou outro programa executar código. O que ele não lê com segurança pede confirmação (ADR-0034).
- `.git/` e `.husky/` passam a ser arquivos de controle; editar `.venv/`, `node_modules/` e `.tox/` com as ferramentas de edição pede confirmação.
- O modelo de ameaças é o decidido no impasse `hook-indirect-code` (commits assinados `cb82caf` e `0e1e94c`). O hook protege contra erros do agente e caminhos óbvios e não é um sandbox. Os riscos residuais estão listados no ADR-0034 e no `threat-model.md`.

Evidência:
- `evidence/tests.txt`: 2386 testes passando.
- `evidence/red.txt`: 129 testes novos que falham no código anterior.
- `independent-review.md`: nona revisão independente, aprovado com ressalvas, com as rodadas anteriores em `evidence/independent-review-*.md`.
- `aifw validate --change hook-indirect-code`: todos os gates passam, exceto a aprovação humana.
