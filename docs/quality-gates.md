# Quality gates e auditors

## Três formas de enforcement

| Modo | Uso | Falha |
| --- | --- | --- |
| `hard` | resultado determinístico: schema, teste, build, contrato, map freshness | bloqueia |
| `audit` | julgamento: arquitetura, UX, ameaça, observabilidade | gera warning/finding; política pode exigir revisão |
| `human` | aceitação de risco, L3, produção ou efeito externo | bloqueia sem aprovação |

Auditor não é sinônimo de teste. Ele recebe escopo, policy IDs e evidências, registra findings com severidade e evita afirmar certeza onde há julgamento.

## Configuração

`.aifw/gates.yaml` seleciona gates por L0–L3. Um gate pode usar built-in (`manifest`, `project-map`, `human-approval`) ou comando como array:

```yaml
- id: tests
  enforcement: hard
  levels: [L1, L2, L3]
  command: [npm, test]
```

O comando é executado diretamente, sem shell implícito. `workingDirectory` deve permanecer dentro da raiz do projeto. Saída é limitada e armazenada como evidência; secrets continuam proibidos.

No Windows, shims batch conhecidos da stack, como `flutter` e `dart`, são resolvidos pelo executor e executados pelo `cmd.exe` de forma explícita. Isso não transforma gates arbitrários em strings de shell. Profiles podem fornecer receitas por ambiente; o projeto copia a receita aplicável para `.aifw/gates.yaml` e mantém evidências de outros executores na CI.

## Política progressiva

- L0: manifesto, descoberta e evidência.
- L1: testes focalizados, mapa e regras básicas da stack.
- L2: integração/contratos, segurança ou acessibilidade conforme os sinais, revisão independente.
- L3: todas as regressões relevantes, threat model, migração/rollback, auditoria e aprovação humana.

Um gate selecionado sem comando ou built-in retorna `not-run`. Hard/human `not-run` bloqueia. Audit `not-run` é warning visível.

O `init` aplica a receita do profile escolhido (`profiles/python/gates.yaml`, `profiles/web-ts/gates.yaml`, `profiles/flutter-mobile/gates.windows*.yaml`). Sem profile, configure os comandos em `.aifw/gates.yaml`. Um gate reprovado pode passar como `waived` com `aifw waiver add` até o prazo expirar; `manifest`, `human-approval` e invariantes do core não aceitam waiver.

## TDD por risco

Feature ou bugfix: teste falha pela razão esperada, implementação mínima, teste passa, refatoração mantendo verde. L2/L3 acrescentam testes de contrato/integridade e revisão independente. “Cobertura alta” não substitui cenários que representam o risco real.

## Evidência de conclusão

O relatório deve registrar comando/fonte, instante do workflow, status, resumo e referências. A conclusão cita evidência fresca; não reutiliza uma execução antiga após novas alterações.
