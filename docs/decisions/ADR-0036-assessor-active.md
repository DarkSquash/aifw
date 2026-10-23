# ADR-0036: modo ativo do avaliador de tarefas

- Status: superseded in part by ADR-0037 (avaliador sempre ativo, sem ativação)
- Date: 2026-10-22
- Impact: L3
- Change: `assessor-active`

## Contexto

O avaliador de tarefas (ADR-0023, ADR-0031) avalia cada pedido em modo sombra. O plano previa um modo ativo, ligado pela pessoa quando o critério fosse atingido: 50 pedidos com veredito, concordância de pelo menos 90% e nenhum CRITICAL rebaixado. Em 2026-10-22 havia 35 pedidos e 31 vereditos, com 94% de concordância, depois de o hook deixar de avaliar as mensagens automáticas da sessão (`9a1eddb`). A pessoa pediu o modo ativo implementado já, para ligar quando os 50 chegarem.

## Decisão

1. **Ativação humana:**
   - `aifw assess activate --feature tasks --by human:<nome>` só roda no terminal da pessoa (lista de aprovações) e só passa com o critério atingido;
   - ela grava `.aifw/assessor.yaml` (arquivo de controle) com quem, quando, o modelo e o retrato do relatório;
   - com `requireSignedCommit`, só vale num commit assinado;
   - fica presa ao modelo aprovado: trocar `spec.assessment.model` desliga o modo ativo até uma nova ativação;
   - o critério é o `criteriaMet` exato do relatório, não o valor arredondado da concordância.

   O plano original também pedia a suíte de avaliação aprovada. Ela foi substituída pelos vereditos da pessoa sobre pedidos reais, que são a evidência mais direta; `aifw assess eval --feature tasks` continua disponível para conferir uma troca de modelo.
2. **Caminho no pedido:** com a ativação válida e a avaliação ligada no `aifw.yaml`, o hook `UserPromptSubmit` avalia o pedido antes do agente, com o piso do diff, e entrega como contexto:
   - o caminho;
   - risco, importância e complexidade;
   - a regra do caminho.

   Se o serviço falhar, o contexto só avisa, e o agente segue a classificação de sempre.
3. **Delegação:** com o modo ativo, delegar a Haiku pede confirmação quando o último caminho da sessão for PLANNED ou CRITICAL. Os registros passam a guardar a sessão e o modo.
4. **Instalação:** `aifw claude enable` instala o hook de pedidos em primeiro plano (60 s, o bastante para as três tentativas do modelo) só com a ativação válida; no modo sombra ele continua em segundo plano. `aifw claude check` acusa quando a instalação não corresponde.
5. **Avisos:**
   - o início de sessão avisa quando o critério foi atingido e a ativação é possível, e quando o modo ativo está valendo;
   - o relatório mostra o estado.

As outras avaliações continuam em modo sombra.

## Consequências

- No modo ativo, cada pedido espera de 1 a 2 s pela avaliação, ou até 60 s se o serviço estiver lento. Qualquer falha vira um aviso ao agente, e um log ilegível só perde a regra de delegação, sem bloquear.
- O caminho orienta a delegação e a revisão. A aprovação humana em L3 e as regras do hook não dependem dele.
- Riscos residuais:
  - no início de uma tarefa nova não há diff, e o caminho vem só do modelo;
  - em projetos sem `requireSignedCommit`, a ativação vale só pelo arquivo, cuja edição pede confirmação;
  - avaliações feitas à mão com `aifw change assess` também entram no critério. Cada uma só conta com um veredito, que é aprovação humana;
  - apagar a ativação sem rodar `aifw claude enable` deixa o hook de pedidos em primeiro plano no modo sombra, e `aifw claude check` acusa.

## Rollback

Apagar `.aifw/assessor.yaml` e rodar `aifw claude enable`, ou `git revert` do commit da mudança.
