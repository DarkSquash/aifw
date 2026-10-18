# Plano: avaliador de tarefas com o Decider v1.2

- Status: modo sombra implementado (ADR-0023); modo ativo aguarda o relatório dos 50 pedidos
- Data: 2026-10-17
- Impacto previsto: L3 (núcleo do framework e serviço externo)

## 1. Objetivo

Hoje o AIFW classifica uma mudança por sinais declarados pelo agente (`change classify --<sinal>`) e por fatos tirados do diff (`--diff`). Não há avaliação do pedido em si, e as dimensões de importância e complexidade não existem.

Proposta: usar o `perplexity/pplx-decider-v1.2`, pelo OpenRouter, para avaliar o pedido em três etapas (risco, importância e complexidade). Uma regra fixa transforma essas avaliações no caminho de execução: FAST, WORK, PLANNED ou CRITICAL.

## 2. Evidência até aqui

Testes feitos em 2026-10-17, gasto total abaixo de US$ 0,01:

| Teste | Resultado |
| --- | --- |
| Nível de risco, 30 pedidos em texto | Decider 30/30, Jev 1.14 29/30 |
| Rota pedida direto ao modelo, 32 casos | Decider 26/32, Jev 19/32; erros sempre para baixo |
| Modelo extrai sinais, regra decide a rota | 32/32 |
| Três etapas e caminho, 24 tarefas de L0 a L3 | risco 22/24 (desvios para cima), caminho 21/24 |
| Caminho decidido só com as avaliações gravadas, sem o texto | idêntico à regra fixa em 24/24 |

