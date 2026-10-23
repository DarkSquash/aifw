# Runbook: regressão crítica de model routing

- Owner: framework:core
- Service/catalog ID: component:core
- Severity: high
- Last verified: 2026-08-22

## Trigger

Conformance trace mostra falha crítica, seleção abaixo da competência necessária, efeito protegido sem aprovação ou custo/latência fora do limite aprovado.

## Mitigação segura

1. preservar relatório, trace, policy e versão do adapter/modelo;
2. restaurar em `.aifw/routing.yaml` os aliases da última tabela que passou na suíte, por Change Case L3 aprovado (o roteamento fica sempre ligado, ADR-0037);
3. subir de modelo nas tarefas afetadas até a correção;
4. reexecutar tarefa afetada com BRAIN/modelo competente sob revisão humana.

## Diagnóstico

Comparar input, impacto, rota, aliases, capabilities, prompt/toolset e decisões do evaluator. Não ajustar thresholds para esconder a falha.

## Recovery

Corrigir causa, adicionar caso de regressão, executar pelo menos o conjunto afetado e depois a suíte inteira. Trocar a tabela apenas com zero falhas críticas.
