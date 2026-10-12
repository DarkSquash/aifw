# ADR-0017 — Validação por mudança, archive com evidência atual e Charter aprovado

- Status: accepted
- Date: 2026-10-11
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

A auditoria de 2026-10-11 encontrou três formas de o framework parecer verde sem estar:

- o agente podia editar a política, os impasses e os registros de aprovação sem objeção do hook;
- `aifw validate --level L3` nunca lia a aprovação da spec, nada conferia os artefatos exigidos pelo nível, e `spec archive` não exigia que os gates tivessem rodado;
- `intake status` dizia `complete` com o Charter em `draft`.

## Decisão

1. O hook pede confirmação humana para alterações nos arquivos de controle: `aifw.yaml`, permissões, gates, roteamento, regras do projeto, lock e policy efetiva, aprovação da adoção, impasses, decisões, specs aceitas, `evidence/validation.json`, `policies/` e as configurações e a skill do AIFW em `.claude/`.
2. `aifw validate --change <id> [--write]` usa o nível e a aprovação da spec change, roda os gates, confere os artefatos do nível e grava `evidence/validation.json` com o digest da mudança (sem o campo `status`) e dos arquivos do projeto (visão do git quando disponível).
   - L2: `design.md` (abordagem e rollback) e `independent-review.md`, que também satisfaz o gate de auditoria `independent-review`.
   - L3: também `proposal.md` (aceitação), `threat-model.md`, `migration.md` e um artefato `adr` com caminho existente.
3. `spec archive` exige essa validação sem bloqueios hard ou human e com os digests iguais aos atuais.
4. `intake status` só é `complete` com o Charter aprovado e inalterado desde a aprovação (`charterApproved`).

## Consequências

- Mudar código ou a spec depois de validar exige validar de novo antes do archive.
- O relatório de validação ainda pode ser forjado por quem roda código fora do hook; o hook só cobre as ferramentas do Claude Code.
- Projetos com o Charter em `draft`, como este repositório, passam a mostrar o intake incompleto até a aprovação.
- Sem git, arquivos de build fora de `dist/` e `coverage/` entram no digest.

## Rollback

Desfazer as mudanças listadas e executar `aifw resolve build` e `aifw map build`.
