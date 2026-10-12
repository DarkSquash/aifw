# ADR-0015 — Aplicar permissões e impasses por hook do Claude Code

- Status: accepted
- Date: 2026-10-11
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

`authorize_action` e a máquina de impasse existiam só como funções testadas. Nenhum comando da CLI as chamava, então `.aifw/permissions.yaml` e o limite de tentativas não tinham efeito: o agente podia executar `git push` ou repetir correções sem que o AIFW soubesse.

## Decisão

1. `aifw-hook` é um hook PreToolUse do Claude Code. Ele traduz a ação (Bash/PowerShell, Edit/Write, WebFetch/WebSearch) em um pedido do AIFW e responde `deny` ou `ask`; sem objeção, não imprime nada e deixa as regras do próprio Claude Code decidirem.
2. `decide_action` aplica o arquivo `.aifw/permissions.yaml` sobre `authorize_action`, incluindo os valores `denied` e `localGit: human-approval`.
3. Leitura de serviço fora da allowlist pede confirmação em vez de negar, porque o hook não identifica serviços com precisão.
4. Comandos `aifw ... approve/decide/activate` sempre pedem confirmação humana, para que o agente não registre aprovação em nome do usuário.
5. Falha ao ler a política vira `ask`: a falha chega ao humano em vez de liberar a ação.
6. `aifw impasse open/attempt/status/review/decide/revalidate` persiste casos em `.aifw/impasses/`. Com caso `OPEN` ou `HUMAN_REVIEW`, o hook nega edições e comandos destrutivos e pede confirmação para outros comandos de shell; em `SUSPECTED` e `HALF_OPEN`, nega só comandos destrutivos.

## Consequências

- A classificação de shell é heurística e pode ser contornada por comandos ofuscados ou scripts; o hook reduz riscos, não substitui revisão.
- Cada ação coberta custa uma inicialização de Python (cerca de 0,3 s).
- Abrir casos e registrar tentativas continua dependendo do agente, orientado pela skill `aifw-workflow`.
- MCP tools e delegação a subagentes ainda não são classificados.

## Rollback

Remover a entrada `aifw-hook` de `.claude/settings.json` do projeto. Os checkpoints locais desta mudança foram descartados em 2026-10-11.
