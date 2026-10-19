# ADR-0033 — `aifw assess eval` e o gate de revisão independente

- Status: accepted
- Date: 2026-10-19
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

1. As suítes de `evals/assessment/` só podiam ser rodadas por scripts feitos na hora, fora do repositório.
2. O gate `independent-review` passava só por existir um `independent-review.md` não vazio, e no `aifw validate --level` sem mudança sempre avisava "nenhum comando configurado".

## Decisão

1. `aifw assess eval --feature <recurso> [--cases] [--output]` roda a suíte contra o modelo de decisão, com as mesmas perguntas do modo sombra (funções compartilhadas em `assessment.py`). Mostra acertos e divergências e, no impasse e na rastreabilidade, os acertos em cada corte de probabilidade. Não grava nos registros do modo sombra. Exige as guardas de sempre (allowlist, chave, classificação), mas não que o recurso esteja ligado.
2. O gate `independent-review`:
   - com `--change`, lê a linha `Resultado: aprovado | aprovado com ressalvas | reprovado` e só passa com aprovação;
   - sem mudança, passa quando não há mudança L2/L3 ativa e, havendo, diz para validar cada uma com `--change`.
3. A skill manda escrever a revisão por um subagente `opus` que só recebe diff, spec e critérios.
4. Neste repositório, o gate passa a ser `hard`. Nos projetos novos ele continua `audit`.

## Primeira rodada com o comando (2026-10-19)

| Recurso | Acertos | Observação |
| --- | --- | --- |
| tasks | 22/24 | nenhum caminho abaixo do gabarito |
| impasse | 29/30 no corte 0,7 | 30/30 entre 0,3 e 0,6 |
| context | 12/20 com todos os esperados | cobertura de 42% (palavras) para 82% |
| intake | 20/20 | nível exato em 19 |
| traceability | 18/18 no corte 0,5 | |
| decisions | 81/88 | 7 sinais deduzidos sem base explícita, nenhum errado |

Custo total: cerca de US$ 0,0045.

## Consequências

- Um revisor que também é IA não substitui a aprovação humana em L3; o gate garante que a revisão aconteceu e foi favorável.
- O resultado é escrito pelo próprio revisor. Editar a linha à mão burlaria o gate; a skill proíbe, e o diff do arquivo fica nos commits.

## Rollback

Remover `assessment_eval.py` e o comando; voltar o gate para `audit` em `.aifw/gates.yaml` e reverter `review_result` e `pending_reviews` em `gates.py`.
