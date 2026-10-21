# Revisão independente (rodada 9) — hook-indirect-code

## Escopo

- Só a correção feita depois da oitava revisão: `scratchpad/review9.diff` (55 linhas, `python/aifw/indirect.py`):
  - `MAKE_KNOWN` passa a ser `MAKE_PROGRAMS | {...}`;
  - no ramo de referência de substituição de `expand`, os dois lados (`a` e `b` de `$(X:a=b)`) são expandidos com o mesmo `memo` antes de `substitute`; qualquer `None` torna a expansão ilegível;
  - docstring de `built_by_function` atualizada;
  - `make_commands` devolve `None` (opaque) quando a soma das receitas expandidas passa de `MAX_SHELL_CHARS`.
- Referência: `evidence/independent-review-8.md`. Conferido também o ADR-0034 item 13, que já cita o teto do total das receitas e os Makefiles grandes do automake.
- Método: skill `code-review`, eixos Standards e Spec feitos por mim, sem subagentes.
- Critério: o modelo decidido no impasse. Reprova só regressão de severidade alta neste diff.
- Análise estática, só com `aifw.shell.analyze`, `aifw.hooks.handle` e `indirect.make_commands` (que só lê texto). Nada classificado foi executado. Sem rede, push nem instalação. O único arquivo do repositório alterado é este relatório.

## Estado dos achados da oitava revisão

Nos fixtures, o alvo perigoso faz `git push origin main`. Rótulos via `handle` num projeto criado por `test_workflows.init`.

| Item | Medido agora | Estado |
| --- | --- | --- |
| R8-A1 soma das receitas sem teto | Cenário exato (variável de 90 mil em 800 linhas, Makefile de 99,6 mil, com `release` ao lado) → ask (opaque) em 0,08 s (era 123,3 s). Variações: 90 mil × 50 → ask 0,02 s; 10 mil × 400 e × 2000 → ask ≤ 0,02 s; dobras de ~86–90 mil × 1000 a 10000 linhas → ask ≤ 0,11 s. Na fronteira: 90 mil × 1, 10 mil × 9 e 1 mil × 99 → sem pergunta (read-only, ≤ 0,17 s); 10 mil × 10, 10 mil × 11 e 1 mil × 101 → ask. Abaixo do teto, um push dentro da variável citada em 10 linhas → ask (git-remote) | Corrigido |
| R8-B1 variável aninhada na referência de substituição | `$(PKGS:%=$(A)-%)`, `${PKGS:%=${A}-%}`, variável no lado esquerdo (`$(PKGS:%$(S)=%)`), em camadas e na receita → ask (git-remote); ciclo e função no padrão → ask (opaque); forma inofensiva (`test-a`) com `release` ao lado → sem pergunta | Corrigido. Resta a forma com variável indefinida (R9-B2) |
| R8-B2 Makefile acima de 100 mil sempre pergunta | Sem mudança; o ADR item 13 agora registra o efeito sobre Makefiles do automake | Aceito como decisão documentada |
| R7-B2 `built_by_function` com rechamadas | Laço inalterado; inalcançável pelo hook pelo teto do Makefile. A docstring ainda diz "stays linear" | Aberto, residual sem efeito no hook |
| Standards R8: `MAKE_KNOWN` duplicado | `MAKE_KNOWN = MAKE_PROGRAMS \| {...}` | Corrigido |
| Standards R8: docstring desatualizada | A parte da referência de substituição foi corrigida; "stays linear" segue | Parcial |

## Achados novos

Nenhum de severidade alta. Nenhuma regressão alta neste diff.

### BAIXA

**R9-B1. `substitute` monta o texto inteiro antes do teto: pico de memória de gigabytes** (`indirect.py`, `substitute` e ramo `reference` de `expand`)
- O teto de 100 mil é conferido depois que `substitute` já juntou todas as palavras. Com `X` de ~48 mil palavras (dobras) e lado direito de 80 mil caracteres, o resultado teria 3,84 bilhões de caracteres antes de ser descartado.
- Medido via `handle` (com `tracemalloc` para o pico): 5 mil palavras × 10 mil → 100 MB, 0,06 s; 20 mil × 4 mil → 161 MB; Makefile de 23 mil caracteres com 48 mil palavras × `$(Y0)` de 80 mil → pico de 7,7 GB, 3,9 s sem rastreio; todos → ask (opaque).
- Não é regressão nascida deste diff: com o lado direito literal, como no código da rodada 8, 20 mil palavras × 50 mil caracteres literais (Makefile de 90 mil) → pico de 2,0 GB, 0,73 s. Este diff só permite montar o lado direito grande por variável, num Makefile menor; o máximo continua na ordem de 5 bilhões de caracteres (50 mil palavras × 100 mil).
- Sempre falha fechado: ou o rótulo é ask, ou um `MemoryError` cai no `except` de `hooks.handle`, ou o atraso passa do timeout e `onFailure: block` bloqueia. O custo é pressão de memória na máquina da pessoa. Só um Makefile montado de propósito chega lá.
- Correção simples, se quiserem: em `substitute`, somar o tamanho das palavras e devolver `None` ao passar de `MAX_SHELL_CHARS`. Senão, declarar como residual.

