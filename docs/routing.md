# Roteamento FAST/WORK/BRAIN

`aifw route explain` classifica uma tarefa por impacto, operação, incerteza e tentativas falhas, e recomenda uma classe cognitiva.

| Classe | Alias | Uso típico |
| --- | --- | --- |
| FAST | haiku | leitura única, classificação simples, docs/discovery de baixa incerteza |
| WORK | sonnet | implementação, testes, revisão e pesquisa comuns |
| BRAIN | opus | arquitetura, L3, alta incerteza, impasse ou falhas repetidas |

Aliases não são competências garantidas e podem apontar para outros modelos em `.aifw/routing.yaml`. L3 sempre recomenda BRAIN; uma tarefa L0 semanticamente difícil também pode usar BRAIN. O impacto continua L0.

## No Claude Code

O Claude Code não troca o modelo da sessão a pedido do AIFW. A skill `aifw` distribui planejamento, execução e revisão entre subagentes (parâmetro `model` da ferramenta Agent), usando a linha mais alta que se aplicar:

| Situação | Planeja | Executa | Revisa |
| --- | --- | --- | --- |
| impacto L3 ou rota BRAIN | opus | opus, ou sonnet com plano passo a passo | revisor independente opus + aprovação humana em L3 |
| impacto L2 | opus | sonnet | revisor independente opus |
| rota WORK | — | sonnet | testes e gates |
| rota FAST | — | haiku | testes e gates |

Revisão não substitui testes e gates, que rodam em toda classe. Trabalho trivial pode ser feito inline. Subir de modelo é permitido; L3 ou BRAIN nunca é rebaixado.

## Ativação

Projetos nascem com `enabled: false` e `mode: recommendation-only`. `aifw route activate` aceita relatório de conformidade e exige identidade + ADR/registro. O core recusa ativação com menos de 30 casos, pass rate abaixo de 95%, falha crítica ou aprovação ausente. Ativação escreve evidência na routing policy; não fica em conversa.

`aifw route eval --output <report.json>` executa a suíte determinística revisável em `evals/routing/cases.yaml`. Troca de modelo-alvo exige nova avaliação e nova aprovação (ADR-0003).
