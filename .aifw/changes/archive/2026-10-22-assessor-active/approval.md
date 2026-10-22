# Aprovação L3 — assessor-active

O que a pessoa aprova ao rodar `aifw spec approve assessor-active`:

- O comando `aifw assess activate`. É uma aprovação humana, só passa com o critério atingido e fica presa ao modelo aprovado. Ao rodar, grava `.aifw/assessor.yaml`, que só vale assinado.
- O modo ativo, depois dessa ativação:
  - cada pedido da pessoa chega ao agente com o caminho de execução;
  - delegar a Haiku depois de um caminho PLANNED ou CRITICAL pede confirmação;
  - qualquer falha vira só um aviso.
- `aifw claude enable` instala o hook de pedidos em primeiro plano só com a ativação válida.
- Os riscos residuais do ADR-0036 e do `threat-model.md`.

Aprovar esta mudança **não liga** o modo ativo. A ativação é uma segunda decisão, que a pessoa toma quando chegar aos 50 pedidos com veredito.

Evidência:
- `evidence/tests.txt`: 2420 testes passando.
- `evidence/red.txt`: os testes novos não rodam no código anterior, porque a funcionalidade não existia.
- `independent-review.md`: segunda revisão independente, aprovado com ressalvas, sem achados altos ou médios. A primeira está em `evidence/independent-review-1.md`.
