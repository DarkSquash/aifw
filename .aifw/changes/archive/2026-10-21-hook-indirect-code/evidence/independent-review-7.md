# Revisão independente (rodada 7) — hook-indirect-code

## Escopo

- Só as correções feitas depois da sexta revisão: `scratchpad/review7.diff` (77 linhas):
  - `indirect.py`: `built_by_function` com conjunto `seen`, referência de substituição (`$(X:a=b)`), `$X` de uma letra e variável indefinida contam como nome montado;
  - `shell.py`: `MAVEN_PUBLISH` ganha `deploy:deploy-file`; `build_publishes` pula valores de `BUILD_VALUE_OPTIONS`, ignora `tasks`/`help` e `*ToMavenLocal`.
- Referência: `evidence/independent-review-6.md`. Docs conferidos: ADR-0034 item 13 e residuais.
- Método: skill `code-review`, eixos Standards e Spec feitos por mim, sem subagentes.
- Critério: o modelo decidido no impasse. Reprova só regressão de severidade alta ou caminho que trave o hook (análise acima do timeout de 10 s).
- Análise estática, só com `aifw.shell.analyze` e `aifw.hooks.handle` (e `indirect.built_by_function` direto, que só lê texto). Nada classificado foi executado. Sem rede, push nem instalação. O único arquivo do repositório alterado é este relatório.

## Estado dos achados da sexta revisão

Nos fixtures, o alvo perigoso faz `git push origin main`. Rótulos via `handle` num projeto criado por `test_workflows.init`.

| Item | Medido agora | Estado |
| --- | --- | --- |
| R6-A1 `built_by_function` exponencial | Cenários exatos da rodada 6 (ciclo de 7, `.DEFAULT_GOAL` e `ifeq` falso) → ask em 0,00–0,01 s (eram 28 s). Ciclos densos de 6, 20 e 60 variáveis via `handle` → ask, até 0,05 s. Camadas fan-out 4/10 prof. 11 direto → 0,000 s | Corrigido para a função. Sobra custo O(arestas × texto), não linear (R7-B2). O mesmo padrão exponencial existe em `expand` e passa de 10 s (R7-A1) |
| R6-B1 referência de substituição e `$X` | Por variável (`T = $(PKGS:%=publish-%)`), `$T`, `${T}`, variável indefinida, `$X` indefinida e `.DEFAULT_GOAL := $(GOAL)` → ask | Parcial. Direto no pré-requisito (`release: $(PKGS:%=publish-%)`, `${PKGS:%=...}`, `$(PKGS:=-publish)`) → read-only: o `=` faz `make_rules` tratar a linha como variável por alvo e a regra some (R7-B1) |
| R6-B2 `deploy:deploy-file` | `mvn deploy:deploy-file ...` → external-write, ask | Corrigido. A forma longa `org.apache.maven.plugins:maven-deploy-plugin:3.1.1:deploy` → filesystem-write, sem pergunta. Rara |
| R6-B3 falsos positivos de gradle/maven | `publishToMavenLocal` (com e sem wrapper), `:app:publishReleasePublicationToMavenLocal`, `build -x publish`, `tasks --group publishing`, `help --task publish`, `mvn -pl deploy install` → sem pergunta | Corrigido, mas a forma escolhida reabre publicação sem pergunta (R7-M1) |

## Achados novos

### ALTA

**R7-A1. `expand` é exponencial em grafos largos de variáveis e passa do timeout do hook** (`python/aifw/indirect.py:428-489`)
- `expand` não memoriza variáveis já expandidas; com profundidade até 10 ele não bate no limite e expande a árvore inteira. O custo é fan-out^profundidade.
- Medido via `handle`, uma chamada, receita `echo $(L0)` com camadas `Lk = $(Lk+1) × f`:
  - fan-out 6, prof. 9, Makefile de 424 caracteres → 41,0 s;
  - fan-out 8, prof. 8, 479 caracteres → 66,4 s;
  - fan-out 6, prof. 8 → 6,8 s; fan-out 10, prof. 6 → 3,9 s; fan-out 4, prof. 9 → 1,1 s.
- O mesmo vale para pré-requisitos (`all: $(L0)`): `built_by_function` agora devolve rápido, e a demora passa a `expand(rule["prerequisites"])`: fan-out 6, prof. 8 → 2,7 s.
- Não é regressão deste diff (`expand` não mudou), e a rodada 6 só mediu `expand` com profundidade 11, onde o limite corta cedo. Mas é um caminho que trava o hook (`timeout: 10`), com Makefile pequeno. Exige um Makefile montado para isso, então a chance por erro do agente é baixa; pelo critério explícito, reprova.
- Correção: cache por nome de variável dentro de uma expansão (o resultado de `$(V)` não depende do caminho), ou um orçamento de tamanho de saída que devolve `None` (falha fechada). Vale um teste com fan-out 6 e prof. 9 e limite de tempo.

