# Storybook/component workbench policy

## Component contract

- propósito e quando não usar;
- props/slots/events públicos;
- semantic tokens consumidos;
- keyboard/focus/ARIA contract;
- responsividade, conteúdo longo e localização;
- owner e estabilidade.

## Stories obrigatórias quando aplicáveis

Default, hover/focus/active, disabled, loading, empty, error, long content, narrow viewport, reduced motion, high contrast e density variants.

## Gates

- build estático;
- interaction tests;
- automated accessibility checks;
- visual regression em viewports definidos;
- revisão humana para mudança estética global.

Uma story não é implementação duplicada. Ela importa o componente real. Exceção ao design system referencia rule ID, Change Case/waiver e expiração quando temporária.
