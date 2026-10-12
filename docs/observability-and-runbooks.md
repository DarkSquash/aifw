# Observabilidade e runbooks

Observabilidade faz parte da feature quando o comportamento opera em produção. Ela não é “adicionar logs”; é tornar perguntas operacionais respondíveis sem expor dados.

## Plano de sinais

Para cada fluxo crítico defina:

- SLI/SLO e janela;
- métricas de volume, erro, latência e saturação;
- logs estruturados com correlation ID e política de redaction;
- traces nas fronteiras relevantes;
- erros visíveis ao usuário e códigos internos;
- dashboards, alertas, owner e custo de cardinalidade;
- teste do sinal e condição de rollback.

Frontend inclui Web Vitals/erros de interação quando relevantes; backend inclui dependências, filas, banco e rate limit. Métricas sem ação associada não justificam alerta.

## Runbook mínimo

Um runbook contém trigger/sintomas, impacto, prerequisites, diagnóstico seguro, mitigação, rollback, recovery, validação, escalada, comunicação e follow-up. Comandos destrutivos são claramente marcados e exigem a policy correspondente.

Runbooks entram no catálogo/PROJECT_MAP quando protegem um fluxo material. Mudança de arquitetura ou observabilidade atualiza o runbook na mesma Change Case.

## Incidentes

Durante incidente, preservar evidência e reduzir dano tem prioridade. Break-glass continua limitado. Após recuperação, registrar timeline, causa, gaps de detecção, ações com owner e mudanças de policy/teste; nunca converter postmortem em culpa individual.
