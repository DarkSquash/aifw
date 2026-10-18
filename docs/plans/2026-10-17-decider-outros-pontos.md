# Plano: o Decider em outros cinco pontos do AIFW

- Status: aprovado em 2026-10-18 (ordem da seção 2; corte do impasse em 0,7; critério de ativação igual ao do avaliador)
- Data: 2026-10-17
- Base: o avaliador de tarefas em modo sombra (ADR-0023), que já tem a chamada ao OpenRouter, as guardas de privacidade e o registro em arquivo

## 1. Regras comuns aos cinco

1. **O modelo avalia; uma regra ou uma pessoa decide.** Nenhum dos cinco pontos deixa o modelo liberar algo que hoje é bloqueado.
2. **Primeiro sombra, depois ativo.** Cada ponto começa só registrando o que faria, ao lado do que o AIFW fez. A ativação de cada um é uma decisão sua, depois de um relatório como o do avaliador de tarefas.
3. **Sem chave, sem rede ou com erro:** o comportamento atual continua, com um aviso.
4. **Mesmas guardas do avaliador:**
   - `openrouter` na allowlist;
   - chave na variável `OPENROUTER_API_KEY`;
   - dados que não sejam `confidential` nem `restricted`.

   Só sai da máquina texto que o projeto já trata como documentação (pedido, Charter, specs, hipóteses de impasse); nunca código, diff ou segredo.
5. **Um interruptor por ponto** em `aifw.yaml`:

   ```yaml
   spec:
     assessment:
       mode: shadow
       features: [tasks, impasse, context, intake, traceability, decisions]
   ```
6. **Infraestrutura compartilhada:**
   - a função de chamada do `assessment.py` passa a aceitar qualquer conjunto de perguntas;
   - cada ponto grava em `.aifw/assessments/<ponto>.jsonl`;
   - `aifw assess report --feature <ponto>` mostra perguntas, respostas e vereditos no mesmo formato de hoje.
7. **Uma suíte de avaliação por ponto**, com gabarito revisado por você antes de rodar, como fizemos com as 24 tarefas.

## 2. Ordem sugerida

| Ordem | Ponto | Por quê |
| --- | --- | --- |
| 1 | Impasse: tentativa realmente nova | Menor mudança, risco zero (só antecipa congelamento) e corrige uma brecha real |
| 2 | Seleção de contexto | Maior ganho no dia a dia; o modelo é forte em reordenar resultados de busca |
| 3 | Intake: resposta suficiente | Melhora a entrevista; não bloqueia nada |
| 4 | Rastreabilidade da spec | Útil em L2/L3, que são menos frequentes |
| 5 | Catálogos de decisão | Uso raro; depende de catálogos bem descritos |

## 3. Impasse: tentativa realmente nova

- **Hoje** (`impasse.py`): uma tentativa repetida é detectada comparando hipótese e intervenção como texto normalizado. Reescrever a mesma ideia com outras palavras conta como tentativa nova e adia o congelamento.
- **Com o Decider:** ao registrar uma tentativa (`aifw impasse attempt`), uma pergunta `noul` contra cada tentativa anterior do mesmo caso:
  - "A nova hipótese e intervenção são, na prática, as mesmas desta tentativa anterior?"
  - estado enviado: as duas hipóteses e intervenções, só o texto.
- **Regra:**
  - sombra: grava a probabilidade ao lado da tentativa;
  - ativo: com probabilidade de 0,7 ou mais, a tentativa conta como repetição, o que pela regra atual abre o impasse na hora.

  O modelo só pode antecipar o congelamento, nunca adiar.
- **Custo:** uma chamada por tentativa anterior; no máximo umas 5 por caso.
- **Suíte:** 30 pares de tentativas, metade reescritas da mesma ideia e metade realmente diferentes.
- **Testes:** paráfrase detectada; tentativas diferentes não detectadas; sem chave, comportamento atual.

## 4. Seleção de contexto

- **Hoje** (`context.select_context`):
  - escolhe documentos por palavras em comum entre a tarefa e o caminho ou escopo do documento;
  - inclui os obrigatórios e os ligados aos arquivos alterados.

  Perde sinônimos ("login" e "autenticação") e traz documentos que só compartilham uma palavra.
- **Com o Decider:** uma pergunta `noul` por documento indexado:
  - "Este documento é relevante para a tarefa?"
  - estado: a tarefa, mais o título e o escopo do documento (não o corpo).
  - Uma requisição por documento, como a Perplexity recomenda para candidatos independentes, todas em paralelo.
