# ADR-0026 — Seleção de contexto avaliada em modo sombra

- Status: accepted
- Date: 2026-10-18
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

`context select` escolhe documentos por palavras em comum entre a tarefa e o caminho ou o assunto de cada documento, além dos obrigatórios e dos ligados a arquivos alterados. Ele perde sinônimos ("segredos" e "senhas") e traz documentos que só compartilham uma palavra. O plano `docs/plans/2026-10-17-decider-outros-pontos.md` (seção 4) propõe usar o Decider.

## Decisão

1. Com `context` em `spec.assessment.features`, cada `context select` pergunta ao Decider se cada documento indexado é relevante para a tarefa:
   - pergunta `noul`;
   - estado: a tarefa, o caminho e o assunto do documento, nunca o corpo;
   - uma requisição por documento, em paralelo.
2. Modo sombra:
   - a seleção não muda;
   - o resultado traz, em `assessment`, os documentos sugeridos (fora da seleção, com probabilidade de 0,5 ou mais) e os duvidosos (escolhidos só por palavra, com probabilidade abaixo de 0,1);
   - tudo vai para `.aifw/assessments/context.jsonl`.
3. Documentos obrigatórios, os ligados a arquivos alterados e as dependências deles nunca são marcados como duvidosos.
4. Relatório e vereditos com `--feature context`. O veredito `model` significa que a seleção ajustada é pelo menos tão boa quanto a atual; `keyword`, que a atual é melhor. O critério de ativação é o mesmo do avaliador de tarefas.

## Primeira rodada da suíte (2026-10-18)

Suíte: `evals/assessment/context-cases.yaml`, com 20 tarefas reais deste repositório e o gabarito do agente.

| Seleção | Cobertura média dos esperados | Precisão média | Documentos por tarefa |
| --- | --- | --- | --- |
| Por palavras (atual) | 42% | 30% | 4,5 |
| Ajustada pelo modelo | **82%** | 28% | 7,1 |
| Só o modelo | 80% | 31% | 5,9 |

- Em 8 das 20 tarefas, a seleção por palavras não achou nenhum documento esperado. A ajustada achou pelo menos um em todas.
- Nenhum documento marcado como duvidoso estava no gabarito.
- Os erros do modelo vêm de assuntos pouco descritivos. `docs/claude-code.md`, cujo assunto é só "AIFW no Claude Code", recebeu de 0,04 a 0,08 em tarefas sobre o hook e a allowlist.
- Custo da rodada: US$ 0,003, com cerca de 1 160 perguntas.

## Consequências

- Uns 58 pedidos por `context select` neste repositório (US$ 0,0002 e de 1 a 2 s).
- A qualidade depende do assunto de cada documento. Um assunto mais descritivo (campo `scope` nos metadados) melhora a avaliação.
- Sem chave, sem rede, fora de projeto AIFW ou com o recurso desligado, `context select` funciona como antes.

## Rollback

Tirar `context` de `spec.assessment.features` e desfazer as mudanças listadas.
