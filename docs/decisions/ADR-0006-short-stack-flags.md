# ADR-0006 — Flags curtas de stack no comando init

- Estado: aceito
- Data: 2026-08-23
- Dono: human:owner
- Impacto: L3 (interface pública da CLI e novo profile distribuído)

## Contexto

O `aifw init` criava `profiles: []`, obrigando humano ou agente a editar o manifesto depois da instalação. Os IDs internos `flutter-mobile` e `web-ts` são precisos para governança, mas são desnecessariamente técnicos para a interação inicial. Também não existia um profile Python distribuído.

## Decisão

1. Oferecer as flags públicas `--flutter`, `--web` e `--python` diretamente em `aifw init`.
2. Mapear `--flutter` para o ID interno `flutter-mobile` e `--web` para `web-ts`, preservando compatibilidade com projetos existentes.
3. Definir `--web` como entrada geral para React, JavaScript, TypeScript e outras stacks Web; decisões de framework continuam pertencendo ao projeto.
4. Adicionar o profile interno `python`, sem impor framework, gerenciador de ambiente, linter ou test runner universal.
5. Tratar as flags como stacks primárias mutuamente exclusivas durante o `init`.
6. Validar conflitos antes de criar qualquer arquivo.
7. Manter a ausência de flag válida: `profiles: []` permite que discovery e Intake recomendem a stack depois.

## Consequências

- O comando desejado passa a ser diretamente expressável: `aifw init --id app --name "Projeto" --flutter --existing`.
- Projetos antigos continuam válidos porque os IDs internos não foram renomeados.
- Novas stacks podem receber outra flag amigável sem alterar o contrato dos profiles existentes.
- Combinações full-stack deliberadas devem ser adicionadas depois do Intake, quando compatibilidade e responsabilidade de cada profile puderem ser verificadas; não são inferidas por duas flags primárias simultâneas.

## Alternativas rejeitadas

- Renomear imediatamente os diretórios e IDs internos: quebraria manifests, locks, recipes e referências existentes.
- Aceitar várias flags sem validação: criaria combinações possivelmente incompatíveis antes de discovery.
- Fazer `--web` significar somente React TypeScript: confundiria uma entrada amigável com uma decisão técnica específica demais.
