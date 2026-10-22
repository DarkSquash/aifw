# Revisão independente: assessor-active

## Escopo

- Diff `review_active.diff` (619 linhas): `python/aifw/assessment.py`, `hooks.py`, `claude.py`, `cli.py`, `tests_python/test_assessor_active.py`, ADR-0036, `CHANGELOG.md`, `docs/claude-code.md`, `docs/routing.md`, `docs/cli-reference.generated.md` e a skill `aifw-workflow` (template e cópia do projeto).
- Spec: `proposal.md`, `design.md`, `threat-model.md`, `migration.md`, `specs/task-assessor.delta.yaml`; plano `docs/plans/2026-10-17-avaliador-de-tarefas.md`, seções 4, 5, 7 e 9.
- Padrões: `principle-catalogs/engineering-principles.yaml`, mais a lista básica de smells da skill `code-review`. Os eixos Standards e Spec foram feitos sem subagentes.
- Não revisei: o comportamento real do Claude Code quando um hook `UserPromptSubmit` estoura o timeout ou roda em modo `async`. Também não chamei o serviço real.

## Achados

### Alta

Nenhum.

### Média

**M1. `activate` usa a concordância arredondada e pode passar abaixo de 90%.** `python/aifw/assessment.py:296` (`activate`) compara `summary["agreement"]`, que `report()` arredonda para 3 casas (`assessment.py:707`). Já `criteriaMet` usa o valor exato.
- Cenário verificado: 209 vereditos com 188 concordâncias dão 89,95%. O relatório mostra `agreement 0.9` e `criteriaMet False`, mas `activate` passa e grava `.aifw/assessor.yaml`.
- Impacto: o critério de ativação pode ser violado, embora numa faixa estreita e só a partir de cerca de 200 vereditos. A lógica do critério também fica duplicada entre `report()` e `activate()` (Standards: `dry-stable-knowledge`). A correção é exigir `summary["criteriaMet"]` e usar os campos só para montar as mensagens.

**M2. O critério conta avaliações manuais, e não só os pedidos da pessoa.** O filtro de `report()` (`assessment.py:690-694`) só remove as mensagens automáticas com `source == "prompt"`. Os registros `source="manual"` de `aifw change assess --task ...`, que o agente roda e que a skill sugere, entram na contagem.
- Cenário verificado: 50 avaliações `manual` com veredito dão `judged 50` e `criteriaMet True`.
- Impacto: o design e o ADR dizem "contando só os pedidos da pessoa", e isso não vale para essas entradas. Os vereditos continuam humanos, então isso não basta para ligar o modo ativo sem a pessoa. Ainda assim, a evidência passa a incluir textos escritos pelo agente, e não pedidos reais (o plano 4.4 fala em "50 pedidos reais"). A correção é contar só `source == "prompt"` em `tasks`, ou documentar a exceção.

**M3. A ativação não fica presa ao modelo aprovado.** `activate` grava `model` (`assessment.py:302`), mas `activation()`/`active()` (`assessment.py:160-181`) não comparam esse valor com `settings(root)["model"]`.
- Cenário verificado: depois da ativação, trocar `spec.assessment.model` para `other/model-latest` mantém `active() == True`.
- Impacto: o plano (4.3) diz que trocar de versão do modelo exige uma nova avaliação. A troca pede confirmação, porque `aifw.yaml` é arquivo de controle, mas a pessoa pode aprovar uma edição de `aifw.yaml` sem perceber que isso mantém ligado o modo ativo de outro modelo. A correção é exigir `entry["model"] == settings(root)["model"]` em `activation()`.

### Baixa

**B1. Falhas que não são `AifwError` somem sem aviso.** `user_prompt` (`hooks.py:547-552`) converte só `AifwError` no aviso de indisponível. Outros erros chegam a `handle()` (`hooks.py:575-578`), que devolve `None`.
- Cenário verificado: com uma resposta malformada do serviço (`KeyError`), um `ValueError` ou uma linha corrompida em `shadow.jsonl`, o pedido segue sem nenhum contexto.
- Impacto: o pedido nunca é bloqueado, o que atende ao critério. Mas o agente não recebe o aviso que o ADR promete ("o contexto só avisa"); Standards: `clean-code-errors`. Com o log corrompido, toda delegação a Haiku pede confirmação, em qualquer sessão. Isso falha de forma segura, mas gera falso positivo. A correção é `except Exception` em `user_prompt`, com o aviso.

**B2. O pior caso de `decide` passa do timeout do hook.** São 3 tentativas de 15 s, com pausas de 1 s e 2 s, ou seja, cerca de 48 s (`assessment.py:194-202`). Já o hook síncrono tem 30 s (`claude.py:44`).
- Cenário: com o serviço lento, o Claude Code mata o hook antes do aviso, e o pedido segue sem contexto. O design admite isso, mas o ADR e a skill dizem que a falha "só avisa".
- Impacto: mais 30 s de espera, e o aviso não chega. Não verifiquei o comportamento do Claude Code no timeout. A correção é um orçamento de tempo menor no modo ativo, por exemplo uma tentativa só ou um timeout de 8 s.