- **Regra:**
  - sombra: o resultado traz `modelSuggested` (relevantes para o modelo e ausentes da seleção) e `modelDoubtful` (selecionados só por palavra e com probabilidade baixa), sem mudar a seleção;
  - ativo:
    - inclui os sugeridos com probabilidade de 0,5 ou mais;
    - remove um documento selecionado só por palavra quando a probabilidade fica abaixo de 0,1;
    - nunca remove obrigatórios, nem os ligados a arquivos alterados, nem as dependências deles.
- **Custo:** cerca de 150 tokens por documento. Com 60 documentos, uns US$ 0,0002 por tarefa, em 1 a 2 s.
- **Suíte:** 20 tarefas reais deste repositório, com a lista de documentos esperados revisada por você. Métricas: quantos esperados foram encontrados e quantos selecionados eram irrelevantes.

## 5. Intake: resposta suficiente

- **Hoje** (`intake.assess_charter`): só verifica se cada campo do Charter está preenchido. "A definir" passa.
- **Com o Decider:** para cada campo respondido (problema, públicos, resultados, escopo dentro e fora), uma pergunta `score`:
  - "A resposta é específica o bastante para guiar decisões de produto?"
  - níveis: vaga, parcial, específica.
  - estado: a pergunta do intake e a resposta.
- **Regra:**
  - `intake status` passa a listar `weakAnswers`, com o campo e o nível;
  - a skill usa essa lista como próximas perguntas da entrevista (`grilling`);
  - **não bloqueia** o `ready` nem a sua aprovação: é um aviso.
- **Custo:** umas 6 chamadas por `intake status`, só quando o Charter muda (o resultado fica em cache pelo hash do Charter).
- **Suíte:** 20 respostas de Charter, de vagas a específicas, com o nível revisado por você.

## 6. Rastreabilidade da spec

- **Hoje** (`specs.analyze_change`): confere se cada requisito tem cenário e teste ligados e se os arquivos existem. Não confere se o cenário realmente cobre o requisito.
- **Com o Decider:** uma pergunta `noul` por par de requisito e cenário ligados:
  - "Este cenário verifica o comportamento exigido por este requisito?"
  - estado: o texto do requisito e o do cenário, ambos da spec.
- **Regra:**
  - pares com probabilidade abaixo de 0,5 viram o achado `WEAK_TRACE`, com severidade **aviso**;
  - nunca bloqueia o archive;
  - o achado entra no relatório do `spec analyze` e na revisão independente.
- **Custo:** uma chamada por ligação; uma mudança L2 típica tem de 5 a 20.
- **Suíte:** 30 pares de specs arquivadas deste repositório, metade com cenários trocados de propósito.

## 7. Catálogos de decisão

- **Hoje** (`catalogs.recommend_decision`): recebe os sinais da decisão digitados à mão (`--signals`) e ranqueia as alternativas do catálogo.
- **Com o Decider:** para cada critério do catálogo da categoria, uma pergunta `noul`:
  - "Este critério se aplica ao projeto?"
  - estado: o Charter e o pedido.
- **Regra:**
  - `decision recommend --suggest-signals` mostra os sinais sugeridos, com probabilidade, e o ranking que resultaria deles;
  - os sinais só entram no ranking se você confirmar, com `--signals` como hoje;
  - o ADR e a aprovação continuam humanos.
- **Custo:** um critério por chamada; um catálogo tem de 5 a 15.
- **Suíte:** 10 projetos fictícios com os sinais esperados por categoria.

## 8. Entregas por ponto

Cada ponto é uma mudança separada, com:
- o código no módulo correspondente, usando a chamada compartilhada;
- testes com HTTP simulado (guardas, regra, sombra, falha de serviço);
- a suíte de avaliação com o gabarito revisado por você e um relatório da primeira rodada;
- documentação, CHANGELOG e um ADR curto, ou uma emenda ao ADR-0023.

## 9. Decisões

1. Ordem: a da seção 2. (Decidido.)
2. Cortes de probabilidade: 0,7 no impasse, 0,5 e 0,1 no contexto, 0,5 na rastreabilidade. Eles podem ser recalibrados pela suíte de cada ponto. (Decidido.)
3. Critério de ativação: o mesmo do avaliador, 50 casos com veredito e 90% de concordância. (Decidido.)
