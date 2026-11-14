# Proposal — Graphify por padrão no aifw claude enable

## Intent

A pessoa pediu "habilitar o graphify por padrão nos projetos com AIFW". A skill global do graphify já manda o Claude consultar `graphify-out/` quando ele existe; o que falta num projeto é o grafo existir e se manter atualizado. O `aifw claude enable` passa a providenciar isso quando o `graphify` está instalado, e não faz nada (além de uma linha informativa) quando não está.

## Scope

Quando `graphify` está no PATH, o `aifw claude enable`:

1. acrescenta `graphify-out/` ao `.gitignore` do projeto (o grafo gerado tem dezenas de MB e é local), salvo se a pasta `graphify-out/` já existir;
2. roda `graphify update .` uma vez, só se ainda não houver `graphify-out/graph.json` (extração por AST, sem modelo e sem custo);
3. roda `graphify hook install` (git hooks que refazem o grafo a cada commit, checkout, merge e rewrite), só se o projeto tiver `.git` e `core.hooksPath` não estiver definido.

Qualquer falha dessas etapas vira uma linha no resultado (`graphify`), nunca erro do `enable`. A opção `--no-graphify` pula tudo. Sem `graphify` no PATH, o `enable` faz exatamente o que fazia e acrescenta ao resultado a linha `graphify: not found on PATH: skipped`.

Também entram: ADR-0045 (rodar um executável de terceiros a partir do `enable`), testes, CHANGELOG, `docs/claude-code.md` e a referência gerada da CLI (nova opção).

## Non-goals

- `graphify claude install`: não roda (grava caminho absoluto da máquina em `.claude/settings.json`, que é versionado, e cria `CLAUDE.md`). A skill global já cobre a consulta.
- `aifw claude check` não relata o graphify: ele é opcional, e o `check` viraria "warning" para todo usuário sem a ferramenta.
- Instalar o graphify, atualizar a versão dele ou exigi-lo. Extração semântica (com modelo), `graphify extract`, `graphify watch`.
- Persistir a escolha de desligar (arquivo de configuração, variável de ambiente), desinstalar o que uma execução anterior instalou, ou tratar `core.hooksPath` com encadeamento próprio.
- Mudar o núcleo do hook (`hooks.py`, `shell.py`, `indirect.py`), a skill `aifw-workflow`, os subagentes ou os templates. Nenhuma cópia em `.claude/` é regenerada.
- Defesa contra burla intencional (ADR-0034, ADR-0037).

## Acceptance

- Sem `graphify` no PATH, `enable_project` devolve o mesmo resultado de antes mais a chave `graphify` com uma linha, não toca o `.gitignore` por causa do graphify, não roda subprocesso e não falha.
- Com `graphify` no PATH, num projeto git sem grafo e sem `core.hooksPath`: `.gitignore` ganha `graphify-out/`, `graphify update .` roda uma vez no diretório do projeto, depois `graphify hook install`; uma segunda execução não roda `update` de novo.
- Com `core.hooksPath` definido, sem `.git`, com `graphify-out/` já existente, ou com `--no-graphify`, a etapa correspondente é pulada e o `enable` termina com sucesso.
- Falha, tempo esgotado ou erro de execução do `graphify` não derrubam o `enable`; o resultado diz o que rodar à mão.
- `aifw claude check` devolve o mesmo resultado com e sem `graphify` no PATH.
- O hook não ganha regra para o graphify: `graphify query ...` e `graphify update .` não são negados nem pedem confirmação (verificado por teste).
- Teste manual com o `graphify` 0.9.107 real num clone descartável confirma grafo, hooks e `.gitignore`, a repetição sem efeito e `--no-graphify`.
- Suíte, lint, `aifw spec validate`/`analyze` e os dois revisores sem pendência.
