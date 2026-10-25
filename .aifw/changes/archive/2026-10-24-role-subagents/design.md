# Design — Subagentes por papel

## Context

O Claude Code resolve o modelo de um subagente nesta ordem: parâmetro `model` da chamada, campo `model` da definição em `.claude/agents/<nome>.md`, `CLAUDE_CODE_SUBAGENT_MODEL` e, por fim, o modelo da sessão. O `aifw claude enable` já instala os hooks e a skill `aifw-workflow` do projeto; não instala subagentes. A revisão independente de L2/L3 hoje é um único subagente `opus` que escreve `independent-review.md` terminando em `Resultado:`; na agent-autonomy, revisões instruídas a achar qualquer falha entraram num ciclo sem fim (ADR-0037).

## Approach

- Templates em `templates/claude/agents/aifw-*.md` (frontmatter `name`, `description`, `model`, `effort` do papel, `tools`/`disallowedTools` e um prompt curto do papel). O `setup.py` já empacota `templates/`.
- Em `claude.py`, a instalação da skill vira uma função que copia um template com o carimbo de versão e guarda a cópia editada em `.bak`; `enable_project` a usa para a skill e para cada subagente, e devolve `agents` e `agentBackups`. `check_project` confere a presença e o carimbo de cada um.
- `assessment.PATH_RULE` cita o subagente de cada caminho, e a tabela da skill passa a dizer por nome quem planeja, executa e revisa. A delegação vai por `subagent_type` sem `model`; o `model` da chamada fica só para subir de modelo.
- Revisão em duas etapas, as duas sem Edit (Read, Grep, Glob, Bash, Skill e Write só para o arquivo da revisão):
  - `aifw-adversary` recebe o diff, a spec e os critérios, escreve a seção do adversário em `independent-review.md` e, com achado provado, termina em `Resultado: reprovado`. O gate `independent-review` já falha nessa linha, então nada muda no núcleo.
  - Sem achado provado, `aifw-qa` acrescenta a sua seção e a linha `Resultado:` final.
  - Na rodada seguinte, o arquivo anterior vai para `evidence/independent-review-<n>.md`, como já se fazia, e o adversário recebe só o diff desde a revisão anterior e os achados dela.

## Decisions

- Nomes com prefixo `aifw-`, para não sobrescrever os subagentes embutidos (Explore, Plan) nem os da pessoa.
- O carimbo `<!-- aifw-version -->` no fim do prompt, como na skill, para o `check` saber a versão.
- CRITICAL continua executado pelo Opus da sessão; só a revisão vai aos revisores.
- Dois agentes em vez de um: intenções opostas (quebrar e conferir) não se misturam num contexto, e o QA só gasta quando o adversário passa.
- Adversário em opus, QA em sonnet: achar o defeito que ninguém viu pede o modelo maior; conferir critérios contra evidência não.
- Esforço pelo peso do papel, com teto `high` (decisão da pessoa): revisores `high`, executor `medium`, rápido e explorador `low`.
- Ônus da prova e limite de rodadas contra o ciclo da agent-autonomy: só reprova o cenário concreto que falha, dentro da spec e do modelo de ameaça; sem cota de achados; no máximo duas rodadas de correção, e a terceira reprovação vai à pessoa.

## Risks and rollback

- Um projeto que já tenha um subagente com o mesmo nome: o `enable` guarda a versão anterior em `.md.bak`.
- O alias `opus` segue o modelo da sessão quando ela é da família Opus; com sessão Sonnet, o adversário roda no Opus padrão.
- O limite de rodadas é instrução da skill, não trava do hook: um agente pode ignorá-lo, o que a pessoa vê no histórico de `evidence/`.
- Rollback: apagar `.claude/agents/aifw-*.md` volta à delegação anterior, com `model` passado na chamada; reverter este PR tira a instalação do `enable` e o fluxo de duas etapas da skill.