### MÉDIA

**R7-M1. `BUILD_VALUE_OPTIONS` engole a tarefa de flags sem valor: `mvn -B deploy` volta a não perguntar** (`python/aifw/shell.py:146-149, 160-162`)
- A lista é a mesma para gradle e maven e é comparada com `lowered`. Várias entradas são flags sem valor numa das ferramentas ou viram outra opção ao baixar a caixa:
  - maven: `-B` (batch) vira `-b`, `-X` (debug) vira `-x`, `-C` vira `-c`; `-c` é `--strict-checksums`;
  - gradle: `-s` é `--stacktrace`, `-S` vira `-s`, `-t` é `--continuous`.
- Medido, todos sem pergunta (filesystem-write): `mvn -B deploy`, `./mvnw -B deploy`, `mvn -X deploy`, `mvn -C deploy`, `mvn -c deploy`, `./gradlew -s publish`, `./gradlew -S publish`, `./gradlew -t publish`. Na rodada 6 todos perguntavam.
- `mvn -B deploy` é a forma de CI mais comum de publicar com Maven, então é um caminho óbvio que um agente pode copiar. Regressão deste diff. Classifico como média, a mesma severidade de R5-M2, que este caminho reabre.
- Correção: listas separadas por ferramenta, comparadas com `args` sem baixar a caixa (só as opções com valor de verdade: gradle `-x`, `--exclude-task`, `-p`, `-b`, `-c`, `--task`, `--group`...; maven `-pl`, `-f`, `-s`, `-rf`, `-T`, `-P`...).

### BAIXA

**R7-B1. Referência de substituição direta no pré-requisito some do parser; o teste passa por acaso** (`indirect.py:510-513`, `tests_python/test_indirect_code.py:582`)
- `release: $(PKGS:%=publish-%)` tem `=` nos pré-requisitos, e `make_rules` descarta a linha como variável por alvo. `make release` → read-only.
- O caso do teste novo (`all: $(PKGS:%=publish-%)` com `make`) passa porque a regra `all` some e o primeiro alvo vira `publish-a`, que tem o push. Não exercita `built_by_function`.
- Correção: só tratar como variável por alvo quando o `=` estiver fora de `$(...)`; no teste, pôr uma regra inofensiva antes de `all` ou usar `make all`.

**R7-B2. `seen` não impede rechamadas: custo O(arestas × texto)** (`indirect.py:539-542`)
- O laço itera um conjunto calculado antes da recursão e não confere `seen` de novo; o docstring e o ADR dizem "cada variável é seguida uma vez".
- Direto, ciclo denso de 300 variáveis → 5,3 s. Via `handle` o Makefile é cortado em 100 mil caracteres, e o pior ciclo denso que cabe (125 variáveis) leva 0,01 s, porque o corte também derruba a regra (R7-B4). Sem caminho medido acima de 1 s pelo hook.
- Correção de uma linha: `if name in seen: continue` antes de `seen.add(name)`.

**R7-B3. Falso positivo novo em Makefiles C com `$(SRCS:.c=.o)` e em variáveis embutidas**
- Makefile C típico com `OBJS = $(SRCS:.c=.o)`, `clean` e `install` (`cp app /usr/local/bin`): `make` e `make app` → ask (antes, sem pergunta; com `OBJS` em lista, segue sem pergunta). É a forma canônica em C.
- Pré-requisitos com variáveis embutidas que o Makefile não define (`$(CURDIR)`, `$(MAKEFILE_LIST)`) também fazem ler todas as regras: com `release` ao lado → ask.
- Coerente com o texto do ADR item 13 e falha fechada, mas vai contra "quanto menos confirmações, melhor". Sugestão: tratar `$(X:a=b)` como `X` (a substituição só troca sufixos de nomes já conhecidos) e reconhecer as variáveis embutidas.

**R7-B4. Makefile acima de 100 mil caracteres é cortado em vez de ilegível** (`indirect.py:614`)
- `release` depois de 110 mil caracteres de comentário: `make release` → read-only. O comentário de `MAX_SHELL_CHARS` diz que um script maior é opaco, e é o que acontece com scripts de shell (linha 185), mas não com Makefiles. Fora do diff e raro (Makefiles gerados por automake passam desse tamanho, mas sem push). Correção: devolver `opaque()` acima do limite.

**R7-B5. `tasks`/`help` em qualquer posição anulam a detecção** (`shell.py:168`)
- `./gradlew tasks publish` e `./gradlew help publish` → sem pergunta, mas o Gradle roda as duas tarefas. Raro. Correção: ignorar só o valor de `--task`, não a lista inteira.

## Falsos positivos que devem seguir sem pergunta

