# ADR-0022 — Itens em aberto das auditorias

- Status: accepted
- Date: 2026-10-12
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

Depois da versão 0.4.0 ainda restavam lacunas das três auditorias:

- `validate_delegation` sem uso;
- o gate de conformidade deste repositório só rodava traces fixos, com a sessão real como auditoria;
- `route explain` ignorava a policy gravada;
- receitas de gates que supunham `npm` e ferramentas Python instaladas;
- cache de validação na pasta temporária compartilhada;
- ativação de roteamento sem assinatura.

Dos limites do desenho, dois eram reduzíveis:

- o conteúdo de scripts Python invisível ao hook;
- o secret scan restrito aos arquivos atuais.

O Stop, que o Claude Code repassa na segunda tentativa, também não deixava rastro.

## Decisão

1. Delegação: os hooks já valem dentro dos subagentes locais (verificado), o que cumpre `childAgents.capabilityCeiling: parent`. `validate_delegation` foi removida. O hook lê o modelo da definição do subagente em `.claude/agents/` quando a chamada não traz `model`, e pede confirmação para `isolation: remote`.
2. O Stop ignorado fica registrado no log da sessão. `aifw runs show` separa achados (falhas repetidas sem impasse e Stop ignorado), que reprovam, de notas (código não verificado e edições em arquivos de controle). Com isso, `session-conformance` passa a ser hard neste repositório e nas receitas.
3. `route explain` usa os aliases e o estado da policy gravada. Com `approvals.requireSignedCommit`, a ativação só vale num commit assinado.
4. O `init` ajusta a receita de gates ao projeto: gerenciador do lockfile, `uv run` e remoção do comando de ferramenta ou script não declarados.
5. O cache de validação fica em `~/.cache/aifw/validated.txt`. Valores desconhecidos nas regras de permissão pedem confirmação em vez de liberar.
6. O hook lê o arquivo de um script Python ou JavaScript chamado diretamente, com as regras do código inline.
7. `aifw secrets scan --history` lê as linhas adicionadas em todos os commits.
8. Este repositório liga `approvals.requireSignedCommit` e o gate `context-integrity`.

## Consequências

- Scripts que chamam outros programas (`subprocess`) passam a pedir confirmação ao serem rodados.
- Módulos importados por um script, scripts chamados por variável ou depois de um `cd` continuam invisíveis.
- Projetos já iniciados mantêm o `gates.yaml` atual; a receita ajustada vale para novos `init`.
- Decisões de arquitetura continuam sem assinatura, porque nada no AIFW as usa para liberar ações.

## Rollback

Desfazer as mudanças listadas e rodar `aifw claude enable`.
