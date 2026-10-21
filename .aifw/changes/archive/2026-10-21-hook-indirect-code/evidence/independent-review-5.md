# Revisão independente (rodada 5) — hook-indirect-code

## Escopo

- Só as correções feitas depois da quarta revisão: `scratchpad/review5.diff` (95 linhas):
  - `indirect.py`: `env` fora de `INSTALLED_TOOLS`, isenção de `activate` no `source`, expansão de `~` e `$HOME` no `source`, `.DEFAULT_GOAL`, superconjunto quando o pré-requisito usa função, `folder` na chave do memo do make, remoção de `MAKE_BUILTINS` e `MAKE_ASSIGNMENT` aceitando nomes com ponto;
  - `shell.py`: `gradle`/`gradlew` `publish` e `mvn`/`mvnw` `deploy` em `PUBLISH`.
- Docs conferidos: ADR-0034 (itens 4, 12, 13 e residuais) e CHANGELOG. Os testes novos de `test_indirect_code.py` (linhas 500-540) foram lidos, não revisados a fundo.
- Referência: `evidence/independent-review-4.md`.
- Método: skill `code-review`, com os eixos Standards e Spec feitos por mim, sem subagentes.
- Critério: o modelo decidido no impasse. Reprova só uma regressão de severidade alta, seguida sem intenção de burlar e fora dos residuais declarados, ou um caminho que trave o hook.
- Análise estática, só com `aifw.shell.analyze` e `aifw.hooks.handle`. Nada classificado foi executado. Sem rede, push nem instalação. O único arquivo do repositório alterado é este relatório.

## Estado dos achados da quarta revisão

Nos fixtures, o script ou alvo perigoso faz `git push origin main`. Rótulos medidos via `handle` num projeto criado por `test_workflows.init`.

| Item | Medido agora | Estado |
| --- | --- | --- |
| N-M1 `env` em qualquer componente | `bash infra/env/deploy.sh`, `source infra/env/deploy.sh`, `./config/env/prod.sh`, `bash env/deploy.sh` → git-remote, ask | Corrigido. A isenção nova de `activate` é larga demais (R5-B1). `venv` continua casando qualquer componente (`bash infra/venv/deploy.sh` → read-only) e Write em `venv/` não pergunta, mas isso já existia na rodada 3 e não foi tocado |
| N-M2 `.DEFAULT_GOAL` | `.DEFAULT_GOAL := release`, por variável e com `+=` → git-remote | Corrigido para as formas comuns. Falha aberta em formas raras (R5-B2) |
| N-M2 pré-requisito por função | `release: $(addprefix publish-,$(PKGS))` e `${addprefix ...}` → git-remote; `$(wildcard ...)` → superconjunto | Parcial. A função dentro de uma variável não é vista (R5-M1) |
| N-M3 `./gradlew publish`, `./mvnw deploy` | `./gradlew publish`, `./gradlew clean publish`, `./mvnw deploy`, `./mvnw clean deploy`, `gradle publish`, `mvn deploy`, `gradlew.bat publish`, `.\mvnw.cmd deploy` → external-write, ask | Parcial. Tarefas fora das duas primeiras palavras ou com outro nome continuam sem pergunta (R5-M2) |
| N-B1 memo sem `folder` | `make -C sub && make -f sub/Makefile` → git-remote | Corrigido. A ordem inversa dá opaque (observação abaixo) |
| N-B2 outras lacunas do make | variável por alvo, `.DEFAULT:`, regra sem receita mais `%:` | Declaradas como residuais no ADR. `--assume-new X` e afins não foram tratados nem declarados |
| N-B3 `source ~/.bashrc` | `source ~/.bashrc`, `. ~/.bashrc`, `. "$HOME/.cargo/env"`, `source ${HOME}/...`, `source $HOME/...` → read-only; `source ~/missing.sh` → opaque | Corrigido. O texto do ADR e do CHANGELOG agora confere |
| N-B4 `source` de qualquer arquivo de fora | `source /tmp/.../x.sh` e `source ~/evil.sh` → read-only; `bash` do mesmo arquivo → ask | Declarado com o alcance real no residual do ADR (linha 108). Resolvido como residual |
| N-B5 caches entre comandos | sem mudança | Mantido. Sem impacto com um processo por comando |
| N-B6 `MAKE_BUILTINS` morto | removido | Corrigido. `CONDITIONALS` fora do bloco de constantes: mantido (julgamento) |

