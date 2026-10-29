# ADR-0041: `enable` silencioso e status livre no plano aprovado

- Status: accepted
- Date: 2026-10-28
- Impact: L2
- Change: `quiet-enable-and-status`
- Amends: ADR-0038 (subagentes por papel), ADR-0039 (edição restrita ao plano aprovado)

## Contexto

O `aifw claude enable` criava `.bak` sempre que a cópia instalada diferia do conteúdo novo, mesmo sem edição da pessoa: toda atualização de versão deixava backups de arquivos intactos para apagar à mão. Já o `tasks.yaml` de uma mudança aprovada era arquivo de controle inteiro, e até marcar uma tarefa como concluída pedia confirmação.

## Decisão

1. A skill e os subagentes instalados terminam com o carimbo de versão e, depois dele, a linha `<!-- aifw-sha256: <hex> -->`, com o sha256 (UTF-8) do corpo do template sem a quebra de linha final.
2. Ao reinstalar, se a cópia existente difere do conteúdo novo, o `enable` confere o formato e o hash: corpo, carimbo, linha de hash e nada depois, com o sha256 do corpo igual ao gravado. Se bate, a cópia não foi editada e é trocada sem `.bak`. Caso contrário (editada, sem a linha de hash ou fora do formato), grava `.bak` como antes.
3. `aifw claude check` continua procurando só o carimbo da versão.
4. No `tasks.yaml` de uma mudança aprovada, a edição pelas ferramentas de edição que não muda os `paths` de nenhuma tarefa (trocar `status` ou título, por exemplo) deixa de pedir confirmação. Mudar `paths`, uma edição que o hook não consegue aplicar, um YAML ilegível e qualquer edição pelo shell continuam pedindo (ADR-0039).

## Consequências

- Atualizar a versão do AIFW não deixa `.bak` de cópia intacta; o `.bak` passa a significar "havia edição sua".
- Cópias instaladas antes deste ADR não têm hash: o primeiro `enable` cria `.bak` delas uma vez, e os seguintes não.
- O hash detecta edição acidental, não adulteração deliberada: quem editar corpo e hash juntos engana a verificação.
- Rollback: reverter a mudança; o `enable` volta a criar `.bak` sempre que o conteúdo difere.
