# Proposal — Subagentes por papel

## Intent

Hoje o modelo de cada subagente depende de o agente lembrar de passar `model` na ferramenta Agent; quando esquece, o subagente roda no modelo da sessão (Opus), mais caro e com o contexto inteiro. O `aifw claude enable` passa a instalar subagentes por papel com o modelo fixo na definição, e o avaliador e a skill delegam por nome. A revisão independente passa a ter duas etapas: um adversário que tenta provar que a mudança está errada e, se ele não conseguir, um QA que confere se ela está completa.

## Scope

- Cinco definições em `templates/claude/agents/`, instaladas em `.claude/agents/` pelo `aifw claude enable`, com o esforço de raciocínio pelo peso do papel, no máximo `high` (decisão da pessoa): planejar, revisar e papéis críticos `high`; executar, pesquisar e intermediários `medium`; FAST, busca e tarefas simples `low`:
  - `aifw-explorer`: haiku, `low`, só leitura (Read, Grep, Glob), busca no código;
  - `aifw-quick`: haiku, `low`, caminho FAST;
  - `aifw-executor`: sonnet, `medium`, caminho WORK e execução de plano do Opus (PLANNED);
  - `aifw-adversary`: opus, `high`, primeira etapa da revisão independente de L2/L3, sem editar código. O objetivo é provar que a mudança está errada; cada achado traz a entrada concreta que falha, de preferência um teste ou comando; sem prova é ressalva, não reprovação. O escopo é a spec, os critérios e o modelo de ameaça aceito (ADR-0034, ADR-0037), e não conseguir quebrar é um resultado válido;
  - `aifw-qa`: sonnet, `high`, segunda etapa, só quando o adversário não achou nada provado. Confere cada critério de aceitação contra a evidência, cenários e testes, suíte e gates, documentação e artefatos derivados (eixo Standards do `code-review`) e escreve o `Resultado:` final.
- Fluxo da revisão: achado provado do adversário para a revisão para correção; a rodada seguinte confere só as correções e o que elas podem ter quebrado, sem refazer a caça no código já revisado; ressalva sem prova não reabre rodada; no máximo duas rodadas de correção, e uma terceira reprovação para a revisão e leva o caso à pessoa (o mesmo limite do impasse em L2/L3).
- `aifw claude enable` guarda a cópia editada em `<nome>.md.bak` antes de substituir, como já faz com a skill; `aifw claude check` acusa subagente ausente ou desatualizado.
- O caminho entregue pelo avaliador nomeia o subagente (FAST → `aifw-quick`, WORK → `aifw-executor`, PLANNED → `aifw-executor`, depois `aifw-adversary` e `aifw-qa`, CRITICAL → Opus da sessão executa, depois `aifw-adversary` e `aifw-qa`).
- A tabela de modelos da skill `aifw-workflow` delega por `subagent_type`, sem passar `model`, para valer o modelo da definição; `model` só para subir. Ela ganha a coluna de esforço pelo mesmo critério, que vale também para agentes fora desses cinco (Workflow, Agent genérico, sessões).
- Documentação (`docs/claude-code.md`, README, CHANGELOG) e ADR-0038.

## Non-goals

- Mudar permissões, aprovações ou o que o hook pede: os hooks continuam valendo dentro dos subagentes.
- Trocar o modelo da sessão principal ou do Explore embutido.
- Configurar o modelo dos agentes do Workflow ou do `CLAUDE_CODE_SUBAGENT_MODEL`.
- Procurar caminhos para um agente malicioso forjar aprovações (fora do modelo de ameaça).

## Acceptance

- Num projeto habilitado, `aifw claude enable` cria os cinco arquivos com o modelo, o esforço do papel e as ferramentas do template; uma segunda execução não muda nada; uma cópia editada vai para `.md.bak`.
- `aifw claude check` acusa a falta ou a versão antiga de cada subagente, e passa depois do `enable`.
- O contexto do avaliador cita o subagente de cada caminho.
- A skill descreve as duas etapas da revisão, o ônus da prova e o limite de rodadas.
- Suíte inteira passando, `spec validate`/`analyze` limpos e esta própria mudança revisada pelo fluxo novo, com `Resultado:` aprovado.
