# Revisão independente (rodada 8) — hook-indirect-code

## Escopo

- Só as correções feitas depois da sétima revisão: `scratchpad/review8.diff` (238 linhas):
  - `indirect.py`: `expand` com `memo` por Makefile, marcador `CYCLE` e teto de 100 mil caracteres por expansão; `substitute` para `$(X:a=b)`; `MAKE_KNOWN`; `make_rules` ignora o `=` dentro de `$(...)`; `built_by_function` deixa de tratar referência de substituição como montada; Makefile acima de 100 mil caracteres vira `opaque()`;
  - `shell.py`: `BUILD_VALUE_OPTIONS` por ferramenta e sem baixar a caixa; `build_publishes` recebe `args`; sai a exceção de `tasks`/`help`.
- Referência: `evidence/independent-review-7.md`. Docs conferidos: ADR-0034 item 13 e residuais.
- Método: skill `code-review`, eixos Standards e Spec feitos por mim, sem subagentes.
- Critério: o modelo decidido no impasse. Reprova só regressão de severidade alta ou caminho que trave o hook (análise acima do timeout de 10 s).
- Análise estática, só com `aifw.shell.analyze`, `aifw.hooks.handle` e funções de `indirect` que só leem texto (`make_commands`, `make_rules`, `built_by_function`). Nada classificado foi executado. Sem rede, push nem instalação. O único arquivo do repositório alterado é este relatório.

## Estado dos achados da sétima revisão

Nos fixtures, o alvo perigoso faz `git push origin main`. Rótulos via `handle` num projeto criado por `test_workflows.init`.

| Item | Medido agora | Estado |
| --- | --- | --- |
| R7-A1 `expand` exponencial | Cenários exatos (fan-out 6 prof. 9, fan-out 8 prof. 8) e também fan-out 10/prof. 10, 20/10, 2/40, diamante 3^9, ciclos densos de 6, 30 e 120 na receita, cada um em receita, pré-requisito e `.DEFAULT_GOAL` → ask em até 0,02 s (eram 41 s e 66 s) | Corrigido. Falha fechada (`opaque` ou leitura de todas as regras). Mas o teto vale por expansão, não para o total das receitas: ver R8-A1 |
| R7-M1 flags sem valor engolindo a tarefa | `mvn -B deploy`, `./mvnw -B deploy`, `mvn -X/-C/-c/-e -B/-q deploy`, `--batch-mode deploy`, `-B -U clean deploy`, `-D skipTests deploy`, `-B release:perform`; `gradle -s publish`, `./gradlew -s/-S/-t/-q/-X/-m/--info/--offline publish`, `-P key=v`, `-D k=v`, `-I init.gradle`, `PUBLISH` → ask | Corrigido |
| R7-B1 substituição direta no pré-requisito | `release: $(PKGS:%=publish-%)`, `${PKGS:%=...}`, `$(PKGS:=-publish)`, `all:` com `make all`, com regra de padrão, com `PKGS` indefinida, `$(PKGS:a=publish)` → ask; `PKGS = $(shell ls)` → ask (opaque) | Corrigido, com uma forma aninhada nova sem pergunta (R8-B1) |
| R7-B2 `seen` não impede rechamadas | Laço inalterado. Direto: ciclo denso de 125 → 0,46 s, de 300 → 6,5 s. Pelo hook, o ciclo de 300 não cabe em 100 mil caracteres, e agora um Makefile maior é `opaque` | Aberto, inalcançável pelo hook. Docstring ainda diz "stays linear" e cita a referência de substituição como montada, o que deixou de valer |
| R7-B3 falso positivo com `$(SRCS:.c=.o)` e variáveis embutidas | Makefile C típico: `make`, `make app`, `make all`, `make install` → sem pergunta (`make clean` pergunta por causa do `rm -f`, independente deste diff). `$(CURDIR)/out`, `$(MAKEFILE_LIST)`, `$(CC)` indefinido com `release` ao lado → sem pergunta; `CC = release` → ask | Corrigido |
| R7-B4 Makefile maior que 100 mil cortado | `release` depois de 110 mil caracteres → ask (opaque) | Corrigido; efeito colateral em R8-B2 |
| R7-B5 `tasks`/`help` anulando a detecção | `./gradlew tasks publish`, `help publish` → ask; `tasks --group publishing`, `help --task publish` → sem pergunta | Corrigido |

