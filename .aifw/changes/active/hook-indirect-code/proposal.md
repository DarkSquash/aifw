# Proposal — Hook lê código indireto

## Intent

O hook `PreToolUse` lê o texto de cada comando para decidir se ele publica, instala, apaga ou envia dados. Hoje basta pôr o comando num arquivo e rodar o arquivo para que nada seja lido: `bash x.sh` com `git push` dentro passa sem pergunta. Esta mudança faz o hook ler também o código que o comando executa indiretamente.

## Scope

- Scripts de shell e PowerShell rodados por um shell ou diretamente: `bash x.sh`, `sh x.sh`, `./x.sh`, `pwsh -File x.ps1`, `./x.ps1`.
- Scripts Python ou JavaScript sem prefixo de interpretador ou sem extensão: `uv run x.py`, `./x.py`, `python x`.
- Módulos locais rodados com `python -m <módulo>`.
- Scripts do `package.json` rodados por `npm`, `pnpm`, `yarn` ou `bun` (`run X`, `test`, `start`), com `preX` e `postX`.
- Receitas do `Makefile` rodadas por `make`.
- Configurações do git que fazem o git executar outro programa (`alias.*`, `core.hooksPath`, `core.sshCommand` e afins), por `git config` ou `git -c`.
- `.git/hooks/` e `.git/config` como arquivos de controle.
- Arquivo local executado que o hook não sabe ler (perl, ruby, binário, sem extensão conhecida): código ilegível, que pede confirmação.

## Non-goals

- Seguir imports de um script ou resolver dependências entre alvos do Makefile.
- `just`, `task`, `rake` e outros executores de tarefas.
- Diretório alterado por `cd` antes de rodar o script: o caminho continua relativo à pasta da sessão.
- Proteger `python/aifw/` neste repositório (decisão do ADR-0025).

## Acceptance

- Cada vetor do escopo, com um script que contém `git push`, faz o hook pedir confirmação.
- O mesmo vetor com um script inofensivo (`echo`, `ls`) não pede confirmação.
- `python -m pytest`, `npm test` com script de teste inofensivo e `./gradlew test` continuam contando como verificação para o Stop.
- `git config --get alias.x` e `git config --list` continuam livres; `git config alias.p push` e `git -c core.hooksPath=x commit` pedem confirmação.
- Editar `.git/hooks/pre-commit` ou `.git/config` pede confirmação.
- A suíte completa de testes passa.
