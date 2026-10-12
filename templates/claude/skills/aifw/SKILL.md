---
name: aifw
description: Habilita o AIFW no projeto aberto. /aifw new para um projeto do zero; /aifw adopt para um projeto que já existe.
disable-model-invocation: true
argument-hint: "new | adopt"
---

# /aifw

Argumento: $ARGUMENTS

O AIFW é ativado por projeto, só quando o usuário pede. Trabalhe apenas na pasta do projeto aberto.

## Antes de tudo

1. `aifw --version` precisa funcionar. Se falhar, diga ao usuário para seguir a instalação no README do AIFW e pare.
2. Se a pasta não for um repositório git (`git rev-parse --is-inside-work-tree` falha), rode `git init` e avise o usuário. O AIFW usa o git para saber quais arquivos fazem parte do projeto; não faça commit nem configure remoto sem pedido.
3. Se a raiz já tiver `aifw.yaml`, não reinicialize: rode `aifw claude enable` (pode repetir sem efeito colateral), mostre `aifw intake status` e pare.
4. Numa única pergunta, confirme com o usuário:
   - id do projeto (proponha o nome da pasta em minúsculas, com hífens);
   - nome de exibição;
   - identidade para aprovações (`human:<nome>`).

## `new` — projeto do zero

1. `aifw init --id <id> --name "<nome>"`. Acrescente `--flutter`, `--web` ou `--python` só se o usuário já tiver dito a stack; caso contrário ela sai do intake.
2. `aifw claude enable`.
3. Conduza a entrevista do intake com a skill `grilling`, usando as perguntas de `aifw intake status --json` como ponto de partida. Grave cada resposta com `aifw intake set --field <campo> --value <valor>`.
4. Quando o intake estiver `ready`, mostre o Charter e peça aprovação. Aprovações só rodam no terminal da pessoa que aprova: o CLI recusa o shell do agente e pede que ela digite o id do projeto. Mostre o comando exato e peça para ela rodar `aifw intake approve --by human:<nome>`.

## `adopt` — projeto existente

1. Detecte a stack: `pubspec.yaml` → `--flutter`; `package.json` → `--web`; `pyproject.toml` → `--python`. Confirme na mesma pergunta do passo 4 acima.
2. `aifw init --id <id> --name "<nome>" --existing [stack]`.
3. `aifw claude enable`.
4. `aifw adopt analyze --write` e `aifw adopt apply`. Mostre o que foi descoberto: módulos, contratos, decisões e o que ainda é incerto. Aprovações só rodam no terminal da pessoa que aprova: o CLI recusa o shell do agente e pede que ela digite o id do projeto. Mostre o comando exato e peça para ela rodar `aifw adopt approve --by human:<nome>`.
5. Siga com o intake como no passo 3 de `new`.

## Sem argumento ou argumento desconhecido

Explique as duas opções em duas linhas e pare.

## Ao terminar

Diga ao usuário para abrir uma nova sessão do Claude Code neste projeto. A partir dela valem o hook de permissões e impasses (`.claude/settings.json`) e a skill `aifw-workflow` do projeto.
