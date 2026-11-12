# Design — Limpeza pós-revisão

## Context

`user_prompt` chama `record_chat_approval` para toda mensagem que não casa com `AUTOMATIC_PROMPT`. Uma mensagem que começa com `/` (comando de barra) passa por esse filtro, é tratada como "outra resposta" e cancela o pedido de aprovação pendente. O avaliador (`is_request`) já ignora esses comandos. O resto da mudança é manutenção sem efeito de comportamento: comentários, um diretório sem uso, três ressalvas de revisão e uma lista repetida.

## Approach

- **Item 1 (sessão principal, núcleo do hook).** Em `hooks.py`, `if not AUTOMATIC_PROMPT.match(prompt)` vira `if not (prompt.startswith("/") or AUTOMATIC_PROMPT.match(prompt))`, com o comentário existente ajustado. `prompt` já vem com `strip()`. Sem função nova. Teste em `tests_python/test_agent_autonomy.py`, ao lado dos testes de aprovação no chat (`say`, `requested`, `change`): com o pedido pendente, `say(change, "/ponytail:ponytail ultra")` não aprova, o arquivo de pedido continua e um "sim" seguinte aprova. O teste é escrito primeiro e falha sem a correção.
- **Item 2 (sessão principal).** Dois comentários reescritos para `shortcut: <limite>, <quando atualizar>`. O de `hooks.py` diz para revisitar quando um comando real precisar de padrão recursivo no topo, com busca limitada; o de `indirect.py`, quando um pacote local puder ser carregado por nome (`NODE_PATH`, workspace).
- **Item 3 (worker).** `git rm -r .aifw/legacy` e reescrever a frase de `docs/python-migration.md` sem apontar para o diretório (o código TypeScript original fica no histórico do git; a evidência da migração segue em `python-cli-core`). Depois: `aifw map check`, `aifw context check` e a suíte.
- **Item 4a, ADR e CHANGELOG (worker).** `docs/claude-code.md`: no parágrafo do limite de aninhamento, acrescentar que nas versões 2.1.217 e 2.1.218 o padrão era 1 e que o `check` só avisa com a variável definida; na tabela do UserPromptSubmit e em Aprovações, citar o comando de barra junto das mensagens automáticas. ADR-0044 curto (contexto, decisão, consequência) e linha no CHANGELOG.
- **Itens 4b e 4c (worker).** Só testes: troca da asserção; `edit` manda só `notebook_path` para `NotebookEdit`. Cada um é conferido quebrando a condição em uma cópia temporária (remover o trecho do plano B do texto lido; tirar `notebook_path` do hook), nunca no arquivo do projeto.
- **Item 4e (worker).** `FEATURES` passa a morar em `common.py`; `assessment.py` e `cli.py` importam de lá e `cli.py` usa `choices=FEATURES` nos três lugares. Importar de `assessment` no topo de `cli.py` carregaria `urllib.request` e `concurrent.futures` em todo comando (cerca de 130 ms a mais, medido na revisão). `aifw assess report --help` e `docs/cli-reference.generated.md` conferidos antes e depois.
- Os `paths` do `tasks.yaml` cobrem tudo o que será tocado. Em `.claude/` só muda a cópia de `skills/aifw-workflow/SKILL.md`, regenerada por `aifw claude enable` depois que o template ganhou a frase do comando de barra (ressalva da revisão adversária).

## Decisions

- O comando de barra é tratado como a mensagem automática: não aprova e não cancela. Descartado: manter o cancelamento atual; o comando de barra é do harness, não é resposta ao plano.
- O pedido permanece e a sessão continua congelada até a pessoa responder ao plano, como já acontece com a mensagem automática (o congelamento depende do arquivo de pedido). Efeito aceito: quem só digita comandos de barra segue bloqueado até responder.
- Uma resposta que começa com `/` ("/sim") não aprova; o contorno é digitar "sim".
- ADR-0044 curto, porque muda o que o ADR-0037 diz que conta como resposta. É L2: sem threat model.
- Item 4d fora: o código saiu no ADR-0037.
- O schema do manifesto, que repete a lista de recursos, não muda.

## Risks and rollback

- A aprovação no chat é governança. O `/` só reduz o que conta como resposta, nunca amplia, então não cria aprovação nova; o efeito colateral é um pedido pendente que sobrevive a um comando de barra. Os testes existentes de aprovação cobrem as regressões.
- Apagar `.aifw/legacy/` é irreversível só na árvore de trabalho: o conteúdo segue no histórico do git, e o código nunca esteve na distribuição.
- Comentários, testes e a lista de `choices` não têm efeito em execução.
- Rollback: reverter o commit da branch, ou `git checkout <base> -- .aifw/legacy` para só o diretório. Sem migração nem dado persistido; `approval.md` e pedidos gravados não mudam de formato.
