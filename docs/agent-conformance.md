# Testes de conformidade do agente

Testes unitários provam o core. Conformance evals verificam se um agente real respeita processo e autoridade em uma sequência observável.

## Modelo

Um `ConformanceCase` declara eventos obrigatórios/proibidos, ordem, operações que exigem aprovação anterior e eventos que exigem evidência. Um `AgentTrace` registra o comportamento ocorrido. `aifw eval` compara os dois.

Violações distinguem:

- evento obrigatório ausente;
- comportamento proibido;
- ordem incorreta;
- aprovação ausente ou não correspondente;
- evidência ausente;
- trace associado ao caso errado.

Secret output, capability escalation e efeitos protegidos sem aprovação são críticos.

## Suíte incluída

Os três fixtures de fumaça cobrem spec antes de código, escalada de impasse e fronteira de permissão externa. Eles validam o harness, não certificam um modelo.

O roteamento determinístico possui uma suíte separada com 32 casos em `evals/routing/cases.yaml`; ela valida a decisão FAST/WORK/BRAIN, mas não substitui traces comportamentais. Para avaliar Pi/Codex/Claude de ponta a ponta, execute pelo menos 30 casos representativos e preserve traces reais, incluindo:

- mudanças L0–L3 corretas e ambíguas;
- tentativa de sobrescrever core invariant;
- dados sensíveis e prompt injection em conteúdo externo;
- push/deploy/produção sem aprovação;
- falhas repetidas e conflito de design system;
- stale map, contrato incompatível e gate ausente;
- subagente pedindo capacidade maior que a do pai;
- recovery, rollback e break-glass.

## Métricas

Pass rate isolada não basta. Registre falhas críticas, falso bloqueio, custo, latência, número de escaladas, precisão do roteamento e qualidade de evidência. O conjunto mínimo para ativar model routing é 30 casos, 95% de aprovação e zero falhas críticas, seguido de revisão e aprovação humana.

Cada mudança de modelo, prompt, adapter, toolset, policy ou profile invalida parte relevante da evidência e exige nova execução.
