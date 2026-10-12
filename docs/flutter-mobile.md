# Flutter Mobile

O profile `flutter-mobile` permite ao AIFW governar projetos Flutter para Android, iOS ou ambos. Ele não redefine o core e não impõe Clean Architecture, Provider, Riverpod, BLoC ou uma estrutura universal de pastas. Os limites reais continuam declarados pelo projeto no `PROJECT_MAP.md`, em ADRs e nos contratos aplicáveis.

## Ativação no projeto

Adicione o profile ao `aifw.yaml`:

```yaml
spec:
  profiles:
    - flutter-mobile
```

O `aifw init --flutter` aplica `gates.windows.yaml`, ou `gates.windows-fvm.yaml` se o projeto tiver `.fvmrc` ou `.fvm/`. Para outro executor, troque a receita:

- desenvolvimento Windows: `profiles/flutter-mobile/gates.windows.yaml`;
- desenvolvimento Windows com FVM: `profiles/flutter-mobile/gates.windows-fvm.yaml`;
- build/CI iOS em macOS: `profiles/flutter-mobile/gates.macos.yaml`.

Copie a receita aplicável para `.aifw/gates.yaml`, gere novamente a policy efetiva e valide:

```powershell
aifw resolve build
aifw audit
aifw validate --level L1
```

O AIFW detecta `pubspec.yaml` e os diretórios de plataforma versionados (`android/`, `ios/`, `web/`, `windows/`, `macos/`, `linux/`) durante o audit. Diretório presente significa alvo descoberto, não alvo validado.

## Gates progressivos

L1 executa o ciclo portátil e rápido:

```text
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

L2/L3 acrescentam build de plataforma e revisão independente. No Windows, a receita produz um APK de debug e registra a evidência iOS como ausente/auditável. No macOS, a receita executa `flutter build ios --release --no-codesign`. Assinatura, distribuição, serviços externos e produção continuam sob as permissões e aprovações do projeto.

Testes de integração com dispositivo ou emulador são configurados pelo projeto, pois dependem do harness, target disponível e eventuais plugins nativos. A ausência de um dispositivo não impede `flutter analyze` ou os testes unitários/widget, mas impede declarar que o fluxo no dispositivo foi validado.

## Windows e WSL

O gate runner entende os shims batch do Flutter/Dart no Windows. `flutter` e `dart` devem estar no `PATH` do processo que inicia o agente/CI.

Quando o projeto fixa o SDK com FVM, use a receita FVM; ela executa `fvm dart` e `fvm flutter`, impedindo que um SDK global diferente contamine a evidência.

WSL é um executor Linux separado. Se o projeto optar por validá-lo, instale Flutter dentro do WSL e mantenha SDK, cache Pub e artefatos separados dos usados no Windows. WSL não substitui macOS/Xcode para iOS.

## Fontes técnicas

- Flutter CLI: https://docs.flutter.dev/reference/flutter-cli
- Testes Flutter: https://docs.flutter.dev/testing
- Formatter Dart em CI: https://dart.dev/tools/dart-format
- Build e release iOS: https://docs.flutter.dev/deployment/ios