## Achados novos

### ALTA

**R8-A1. O teto de 100 mil vale por expansão; a soma das receitas expandidas não tem limite e passa do timeout do hook** (`python/aifw/indirect.py`, `make_commands` linhas ~635-637 e `make_requests` ~672)
- Cada receita é expandida em separado (`[expand(command, variables, memo=memo) for command in commands]`), cada uma até 100 mil caracteres. Uma variável grande citada em muitas linhas gera megabytes, e `make_requests` passa tudo junto para `shell.analyze`, que custa cerca de 1,5 s por MB.
- Medido via `handle`: variável de 90 mil caracteres citada em 800 linhas de receita (Makefile de 99.611 caracteres, abaixo do corte) → 123,3 s, rótulo read-only.
- Medido com `make_commands` + `shell.analyze` (o que `make_requests` faz): a expansão custa até 0,1 s; a análise é o gargalo:
  - 90 mil × 50 linhas → 7,1 s; × 100 → 14,6 s; × 200 → 28,4 s;
  - variável de 10 mil × 400 linhas (Makefile de 14,8 mil caracteres) → 6,0 s; × 2000 linhas (34 mil) → 32,9 s.
- Não é regressão deste diff: o código da rodada 7 também expandia cada receita sem limite total. A rodada 7 não mediu esse formato. Exige Makefile montado para isso (ou um gerado com uma lista grande repetida em centenas de receitas), então a chance por erro do agente é baixa; pelo critério explícito (caminho acima de 10 s), reprova.
- Correção: somar o tamanho das receitas expandidas em `make_commands` e devolver `None` (opaque) acima de `MAX_SHELL_CHARS`, como já vale para scripts de shell. Teste: variável de 10 mil citada em 1000 linhas, com limite de tempo.

### BAIXA

**R8-B1. Variável aninhada dentro da referência de substituição não é expandida** (`indirect.py`, ramo `reference` de `expand` e regex de `built_by_function`)
- `A = publish`, `PKGS = a`, `all: $(PKGS:%=$(A)-%)` com `publish-a:` fazendo push → `make all` sem pergunta (read-only). `substitute` recebe `$(A)-%` literal e gera `$(A)-a`, alvo que não existe; `built_by_function` vê só `PKGS` e `A`, ambos definidos.
- Na rodada 7 esse caso perguntava, porque qualquer `:`/`=` em `$(...)` mandava ler todas as regras. Regressão pequena, forma rara que pede intenção.
- Correção: expandir os dois lados (`reference.group(2)` e `group(3)`) com `expand(..., memo)` antes de `substitute`, ou tratar `$` dentro deles como nome montado.

**R8-B2. Makefile acima de 100 mil caracteres agora sempre pergunta**
- Makefile inofensivo de 110 mil caracteres: `make test` → ask (opaque); de 95 mil → sem pergunta. Makefiles gerados por automake/CMake de projetos grandes passam desse tamanho, então todo `make` nesses projetos vai pedir confirmação.
- Coerente com o ADR item 13 ("um Makefile desse tamanho é ilegível") e falha fechada; o custo é mais confirmações para quem usa autotools. Registro só para a decisão consciente; não pede mudança se a pessoa aceitar.

**Observação (sem ação).** O `memo` guarda o resultado da primeira expansão de cada variável. Se ela for expandida primeiro perto do limite de profundidade 10, fica `None` para todos os usos seguintes. Isso falha fechado (ask) e só afeta cadeias com mais de 10 níveis.

## Falsos positivos que devem seguir sem pergunta

| Caso | Rótulo | Estado |
| --- | --- | --- |
| `make test` com `release` ao lado | read-only | Sem pergunta |
| Makefile do Sphinx: `make html`, `make` | filesystem-write | Sem pergunta |
| Makefile C típico (`$(SRCS:.c=.o)`): `make`, `make app`, `make install` | filesystem-write | Sem pergunta |
| `all: $(TARGETS)` com `release` ao lado | read-only | Sem pergunta |
| `./gradlew build` / `./gradlew test` | filesystem-write / read-only | Sem pergunta |
| `gradle publishToMavenLocal`, `./gradlew publishToMavenLocal`, `:app:publishReleasePublicationToMavenLocal` | filesystem-write | Sem pergunta |
| `mvn install`, `mvn -B test`, `./mvnw -B verify`, `mvn -B -DskipTests install`, `mvn -B clean package` | filesystem-write | Sem pergunta |
| `mvn -pl deploy install`, `./gradlew -x publish build` | filesystem-write | Sem pergunta |

