# ADR-0044: Comando de barra não responde à aprovação

- Status: accepted
- Date: 2026-11-11
- Impact: L2
- Change: `post-review-cleanup`
- Amends: ADR-0037 (o que conta como resposta ao pedido de aprovação no chat)

## Contexto

Com um pedido de aprovação pendente (`aifw spec request-approval`), o hook `UserPromptSubmit` tratava toda mensagem da pessoa que não fosse automática como resposta ao plano. Um comando de barra (`/clear`, `/ponytail:ponytail ultra`) contava como "outra resposta" e cancelava o pedido, o que obrigava a pessoa a pedir o plano de novo. O comando é do harness, não uma resposta ao plano. O avaliador de tarefas já ignorava esses comandos (`is_request`).

## Decisão

1. Uma mensagem que começa com `/` é tratada como a mensagem automática: `user_prompt` não chama `record_chat_approval`. Ela não aprova, não cancela e não descongela a sessão. O pedido continua pendente, e um "sim" seguinte ainda aprova.
2. Uma resposta que começa com `/` ("/sim") não aprova. O contorno é digitar "sim".
3. Alternativa descartada: manter o cancelamento. O comando de barra não é decisão sobre o plano.

## Consequências

- Quem só digita comandos de barra fica bloqueado até responder ao plano. É o efeito aceito; o pedido e o congelamento só terminam com a resposta da pessoa.
- A mudança só reduz o que conta como resposta: nenhuma mensagem que antes não aprovava passa a aprovar, então não cria aprovação nova. Por isso é L2 e não há threat model.
- Rollback: reverter o commit da mudança. Não há migração; `approval.md` e o arquivo de pedido não mudam de formato.
