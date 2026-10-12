# ADR-0021 — Código embutido, allowlist por domínio e caminhos protegidos

- Status: accepted
- Date: 2026-10-12
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

A terceira auditoria encontrou seis brechas:

- comandos dentro de `$(...)`, crases, blocos `{ }` e variáveis;
- allowlist casando por pedaço do nome do domínio (`github.attacker.example`);
- Grep e Glob fora do hook;
- aprovação por script Python, que escapa do terminal humano;
- `git commit -S` silencioso com a senha em cache, e o modo de assinatura não cobria adoção nem impasse;
- o hook editável neste repositório.

Também faltavam o registro de uso do break-glass, a proteção de variáveis de ambiente, o aviso de skill de projeto editada e uma latência aceitável.

## Decisão

1. O leitor de shell extrai e analisa o conteúdo de `$(...)`, `<(...)`, crases e blocos `{ }`; expansões como `{a,b}` e `${VAR}` não contam como código. São opacos: programa vindo de variável, programa vindo de código embutido, `Invoke-Command` e `.`. `printenv`, `env`, `set` e `env:` são leitura de segredo. Assinar commit ou tag pede confirmação.
2. A allowlist casa por domínio exato ou subdomínio, com tabela padrão (`github`, `gitlab`, `context7`, `npm`, `pypi`) e `serviceDomains` no `permissions.yaml`.
3. Grep e Glob entram no hook com a regra de arquivos de segredo.
4. `protectedPaths` no `permissions.yaml` estende os arquivos de controle; neste repositório, `python/aifw/`.
5. O modo `approvals.requireSignedCommit` cobre também adoção e decisões de impasse. Uma decisão de impasse sem assinatura mantém o congelamento. A documentação exige gpg-agent sem cache de senha.
6. Cada ação liberada por break-glass é registrada em `.aifw/break-glass/<incidente>.log`.
7. Documentos já validados (por hash do conteúdo) não carregam o jsonschema de novo.
8. `aifw claude enable` guarda `SKILL.md.bak` quando a skill do projeto difere da que seria gravada.

## Consequências

- Sem o modo de commit assinado, um script Python continua podendo aprovar sem terminal; o modo é a única defesa contra isso.
- Comandos com blocos `{ }` de verdade passam a pedir confirmação.
- O cache de validação fica no diretório temporário do sistema e só registra que um conteúdo passou no schema; os valores sempre vêm do arquivo.

## Rollback

Desfazer as mudanças listadas e rodar `aifw claude enable`.
