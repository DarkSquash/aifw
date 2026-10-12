# Changelog

## 0.4.0 — 2026-10-11

Claude Code passa a ser o host de referência, ativado por projeto, e a validação deixa de poder parecer verde sem evidência.

### Adicionado

- `aifw claude install|enable|check`, comando `/aifw new|adopt` e skill de projeto `aifw-workflow` (ADR-0014, ADR-0016).
- Hook `aifw-hook` para PreToolUse, PostToolUse, PostToolUseFailure, Stop e SessionStart (ADR-0015, ADR-0018):
  - aplica permissões, impasses, arquivos de controle, MCP, delegação a subagentes, `dataClassification` e break-glass;
  - registra a sessão em `.aifw/runs/`, bloqueia a conclusão com código não verificado e sugere abrir impasse após falhas repetidas;
  - informa intake, mudanças ativas e impasses ao abrir a sessão.
- `aifw validate --change <id> --write`, com artefatos exigidos por nível e relatório com digest; `spec archive` exige esse relatório atual (ADR-0017).
- `aifw impasse open|attempt|status|review|decide|revalidate`.
- `aifw waiver add|list`, `aifw break-glass grant|list`, `aifw intake set`, `aifw template list|copy`, `aifw runs show`, `aifw change classify --diff`.
- Receitas de gates aplicadas no `init` para os profiles Python, Web e Flutter (com detecção de FVM).
- `aifw doctor` informa a integração com o Claude Code quando roda num projeto.
- Leitura real de comandos de shell no hook (`aifw.shell`): aspas, separadores, wrappers, opções globais do git e `bash -c`; código ilegível pede confirmação (ADR-0019).

### Alterado

- `intake status` só é `complete` com o Charter aprovado e inalterado (`charterApproved`).
- A allowlist de serviços externos vem só de `aifw.yaml` (`spec.externalAllowlist`); `externalServices.allowlist` em `permissions.yaml` ficou obsoleta.
- Roteamento usa haiku/sonnet/opus; a policy volta a `recommendation-only` até nova avaliação.
- Gates com `python` ignoram o atalho da Microsoft Store e usam o interpretador do AIFW.
- Git passa a ser dependência obrigatória.
- Comandos de aprovação só rodam no terminal da pessoa que aprova, com o id do projeto digitado; o shell do agente é recusado (ADR-0019).
- Teste com saída escondida por `|`, `;`, `||` ou `&` não conta como verificação.
- Hooks de projeto rodam no bash e, sem o AIFW instalado, explicam como instalar em vez de falhar sem mensagem.
- Waivers, break-glass, Charter, `change.yaml`, registros de sessão e qualquer `.claude/settings*.json` passam a ser protegidos pelo hook (ADR-0020).
- O Stop compara o estado do git e só aceita o executor de testes de fato como verificação.
- O leitor de shell cobre `cmd /c`, `powershell -Command`, `Start-Process`, `xargs`, `python -c`, aliases do git, publicação, acesso remoto e instalação de pacotes.
- `aifw secrets scan` e gates `secret-scan` e `session-conformance` nos scaffolds; leitura de arquivos de segredo pede confirmação.
- Modo opcional `approvals.requireSignedCommit`: aprovações só valem em commit assinado.
- O leitor de shell analisa `$(...)`, crases e blocos `{ }`; programa vindo de variável, `Invoke-Command` e `.` pedem confirmação; `printenv`/`env`/`set` são leitura de segredo; `git commit -S` pede confirmação (ADR-0021).
- Menos confirmações sem reabrir brechas: blocos `{ }` têm o conteúdo analisado, `python -c`/`node -e` são lidos pelo que fazem, e escrita externa fora da allowlist pede confirmação em vez de ser negada (exceto dados `confidential`/`restricted`).
- `script -c` é analisado; `expect`, `unbuffer`, `socat`, `winpty` e `script` sem comando pedem confirmação, fechando aprovação por terminal falso no Linux.
- `uv sync` é liberado; `pip install`, `npm install` e `uv add` pedem confirmação.
- Allowlist casa por domínio, com `serviceDomains` editável; Grep e Glob passam pelo hook; `protectedPaths` no `permissions.yaml`.
- Modo de commit assinado cobre também adoção e decisões de impasse; uso de break-glass é registrado.
- O hook só carrega o validador de schemas para conteúdo ainda não validado (cerca de 300 ms em vez de 650 ms); `aifw claude enable` guarda backup de uma skill de projeto editada.
- Registros de sessão com mais de 30 dias são apagados; `aifw claude check` detecta o `/aifw` global desatualizado; schemas são carregados uma vez por processo.

### Removido

- Integração Pi (`extensions/aifw.ts`, `aifw-pi-bridge`, adapter) e Codex (templates e guia).
- `aifw handoff codex` e `aifw principle review`; a entrevista do intake usa a skill `grilling` e a revisão de princípios usa `code-review` (ADR-0013).
