# Revisão independente: assessor-active, rodada 2

## Escopo

- Só as correções feitas depois da rodada 1 (`evidence/independent-review-1.md`), lidas no diff de diffs `review_active2.delta` (173 linhas) e conferidas no código atual de `python/aifw/assessment.py`, `hooks.py` e `claude.py`, no ADR-0036, no `threat-model.md`, no `design.md` e nos testes novos de `tests_python/test_assessor_active.py`.
- Skill `code-review`, eixos Standards e Spec feitos por mim, sem subagentes. Standards: catálogo de princípios e lista básica de smells. Spec: os achados da rodada 1 e o que o ADR passou a prometer.
- Não revisei de novo o restante do diff, já coberto pela rodada 1. Não chamei o serviço real nem a rede.

## Estado dos achados da rodada 1

| Achado | Estado | Evidência |
|---|---|---|
| M1, concordância arredondada | Corrigido | `activate` (`assessment.py:322-323`) passa a exigir `summary["criteriaMet"]`, calculado com o valor exato. O teste `test_agreement_below_ninety_percent_refuses_even_when_it_rounds_up` (188 de 209) passa. A comparação arredondada continua, mas só para montar a mensagem. A lógica do critério ainda está em dois lugares, o que é aceitável. |
| M2, avaliações manuais no critério | Risco residual declarado | `report()` não mudou. O ADR-0036, em Consequências, diz que `aifw change assess` entra no critério e que cada avaliação só conta com um veredito humano. O plano 4.4 fala em "50 pedidos reais", então isso é um desvio aceito, e não uma correção. |
| M3, ativação presa ao modelo | Corrigido | `activation()` (`assessment.py:295-296`) devolve `None` quando `entry["model"]` difere de `settings(root)["model"]`. Por isso, `active()`, o relatório, `claude check` e `enable` também seguem a troca. O teste `test_a_new_model_needs_a_new_activation` passa. Voltar ao modelo original reativa o modo ativo sem nova ativação. Isso é coerente, porque os vereditos valem para aquele modelo. |
| B1, falhas que não são `AifwError` | Corrigido | `user_prompt` faz `except Exception` e usa `type(error).__name__` quando a mensagem é vazia. `last_path` trata `OSError`/`ValueError` e devolve `None`. Os testes `test_any_failure_reaches_the_agent_as_a_notice` (`KeyError`) e `test_a_corrupted_log_does_not_make_every_delegation_ask` passam. Veja N2, sobre a mudança de comportamento com o log corrompido. |
| B2, timeout menor que o pior caso | Corrigido | `ACTIVE_PROMPT` passou a ter 60 s (`claude.py:44-45`). As três perguntas rodam em paralelo (`ThreadPoolExecutor(3)`), e o pior caso de `decide` é 3 × 15 + 1 + 2 = 48 s. Somando a partida do Python e o `git diff` do piso, a folga é de cerca de 10 s. O ADR, o design e o threat model dizem 60 s, e nenhum documento ainda fala em 30 s. O `urlopen(timeout=15)` vale por operação de socket, e não pela resposta inteira, então uma resposta muito lenta ainda pode passar disso. O teste de `enable` não confere o valor do timeout. |
| B3, hook síncrono sem modo ativo | Aceito como risco residual | O ADR passou a registrá-lo. Com 60 s, o hook síncrono no modo sombra tem o mesmo orçamento do assíncrono. |
| B4, docstrings | Parcial | A docstring do módulo foi corrigida. A de `enabled()` (`assessment.py:162`) ainda diz "shadow assessment", embora `enabled()` também valha no modo ativo. `SHADOW_LOG` manteve o nome, o que é uma escolha razoável para não mexer nos outros usos. |
| B5, lacunas nos testes | Corrigido | Há testes novos para a concordância abaixo de 90% sem CRITICAL, para a nova ativação ao trocar de modelo, para qualquer falha virar aviso, para o log corrompido e para o aviso "is active" no início de sessão. |
| I1, Haiku só pelo campo `model` | Não registrado | Ao contrário do que foi informado, o ADR-0036 não fala da heurística nem de `subagent_type` sem `model`. Também não há nada sobre isso em `design.md`, `threat-model.md` ou `proposal.md` (veja N1). O código usa `item.get("model") or agent_model(...)`, ou seja, o campo `model` ou a definição do agente em `.claude/agents/`, como diz `docs/claude-code.md:60`. Agentes embutidos sem definição local continuam fora da regra. |
| I2 | Sem mudança | Não se aplica. |
| I3 | Sem mudança | `docs/routing.md:55` continua sem a ressalva de `requireSignedCommit`. |
| I4 | Resolvido | O ADR agora explica por que a suíte de avaliação aprovada saiu do critério. |