## Falsos positivos

| Caso | Rótulo | Estado |
| --- | --- | --- |
| `source .venv/bin/activate`, `source env/bin/activate`, `. env/bin/activate`, `source env/bin/activate && pytest` | read-only | Sem pergunta |
| `env/bin/pytest -q`, `env/Scripts/python.exe -m pytest` (com `env` fora de `INSTALLED_TOOLS`) | read-only | Sem pergunta |
| `./gradlew build`, `./mvnw verify` commitados | filesystem-write | Sem pergunta |
| `./gradlew test` commitado | read-only | Sem pergunta |
| `make test` com `release:` ao lado | read-only | Sem pergunta |
| Makefile do Sphinx: `make html` e `make` | filesystem-write | Sem pergunta |
| `make test` com `test: $(wildcard tests/*.py)` e `release:` ao lado | git-remote, ask | Falso positivo novo (R5-B3) |

## Achados novos

Nenhum é de severidade alta sob o modelo decidido, e nenhum trava o hook. Os dois médios são sobras de N-M2 e N-M3, e não regressões em relação à rodada 4.

### MÉDIA

**R5-M1. Pré-requisito montado por função dentro de uma variável** (`python/aifw/indirect.py:546`)
- O teste `\$[({][\w-]+\s` olha só o texto cru do pré-requisito. `T = $(addprefix publish-,$(PKGS))` mais `release: $(T)` → `make release` read-only, sem pergunta. O mesmo vale para referência de substituição: `T = $(PKGS:%=publish-%)` → read-only.
- Impacto: é a forma mais comum em Makefiles de monorepo (`TARGETS = $(addprefix ...)`, `all: $(TARGETS)`). Fica em média, como N-M2.
- Correção barata: aplicar o mesmo teste ao texto já expandido, ou cair no superconjunto quando `expand` devolver `,` ou um pré-requisito sem regra explícita.

**R5-M2. Publicação de gradle e maven fora das duas primeiras palavras** (`python/aifw/shell.py:617`)
- `PUBLISH[name] in lowered[:2]` exige a tarefa exata entre as duas primeiras palavras, contando opções.
- Sem pergunta via `handle` (filesystem-write): `./gradlew clean build publish`, `./gradlew publishToMavenCentral`, `./gradlew :lib:publish`, `./mvnw -B -DskipTests deploy`, `./mvnw clean install deploy`, `./mvnw release:perform`, `mvn deploy:deploy-file`.
- Impacto: `publishToMavenCentral`, `:modulo:publish` e `mvn -B ... deploy` são formas comuns em README e CI. Não é regressão em relação à rodada 4, mas o ADR item 13 diz que "`publish` e `deploy` deles [...] contam como publicação" sem essa restrição.
- Correção: para gradle e maven, olhar todas as palavras que não são opção. No gradle, contar a tarefa cujo último segmento após `:` começa com `publish`. No maven, contar `deploy`, `deploy:*` e `release:perform`.

### BAIXA

**R5-B1. A isenção de `activate` vale para qualquer arquivo com esse prefixo** (`indirect.py:259`)
- `file.name.lower().startswith("activate")` não olha a pasta. `source scripts/activate-deploy.sh` e `source activate`, ambos com push, → read-only.
- Exige um script do projeto com esse nome que publique, então é raro. O ADR item 13 fala em "script `activate` de ambiente virtual", que é mais estreito que o código.
- Correção barata: exigir a pasta `bin` ou `Scripts` e um `pyvenv.cfg` na pasta acima dela.

**R5-B2. `.DEFAULT_GOAL` que o reader não resolve falha aberto** (`indirect.py:535-536`)
- Quando `expand` devolve `None` (`.DEFAULT_GOAL := $(if $(CI),release,release)`), o código usa `(None or "")` e não lê nenhuma regra: `make` → read-only. O docstring do módulo diz que a leitura falha fechada.
- O mesmo para `.DEFAULT_GOAL :=` vazio (o make usa o próximo alvo, aqui `release`) e para variável indefinida (`$(GOAL)` vira `makevar`): read-only.
- Formas raras. Correção: devolver `None` quando `expand` falhar e usar `first` quando o resultado for vazio ou `makevar`.

