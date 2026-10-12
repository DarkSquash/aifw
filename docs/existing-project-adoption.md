# Adoção de um projeto existente

AIFW v0.2 possui um fluxo brownfield nativo. Ele analisa a base existente, persiste uma proposta factual revisável e atualiza as fontes correspondentes sem alterar código da aplicação.

## 1. Inicializar o control plane

Na raiz real do projeto:

```powershell
aifw init --id app --name "Projeto" --existing --flutter
```

Troque `--flutter` por `--web` ou `--python`; omita a stack quando o agente ainda precisar recomendá-la. `init --existing` cria apenas o control plane, os diretórios de specs/changes/adoption e o primeiro `PROJECT_MAP.md`.

## 2. Descobrir sem escrever

```powershell
aifw audit --json
aifw adopt analyze --json
```

`adopt analyze` detecta fatos verificáveis: manifests, package managers, scripts, dependências, entrypoints, source roots, contratos, CI, ADRs, configurações, documentação e targets conhecidos. Sem `--write`, a operação é somente leitura.

## 3. Persistir a proposta

```powershell
aifw adopt analyze --write
```

Isso cria:

- `.aifw/adoption/discovery.json`: relatório factual com digest;
- `.aifw/adoption/status.yaml`: estado do processo.

O catálogo e o mapa ainda não mudam nesta etapa.

## 4. Aplicar candidatos factuais

```powershell
aifw adopt apply
```

O comando mescla candidatos sem apagar entidades manuais e atualiza:

- `.aifw/catalog.yaml`;
- `docs/architecture/discovered.md`;
- `PROJECT_MAP.md`.

As entidades entram como `origin: discovered`, `confidence: candidate` e owner ainda não confirmado. Conflito com uma entidade humana existente bloqueia em vez de sobrescrever silenciosamente.

## 5. Revisar e aprovar

Revise responsabilidades, boundaries, owners, relações e unknowns. Corrija as fontes versionadas quando necessário e então confirme:

```powershell
aifw adopt approve --by "human:proprietario"
aifw adopt status
aifw intake status
```

A aprovação muda os candidatos descobertos para `confidence: confirmed`, registra humano, data e digest do conteúdo, recompila o mapa e torna a avaliação brownfield atual no intake. Se uma entidade confirmada for editada depois, `adopt status` detecta drift pelo digest e exige novo `apply` + revisão.

## O que é automático e o que não é

Automático e factual:

- estrutura, manifests, entrypoints e source roots;
- contratos e arquivos CI;
- ADRs e documentação existente;
- candidatos de catálogo, referências e `PROJECT_MAP` compilado.

Exige evidência/revisão:

- responsabilidade real de cada módulo;
- boundaries e dependências sem contrato/importação verificável;
- owner organizacional;
- fluxo de negócio, dados sensíveis e criticidade;
- decisão de transformar documentação histórica em arquitetura aceita.

O AIFW nunca usa nomes de pastas como autorização para inventar arquitetura. Reexecute `adopt analyze --write` depois de mudanças estruturais relevantes; um novo digest invalida a aprovação anterior até nova revisão.

## Integração com specs

Depois do baseline aprovado, mudanças novas usam `.aifw/changes/active/<id>` e deltas contra `.aifw/specs/current/`. O inventário brownfield diz o que existe; capability specs dizem o comportamento aceito; ADRs explicam por que decisões arquiteturais foram tomadas.