## Achados novos

### Alta

Nenhum.

### Média

Nenhum.

### Baixa

**N1. O I1 foi declarado como registrado no ADR, mas não está lá.** É uma lacuna de documentação. A correção é uma linha nos riscos residuais do ADR-0036. Por exemplo: "a regra só reconhece Haiku pelo `model` do pedido ou da definição em `.claude/agents/`; agentes embutidos sem `model` não pedem confirmação".

**N2. O log corrompido mudou de falha segura para falha aberta, só na regra de delegação.** Antes, uma linha inválida em `shadow.jsonl` fazia toda delegação a Haiku pedir confirmação. Agora `last_path` devolve `None`, e a delegação passa sem pedir.
- O ADR assume isso ("um log ilegível só perde a regra de delegação"), e era o que a rodada 1 sugeria contra o falso positivo.
- Pelo código, a escrita do agente em `.aifw/assessments/` pede confirmação (`hooks.py:49`), então o agente não desliga a regra sozinho.
- Há uma pequena inconsistência: uma linha JSON válida que não seja objeto, como `[1, 2]`, gera `AttributeError` em `e.get`, fora do `except (OSError, ValueError)`. O `pre_tool_use` captura o erro e pede confirmação. Isso falha de forma segura, mas diferente da linha inválida. Verifiquei só lendo o código, porque o script não pôde rodar (veja Verificações).

### Standards

Não há violação dura. O `except Exception` tem `noqa` com justificativa, como o padrão do arquivo. A checagem dupla do critério em `activate` é um caso leve de Duplicated Code, por julgamento, e é aceitável porque a decisão final é a de `report()`.

## Verificações

- Suíte completa, na raiz: `python -m pytest -q -p no:cacheprovider tests_python` deu `2420 passed in 45.68s`. Na rodada 1 foram 2415; os 5 a mais são os testes novos.
- `tests_python/test_assessor_active.py`: 15 testes passaram, inclusive os 5 novos que cobrem M1, M3, B1 (dois casos) e B5.
- Leitura direta do código corrigido: `activation`, `activate`, `last_path`, `user_prompt`, `ACTIVE_PROMPT` e `entries_for`, e o fan-out paralelo em `assess`. Também conferi por grep que ADR, design, threat model, docs e skill não mencionam mais 30 s.
- **Limitação:** os scripts de verificação no scratchpad, que simulam `assessment.decide` e gravam vereditos em projetos temporários, foram negados pelo próprio hook do AIFW: "approvals must be run by the person approving, in their own terminal". Os scripts são `active_review2_probe.py`, `active_review2_probe_b.py` e `active_review2_probe_c.py`.
  - O motivo é `shell.inline_script` (`shell.py:584-586`), que marca como aprovação todo script cujo texto cita `aifw` junto com `activate`, `decide` ou `verdict`.
  - Não contornei a guarda. Por isso, a conferência de cada achado ficou nos testes do repositório, que rodam pelo pytest e passam, e na leitura do código.
  - Os casos que só seriam vistos pelo script ficaram sem execução: `RuntimeError()` sem mensagem, a linha não-objeto no log e o retorno ao modelo original.
  - A negação confirma de novo que o agente não consegue registrar vereditos nem ativar o modo ativo por script.

Resultado: aprovado com ressalvas