**R5-B3. O superconjunto também dispara para `$(wildcard ...)`**
- `test: $(wildcard tests/*.py)` mais um `release:` com push → `make test` pergunta (git-remote). Na rodada 4, esse caso não perguntava. É uma volta parcial do falso positivo M2 da rodada 3.
- É conservador e exige as duas coisas no mesmo Makefile. Para reduzir: excluir do gatilho as funções de `MAKE_PATH_FUNCTIONS`, que geram nomes de arquivo.

### Observação

- `make -f sub/Makefile && make -C sub` (e com `;`) → opaque, enquanto cada parte isolada dá git-remote e read-only. É conservador, então não abre caminho. Não investiguei a causa, e não sei se já acontecia na rodada 4.

## Eixo Standards

- `MAKE_BUILTINS` removido: o código morto de N-B6 sumiu.
- `re.sub` com função de substituição evita que as barras de um caminho Windows virem escapes: correto.
- A detecção de função fica em dois lugares, o regex de `make_commands` e o `partition(" ")` de `expand` (Duplicated Code, julgamento). A divergência entre os dois é a causa de R5-M1.
- `import os` serve só para `expanduser`, e `Path(word).expanduser()` resolveria sem ele. É menor.
- Os testes novos cobrem `infra/env`, `env/bin/activate`, `.DEFAULT_GOAL`, `addprefix`, `./gradlew publish` e `~`/`$HOME`. Faltam testes para a função dentro de uma variável, para `-C` contra `-f` e para as formas de publicação de R5-M2.

## Eixo Spec

- REQ-HOOK-SCRIPT-FILES: a regressão de `env/` foi corrigida. `activate` abre uma isenção rara (R5-B1).
- REQ-HOOK-TASK-RUNNERS: `.DEFAULT_GOAL` e função no pré-requisito agora são seguidos, mas com as falhas de R5-M1 e R5-B2.
- A publicação (gradle e maven) está parcial em relação ao texto do ADR item 13 (R5-M2).
- Documentação divergente:
  - ADR item 13 sobre `activate` (R5-B1) e sobre `publish`/`deploy` (R5-M2);
  - ADR item 4 ainda diz que editar `venv` pede confirmação, mas Write em `venv/bin/x` não pergunta. Isso vem da rodada 3 e não foi tocado.
- Sem escopo extra no diff.

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python`: 2350 passaram em 36,2 s.
- `scratchpad/review5_probe.py`, com `_READ`/`_READING` limpos antes de cada caso e `HOME`/`USERPROFILE` apontando para uma pasta temporária fora do projeto:
  - N-M1: 13 comandos com `env/`, `venv/`, `activate` e binários de venv, mais Write em `env/`, `venv/` e `.venv/`;
  - N-M2: 11 Makefiles (`.DEFAULT_GOAL` em seis formas, `addprefix` direto, por variável e com chaves, substituição, `wildcard`);
  - falsos positivos: superconjunto, Sphinx e `make test` com `release` ao lado;
  - `.RECIPEPREFIX` e `.SHELLFLAGS`, que agora casam `MAKE_ASSIGNMENT`, continuam opaque; `.PHONY` e `.ONESHELL` não mudaram;
  - N-B1: `-f` e `-C` nas duas ordens;
  - N-M3: 20 formas de gradle e maven, com wrappers `.bat` e `.cmd`, commitados num repositório git temporário;
  - N-B3/N-B4: 11 formas de `source`, `.` e `bash` com `~`, `$HOME`, `${HOME}` e caminho absoluto de fora;
  - tempo: 40 alvos com `addprefix` de 40 itens → 0,01 s. Nenhum caso passou de 0,25 s.
- `scratchpad/review5_probe2.py`: combinações de `make -C sub` e `make -f sub/Makefile` via `analyze`.
- Não verifiquei:
  - o comportamento real de make, gradle e maven, porque nada foi executado;
  - a causa do opaque em `make -f ... && make -C ...`.

Resultado: aprovado com ressalvas
