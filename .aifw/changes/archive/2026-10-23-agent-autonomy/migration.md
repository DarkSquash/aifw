# Migração — Mais autonomia para o agente

- Projetos existentes: as configurações antigas continuam válidas. Para adotar o novo comportamento, em `.aifw/permissions.yaml`: `remoteMutation: branches`, `externalServices.writes: allowlist`, `commits: allow` e, se desejado, `opaqueCode: allow`. Projetos novos já nascem assim (`templates/project-scaffold.json`).
- Com `remoteMutation: branches`, rode `git remote set-head origin --auto` uma vez se o repositório não tiver `refs/remotes/origin/HEAD` (remoto adicionado à mão); sem ele, todo push pede confirmação.
- Com dados `confidential`, inclua `github` em `spec.externalAllowlist` para abrir PR sem confirmação; com `restricted`, escrita externa (inclusive PR) é negada.
- Rodar `aifw claude enable` em cada projeto: tira o hook do juiz e deixa o hook de pedidos síncrono.
- Tirar `judge` de `spec.assessment.features` em `aifw.yaml`; `.aifw/assessments/judge.jsonl` pode ser apagado.
- `.aifw/assessor.yaml` deixa de ser lido e pode ser apagado.
- O `activation` de `.aifw/routing.yaml` deixa de ser exigido e é ignorado.
- Mudanças L3 já aprovadas continuam válidas, assinadas ou não.
- Sem migração de dados.
