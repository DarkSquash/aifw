# Versionamento e migrations

Cada `aifw.yaml` fixa `frameworkVersion`; `latest`, ranges e atualização silenciosa são inválidos. `.aifw/framework.lock.yaml` fixa profiles e digests resolvidos.

## Atualização

1. ler release notes e breaking changes;
2. criar Change Case — L2 por padrão, L3 se core/Constitution/security mudar;
3. gerar checkpoint e plano de rollback;
4. executar migration explícita em branch/worktree;
5. regenerar effective policy, lock e PROJECT_MAP;
6. atualizar schemas/templates/ADRs necessários;
7. executar testes, conformance evals e matriz Windows/Linux;
8. aprovar e atualizar `frameworkVersion` somente após evidência.

## Regras

- migration é idempotente ou detecta que já foi aplicada;
- nunca sobrescreve decisão humana sem conflito explícito;
- mantém backup/checkpoint recuperável;
- dry-run lista arquivos e alterações;
- falha parcial deixa instrução de recovery;
- downgrade só é prometido quando testado.

Aprendizado de um projeto vira default apenas por RFC/ADR, evidência em contextos diferentes e aprovação. Até lá permanece project rule ou waiver local.

## v0.1.x → v0.2.0

Esta migração adiciona contratos executáveis de capability specs e o baseline brownfield. Ela não reorganiza nem modifica o código da aplicação.

1. crie branch/worktree ou checkpoint recuperável;
2. atualize o pacote AIFW e execute `uv run --no-sync python -m pytest` + `uv run --no-sync python -m build --no-isolation` na origem instalada;
3. crie, sem sobrescrever conteúdo existente:
   - `.aifw/specs/current/`;
   - `.aifw/changes/active/`;
   - `.aifw/changes/archive/`;
   - `.aifw/adoption/`;
4. adicione `.aifw/specs/current/` às fontes de verdade de `.aifw/catalog.yaml`;
5. para `projectType: existing`, execute `adopt analyze --write`, revise, `adopt apply` e `adopt approve`;
6. documente o baseline comportamental confirmado como `CapabilitySpec` quando houver evidência suficiente;
7. fixe `frameworkVersion: 0.2.0` em `aifw.yaml`;
8. execute `aifw resolve build`, `aifw map build`, `aifw intake status`, `aifw audit` e os gates proporcionais ao impacto.

Se qualquer etapa falhar, preserve o relatório e restaure manifesto, catálogo, lock e mapa a partir do checkpoint. Não apague capability specs já revisadas: elas podem permanecer como documentação enquanto a automação volta à v0.1.

## Correções de integridade do lifecycle v0.2

Antes de promover mudanças ativas, consolide arquivos duplicados da mesma capability, preencha títulos vazios e forneça arquivos de evidência para artefatos `passed`. Gates ligados por `checkedBy` precisam estar `passed`; revise observações de auditoria que tenham sido registradas como compromissos obrigatórios. Revalide a existência do registro de aprovação L3. Nenhum arquivo histórico é reescrito automaticamente.

O archive pode retornar `cleanupPending` após commit bem-sucedido: preserve current e archive, confira o caminho da transação e remova somente o resíduo verificado. Não restaure backups parcialmente removidos nem repita o archive. Veja ADR-0010.

## v0.4.0 → v0.4.1

Fecha os itens em aberto das auditorias (ADR-0022). Consulte o [CHANGELOG](../CHANGELOG.md).

1. Reinstale o CLI (`uv tool install --force <pasta-do-aifw>`) e, no projeto, rode `aifw claude enable`.
2. Fixe `frameworkVersion: 0.4.1` em `aifw.yaml` e rode `aifw resolve build` e `aifw map build`.
3. Para reprovar sessões que ignoram o Stop ou repetem falhas sem impasse, mude `session-conformance` para `enforcement: hard` em `.aifw/gates.yaml`.
4. Rode `aifw secrets scan --history` uma vez para conferir o histórico do git.
5. Scripts que chamam outros programas (`subprocess`) passam a pedir confirmação quando o agente os roda.

## v0.3.0 → v0.4.0

Esta versão troca o host de referência para o Claude Code e endurece a validação. Consulte o [CHANGELOG](../CHANGELOG.md).

1. Inicialize git no projeto, se ainda não houver: `git init`.
2. Reinstale o CLI (`uv tool install --force <pasta-do-aifw>`) e rode `aifw claude install`.
3. No projeto, rode `aifw claude enable` para gravar os hooks e a skill `aifw-workflow`; abra uma nova sessão do Claude Code.
4. Fixe `frameworkVersion: 0.4.0` em `aifw.yaml` e rode `aifw resolve build` e `aifw map build`.
5. Mova a allowlist de `.aifw/permissions.yaml` (`externalServices.allowlist`) para `spec.externalAllowlist` em `aifw.yaml`. O hook só lê a do manifesto.
6. Se `.aifw/gates.yaml` tiver gates sem `command`, configure-os ou registre um waiver (`aifw waiver add`). Para comparar, as receitas ficam em `profiles/*/gates*.yaml`.
7. Se o Charter estiver em `draft`, `intake status` deixa de dizer `complete`: revise e rode `aifw intake approve`.
8. Antes de arquivar uma mudança ativa, rode `aifw validate --change <id> --write`. Em L2 e L3, crie os artefatos que o comando apontar como ausentes.
9. Pare de usar `aifw handoff codex` e `aifw principle review`, que foram removidos. A extensão Pi e o pacote `aifw-pi-bridge` também saíram; remova a instalação no Pi, se existir.

10. Acrescente os gates `secret-scan` e `session-conformance` ao `.aifw/gates.yaml` (veja as receitas em `profiles/`) e rode `aifw secrets scan`.
11. Se o projeto instala pacotes, publica ou acessa servidores pelo agente, decida se inclui `package-registry` ou `remote-host` em `spec.externalAllowlist`.

Nenhum arquivo é reescrito automaticamente, e os registros já arquivados continuam válidos.
