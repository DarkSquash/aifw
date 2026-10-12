# ADR-0001: TypeScript/Node para o control plane v0.1

- Status: accepted
- Date: 2026-08-22
- Impact: L2

## Contexto

O framework precisa de CLI multiplataforma, schemas, adapters tipados e primeiro profile Web TypeScript. O ambiente primário é Windows com WSL como validação Linux. Python também seria viável.

## Decisão

Implementar a v0.1 em TypeScript estrito, distribuir JavaScript ESM e exigir Node 22+. Formatos persistidos continuam YAML/JSON/Markdown para não acoplar projetos à linguagem.

## Consequências

Compartilhamos tipos entre core/CLI/adapters, reduzimos fricção no profile Web e testamos Windows/Linux. Aceitamos runtime Node e tooling npm. Python segue permitido nos projetos e pode receber adapter/profile; reescrever o core exigiria migration e paridade de testes, não apenas trocar arquivos.

## Alternativas

Python: ótimo ecossistema de automação/dados, mas menor alinhamento com o primeiro profile e distribuição Node já presente. Binário nativo: melhor instalação isolada, maior custo inicial e menor velocidade de evolução.
