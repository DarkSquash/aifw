# Flutter Mobile profile

Optional stack profile for Flutter applications targeting Android, iOS or both. It adds Dart formatting, Flutter analysis and tests, platform-specific evidence, mobile security, adaptive UI and observability rules without forcing Clean Architecture, a state-management package or a universal folder structure.

Activate it during initialization with `aifw init --flutter`. The internal id remains `flutter-mobile` for compatibility with existing manifests.

## Gate recipes

- `gates.windows.yaml`: local Windows validation plus Android debug build for L2/L3. iOS evidence remains an explicit audit finding.
- `gates.windows-fvm.yaml`: a mesma política usando o SDK Flutter fixado pelo FVM do projeto.
- `gates.macos.yaml`: macOS/CI validation that can produce the required unsigned iOS release build evidence.

Copy the recipe for the executor into `.aifw/gates.yaml`. Windows and WSL installations must use their own Flutter SDK/cache. A checked-in `ios/` target is not considered validated by an Android build.

The base L1 loop is intentionally fast and deterministic:

```text
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

L2/L3 add a platform build, independent review and the normal AIFW approval rules. Device or emulator integration tests remain project-specific because their command depends on the repository's test harness and available targets.
