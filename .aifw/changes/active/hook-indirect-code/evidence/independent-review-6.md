# Revisão independente (rodada 6) — hook-indirect-code

## Escopo

- Só as correções feitas depois da quinta revisão: `scratchpad/review6.diff` (114 linhas):
  - `indirect.py`: `ACTIVATE_SCRIPTS` com pasta `bin`/`Scripts`, `built_by_function` (função no pré-requisito, direta ou dentro de variável, sem contar funções de caminho), `.DEFAULT_GOAL` não resolvido lê todas as regras;
  - `shell.py`: gradle/maven saem de `PUBLISH` e passam para `build_publishes` (qualquer palavra, último segmento com `publish`; goals `deploy`, `deploy:deploy`, `release:prepare`, `release:perform`).
- Referência: `evidence/independent-review-5.md`. Docs conferidos: ADR-0034 item 13 e residuais, linha do CHANGELOG.
- Método: skill `code-review`, eixos Standards e Spec feitos por mim, sem subagentes.
- Critério: o modelo decidido no impasse. Reprova só uma regressão de severidade alta ou um caminho que trave o hook.
- Análise estática, só com `aifw.shell.analyze` e `aifw.hooks.handle` (e, para medir custo, `indirect.expand` e `indirect.built_by_function` diretamente, que só leem texto). Nada classificado foi executado. Sem rede, push nem instalação. O único arquivo do repositório alterado é este relatório.

## Estado dos achados da quinta revisão

Nos fixtures, o alvo ou script perigoso faz `git push origin main`. Rótulos via `handle` num projeto criado por `test_workflows.init`.

| Item | Medido agora | Estado |
| --- | --- | --- |
| R5-M1 função dentro de variável | `T = $(addprefix ...)` + `release: $(T)`, `${T}` e por duas variáveis → git-remote, ask; `patsubst` por variável → opaque, ask | Corrigido para funções. Sobram: referência de substituição `$(PKGS:%=publish-%)`, direta ou por variável → read-only; variável de uma letra sem parênteses (`release: $T`) → read-only. Ver R6-B1 |
| R5-M2 gradle/maven em qualquer posição | `./gradlew clean build publish`, `publishToMavenCentral`, `:lib:publish`, `--no-daemon publish`, `./mvnw -B -DskipTests deploy`, `clean install deploy`, `release:perform`, `release:prepare`, `mvn deploy:deploy`, `.bat`/`.cmd` → external-write, ask | Corrigido. `mvn deploy:deploy-file` continua sem pergunta (R6-B2). Falsos positivos novos em R6-B3 |
| R5-B1 `activate` largo | `source scripts/activate-deploy.sh`, `source activate` → git-remote, ask; `env/bin/activate`, `.venv/bin/activate`, `activate.fish`, `call .venv\Scripts\activate.bat`, `. env\Scripts\Activate.ps1` → read-only | Corrigido. `pyvenv.cfg` não é exigido: `source tools/bin/activate` e `source scripts/activate` com push → read-only. Raro e com nome de venv; aceito como residual, mas não está declarado |
| R5-B2 `.DEFAULT_GOAL` não resolvido | `$(if ...)`, vazio e por variável que usa `if` → git-remote, ask | Parcial. `.DEFAULT_GOAL := $(GOAL)` indefinida → read-only (o make cai no primeiro alvo, aqui `release`). Raro |
| R5-B3 superconjunto com `wildcard` | `make test` com `test: $(wildcard tests/*.py)` (direto ou por variável) e `release` ao lado → read-only | Corrigido |

## Falsos positivos

