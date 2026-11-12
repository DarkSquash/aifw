# ADR-0045: Graphify por padrão no aifw claude enable

- Status: accepted
- Date: 2026-11-12
- Impact: L2 (risco alto)
- Change: `graphify-default`
- Amends: nenhum (relacionado: ADR-0034 e ADR-0037, modelo de ameaça)

## Contexto

A pessoa pediu para habilitar o graphify por padrão nos projetos com AIFW. A skill global do graphify já manda o Claude consultar `graphify-out/` quando a pasta existe; faltava o grafo existir e ficar atualizado. O repositório do AIFW é público e outros usuários podem não ter o graphify, então a mudança não pode alterar o `enable` de quem não o usa.

Há uma decisão de segurança: o `aifw claude enable` passa a EXECUTAR um programa de terceiros (`graphify`, resolvido pelo PATH, sem shell, dois subcomandos fixos, `cwd` na raiz do projeto, com tempo limite) e a gravar em `.git/hooks`, em `.git/config` e no `.gitattributes`. Essas escritas são feitas por um processo filho do `aifw` e não passam pelo hook do AIFW, que só vê o comando `aifw claude enable`.

## Decisão

1. O `enable` só age quando o `graphify` está no PATH, achado fora da raiz do projeto e por caminho absoluto; um `graphify` instalado dentro do projeto (p.ex. numa `.venv`) é pulado e a linha avisa. Sem ele, o resultado ganha a chave `graphify` com uma linha e nada mais muda.
2. Roda apenas `graphify update .` e `graphify hook install`. Ficam de fora `graphify extract`, `graphify watch`, `cluster-only` e `label` (usam modelo, custam ou deixam processo residente).
3. O `update` roda só quando não existe `graphify-out/graph.json`: o `enable` se repete a cada versão do AIFW, e os hooks de git já mantêm o grafo. Limite de 300 s; estourado, a linha diz o comando para rodar à mão.
4. `graphify claude install` não roda: gravaria o caminho absoluto da máquina em `.claude/settings.json` (versionado e usado pelo AIFW para reconhecer os próprios hooks), adicionaria mais hooks `PreToolUse`, criaria um `CLAUDE.md` que concorre com o bloco gerenciado por `aifw instructions` e deixaria `.graphify-bak`. A skill global já cobre a consulta.
5. `graphify-out/` entra no `.gitignore` (gerado, local, 17 MB no repositório do AIFW), salvo se a pasta já existir: nesse caso a decisão já foi da pessoa ou do projeto.
6. Hooks de git: `graphify hook install` acrescenta ao hook existente e é idempotente. É pulado, com nota, se `core.hooksPath` está definido (os hooks iriam para uma pasta versionada, com caminho da máquina) ou se não há `.git` (o graphify lança traceback). O `.gitattributes` versionado ganha a linha `graphify-out/graph.json merge=graphify` e o `.git/config` registra o merge driver.
7. Qualquer falha, tempo esgotado ou erro de execução vira uma linha com o comando a rodar à mão. Um `.gitignore` não gravável também vira uma linha (`add graphify-out/ yourself`). Nenhuma exceção sai do `enable`.
8. `aifw claude check` não relata o graphify: a ferramenta é opcional, e o `check` viraria aviso para todo usuário sem ela.
9. `--no-graphify` pula tudo. Vale só para aquela execução e não desfaz o que uma execução anterior instalou.
10. O núcleo do hook (`hooks.py`, `shell.py`, `indirect.py`) não muda. O hook hoje não devolve decisão para `graphify query` nem para `graphify update .`, com ou sem `opaqueCode`, medido por teste; não há lista de permissão nova para um programa de terceiros. Vale o modelo de ameaça dos ADR-0034 e ADR-0037: o hook protege contra engano do agente, e quem controla o PATH e põe um `graphify` falso já controla a máquina.

## Alternativas descartadas

- Uma linha no `CLAUDE.md` global da pessoa mandando rodar o graphify: não é por projeto, não instala hooks, depende de o agente lembrar, e esse arquivo está fora do repositório e do AIFW.
- Configurar por projeto à mão (`graphify hook install`, `.gitignore`, primeiro `update`): é o que ninguém quer repetir em cada projeto; o pedido foi fazer no produto.
- `graphify claude install`: pelos motivos da decisão 4.
- Exigir o graphify ou checar a versão: quebraria o `enable` de quem não o usa, e ninguém pediu a checagem.
- Opção persistente de desligar (`aifw.yaml`, `permissions.yaml`, variável de ambiente): superfície nova que ninguém pediu; `--no-graphify` é a menor forma e aparece na ajuda.
- Rodar o `update` em segundo plano: processo destacado no Windows sem garantia de sobreviver ao `aifw` e sem saída para relatar.
- Lista de permissão do graphify no hook: ampliaria o que o hook libera, sem necessidade, já que hoje ele não decide nada para esses comandos.

## Consequências

- A primeira execução é lenta (24 s no repositório do AIFW, até 300 s de limite).
- O `.gitattributes` versionado muda e aparece no `git status`.
- Rodar o `enable` de novo sem `--no-graphify` religa o graphify.
- `--no-graphify` não desfaz o que já foi instalado.
- Projetos com `core.hooksPath` ficam sem rebuild automático até a pessoa instalar os hooks por conta própria.
- O grafo é refeito em segundo plano a cada commit, checkout, merge e rewrite, o que consome CPU.
- Subagentes sem Bash (como o `aifw-explorer`) não consultam o grafo; só quem roda `graphify` pelo shell.
- Rollback: reverter o commit da mudança. Em projetos onde o `enable` novo já rodou: `graphify hook uninstall` (remove os quatro hooks, o driver e a linha do `.gitattributes`, preservando o resto), apagar `graphify-out/` e a linha do `.gitignore`. Não há migração; nenhum formato persistido do AIFW muda.
