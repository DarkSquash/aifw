# Windows, WSL e Python

O AIFW usa Python 3.11 ou superior em Windows, WSL e Linux. PowerShell é o ambiente primário deste projeto. A escolha do runtime está no [ADR-0011](decisions/ADR-0011-python-runtime.md).

Windows e WSL precisam de ambientes virtuais e caches próprios. Instale a partir do mesmo `uv.lock`, mas não compartilhe `.venv` entre sistemas. `aifw doctor` verifica Python e Git do ambiente atual e consulta WSL separadamente no Windows; a indisponibilidade de WSL não invalida Python no Windows.

O mesmo isolamento vale para os SDKs dos projetos governados. Um Flutter instalado apenas no Windows não fica disponível automaticamente no WSL. Build iOS continua exigindo macOS com Xcode.

Use `uv sync --locked --extra dev` em cada ambiente e execute os testes com `uv run --no-sync python -m pytest`. A CI declara Windows e Ubuntu com Python 3.11–3.13. Registre resultados de cada ambiente efetivamente executado.
