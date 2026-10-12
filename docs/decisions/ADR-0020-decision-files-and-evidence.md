# ADR-0020 — Arquivos de decisão protegidos, verificação pelo git e prova de aprovação

- Status: accepted
- Date: 2026-10-12
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

A segunda auditoria provou que o agente podia escrever direto os arquivos que guardam decisões humanas (waivers, break-glass, Charter, `change.yaml`), o registro de sessões e o `settings.json` global do Claude Code. Isso anulava a exigência de aprovar no terminal. Também mostrou que:

- `echo pytest` contava como teste;
- o Stop não via edições feitas por scripts;
- comandos indiretos (`cmd /c`, `xargs`, aliases), publicação e acesso remoto escapavam do leitor de shell;
- a regra de não expor segredos prometia um *secret scan* que não existia.

## Decisão

1. O hook pede confirmação para alterar `.aifw/charter.yaml`, `.aifw/waivers/`, `.aifw/break-glass/`, `.aifw/runs/`, qualquer `change.yaml` de mudança e qualquer `.claude/settings*.json`, inclusive fora do projeto. Leitura de `.env`, chaves e certificados também pede confirmação.
2. O Stop compara o conteúdo dos arquivos alterados segundo o git com o estado da última verificação bem-sucedida (ou do início da sessão). Só conta como verificação o executor de testes ou `aifw validate`, identificado pelo programa do comando.
3. O leitor de shell analisa `cmd /c` e `powershell -Command` até o fim da linha. Trata como opacos `python -c` e afins, `Start-Process`, `xargs` e subcomandos desconhecidos do git. Classifica publicação e acesso remoto como escrita externa e instalação de pacotes como leitura externa (`package-registry`).
4. `aifw secrets scan` e o gate `secret-scan` (hard, L1+) cumprem a evidência prometida pela regra `security.no-secret-output`.
5. Modo opcional `approvals.requireSignedCommit`: Charter, aprovação de spec, waivers e break-glass só valem num commit assinado e inalterado.
6. O gate de auditoria `session-conformance` usa `aifw runs show`. Registros de sessão com mais de 30 dias são apagados. `aifw claude check` detecta o `/aifw` global desatualizado. Os schemas são carregados uma vez por processo.

## Consequências

- Sem o modo de commit assinado, qualquer segredo que a pessoa consiga ler o agente também lê; a proteção dos arquivos depende de a pessoa negar a confirmação.
- Instalar pacotes, publicar e acessar servidores passa a pedir confirmação ou ser negado até entrar na allowlist.
- O Stop depende do git; sem ele, volta a olhar só as edições feitas pela ferramenta Edit.

## Rollback

Desfazer as mudanças listadas e rodar `aifw claude enable`.