**R9-B2. Variável indefinida dentro da referência de substituição não faz ler todas as regras** (`indirect.py`, regex de nomes de `built_by_function`)
- `PKGS = a`, `all: $(PKGS:%=$(UNDEF)-%)`, `publish-a:` com push → `make all` sem pergunta (read-only). O regex `\$[({]([\w.-]+)(?::[^)}]*)?[)}]` casa `$(PKGS:%=$(UNDEF)` e nunca vê `UNDEF`. Já `all: $(UNDEF)-a` pergunta, pela regra "variável indefinida faz ler todas as regras".
- Sem ambiente, o make expande `UNDEF` para vazio e o alvo vira `-a`, então o push não roda; só roda com `UNDEF=publish` vindo do ambiente, que o ADR já declara como residual (`export` anterior). Anterior a este diff (o regex não mudou) e exige Makefile montado de propósito.
- Residual a declarar, ou varrer os nomes dentro do padrão da referência em `built_by_function`.

**Observação (sem ação).** `make_commands` monta a lista inteira de receitas expandidas antes de somar. Com receitas `echo $(W0)` de 89,6 mil caracteres, 5 mil linhas → pico de 449 MB e 0,28 s; o teto do Makefile limita isso a ~8 mil linhas (< 1 GB, < 1 s). Falha fechado; uma saída antecipada na soma evitaria o pico.

## Falsos positivos que devem seguir sem pergunta

| Caso | Rótulo | Estado |
| --- | --- | --- |
| `make test` com `release` ao lado | read-only | Sem pergunta |
| Makefile do Sphinx: `make html`, `make` | filesystem-write | Sem pergunta |
| Makefile C típico (`$(SRCS:.c=.o)`, `CC`, `CFLAGS`, regra `%.o: %.c`) com `release` ao lado: `make`, `make app`, `make all`, `make install` | filesystem-write | Sem pergunta |
| Substituição inofensiva com variável aninhada (`$(PKGS:%=$(A)-%)` → `test-a`) | read-only | Sem pergunta |

## Eixo Standards

- `MAKE_KNOWN = MAKE_PROGRAMS | {...}`: resolve a duplicação apontada na rodada 8; o comentário diz por que existe.
- O ramo novo de `expand` reaproveita `expand` e `memo`, e trata `None` de forma uniforme. Judgement call: `ready = None not in (...)` seguido do ternário é legível, mas `substitute` continua sem teto próprio (R9-B1).
- Docstring de `built_by_function`: correta quanto à referência de substituição, mas "stays linear" segue impreciso (R7-B2) e ela não diz que nomes dentro do padrão da referência não são vistos (R9-B2).
- Comentário do novo `return None` em `make_commands` explica o motivo. Sem smells novos relevantes.
- Os testes `test_large_expanded_recipes_are_opaque_and_fast` e `test_substitution_with_variables_inside_is_expanded` existem em `tests_python/test_indirect_code.py` para as duas correções.

## Eixo Spec

- ADR item 13: "É ilegível uma expansão maior que 100 mil caracteres, o total das receitas expandidas acima disso e um Makefile desse tamanho" — implementado e medido (R8-A1). O teto vale para o resultado de `substitute`, não para o que ela monta antes (R9-B1, falha fechado).
- ADR item 13: "Referências de substituição (`$(SRCS:.c=.o)`, `$(PKGS:%=publish-%)`) são expandidas como no make" — agora também com variáveis nos dois lados.
- ADR item 13: "Pré-requisitos ... montados ... por variável indefinida, direto ou numa variável, fazem ler todas as regras" — exceto quando a variável indefinida está dentro do padrão de uma referência de substituição (R9-B2, anterior ao diff).
- Sem escopo extra no diff.

## Verificações feitas

- `python -m pytest -q -p no:cacheprovider tests_python`: 2386 passaram em 57,1 s.
- `scratchpad/review9_probe.py` (`HOME`/`USERPROFILE` numa pasta temporária, `_READ`/`_READING` limpos antes de cada caso), via `handle` e `analyze`: R8-A1 em 13 tamanhos (cenário exato, fronteira do teto, dobras), R8-B1 em 9 Makefiles, falsos positivos da tabela acima.
- `scratchpad/review9_probe2.py`: substituição com lado direito grande por variável e literal, com pico de memória (`MEM=1`) e sem rastreio para o tempo.
- `scratchpad/review9_probe3.py`: pico de memória da lista de receitas expandidas antes da soma.
- Análises acima de 1 s via `handle`: só a de R9-B1 com 3,84 bilhões de caracteres (3,9 s, ask).
- Não verifiquei:
  - o comportamento real do Claude Code quando o hook passa do timeout ou o processo fica sem memória;
  - o comportamento real de make, porque nada foi executado;
  - a versão da rodada 8 rodando os casos de R9-B1: a comparação vem da leitura do diff (a linha removida já chamava `substitute` com o lado direito literal).

Resultado: aprovado com ressalvas