Na revisão humana do último teste, a maioria das respostas do modelo foi considerada correta. Onde houve discordância, ele foi conservador. O caso da busca aproximada (#10) foi reavaliado como complexidade **moderada**, então o modelo acertou e o gabarito estava errado.

Conclusões:

- o modelo é bom em avaliar o pedido;
- a decisão final não precisa de modelo: com as avaliações em mãos, a regra fixa dá o mesmo resultado, sem custo e de forma previsível.

## 3. Desenho

```
pedido em texto ──► etapa 1: risco (L0–L3)        ┐
                ──► etapa 2: importância (4 níveis) ├─► gravado em arquivo ──► regra fixa ──► caminho
                ──► etapa 3: complexidade (4 níveis)┘           ▲
diff do git ──► sinais verificáveis (auth, deploy, contratos, controle) ──► piso de risco
```

- As três etapas são requisições separadas e independentes, que rodam em paralelo (cerca de 1 s no total). Uma pergunta não contamina a outra.
- As respostas, com as probabilidades, ficam gravadas em arquivo. A regra lê o arquivo; o texto do pedido não entra na decisão final.
- Tabela da regra, a mesma do teste:

| Caminho | Quando | Planeja | Executa | Revisa |
| --- | --- | --- | --- | --- |
| FAST | risco L0, complexidade trivial ou simples, importância baixa ou média | — | Haiku | testes e gates |
| WORK | risco L1; ou L0 com complexidade moderada ou alta, ou com importância alta ou crítica | — | Sonnet | testes e gates |
| PLANNED | risco L2; ou L1 com complexidade alta | Opus | Sonnet | Opus |
| CRITICAL | risco L3 | Opus | Opus | revisor independente e humano |

## 4. Decisões propostas (revisar)

1. **Autoridade do modelo** (aprovado, com o piso):
   - Importância e complexidade: a avaliação do modelo vale como está, inclusive quando fica abaixo do palpite do agente, porque hoje não existe regra para essas dimensões.
   - Risco: o modelo também pode ficar abaixo do palpite do agente. O único limite é um **piso** dado pelos fatos verificáveis do diff, que já existem hoje em `derive_signals`: arquivo de autenticação ou segurança, deploy, contrato compartilhado, arquivos de controle do AIFW, constituição. Se o diff toca um arquivo de autenticação, o risco não cai abaixo de L2, diga o modelo o que disser.
   - Motivo do piso: o texto do pedido pode conter "isso é só um ajuste trivial". Isso não deve baixar o risco de uma mudança que comprovadamente mexe em segurança.
   - Alternativa sem piso: o modelo decide tudo. É mais simples, mas fica exposto a texto enganoso.
2. **Regra fixa para o caminho**, sem modelo na etapa 4.
3. **Modelo fixado por versão** (`pplx-decider-v1.2`), nunca `-latest`. Trocar de versão exige rodar a suíte de avaliação de novo.
4. **Duas fases** (aprovado), como já acontece com a ativação de roteamento:
   - **Sombra:** avalia e registra, sem mudar o caminho. Serve para comparar com as suas decisões reais.
   - **Ativo:** o caminho passa a sair da avaliação. A ativação exige a suíte aprovada e a sua aprovação no terminal, como `route activate`.
   - **Critério para ativar:**
     - 50 pedidos reais em sombra;
     - concordância de pelo menos 90% entre o caminho do avaliador e o caminho escolhido por você;
     - nenhum caso CRITICAL rebaixado.
   - **Relatório ao fim da sombra:** `aifw assess report` gera a mesma tabela usada na revisão dos testes. Para cada pedido, mostra:
     - as perguntas;
     - a resposta do modelo em cada etapa, com a confiança;
     - o caminho dele e o caminho escolhido por você;
     - as divergências.

     Ao atingir 50 pedidos, o aviso de início de sessão passa a dizer que o relatório está pronto, para o agente trazê-lo a você.
5. **Sem a chave, sem internet ou com erro:** tudo continua como hoje, com um aviso. O avaliador nunca bloqueia o trabalho.

## 5. Configuração

Em `aifw.yaml` (schema `project-manifest`):

```yaml
spec:
  assessment:
    provider: openrouter
    model: perplexity/pplx-decider-v1.2
    mode: shadow        # off | shadow | active
```

- A chave vem só da variável `OPENROUTER_API_KEY`, nunca de arquivo do projeto.
- `mode: active` só é aceito depois de `aifw assess activate` (aprovação humana, assinada quando `requireSignedCommit` estiver ligado).

## 6. Privacidade e permissões

- O texto do pedido sai da máquina para o OpenRouter e para a Perplexity. Diffs e código não são enviados.
- O avaliador só chama a API se `openrouter` estiver em `spec.externalAllowlist`, com domínio `openrouter.ai` na tabela de serviços.
- Com `dataClassification` `confidential` ou `restricted`, o avaliador se recusa a rodar.
- Atenção: o hook trata `aifw` como comando de leitura, então não enxerga a chamada de rede. A checagem de allowlist e de classificação precisa estar **dentro** do próprio comando.

## 7. Interface

- `aifw change assess --task "<pedido>" [--diff] [--change <id>] [--json]`:
  - roda as três etapas e devolve as avaliações com probabilidades, o piso do diff e o caminho;
  - com `--change`, grava `evidence/assessment.json` na mudança.
- `aifw assess report`: o relatório da sombra descrito em 4.4. Para cada pedido, você pode registrar o caminho que considera certo com `aifw assess verdict --id <pedido> --path <caminho>`.
- `aifw assess eval [--cases <arquivo>]`: roda a suíte de avaliação e mostra a taxa de acerto por etapa e quantas respostas ficaram abaixo do esperado.
- `aifw assess activate --report <arquivo> --by human:<nome>`: aprovação humana para sair da sombra.
- Skill `aifw-workflow`: passa a chamar `change assess` no início de cada pedido e a seguir o caminho resultante, mantendo a tabela de modelos como já está.

## 8. Implementação

1. `python/aifw/assessment.py`:
   - as perguntas, a regra, a chamada HTTP com `urllib`, sem dependência nova;
   - timeout de 15 s e até 2 novas tentativas;
   - as três chamadas em paralelo.
2. Schema: `spec.assessment` em `project-manifest.schema.json`, e `assessment.json` como documento validado.
3. Suíte `evals/assessment/cases.yaml`:
   - as 24 tarefas, já com o gabarito corrigido por você (#10 com complexidade moderada e caminho WORK);
   - mais casos reais seus ao longo da fase sombra.
4. Testes com HTTP simulado:
   - regra e piso do diff;
   - recusa por allowlist e por classificação de dados;
   - comportamento sem chave e com erro de rede;
   - gravação da evidência.
5. Documentação:
   - `routing.md` e `claude-code.md`;
   - `HOW_TO_USE.md`, com a chave na lista de dependências opcionais;
   - ADR-0023, CHANGELOG e nota de migração.
6. Pelo próprio AIFW, como mudança L3: `spec new`, threat model, revisão independente e a sua aprovação.

## 9. Custo e latência

- Cerca de US$ 0,00001 por pedido (três chamadas), ou seja, um centavo a cada mil pedidos.
- Cerca de 1 s por pedido, com as chamadas em paralelo.

## 10. Riscos e perguntas em aberto

- **Texto enganoso no pedido:** mitigado pelo piso do diff. Sem diff, no começo de uma tarefa, não há piso.
- **Dependência de fornecedor:** se a Perplexity tirar o modelo do ar, o AIFW volta ao comportamento atual. Vale ter um segundo modelo avaliado como reserva.
- **Importância é subjetiva:** as descrições dos níveis devem vir do Charter do projeto, como prazos, receita e usuários.

## 11. Outros encaixes do Decider no AIFW

Avaliados pelo que o código faz hoje. Todos seguem a mesma linha:
- o modelo avalia, e uma regra ou uma pessoa decide;
- sem chave ou sem rede, o comportamento atual continua;
- nada de código, diff ou segredo sai da máquina, só texto que o projeto já trata como documentação.

| Prioridade | Onde | Como funciona hoje | Com o Decider |
| --- | --- | --- | --- |
| 1 | **Seleção de contexto** (`context select`) | Escolhe documentos por palavras em comum entre a tarefa e o nome ou escopo do documento: perde sinônimos e traz falsos positivos | Pergunta `noul` por documento ("este documento é relevante para a tarefa?") sobre o título e o escopo. A Perplexity relata bons resultados do modelo em reordenar resultados de busca. Documentos obrigatórios continuam sempre incluídos |
| 2 | **Impasse: tentativa realmente diferente** (`impasse attempt`) | Compara hipótese e intervenção como texto normalizado: reescrever a mesma ideia com outras palavras conta como tentativa nova e adia o congelamento | Pergunta `noul` contra cada tentativa anterior ("a nova hipótese é materialmente igual a esta?"). Se o modelo achar igual, o hook pede confirmação. Só pode antecipar o congelamento, nunca adiar |
| 3 | **Intake: resposta suficiente** (`intake status`) | Só verifica se o campo do Charter está preenchido: "a definir" passa | Pergunta `score` por campo ("a resposta é específica o bastante para guiar decisões?"). Respostas vagas viram nova pergunta da entrevista. A aprovação continua sendo sua |
| 4 | **Rastreabilidade da spec** (`spec analyze`) | Confere se cada requisito tem cenário e teste ligados, não se o cenário cobre o requisito | Pergunta `noul` por par requisito e cenário, sobre os textos da spec. Os pares fracos viram avisos, não bloqueios |
| 5 | **Catálogos de decisão** (`decision recommend`) | Recebe os sinais da decisão digitados à mão | Extrai os sinais do Charter e do pedido, com perguntas `noul` por critério do catálogo. O ADR e a aprovação continuam humanos |

Lugares onde **não** recomendo usar:
- **Hook de cada ação:** acrescentaria cerca de 1 s a cada comando e mandaria comandos, que podem conter segredos, para fora da máquina. Também abriria espaço para um texto no comando convencer o modelo a liberar a ação.
- **Secret scan:** enviaria o possível segredo justamente para fora.
- **Revisão de código e princípios:** exige mandar código e diffs para fora, e a revisão independente com Opus já cobre isso.