## Eixo Standards

- `MAKE_KNOWN` repete metade de `MAKE_PROGRAMS` (`CC`, `CXX`, `CPP`, `FC`, `AR`, `AS`, `LD`, `RM`). Judgement call de Duplicated Code: `MAKE_KNOWN` poderia ser `MAKE_PROGRAMS | {...}`.
- Docstring de `built_by_function` desatualizada: diz que a referência de substituição conta como montada e que o custo "stays linear" (R7-B2).
- `BUILD_VALUE_OPTIONS` por ferramenta resolve o Primitive Obsession apontado na rodada 7.
- `built_by_function` e `expand` continuam percorrendo o mesmo grafo com regexes diferentes (judgement call); a divergência aparece de novo em R8-B1.
- Testes novos cobrem camadas de variáveis com limite de tempo, flags sem valor, substituição no pré-requisito, `CURDIR` e Makefile longo. Falta um teste para o total das receitas expandidas (R8-A1).

## Eixo Spec

- ADR item 13: "uma expansão maior que 100 mil caracteres, assim como um Makefile desse tamanho, é ilegível; camadas e ciclos de variáveis não pesam no hook" — vale para cada expansão, mas não para o texto total entregue a `shell.analyze` (R8-A1).
- ADR item 13: "Referências de substituição (`$(SRCS:.c=.o)`, `$(PKGS:%=publish-%)`) são expandidas como no make" — exceto quando o padrão tem variável (R8-B1).
- "Isso não vale para ... as variáveis do próprio make (`CURDIR`, `CC`)" — implementado e conferido.
- ADR item 13 sobre gradle/maven: valores de opções por ferramenta e `tasks`/`help` sem exceção — conforme.
- Sem escopo extra no diff.

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python`: 2384 passaram em 56,6 s.
- `scratchpad/review8_probe.py` (`HOME`/`USERPROFILE` numa pasta temporária, `_READ`/`_READING` limpos antes de cada caso), via `handle` e `analyze`:
  - R7-A1: camadas 6/9, 8/8, 10/10, 20/10 e 2/40 em receita, pré-requisito e `.DEFAULT_GOAL`; ciclos densos de 6, 30 e 120; diamante 3^9; dobras de 12 níveis em 7000 e 3000 linhas; variável de 90 mil em 800 linhas;
  - R7-M1/R7-B5: 40 formas de maven e gradle num repositório git temporário com `mvnw` e `gradlew` commitados;
  - R6-B1/R7-B1: 12 Makefiles com referência de substituição direta, por variável, aninhada e variável por alvo;
  - R7-B3/R7-B4: Makefile C (5 alvos), `CURDIR`, `MAKEFILE_LIST`, `CC`, `MAKECMDGOALS`, Makefiles de 95 mil e 110 mil caracteres;
  - falsos positivos da lista acima.
- `scratchpad/review8_probe2.py`: tempo de `make_commands` e `shell.analyze` separados em 6 tamanhos (tabela de R8-A1) e as formas de substituição com espaço e aninhada.
- `scratchpad/review8_probe3.py`: `built_by_function` direto em ciclos densos de 125 e 300 variáveis.
- Análises acima de 1 s: via `handle`, só a de 800 linhas × 90 mil (123,3 s). Fora do hook: as da tabela de R8-A1 (6,0 s a 32,9 s) e `built_by_function` direto no ciclo de 300 (6,5 s, inalcançável pelo hook).
- Não verifiquei:
  - o comportamento real do Claude Code quando o hook passa do timeout;
  - o comportamento real de make, gradle e maven, porque nada foi executado;
  - o tamanho real de Makefiles gerados por automake/CMake (R8-B2 se apoia em conhecimento geral).

Resultado: reprovado
