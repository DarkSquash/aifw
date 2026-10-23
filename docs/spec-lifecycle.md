# Ciclo executável de especificações

AIFW v0.2 separa a verdade aceita do produto das mudanças ainda em análise. O repositório continua sendo a fonte de verdade; uma conversa com IA nunca substitui estes artefatos.

```text
.aifw/specs/current/*.yaml
        verdade aceita
              ↑ archive validado e atômico
.aifw/changes/active/<change-id>/
  change.yaml
  proposal.md
  design.md
  tasks.yaml
  traceability.yaml
  specs/*.delta.yaml
  evidence/*
              ↓
.aifw/changes/archive/<data>-<change-id>/
```

## Documentos

- `CapabilitySpec`: comportamento atualmente aceito, organizado por capability, requisito e cenário observável;
- `CapabilityDelta`: operações `added`, `modified` e `removed` propostas contra a verdade atual;
- `ChangeTasks`: tarefas, dependências, requisitos cobertos e caminhos afetados;
- `ChangeTraceability`: relações entre requisitos, cenários, tarefas, testes, gates, ADRs, design e evidências;
- `SpecChange`: identidade, impacto L0–L3, estado e eventual aprovação humana.

Os contratos públicos estão em `schemas/`; exemplos editáveis estão em `templates/`.

## Fluxo operacional

```powershell
aifw spec new add-search `
  --title "Adicionar busca" `
  --summary "Permitir busca por identificadores autorizados" `
  --level L2
```

1. Preencha `proposal.md` e `design.md` na pasta criada.
2. Adicione um ou mais `specs/*.delta.yaml`.
3. Relacione cada requisito às tarefas em `tasks.yaml`.
4. Registre testes e evidências reais em `traceability.yaml`.
5. Execute:

```powershell
aifw spec validate add-search
aifw spec analyze add-search
aifw spec sync add-search --dry-run
```

`sync` é deliberadamente apenas preview. Ele mostra exatamente quais capability specs seriam criadas ou alteradas e nunca muda a verdade atual.

Quando implementação, tarefas, cenários e evidências estiverem completos:

```powershell
aifw spec status add-search --set ready
aifw spec archive add-search
```

`archive` revalida tudo, constrói a próxima árvore de specs em staging e só então troca os diretórios. Se a pré-condição falhar, a verdade atual e a mudança ativa são preservadas.

Após instalar as specs e o arquivo da mudança, a transação está concluída. Se a limpeza dos backups falhar, o resultado preserva o commit e inclui `cleanupPending` com `path` e `reason`. O comando não tenta desfazer o commit com backups parcialmente removidos. Confira current e archive antes de remover o resíduo indicado; não execute novamente o archive da mesma mudança. Isso não promete recuperação automática após interrupção do processo ou coordenação entre archives concorrentes.

Para L3, a mudança só pode ficar `ready` depois de aprovação humana vinculada a um registro existente dentro do projeto. O caminho normal é o chat (ADR-0037): o agente apresenta o plano e roda `aifw spec request-approval <id>`; se a resposta seguinte da pessoa for um "sim", o hook `UserPromptSubmit` grava `approval.md` na pasta da mudança e registra a aprovação. No terminal da pessoa também vale:

```powershell
aifw spec approve change-core-policy `
  --by "human:proprietario" `
  --record docs/adr/ADR-0042-core-policy.md
```

A aprovação é revalidada no archive: reclassificação para L3, remoção da aprovação ou do arquivo citado impedem a operação. O registro precisa ser um arquivo dentro da raiz real do projeto, inclusive após resolver links simbólicos.

## Estados

```text
draft → active → ready → archived
                  ↑
       validação + traceabilidade
       + tarefas concluídas
       + aprovação humana em L3
```

Não existe promoção silenciosa. Um delta inválido, requisito órfão, cenário sem teste, tarefa incompleta, artefato ausente ou link quebrado bloqueia prontidão/arquivo.

## Regras de autoria

- IDs de mudança, capability, requisito, cenário, tarefa e artefato são estáveis;
- requisitos descrevem comportamento observável, não uma implementação preferida;
- `modified` e `removed` precisam existir na verdade atual;
- `added` não pode reutilizar requisito já existente;
- criar capability exige `purpose` explícito;
- uma mudança contém no máximo um delta por capability; duplicidade gera `DUPLICATE_CAPABILITY_DELTA`;
- o título do delta não pode ser vazio ou conter somente espaços; a spec produzida é validada antes de staging;
- L2 e L3 exigem pelo menos um delta de capability;
- evidência apontada precisa existir dentro do projeto;
- artefatos `passed` exigem `path` para um arquivo existente; diretórios não contam como evidência;
- gate ligado por `checkedBy` é uma obrigação da mudança e deve estar `passed`; `planned`, `failed` e `waived` geram `TRACE_GATE_NOT_PASSED`;
- edições manuais em `.aifw/specs/current/` fora deste fluxo devem ser tratadas como drift ou migração explícita.
