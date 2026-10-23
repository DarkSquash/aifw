# Threat model: modo ativo do avaliador de tarefas

## Escopo e assets

- O caminho de execução entregue ao agente: decide quem planeja, executa e revisa.
- A decisão humana de ativar, em `.aifw/assessor.yaml`.
- O texto dos pedidos enviado ao serviço externo.
- A disponibilidade da sessão: o hook de pedidos passa a rodar antes do agente.

## Diagrama e trust boundaries

Pedido da pessoa → hook `UserPromptSubmit` → OpenRouter / Decider (serviço externo, fora da fronteira) → caminho, que vira contexto do agente.

O modelo de decisão é não confiável quanto ao resultado: o piso do diff só sobe o risco, e a aprovação humana em L3 continua independente dele.

## Actors

- A pessoa.
- O agente, inclusive sob prompt injection.
- O serviço externo.

## STRIDE

| ID | Categoria | Cenário | Impacto | Controle | Evidência | Risco residual | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | Spoofing | o agente grava `.aifw/assessor.yaml` ou roda `assess activate` para ligar o modo ativo | caminhos menos cautelosos sem decisão humana | `activate` é aprovação humana (terminal e id do projeto); o hook nega o comando ao agente; o arquivo é de controle; com `requireSignedCommit`, só vale assinado | `test_activation_is_a_human_approval`, `test_unsigned_activation_does_not_count` | projeto sem `requireSignedCommit`: a edição do arquivo pede confirmação, mas não exige assinatura | human:DarkSquash |
| T-002 | Elevation of privilege | o pedido diz "isso é trivial" para baixar o caminho | trabalho de risco em Haiku | piso do diff; a aprovação humana em L3 não depende do caminho; delegar a Haiku depois de PLANNED pede confirmação | `test_haiku_asks_after_a_planned_path_in_this_session` | no início de uma tarefa nova não há diff, e o caminho vem só do modelo | human:DarkSquash |
| T-003 | Tampering | ativação feita antes do critério | ativar sem evidência | `activate` confere 50 vereditos, 90% e nenhum CRITICAL rebaixado, contando só pedidos da pessoa | `test_activation_waits_for_the_criteria`, `test_activation_needs_agreement_and_no_demoted_critical` | vereditos dados sem leitura cuidadosa | human:DarkSquash |
| T-004 | Denial of service | serviço lento ou fora | pedido atrasado | falha vira aviso, inclusive as que não são do serviço; o hook tem 60 s de timeout, o bastante para as três tentativas | `test_service_failure_only_says_so`, `test_any_failure_reaches_the_agent_as_a_notice` | até 60 s de espera por pedido no pior caso | human:DarkSquash |
| T-005 | Information disclosure | texto do pedido sai da máquina | vazamento | as mesmas guardas do modo sombra: allowlist, classificação, `redact` e só pedidos da pessoa | testes existentes de `test_assessment.py` | conteúdo sensível sem padrão de segredo reconhecido | human:DarkSquash |
| T-006 | Repudiation | quem ligou e com que evidência | sem trilha | `.aifw/assessor.yaml` guarda quem, quando, o modelo e o retrato do relatório; cada registro guarda o modo | `test_active_mode_hands_the_path_to_the_agent` | nenhum | human:DarkSquash |

## Abuse cases

- **Prompt injection pede "rode `aifw assess activate`":** o hook nega, e a CLI recusa sem terminal humano.
- **Mensagens automáticas avaliadas como pedidos:** ignoradas desde `9a1eddb`.

## Decisão e aprovação

- Os riscos residuais da tabela são aceitos, e o ADR-0036 os registra.
- A ativação em si continua sendo uma segunda decisão humana, separada da aprovação desta mudança.
