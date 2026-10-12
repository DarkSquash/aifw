# ADR-0018 — Fechamento da auditoria de 2026-10-11

- Status: accepted
- Date: 2026-10-11
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

A auditoria encontrou brechas no hook, funções sem comando, gates sem comando no scaffold, uma allowlist duplicada, uma `dataClassification` sem efeito e uma conformidade medida só em fixtures. O ADR-0017 tratou validação, archive e Charter; este trata o restante.

## Decisão

1. Git é dependência obrigatória: `/aifw` roda `git init` quando falta, e a lista de arquivos do projeto respeita o `.gitignore`.
2. O `init` aplica a receita de gates do profile (Python, Web, Flutter com detecção de FVM).
3. O hook de projeto cobre PreToolUse (com `onFailure: block`), PostToolUse (em segundo plano), PostToolUseFailure, Stop e SessionStart.
   - PreToolUse passa a considerar MCP (`mcpServers.deny/ask`), delegação para `haiku` com mudança L2/L3 ativa, `dataClassification` e break-glass.
   - PostToolUse e PostToolUseFailure gravam a sessão em `.aifw/runs/`, ignorada pelo git, e sugerem abrir impasse após falhas repetidas do mesmo teste.
   - Stop impede concluir com código alterado depois da última verificação bem-sucedida.
   - SessionStart informa o estado do projeto.
4. A allowlist vem só de `spec.externalAllowlist` em `aifw.yaml`.
5. Novos comandos: `intake set`, `waiver add/list`, `break-glass grant/list`, `template list/copy`, `runs show`, `change classify --diff`, `claude check`. `doctor` mostra a integração com o Claude.
6. Gates com `python` não usam o atalho da Microsoft Store.
7. A versão passa a 0.4.0, com CHANGELOG e nota de migração.

## Consequências

- Quem clonar um projeto habilitado precisa do AIFW instalado: o PreToolUse bloqueia se o hook não rodar.
- A classificação de shell continua heurística, e a aprovação humana continua sendo um identificador declarado; o hook reduz riscos, mas não substitui revisão.
- `aifw runs show` mede comportamento real, mas só o que passa pelas ferramentas registradas.
- Sem commits, todo o projeto conta como alterado para `change classify --diff`.

## Rollback

Desfazer as mudanças listadas, voltar a versão para 0.3.0 e rodar `aifw claude enable`, `aifw resolve build` e `aifw map build`.