| Caso | Rótulo | Estado |
| --- | --- | --- |
| `make test` com `release` ao lado | read-only | Sem pergunta |
| Makefile do Sphinx: `make html`, `make` | filesystem-write | Sem pergunta |
| `all: $(TARGETS)` e `all: ${TARGETS}` com TARGETS definido e `release` ao lado | read-only | Sem pergunta |
| `./gradlew build` commitado | filesystem-write | Sem pergunta |
| `./gradlew test` | read-only | Sem pergunta |
| `gradle publishToMavenLocal`, `./gradlew publishToMavenLocal` | filesystem-write | Sem pergunta |
| `mvn install` | filesystem-write | Sem pergunta |
| Makefile C com `$(SRCS:.c=.o)` | ask | Falso positivo novo (R7-B3) |

Continuam perguntando: `./gradlew publish`, `clean build publish`, `:lib:publish`, `publishToMavenCentral`, `-x test publish`, `--scan publish`, `publish --no-daemon`, `-p lib publish`, `-c settings.gradle publish`, `publishAllPublicationsToMavenRepository`, `publishPlugins`, `./mvnw -B -DskipTests deploy` (só porque `-B` engole `-DskipTests`), `clean install deploy`, `release:perform`, `mvn deploy`, `-T 4 deploy`, `-P release deploy`, `-s settings.xml deploy`.

## Eixo Standards

- `BUILD_VALUE_OPTIONS` mistura opções de duas ferramentas com semânticas diferentes e é comparada depois de baixar a caixa: causa de R7-M1. Judgement call de Primitive Obsession / Data Clumps: a tabela de opções quer ser por ferramenta.
- `built_by_function` e `expand` continuam percorrendo o mesmo grafo de variáveis com regexes e regras diferentes (Duplicated Code, judgement call). A divergência agora aparece no custo: uma tem `seen`, a outra é exponencial (R7-A1), e no parser (R7-B1).
- Docstring de `built_by_function` ("each variable is followed once ... stays linear") não confere com o código (R7-B2).
- Testes novos cobrem o ciclo de 12 variáveis com limite de tempo e as bordas de gradle/maven. Faltam: flags sem valor antes da tarefa (`mvn -B deploy`, `gradlew -s publish`), grafo largo sem ciclo na receita, e o caso de referência de substituição que hoje passa por acaso.

## Eixo Spec

- ADR item 13: "sem contar valores de opções como `-pl`" — o código conta também flags sem valor como se tivessem valor, o que contraria "contam como publicação, em qualquer posição" (R7-M1). "As listagens `tasks` e `help`" está implementado de forma mais larga que o texto (R7-B5).
- ADR item 13: "Cada variável é seguida uma vez, então ciclos de variáveis não pesam no hook" — vale para `built_by_function` pelo hook; não vale para `expand` (R7-A1) e não é exatamente "uma vez" (R7-B2).
- Residuais do ADR: não citam grafos largos de variáveis, o corte de Makefiles grandes nem a forma longa do deploy plugin.
- Sem escopo extra no diff.

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python`: 2370 passaram em 42,5 s.
- `scratchpad/review7_probe.py` (`HOME`/`USERPROFILE` numa pasta temporária, `_READ`/`_READING` limpos antes de cada caso):
  - R6-A1: os dois cenários exatos da rodada 6 e a variante sem alvo; ciclos densos de 6 a 150 variáveis via `handle`; camadas com fan-out 4, 6 e 10; 300 regras encadeadas; `built_by_function` direto em ciclos de 7, 50 e 300 e casos que devem dar `True`;
  - R6-B1: 9 Makefiles; R6-B2/R6-B3 e regressões: 43 formas de gradle e maven com wrappers commitados num repositório git temporário;
  - falsos positivos: `make test`, Sphinx, `all: $(TARGETS)`, `./gradlew build`, `gradle publishToMavenLocal`, `mvn install`, e quatro Makefiles com variáveis embutidas ou referência de substituição.
- `scratchpad/review7_probe2.py`: `expand` com fan-out 6 prof. 9 e fan-out 8 prof. 8 (41 s e 66 s), Makefile de 110 mil caracteres, ciclo denso de 125 variáveis perto do limite.
- `scratchpad/review7_probe3.py`: Makefile C com `OBJS` por referência de substituição, `patsubst` e lista.
- Análises acima de 1 s: as camadas da tabela de R7-A1 (1,1 s a 66,4 s, todas em `expand`) e `built_by_function` direto no ciclo denso de 300 (5,3 s, inalcançável pelo hook por causa do corte de 100 mil caracteres).
- Não verifiquei:
  - o comportamento real do Claude Code quando o hook passa do timeout;
  - o comportamento real de make, gradle e maven, porque nada foi executado.

Resultado: reprovado
