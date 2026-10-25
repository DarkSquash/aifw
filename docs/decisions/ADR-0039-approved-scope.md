# ADR-0039: edição restrita ao plano aprovado

- Status: accepted
- Date: 2026-10-25
- Impact: L2
- Change: `approved-scope`
- Amends: ADR-0037 (aprovação de L2/L3 pelo chat)

## Contexto

Desde o ADR-0037, o "sim" da pessoa ao plano de uma mudança L2/L3 aprova a mudança inteira, mas não limita o que o agente edita: os `paths` do `tasks.yaml` serviam só à rastreabilidade. A pessoa perguntou se a aprovação dava permissão sobre todos os arquivos do projeto e pediu que o agente ficasse nos arquivos do plano.

## Decisão

1. Enquanto houver uma mudança ativa com `approval` no `change.yaml`, editar pelas ferramentas de edição (Edit, Write, MultiEdit, NotebookEdit) um arquivo do projeto fora dos `paths` do `tasks.yaml` dela pede confirmação, com o motivo e o id da mudança. Com mais de uma aprovada, vale a união dos paths.
2. Um path casa com o arquivo exato, com tudo dentro de uma pasta ou com um padrão (`fnmatch`). A pasta `.aifw/changes/active/` fica livre, porque guarda os artefatos das mudanças; arquivos fora do projeto não entram na regra.
3. O `tasks.yaml` de uma mudança aprovada é arquivo de controle: ampliar o plano custa uma confirmação, e depois o agente segue livre no arquivo incluído.
4. `changeScope` no `permissions.yaml`: `ask` (padrão) ou `off`.
5. A skill pede que o `tasks.yaml` liste, antes do pedido de aprovação, tudo o que a mudança vai tocar.

## Consequências

- O que o agente edita numa mudança aprovada é o que a pessoa viu no plano, ou o que ela confirmou depois.
- Comandos de shell que escrevem (`sed -i`, scripts, `cp`) ficam fora da regra, porque o hook não sabe com segurança o arquivo alterado. É a fronteira do ADR-0037: o hook protege contra erro do agente, não contra um agente decidido a contornar a regra.
- Um `change.yaml` ou `tasks.yaml` ilegível deixa aquela mudança fora da regra, sem travar o hook.
- Rollback: `changeScope: off`, ou reverter a mudança.
