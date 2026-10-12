# PROJECT_MAP

`PROJECT_MAP.md` é a porta de entrada compilada para humano ou IA entender rapidamente propósito, versão, revisão verificada, sistemas, módulos, APIs, stores, runtimes, dependências, contratos, decisões, runbooks e relações.

## Fonte e compilado

```text
aifw.yaml + .aifw/catalog.yaml + Charter/ADRs/contratos
                         ↓ aifw map build
                    PROJECT_MAP.md
```

O mapa não substitui contratos ou ADRs; aponta para eles. `.aifw/catalog.yaml` contém entidades e relações. O Markdown inclui digest e é determinístico. `aifw map check` compara o conteúdo esperado byte a byte e retorna status diferente de zero se houver drift.

## Entidades

Kinds suportados: `System`, `Component`, `API`, `Resource`, `DataStore`, `Runtime`, `ExternalDependency`, `Contract`, `Decision` e `Runbook`.

Relações suportadas: `partOf`, `dependsOn`, `consumes`, `provides`, `providedBy`, `storesIn`, `runsOn` e `documentedBy`.

Cada entidade possui ID estável, owner, source e visibility. Entidades vindas do fluxo brownfield também registram `origin`, `confidence` e `lastVerifiedAt`; `candidate` nunca é apresentado como confirmação humana. IDs duplicados bloqueiam a compilação.

## Atualização

- mudança de módulo/contrato atualiza catálogo na mesma Change Case;
- novo ADR/runbook entra como entidade ou source of truth relevante;
- aprovação do Charter propaga o problema ao propósito do catálogo;
- CI executa `map check` para mudanças L1+;
- edição manual do Markdown gerado é descartada em favor da fonte.
- `aifw adopt apply` adiciona referências factuais como candidatos e recompila o mapa;
- `aifw adopt approve` confirma o digest revisado e a autoria humana.
