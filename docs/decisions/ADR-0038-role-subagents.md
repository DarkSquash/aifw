# ADR-0038: subagentes por papel

- Status: accepted
- Date: 2026-10-24
- Impact: L2
- Change: `role-subagents`, `reviewer-guardrails`
- Amends: ADR-0036 e ADR-0037 (caminho do avaliador e tabela de modelos da skill)

## Contexto

O modelo de um subagente dependia de o agente lembrar de passar `model` na ferramenta Agent. Quando esquecia, o subagente rodava no modelo da sessão (Opus), com custo e contexto maiores do que o papel pedia; foi o que aconteceu com uma verificação de seis agentes na agent-autonomy. O Claude Code resolve o modelo nesta ordem: o `model` da chamada, o `model` da definição em `.claude/agents/`, `CLAUDE_CODE_SUBAGENT_MODEL` e o modelo da sessão.

A revisão independente de L2/L3 era um único revisor `opus`. Na agent-autonomy, revisões instruídas a achar qualquer falha entraram num ciclo em que cada rodada achava uma brecha nova (ADR-0037).

## Decisão

1. `aifw claude enable` instala cinco subagentes em `.claude/agents/`, com modelo e esforço na definição:

   | Subagente | Modelo | Esforço | Papel |
   | --- | --- | --- | --- |
   | `aifw-explorer` | haiku | low | busca só de leitura (Read, Grep, Glob) |
   | `aifw-quick` | haiku | low | caminho FAST |
   | `aifw-executor` | sonnet | medium | caminho WORK e planos do Opus |
   | `aifw-adversary` | opus | high | primeira etapa da revisão |
   | `aifw-qa` | sonnet | high | segunda etapa da revisão |

   Uma cópia editada vai para `<nome>.md.bak` antes da troca, como a skill; `aifw claude check` acusa subagente ausente ou desatualizado.
2. **Esforço pelo peso do papel, decidido pela pessoa:** planejar, revisar e papéis críticos `high`; executar, pesquisar e intermediários `medium`; FAST, busca e tarefas simples `low`. Nada acima de `high`. O mesmo critério vale para agentes fora desses papéis (Workflow, Agent genérico, outras sessões).
3. O caminho entregue pelo avaliador nomeia o subagente: FAST `aifw-quick`; WORK `aifw-executor`; PLANNED o Opus planeja, o `aifw-executor` executa, e `aifw-adversary` e depois `aifw-qa` revisam; CRITICAL o Opus planeja e executa, e os dois revisam.
4. A skill delega por `subagent_type` sem passar `model`, porque o parâmetro da chamada sobrepõe a definição; `model` fica só para subir de modelo.
5. **Revisão em duas etapas, proposta pela pessoa:**
   - O `aifw-adversary` tenta provar que a mudança está errada. Cada achado traz o cenário concreto que falha, de preferência um teste ou comando; sem prova é ressalva e não reprova. O escopo é a spec, os critérios e o modelo de ameaça aceito (ADR-0034, ADR-0037), sem cota de achados.
   - Com achado provado, a revisão para para correção. A rodada seguinte confere só as correções e o que elas podem ter quebrado, sem refazer a caça no código já revisado.
   - Sem achado provado, o `aifw-qa` confere critérios de aceitação, evidências, testes, gates e documentação e escreve o `Resultado:` que o gate `independent-review` lê.
   - Depois de duas rodadas de correção, uma terceira reprovação para a revisão e leva o caso à pessoa, o mesmo limite do impasse em L2/L3.
6. **Revisores sem alterar o projeto (mudança `reviewer-guardrails`):**
   - O hook lê o `agent_type` que o Claude Code envia nas chamadas de subagentes. Aos revisores `aifw-adversary` e `aifw-qa` nega editar arquivos do projeto além do `independent-review.md` da mudança e rodar comando que escreve, commita ou muda o repositório.
   - Leitura, testes, `aifw`, código opaco e arquivos fora do projeto seguem, para o adversário poder provar um achado com um experimento numa pasta temporária.
7. **As definições `.claude/agents/aifw-*.md` são arquivos de controle**, como a skill `aifw-workflow`: editá-las pede confirmação, e o `aifw claude enable` continua instalando sem perguntar.
8. **Os dois eixos do `code-review` são as duas etapas:** o adversário faz o eixo Spec e o QA o eixo Standards, cada um no próprio contexto. Nenhum tem a ferramenta `Agent`: subagentes aninhados rodariam no modelo da sessão e com outro `agent_type`, fora da trava do item 6.

## Consequências

- O trabalho delegado roda no modelo e no esforço do papel sem depender da memória do agente, e a busca no código sai do contexto da sessão.
- Os revisores não editam código; o QA só gasta quando o adversário passa.
- O limite de rodadas e o ônus da prova são instruções da skill e dos subagentes, não travas do hook. A proibição de editar, essa sim, é do hook; ela some se o Claude Code deixar de enviar `agent_type`, e o código opaco do revisor não é lido (ADR-0037). O histórico das rodadas fica em `evidence/independent-review-<n>.md`.
- O alias `opus` segue o modelo da sessão quando ela é da família Opus.
- Rollback: apagar `.claude/agents/aifw-*.md` volta à delegação com `model` na chamada; reverter a mudança tira a instalação do `enable` e o fluxo da skill.
