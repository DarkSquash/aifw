# ADR-0019 — Leitura real de comandos, aprovação no terminal humano e hook sem AIFW instalado

- Status: accepted
- Date: 2026-10-12
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

Depois do ADR-0018 restaram quatro limites:

- o hook procurava padrões no texto do comando, e por isso deixava passar `git -C . push` e acusava `grep "git push"`;
- a identidade de aprovação era só uma declaração (`human:<nome>`);
- um teste que falhava, mas terminava com `| tail` ou `; echo`, contava como verificação;
- quem clonasse um projeto habilitado sem o AIFW via todas as ações bloqueadas sem explicação.

## Decisão

1. `aifw.shell` lê o comando como um shell: respeita aspas, separadores, continuação de linha e redirecionamentos, passa por wrappers (`sudo`, `env`, `uv run`, `python -m`, `npx`), pula as opções globais do git e analisa o conteúdo de `bash -c`. `eval`, comandos codificados e texto enviado a um shell por pipe são opacos e pedem confirmação.
2. Os comandos de aprovação só rodam no terminal da pessoa que aprova:
   - o CLI recusa quando não há janela de console (Windows), quando falta `/dev/tty` (outros sistemas) ou quando `CLAUDECODE=1`;
   - a pessoa digita o id do projeto para confirmar;
   - o hook nega esses comandos no shell do agente.
3. Um teste cujo código de saída é escondido por `|`, `;`, `||` ou `&` posterior é registrado como inconclusivo (`ok: null`, `masked: true`) e não libera o hook Stop. `set -o pipefail` mantém o pipe válido.
4. Os hooks de projeto rodam no bash:
   - antes de cada ação, se o `aifw-hook` falhar ou não existir, bloqueia com instrução de instalação (saída 2);
   - no início da sessão, injeta a mesma instrução como contexto;
   - nos demais eventos, fica em silêncio.
5. As referências a arquivos TypeScript removidos nos documentos históricos apontam para os equivalentes Python. O gate `context-integrity` continua desligado até o fim das alterações no projeto.

## Consequências

- O que um script faz por dentro (`python publicar.py`) continua invisível para o hook.
- A presença humana é inferida pelo terminal; um agente que crie um pseudoterminal e remova `CLAUDECODE` ainda precisaria digitar o id, e o hook nega o comando de aprovação.
- Aprovar exige sair do chat: o agente mostra o comando e a pessoa o roda.
- No Windows, os hooks dependem do Git Bash, que vem com o Git.

## Rollback

Desfazer as mudanças listadas e rodar `aifw claude enable`.
