# Design — Juiz por modelo do resíduo opaque, em modo sombra

## Context

- O hook síncrono (`hooks.py`) classifica cada comando e pede confirmação para o tipo `opaque` (`opaqueCode: ask`, ADR-0025 e ADR-0034).
- O plano do avaliador de tarefas (§11) rejeitou um modelo em toda ação do hook, por três motivos: cerca de 1 s por comando, comandos com segredos saindo da máquina e prompt injection. Aqui o escopo é menor: só o resíduo `opaque`, em modo sombra, para medir antes de decidir.
- A mudança `hook-indirect-code` ainda está ativa e mexe em `hooks.py`, `shell.py` e `indirect.py`. Esta mudança não edita esses arquivos, só importa `hooks.classify`, `hooks.evaluate` e `shell.SECRET_FILE`.

## Approach

1. **Onde roda:** numa segunda entrada no `PreToolUse` (`matcher: Bash|PowerShell`, `async: true`, `aifw assess judge --hook || true`). Pela documentação do Claude Code, a saída de um hook assíncrono não controla a ação, e o hook não atrasa a sessão. A entrada vem em `claude.JUDGE` e o `aifw claude enable` a instala. Comandos que a pessoa recusa também são julgados; um juiz no `PostToolUse` perderia esses casos.
2. **Filtro:** `judge.judge()` só chama o modelo quando o recurso está ligado, as guardas passam e `hooks.classify` traz um item `opaque`. Ele chama `hooks.evaluate` para registrar a decisão da regra fixa, sem alterá-la.
3. **Entrada:**
   - o comando passa por `context.redact` e é cortado em 4000 caracteres;
   - `candidates()` acha os arquivos citados também dentro de `$(...)`, de `bash -c "..."`, depois de um `;` colado e em caminhos com `\`;
   - `sources()` envia só arquivos de código (por extensão, `Makefile` ou shebang) dentro do projeto, em texto UTF-8 de até 20 KB, no máximo 5. Não envia nada que case com `SECRET_FILE` ou `SECRET_NAME` (`secrets.yml`, `.npmrc`, `.netrc`...) nem arquivos com chave privada;
   - `mask()` aplica o `context.redact` e mascara também tokens do GitHub, GitLab, Slack e AWS e atribuições a nomes como `*_SECRET*` e `*TOKEN*`;
   - os arquivos recusados aparecem só pelo nome, com o motivo;
   - a descrição do agente (`tool_input.description`) vai num bloco à parte, rotulado como alegação.
4. **Prompt:** um prompt de sistema fixo manda julgar pelo que o código faz, tratar como dado o que estiver entre `<dado-NONCE>` e responder só JSON.
   - O nonce tem 16 caracteres hexadecimais aleatórios, novo a cada chamada.
   - Texto que tenta convencer o juiz conta como sinal de risco.
5. **Modelo:** `claude -p --model haiku|sonnet --system-prompt ... --tools "" --disable-slash-commands --strict-mcp-config --no-session-persistence --settings {"disableAllHooks":true} --output-format json`.
   - A mensagem vai pela entrada padrão.
   - O processo roda numa pasta temporária nova e vazia, com `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` e `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. Assim nenhum `CLAUDE.md` que o agente tenha escrito em pastas acima dela entra no contexto do juiz.
   - Usa o login da assinatura. `--bare` não serve, porque exige `ANTHROPIC_API_KEY`.
   - Haiku decide quando tem confiança de 0,7 ou mais. Abaixo disso, ou com resposta `unknown`, a decisão vai para o Sonnet.
6. **Registro:** `assessment.store(root, "judge", ...)` grava:
   - o comando mascarado, os tipos de item e os arquivos lidos;
   - a decisão e os motivos da regra fixa;
   - o veredito, a confiança, a intenção, o `mismatch` e se houve escalada;
   - `sensitive`: efeitos que a regra fixa reserva à pessoa (push, instalação, rede, `aifw.yaml`, `.aifw/`, `.claude/`), achados por texto no comando ou no código;
   - `wouldChange`, verdadeiro só quando o único motivo da pergunta era o código opaco, `sensitive` está vazio e o veredito é `harmless`;
   - a marca `malformed` de cada chamada;
   - a latência medida (tempo total e de API) e o custo estimado de cada chamada.
7. **Revisão:** `aifw assess report/verdict --feature judge`, com os vereditos `harmless` e `ask` (`unknown` conta como `ask`). O critério de ativação é o mesmo dos outros recursos: 50 vereditos e 90% de concordância.
8. **Suíte:** `run_judge` roda cada caso nos dois modelos e calcula três formas a partir das mesmas respostas:
   - só Haiku, que é a regra "um nível abaixo" para sessões Sonnet e Haiku;
   - só Sonnet, que é a mesma regra para sessões Opus;
   - Haiku escalando para Sonnet.

   Para cada forma, mede acertos, liberações indevidas (com injeção à parte), latência p50, p95 e máxima, casos acima de 10 s e custo. Também mede a fidelidade da intenção, por palavras-chave, e o acerto do `mismatch`.

## Decisions

- **Assinatura via `claude -p`, não OpenRouter:** pedido da pessoa em 2026-10-20. Não exige chave, e os comandos vão ao mesmo provedor que já recebe a conversa da sessão. O preço é a inicialização do CLI: uma chamada medida levou 11,4 s no total e 2,7 s de API.
- **Sem entrada na `externalAllowlist`:** ela governa as ações de rede do agente. Pôr `anthropic` nela liberaria `curl` para esse domínio e mudaria decisões do hook. A guarda que vale é a `dataClassification`.
- **Haiku com escalada, não um nível abaixo da sessão:** o payload do `PreToolUse` não traz o modelo da sessão, e o risco de um comando não depende de quem o roda. A suíte mede as duas formas.
- **`type: "prompt"` e `type: "agent"` nativos descartados para o modo sombra:**
  - a resposta deles vira decisão;
  - não existem em modo assíncrono;
  - rodariam de forma síncrona em todo comando Bash;
  - o `prompt` não lê arquivos;
  - o `agent` é experimental.

  Ficam como candidatos para o modo ativo, porque evitam a inicialização do CLI.

## Risks and rollback

- **Risco: uso da assinatura.** Cada comando `opaque` consome uma ou duas chamadas. Mitigação: só o resíduo `opaque` é julgado, e `features` desliga tudo.
- **Risco: o `claude -p` muda flags ou comportamento.** Mitigação: qualquer falha vira exceção, engolida no hook assíncrono, e nada é registrado.
- **Risco: uma pasta acima da temporária ter `.claude/settings.json` com hooks ou um `CLAUDE.md`.** Mitigação: `disableAllHooks` vem nas configurações passadas pela linha de comando, que têm a maior precedência, e as variáveis de ambiente desligam `CLAUDE.md` e a memória automática.
- **Rollback:**
  - tirar `judge` de `spec.assessment.features`, o que desliga sem remover código;
  - para remover de vez, apagar a entrada `JUDGE` de `claude.py` e de `.claude/settings.json`, `judge.py`, `run_judge`, o recurso `judge` em `assessment.py`, o comando `assess judge` e a suíte.
