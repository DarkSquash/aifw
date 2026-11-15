# Proposal — Perfil de revisão pela natureza da mudança

## Intent

A cascata (ADR-0042) manda toda mudança L2/L3 por dois revisores, `aifw-adversary` e depois `aifw-qa`. Para mudança só de interface ou só de texto isso é demais. A pessoa pediu um perfil de revisão pela natureza da mudança: nesses dois casos, um revisor só (`aifw-qa`); todo o resto continua com os dois.

## Scope

1. Dois perfis leves, com o `aifw-qa` sozinho: `interface` (só estilo, layout ou componente visual, sem lógica, dados nem autenticação) e `texto` (só docs, mensagens e comentários que pessoas leem). O que não é um dos dois é o perfil `completo`, com os dois revisores.
2. Risco alto ou crítico fica sempre no perfil `completo`, qualquer que seja a natureza. L0 e L1 não mudam.
3. O agente principal declara o perfil no chat, antes de delegar, numa linha (`Perfil de revisão: completo | interface | texto`), e segue sem perguntar; a pessoa pode barrar se discordar. Não há aprovação do perfil: o perfil leve só vale em risco baixo ou médio, que não pede aprovação no chat. Na dúvida, `completo`.
4. No perfil leve, o `aifw-qa` confere primeiro se o diff cabe no perfil; se não couber, não escreve `Resultado:` e devolve ao agente principal, que chama o `aifw-adversary` e depois o `aifw-qa` de novo. O `aifw-qa` faz também o eixo Spec.
5. Em `interface`, o agente principal nomeia no brief do `aifw-qa` as skills de front end e pede checagem visual quando há como rodar a tela. Os templates não fixam nome de skill.
6. Texto: skill `aifw-workflow` e template `aifw-qa` (mais as cópias regeneradas em `.claude/`), uma frase no aviso do avaliador (caminhos PLANNED e CRITICAL com risco baixo ou médio), `docs/claude-code.md`, `docs/routing.md`, CHANGELOG, ADR-0046, delta de spec e testes das frases.

## Non-goals

- Código de classificação, campo novo em `change.yaml` ou no avaliador, regra por extensão de arquivo, opção ou configuração do perfil.
- Mudar o gate `independent-review`, o núcleo do hook (`hooks.py`, `shell.py`, `indirect.py`), as ferramentas dos revisores, o `aifw-adversary`, o planner, o lead, o executor e o senior (seus textos continuam verdadeiros).
- Defesa contra um orquestrador que declare o perfil leve de má-fé (ADR-0034, ADR-0037): o erro de classificação honesto é pego pelo `aifw-qa` depois que o diff existe.
- Checagem visual automatizada: o `aifw-qa` roda a tela só quando o brief diz como.

## Acceptance

- A skill instalada manda declarar `Perfil de revisão: completo|interface|texto` no chat antes de delegar, sem pedir aprovação, define `interface` e `texto`, manda chamar só o `aifw-qa` nesses dois com risco baixo ou médio e fixa `completo` na dúvida e com risco alto ou crítico.
- O `aifw-qa` instalado manda conferir o diff contra o perfil antes de tudo, devolver sem `Resultado:` quando não couber, fazer o eixo Spec e carregar as skills de front end que o brief nomear; as ferramentas dele não mudam (sem `Agent`, com `Skill`).
- O contexto do avaliador cita a exceção em PLANNED e CRITICAL com risco baixo ou médio, e não cita com risco alto ou crítico nem em FAST e WORK.
- Um `independent-review.md` só com a seção `## QA` e `Resultado: aprovado` passa o gate; sem a linha `Resultado:` falha.
- Nenhum template nomeia skill de front end.
- Suíte, lint, `aifw claude check`, `aifw spec validate`/`analyze` e os dois revisores (perfil `completo`, porque a mudança toca skill, subagente e código) sem pendência.