| Caso | Rótulo | Estado |
| --- | --- | --- |
| `make test` com `release` ao lado | read-only | Sem pergunta |
| Makefile do Sphinx: `make html`, `make` | filesystem-write | Sem pergunta |
| `source .venv/bin/activate`, `source env/bin/activate`, `. env/bin/activate`, `... && pytest` | read-only | Sem pergunta |
| `./gradlew build` commitado, `./mvnw verify` | filesystem-write | Sem pergunta |
| `./gradlew test` | read-only | Sem pergunta |
| `mvn test` | read-only | Sem pergunta |
| `mvn install`, `mvn clean install`, `mvn -f deploy/pom.xml install`, `mvn -Dmaven.deploy.skip=true install` | filesystem-write | Sem pergunta |
| `./gradlew -Ppublish=true build`, `assemble -PskipPublish` | filesystem-write | Sem pergunta |
| Makefile C típico (`OBJ = $(patsubst %.c,%.o,$(SRC))`, `all: $(OBJ)`) | opaque, ask | Pergunta; o reader não segue `patsubst` na receita. Não é efeito deste diff (`expand` já devolvia `None`), mas fica registrado |
| `./gradlew publishToMavenLocal` e afins | external-write, ask | Falso positivo novo (R6-B3) |

## Achados novos

### ALTA

**R6-A1. `built_by_function` é exponencial e passa do timeout do hook** (`python/aifw/indirect.py:527-536`)
- A recursão pelas variáveis não guarda o que já visitou e, ao bater no limite de nível, devolve `False` e segue para o próximo ramo. `expand`, no mesmo caso, devolve `None` no limite e para. O custo é fan-out^10.
- Medido direto: variáveis que se referenciam em ciclo, com 6 variáveis → `built_by_function` 5,7 s (`expand` 0,00 s); camadas com fan-out 4 e profundidade 11 → 1,0 s.
- Medido via `handle`, uma chamada, ciclo de 7 variáveis → 28 s, nos dois cenários abaixo, em que o próprio make roda o push sem erro:
  - `.DEFAULT_GOAL = $(V0)` recursivo mais `make release` (com alvo dado o make não expande `.DEFAULT_GOAL`, mas `unresolved` chama `built_by_function` mesmo assim);
  - `release: $(V0)` dentro de `ifeq (1,0)` mais uma regra `release:` com push (o reader lê os dois lados do condicional).
- O hook está configurado com `timeout: 10` e `aifw-hook || true` (`python/aifw/claude.py:19`). Passar do timeout é um caminho que trava o hook. Hipótese não verificada aqui: o Claude Code trata o timeout como erro não bloqueante, e o comando segue sem a pergunta, ou seja, falha aberta.
- Exige um Makefile montado para isso, então a chance de acontecer por erro do agente é baixa. Ainda assim é regressão deste diff (a rodada 5 só aplicava um regex ao texto cru) e cai no critério explícito de reprovação.
- Correção de uma linha: devolver `True` no limite de nível (falhar fechado, como `expand`), ou passar um conjunto de nomes já visitados. Vale um teste com um ciclo de 7 variáveis e um limite de tempo.

### BAIXA

**R6-B1. Referência de substituição e `$X` não contam como nome montado** (`indirect.py:532-535`)
- `release: $(PKGS:%=publish-%)`, direto ou por variável, e `release: $T` → read-only. O regex de chamadas exige espaço depois do nome; o de nomes exige `)` ou `}` logo depois do nome.
- `$(VAR:a=b)` é comum em Makefiles C; como montagem de alvos para publicar é menos comum. Correção: tratar `:` dentro de `$(...)` como função não seguida.

**R6-B2. `mvn deploy:deploy-file` sem pergunta** (`shell.py:144`)
- `MAVEN_PUBLISH` aceita `deploy:deploy`, mas não `deploy:deploy-file` nem a forma longa `org.apache.maven.plugins:maven-deploy-plugin:...:deploy`. O ADR lista só `deploy` e `release:*`, então código e ADR concordam, mas `deploy-file` envia ao repositório remoto. Correção: aceitar qualquer palavra que comece com `deploy:`.

