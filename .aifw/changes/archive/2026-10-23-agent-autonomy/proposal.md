# Proposal — Mais autonomia para o agente

## Intent

O fluxo dependia demais da pessoa: aprovação de L3 por comando no terminal e commit assinado, ativação manual do roteamento e do avaliador, confirmação a cada push, escrita externa, delegação a Haiku e código opaco. A pessoa revisou a lista de tudo que exigia a aprovação dela e decidiu o que fica (ADR-0037).

## Scope

- Aprovação de L2/L3 pelo chat: o agente apresenta o plano e roda `aifw spec request-approval <id>`; o hook `UserPromptSubmit` grava a resposta da pessoa em `approval.md` e aprova a mudança inteira. Sem assinatura para aprovação de mudança.
- Roteamento sempre ligado: sai `aifw route activate`; a invariante `routing.eval-before-automation` e o §11 da Constituição passam a exigir a suíte só para mudar a tabela.
- Avaliador de tarefas sempre ativo: sai `aifw assess activate` e `.aifw/assessor.yaml`; o hook de pedidos roda em primeiro plano.
- Push: novo valor `remoteMutation: branches`. Branch de trabalho e PR livres; branch padrão, tags, force push, apagar branch remota e merge de PR pedem.
- Escrita externa: novo valor `externalServices.writes: allowlist`. A allowlist roda livre; o agente pergunta uma vez antes de incluir domínio novo.
- Publicação de pacote vira tipo próprio (`publish`): sempre pede, negada com dados confidential/restricted.
- Segredos: ler o conteúdo é negado, não mais confirmável; só citar o arquivo continua pedindo.
- Commits: projetos novos nascem com `commits: allow`, e commitar o `change.yaml` aprovado não pede.
- Delegação a subagentes local livre; nuvem continua pedindo.
- Juiz do código opaco (ADR-0035) removido: `aifw assess judge`, `judge.py`, recurso `judge`, hook assíncrono, suíte e capability.
- `spec archive` apaga a spec de uma capability que perde todos os requisitos.
- Mantidos: instalações, deploy de produção, destrutivos, decisões de arquitetura no terminal, e impasse, waiver, break-glass, Charter e adoção com as assinaturas deles.
- Código opaco liberado no scaffold (`opaqueCode: allow`).

## Non-goals

- Mudar o que conta como instalação, destrutivo ou deploy de produção.
- Inclusão automática de domínios na allowlist.
- Fazer merge na branch padrão: continua sendo da pessoa.

## Acceptance

- Um "sim" sem pergunta, depois de `spec request-approval`, aprova a mudança; outra resposta cancela; mensagem automática não conta; dois pedidos pendentes não aprovam nenhum; o agente não escreve `approval.md`.
- `git push` de branch de trabalho e `gh pr create` rodam; push para `main`, `--tags`, force, delete e `gh pr merge` pedem.
- POST para domínio da allowlist roda; fora dela pede; `restricted` nega.
- `npm publish` pede mesmo com `npm` na allowlist; com `confidential`, nega.
- `.env` e `printenv` negados.
- `route explain` responde `automatic`; `route activate`, `assess activate` e `assess judge` não existem.
- A suíte inteira passa.
