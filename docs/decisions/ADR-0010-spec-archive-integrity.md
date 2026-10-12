# ADR-0010: Integridade de archive, aprovação e evidência de specs

- Status: accepted
- Date: 2026-09-06
- Impact: L3
- Authorization: human:DarkSquash, nesta tarefa, após apresentação da auditoria: "pode corrigir meu bom".
- Scope: correções F1-F5 de `docs/audits/2026-09-05-v02-review.md`. A autorização não se estende a publicação, roteamento ou alterações da Constitution.

## Contexto

A auditoria reproduziu perda de estado durante limpeza de backups, aprovação L3 não revalidada, sobrescrita de deltas da mesma capability, evidência insuficiente aceita e geração de spec com título inválido. A intenção já aprovada no ADR-0009 exige preservar o estado e revalidar as pré-condições no archive.

## Decisão

1. Separar commit da limpeza: após instalar current e archive e retirar active, falha na remoção da transação é limpeza pendente, nunca motivo para apagar o estado já instalado. Retornar aviso e caminho recuperável ao chamador. Falhas anteriores ao commit continuam com rollback; falha de rollback preserva a transação.
2. Compartilhar validação de aprovação entre ready e archive. Para L3, exigir humano identificado, data válida e arquivo de registro existente dentro da raiz real do projeto. Não introduzir assinatura ou autenticação de identidade nesta correção.
3. Recusar capabilities duplicadas em uma mudança, conforme a convenção existente de um delta por capability. Não definir ordem implícita de merge.
4. Artefatos passed precisam referenciar arquivo existente dentro do projeto. Uma relação checkedBy com um gate declara uma obrigação de verificação da mudança: ela só é satisfeita por passed. failed, planned e waived não substituem comprovação. Observações de auditoria sem esse compromisso permanecem não bloqueantes; classificação hard/audit/human e waivers do avaliador de gates mantêm seu próprio contrato. O analisador não executa testes nem autentica logs.
5. Rejeitar título vazio/apenas espaços em deltas e validar a spec resultante antes de staging. Alinhar o schema de título e a exigência condicional de path em artefatos passed.

## Alternativas e consequências

- Consolidar deltas repetidos exigiria novas regras de conflito; a rejeição é menor e previsível.
- Fazer rollback após limpeza parcial perde a única cópia recuperável; conservar commit e avisar sobre resíduos é preferível.
- Exigir todo gate do projeto neste comando introduziria uma integração nova. Esta correção cobre compromissos explícitos de trace, mantendo execução e autoridade no avaliador existente.
- Artefatos históricos sem path ou que usavam checkedBy como observação devem ser revisados antes de nova promoção. Arquivos arquivados não são reescritos.
- Não são prometidas atomicidade entre processos, recuperação automática após queda de energia ou vinculação criptográfica de aprovação ao conteúdo. São evoluções separadas.

## Migração e rollback

Sem migração destrutiva. Revisar deltas duplicados, títulos vazios e artefatos passed sem path nas mudanças ativas. A cópia anterior à implementação está registrada em `evidence/checkpoint.json` da mudança. Para rollback de implementação, restaurar fontes, schemas e documentos do checkpoint e recompilar; preservar specs e evidências aceitas posteriormente.

## Verificação

Regressões reais em `tests/spec-integrity.test.ts`, incluindo injeção controlada de falha de filesystem em diretórios temporários. Executar check, build, análise da mudança, sincronização, archive e verificações de mapa/política/intake. Evidências finais pertencem à mudança `harden-spec-archive`.
