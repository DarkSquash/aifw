# Threat model: autonomia do agente

## Escopo e assets

- A aprovação de mudanças L2/L3 (`approval.md`, `change.yaml`).
- A branch padrão e o histórico remoto.
- Serviços externos e registros de pacotes.
- Segredos locais (`.env`, chaves, variáveis de ambiente).

## Diagrama e trust boundaries

Pessoa → Claude Code (`UserPromptSubmit`) → `aifw-hook` → arquivos da mudança. Agente → ferramentas → `aifw-hook` (`PreToolUse`) → shell, git, rede. Entradas não confiáveis: texto de ferramentas, páginas, arquivos e mensagens de subagentes ou de outras sessões.

## Actors

- A pessoa dona do projeto.
- O agente e seus subagentes.
- Conteúdo injetado por páginas, arquivos ou respostas de ferramentas.

## STRIDE

| ID | Categoria | Cenário | Impacto | Controle | Evidência | Risco residual | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-001 | Spoofing | O agente ou um subagente se passa pela pessoa e aprova a mudança: mensagem automática, `aifw-hook`/`python -m aifw.hooks` com um JSON forjado, `claude -p sim`, código que monta `UserPromptSubmit`, ou um "ok" em outra sessão | Mudança sem aval | Só o `UserPromptSubmit` grava; mensagens automáticas ignoradas; rodar o hook ou o `claude` pelo shell é negado; o pedido vale só na sessão que o fez | `test_the_agent_cannot_feed_the_hook_a_reply`, `test_a_reply_in_another_session_leaves_the_request_alone` | Código opaco que esconde a chamada (variáveis, `$(...)`) não é visto; o agente ainda pode pedir um "sim" com um plano enganoso | human:owner |
| T-002 | Tampering | O agente edita `approval.md`/`change.yaml` por engano | Aprovação errada | Edição direta, por padrão de shell (`chang?.yaml`) ou em outra árvore pede confirmação | `test_the_agent_requests_but_cannot_write_the_approval`, `test_patterns_naming_the_approval_ask`, `test_a_change_written_in_another_tree_asks` | Aceito pela pessoa (2026-10-23): um agente decidido a forjar a aprovação (cópia de pasta, `git merge`, código opaco) não é coberto; o hook protege contra erro, não é sandbox (ADR-0034) | human:owner |
| T-003 | Tampering | Push para a branch padrão disfarçado (`heads/main`, `+HEAD:main`, `refs/heads/*`, `--branches`, `-c remote.origin.push`, upstream na main, tag, `-fu`, API do GitHub) | Código não revisado na main | Parser de destinos e opções, branch padrão do remoto obrigatória, configuração lida antes do push sem destino, API do GitHub fora de discussão protegida | `test_work_branches_push_on_their_own`, `test_a_bare_push_that_lands_on_the_default_branch_asks` | Script opaco pode fazer push sem o hook ver (já aceito no ADR-0025) | human:owner |
| T-004 | Repudiation | Não saber quem aprovou | Auditoria fraca | `approval.md` cita a mensagem, quem e quando | `test_the_persons_reply_approves_the_plan_awaiting_it` | Sem assinatura, prova é o registro + histórico do chat | human:owner |
| T-005 | Information disclosure | Escrita livre para a allowlist vaza dados | Exfiltração | Só domínios que a pessoa incluiu; o agente pergunta antes de incluir; `restricted` nega | `test_writes_to_allowlisted_services_run_and_others_ask` | Um domínio incluído pode receber dados; a pessoa escolhe a lista | human:owner |
| T-006 | Information disclosure | Agente lê segredos por engano | Vazamento | Ler o conteúdo (Read, `cat`, `grep`, `git diff`, `printenv`) é negado sem confirmação; só citar o arquivo pede | `test_secrets_are_never_read`, `test_naming_a_secret_file_asks` | Leitura por script opaco não é vista | human:owner |
| T-007 | Elevation of privilege | Publicação de pacote passa pela allowlist | Pacote público indevido | `publish` (npm, twine, uv, poetry, dotnet nuget, vsce, gh release...) sempre pede, nega com confidential/restricted | `test_publishing_asks_even_with_the_registry_allowlisted` | — | human:owner |
| T-008 | Denial of service | Hook de pedidos síncrono atrasa cada mensagem | Latência | Timeout de 60 s; falha vira aviso | `test_any_failure_reaches_the_agent_as_a_notice` | Até 60 s num serviço fora | human:owner |

## Abuse cases

- Injeção em página/arquivo pedindo ao agente para "aprovar": o agente não tem como gravar a aprovação; só a mensagem da pessoa conta.
- Resposta da pessoa que é uma pergunta ("pode me explicar?"): não aprova e cancela o pedido.
- Dois planos pendentes e um "sim": nenhum é aprovado.

## Decisão e aprovação

Riscos residuais aceitos pela pessoa ao revisar a lista de aprovações (ADR-0037). A aprovação desta mudança é a resposta dela ao plano no chat.
