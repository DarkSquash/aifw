# ADR-0003: Model routing desativado por padrão

- Status: superseded by ADR-0037 (roteamento sempre ligado)
- Date: 2026-08-22
- Impact: L3

## Contexto

Luna/Terra/Sol podem reduzir custo e latência, mas roteamento prematuro pode colocar decisões difíceis em modelo inadequado ou confundir impacto com complexidade.

## Decisão

Gerar apenas recomendação FAST/WORK/BRAIN. Ativação automática exige 30 casos, pass rate ≥ 95%, zero falhas críticas, avaliação de custo/latência/fallback e aprovação humana persistida.

## Consequências

O roteamento ainda NÃO foi configurado para execução automática. O adapter pode exibir sugestão, mas não selecionar modelo até policy ativada. Mudança de modelo/tool/prompt relevante pede nova avaliação; regressão crítica deve desativar o recurso.