**R6-B3. Falsos positivos novos de gradle e maven** (`shell.py:147-151`)
- Perguntam (external-write): `./gradlew publishToMavenLocal`, `:app:publishReleasePublicationToMavenLocal`, `./gradlew build -x publish`, `gradle tasks --group publishing`, `./gradlew help --task publish`, `mvn -pl deploy install`.
- `publishToMavenLocal` é comum no desenvolvimento de bibliotecas e plugins Gradle e só grava em `~/.m2`. O ADR item 13 diz "tarefas do Gradle com `publish` no nome", então é coerente com o texto, mas vai contra "quanto menos confirmações, melhor". Correção barata: ignorar tarefas que terminam em `ToMavenLocal` e o valor de `-x`/`--exclude-task`, `-pl`, `--task`, `--group`.

### Observações

- R5-B1: o ADR fala em "script `activate` de ambiente virtual"; o código aceita qualquer `bin/activate*` e `Scripts/activate*`. Diferença pequena, não declarada.
- R5-B2: `.DEFAULT_GOAL` com variável indefinida segue sem pergunta. Raro.

## Eixo Standards

- `built_by_function` duplica a detecção de função que `expand` já faz com `partition(" ")` (Duplicated Code, julgamento). A divergência de comportamento no limite de nível é a causa de R6-A1, e a dos regexes, a de R6-B1.
- `MAVEN_PUBLISH` fica no meio do arquivo, depois de `request`, e não com as outras constantes (`PUBLISH`, `REMOTE_SHELL`). Menor.
- O fechamento `"publish",}  # fmt: skip` ficou na mesma linha do último item. Menor.
- Testes novos cobrem `publishToMavenCentral`, `-B -DskipTests deploy`, `clean install deploy`, `release:perform`, `addprefix` por variável, `.DEFAULT_GOAL` com `if` e `wildcard` sem superconjunto. Faltam um teste de tempo para variáveis em ciclo e casos de `activate` fora de venv.

## Eixo Spec

- ADR item 13: `activate` e publicação de gradle/maven agora conferem com o código, salvo a diferença menor de `activate` acima.
- REQ-HOOK-TASK-RUNNERS: função por variável e `.DEFAULT_GOAL` com função passam a ser seguidos; sobram R6-B1 e a variável indefinida.
- Residuais do ADR: não citam ciclos de variáveis nem limite de tempo do reader de Makefile.
- CHANGELOG: a linha "`gradle publish` e `mvn deploy` contam como publicação" está correta, mas não menciona que agora vale em qualquer posição. Menor.
- Sem escopo extra no diff.

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python`: 2360 passaram em 42,9 s.
- `scratchpad/review6_probe.py`, com `_READ`/`_READING` limpos antes de cada caso e `HOME`/`USERPROFILE` numa pasta temporária fora do projeto:
  - R5-B1: 10 formas de `source`, `.` e `call` com `activate`;
  - R5-M1/R5-B2/R5-B3: 23 Makefiles (`.DEFAULT_GOAL` em oito formas, `addprefix` direto, por variável, `${}`, `$T` e duas variáveis, `patsubst`, referência de substituição, `wildcard`, Makefile C, `CFLAGS`), mais Sphinx;
  - R5-M2 e regressões: 35 formas de gradle e maven, com wrappers `.bat`/`.cmd` commitados num repositório git temporário;
  - custo: grafos de variáveis em DAG e em ciclo.
- `scratchpad/review6_probe2.py`: tempo de `expand` contra `built_by_function` em ciclos de 4 a 6 variáveis e em camadas com fan-out 3 e 4.
- `scratchpad/review6_probe3.py`: uma chamada de `handle` com ciclo de 7 variáveis, nos dois cenários de R6-A1 → 28 s cada.
- `scratchpad/review6_probe4.py`: `call` e `.` de `activate.bat` e `Activate.ps1` com barra invertida.
- Não verifiquei:
  - o comportamento real do Claude Code quando o hook passa do timeout;
  - o comportamento real de make, gradle e maven, porque nada foi executado.

Resultado: reprovado
