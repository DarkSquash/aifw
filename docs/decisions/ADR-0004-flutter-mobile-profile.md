# ADR-0004 — Profile Flutter Mobile e gates multiplataforma

- Estado: aceito
- Data: 2026-08-22
- Dono: human:owner
- Impacto: L3 (extensão do framework e do executor de gates)

## Contexto

O AIFW v0.1 possuía um profile Web TypeScript e um gate runner portátil para executáveis nativos e shims npm, mas não modelava projetos Flutter. No Windows, Flutter e Dart são normalmente expostos por arquivos batch; iniciá-los diretamente com `execFile` produz `spawn EINVAL`. Projetos Android+iOS também precisam distinguir código Dart compartilhado de evidência real dos toolchains nativos.

## Decisão

1. Adicionar um stack profile opcional `flutter-mobile` em vez de colocar regras Flutter no core independente de stack.
2. Detectar `pubspec.yaml`, uso do SDK Flutter e diretórios de plataforma durante discovery somente leitura.
3. Manter a arquitetura concreta do app como decisão do projeto. O profile não impõe estrutura de pastas, state manager ou padrão arquitetural universal; ele pode oferecer alternativas Flutter ao motor global de decisões.
4. Usar como gates L1: formatter Dart em modo check, `flutter analyze` e `flutter test`.
5. Fornecer receitas separadas: Windows com build Android e macOS com build iOS sem assinatura.
6. Exigir evidência macOS/Xcode para iOS. Windows, WSL ou sucesso Android não contam como substitutos.
7. Resolver executáveis e shims batch pelo `PATH` no Windows, incluindo Flutter, Dart e FVM, preservando execução sem shell implícito para os demais comandos.
8. Tratar WSL como executor separado, com SDK e caches próprios.

## Consequências

- Projetos Flutter podem usar resolução de policies, audit e gates específicos sem fork do AIFW.
- O loop L1 continua rápido e não exige dispositivo.
- Integração em dispositivo, assinatura e distribuição permanecem project-specific e sujeitos a permissões.
- Apps iOS precisam de um executor macOS local ou em CI antes que a compatibilidade iOS seja declarada.
- Alterações futuras nos comandos do Flutter/Dart exigem atualização do profile, testes do gate runner e nova validação do projeto piloto.

## Alternativas rejeitadas

- Colocar Flutter nas core policies: quebraria a independência de stack.
- Forçar Clean Architecture ou uma biblioteca de estado: conhecimento específico demais para todos os projetos Flutter.
- Executar todos os gates via shell: ampliaria parsing e superfície de injeção sem necessidade.
- Considerar o diretório `ios/` ou um build Android como prova de suporte iOS: confundiria descoberta com evidência.
