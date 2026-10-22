# Proposal — Modo ativo do avaliador de tarefas

## Intent

O avaliador de tarefas (ADR-0023) roda em modo sombra: avalia cada pedido e só registra. O plano original previa um modo ativo, ligado pela pessoa quando o critério fosse atingido: 50 pedidos com veredito, concordância de 90% e nenhum CRITICAL rebaixado. Esta mudança implementa esse modo, para ser ligado quando o critério for atingido.

## Scope

- `aifw assess activate --feature tasks --by human:<nome>`: aprovação humana que só passa com o critério atingido e grava `.aifw/assessor.yaml`. Com `requireSignedCommit`, vale só num commit assinado.
- Com a ativação válida, o hook `UserPromptSubmit` avalia o pedido antes de o agente começar e entrega o caminho (FAST, WORK, PLANNED ou CRITICAL) como contexto, com o piso do diff.
- Se o serviço falhar, o contexto só avisa, e o agente segue a classificação de sempre.
- Delegar a Haiku pede confirmação quando o último caminho da sessão for PLANNED ou CRITICAL.
- `aifw claude enable` instala o hook de pedidos em primeiro plano só com a ativação válida.
- O relatório mostra se o modo ativo está valendo.
- O início de sessão avisa quando o critério foi atingido e a ativação ainda não foi feita.

## Non-goals

- Modo ativo para as outras avaliações (impasse, contexto, intake, rastreabilidade, decisões, juiz).
- Trocar o modelo da sessão automaticamente: o caminho orienta a delegação a subagentes, como a tabela de modelos já faz.
- Desligar a aprovação humana em L3, ou rebaixar um caminho pedido pela classificação.

## Acceptance

- `activate` recusa abaixo de 50 pedidos com veredito, abaixo de 90% de concordância ou com CRITICAL rebaixado, e recusa no shell do agente.
- Sem ativação, o hook de pedidos continua só registrando. Com ela, devolve o caminho, e uma falha do serviço vira aviso.
- Uma ativação sem commit assinado não vale quando `requireSignedCommit` está ligado.
- Desligar a avaliação no `aifw.yaml` também desliga o modo ativo.
- Delegar a Haiku pede confirmação depois de um caminho PLANNED ou CRITICAL na mesma sessão, e não em outra.
- `aifw claude enable` instala o hook síncrono só com a ativação válida, e `aifw claude check` acusa a diferença.
- A suíte completa passa.