**B3. Um hook síncrono pode ficar instalado sem o modo ativo.** Se a pessoa apaga `.aifw/assessor.yaml` sem rodar `aifw claude enable` (ou a assinatura deixa de valer), o hook continua síncrono e roda a avaliação sombra em primeiro plano, com 30 s em vez de 60. `aifw claude check` acusa isso (verificado), e o rollback documentado inclui o `enable`.
- Impacto: latência, e as avaliações sombra lentas são cortadas.

**B4. Docstrings desatualizadas.** A docstring do módulo (`assessment.py:1`) ainda diz que as avaliações "never decide", e `enabled()` (`assessment.py:161`) fala só de "shadow assessment". `SHADOW_LOG` passou a guardar também os registros do modo ativo (Mysterious Name, por julgamento).

**B5. Lacunas nos testes.**
- A recusa por concordância abaixo de 90% sem CRITICAL rebaixado não tem teste próprio: `test_activation_needs_agreement_and_no_demoted_critical` só exercita o CRITICAL, com 98% de concordância.
- O aviso "assessor is active" do início de sessão não é testado.
- A falha que não é `AifwError` (B1) também não é testada.

### Informativo

- **I1.** A regra de delegação só reconhece Haiku pelo campo `model`, uma heurística anterior a esta mudança. `subagent_type="Explore"` sem `model` não pede confirmação. Não verifiquei se esse agente roda em Haiku por padrão.
- **I2.** O custo de `last_path` é aceitável. Com um log de 8,4 MB (cerca de 20 mil registros), a delegação a Haiku levou 0,15 s, e as outras delegações não leem o log. Ele só é lido com o modo ativo e `haiku` no modelo.
- **I3.** `docs/routing.md` diz "assina `.aifw/assessor.yaml`" sem a ressalva "quando `requireSignedCommit` está ligado", que o ADR e o CHANGELOG trazem.
- **I4.** A ativação fica num arquivo próprio, e não em `mode: active` no `aifw.yaml` (plano, seção 5). Isso é um desvio consciente, justificado no design. A exigência de "suíte aprovada" (`assess eval`, plano 4.4) não entrou no critério, e nem a proposta nem o ADR dizem isso.

## Verificações feitas

- Suíte completa: `python -m pytest -q -p no:cacheprovider tests_python` deu `2415 passed in 44.27s`.
- Script `active_review_probe.py`, no scratchpad da sessão, rodado em projetos temporários criados com `test_workflows.init` e com `assessment.decide` simulado, sem rede:
  - **Caminhos para o agente ligar o modo ativo sozinho:**
    - `aifw assess activate` foi negado em Bash, `python -m aifw`, `uv run` e PowerShell.
    - `python w.py`, que grava o arquivo, e `python act.py`, que chama `activate()`, foram negados.
    - `echo >`, `cp`, `Set-Content`, `python -c`, Write e Edit no arquivo, inclusive por caminho absoluto e com `./`, pedem confirmação.
    - Gravar em `.aifw/assessments/verdicts.jsonl` pede confirmação.
    - Com `requireSignedCommit`, a ativação sem assinatura não vale; isso é coberto por teste, e o teste passa.
  - **Critério:** confirmei M1 e M2.
  - **Resiliência:** confirmei B1. Nenhum caso bloqueou ou travou o pedido.
  - **Modelo:** confirmei M3.
  - **Delegação:**
    - Haiku depois de PLANNED pede confirmação na mesma sessão, com `haiku` ou `claude-haiku-4-5`.
    - Não pede em outra sessão, sem sessão ou com `sonnet`.
    - Depois de um caminho FAST na mesma sessão, deixa de pedir.
  - **`claude enable`/`check`:**
    - No modo sombra, o hook é `async` com 60 s.
    - Com a ativação, o `check` acusa a diferença, e o `enable` instala o hook síncrono de 30 s.
    - Ao apagar a ativação, o `check` acusa de novo, e o `enable` volta ao `async`.
- Leitura de todo o diff, contra a proposta, o delta, o ADR e o plano. A cópia da skill no projeto é igual ao template, a menos do marcador de versão.
- Regressões: as outras avaliações continuam em modo sombra (`ACTIVE_FEATURES = ("tasks",)`), e `review_decisions` etc. ainda devolvem `mode="shadow"`. A remoção de `mode="shadow"` do retorno de `assess` não quebrou nenhum teste. Os registros novos ganham `mode` e `session`, como diz a migração.

Resultado: aprovado com ressalvas
