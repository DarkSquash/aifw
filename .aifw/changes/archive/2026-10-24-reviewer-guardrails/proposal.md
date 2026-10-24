# Proposal — Revisores sem alterar o projeto

## Intent

Resolver três ressalvas da revisão da `role-subagents` (ADR-0038):

1. "Revisor não edita código" era só instrução: `aifw-adversary` e `aifw-qa` têm `Write` e `Bash`.
2. `.claude/agents/aifw-*.md` não era arquivo de controle: um agente podia mudar o modelo ou as instruções de um revisor sem confirmação, ao contrário da skill `aifw-workflow`.
3. Os revisores mandavam usar a skill `code-review`, que lança dois subagentes, mas eles não têm a ferramenta `Agent`. Subagentes podem lançar subagentes quando têm `Agent`; liberá-la faria os subagentes aninhados rodarem no modelo da sessão e fora da trava do item 1.

## Scope

- O hook lê `agent_type`, que o Claude Code envia quando a chamada vem de um subagente. Para `aifw-adversary` e `aifw-qa`:
  - nega edição (Edit, Write, NotebookEdit) dentro do projeto, salvo o `independent-review.md` da mudança; arquivos fora do projeto, como experimentos numa pasta temporária, seguem as regras normais;
  - nega comando de shell que escreva arquivos, faça commit ou altere o repositório (`filesystem-write`, `commit`, `git-local`, `git-remote`, `install`, `publish`, `deploy`, `external-write`, `signing`, `destructive`); leitura, testes, `aifw` e código opaco seguem, para o adversário poder provar um achado.
- `.claude/agents/aifw-` entra na lista de arquivos de controle: editar uma definição do AIFW pede confirmação; o `aifw claude enable` continua instalando sem perguntar.
- Os eixos do `code-review` passam para as duas etapas: o `aifw-adversary` faz o eixo Spec (requisito faltando ou parcial, comportamento não pedido, implementação errada, citando a spec) e o `aifw-qa` faz o eixo Standards (padrões do repositório, `principle-catalogs/` e a lista de smells da skill). Cada um no próprio contexto, sem lançar subagentes; o adversário perde a ferramenta Skill.
- Skill `aifw-workflow`, `docs/claude-code.md`, CHANGELOG e ADR-0038 atualizados; `aifw claude enable` roda neste repositório.

## Non-goals

- Travar o agente principal ou o `aifw-executor`: as regras normais continuam valendo para eles.
- Ler o que o código opaco de um revisor faz: ele roda pela instrução, no modelo de ameaça aceito (ADR-0034, ADR-0037).
- Proteger outras definições em `.claude/agents/` que não sejam do AIFW.

## Acceptance

- Um `aifw-adversary` ou `aifw-qa` não consegue editar `python/aifw/claude.py`, rodar `sed -i`, `git commit` ou `git stash`, mas escreve o `independent-review.md` da mudança, um arquivo numa pasta temporária, e roda `pytest`, `git diff` e `aifw spec analyze`.
- As mesmas chamadas do agente principal ou do `aifw-executor` seguem as regras de antes.
- Editar `.claude/agents/aifw-qa.md` pede confirmação; `aifw claude enable` não.
- As definições dos revisores não citam a skill `code-review` como algo a executar, nem têm `Agent`; o adversário cobre o eixo Spec e o QA o eixo Standards.
- Suíte inteira passando e esta mudança revisada pelo fluxo de duas etapas.
