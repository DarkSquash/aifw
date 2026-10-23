# CLI do AIFW

A CLI é o **plano de controle** do framework: uma camada pequena que lê fontes versionadas, aplica regras determinísticas e escreve apenas artefatos explicitamente gerados. Ela não é o produto nem obriga o usuário a “programar pelo terminal”; agentes e CI podem chamá-la em segundo plano.

## Comandos

| Comando | Efeito |
| --- | --- |
| `init` | cria manifesto, Charter, catálogo, policies locais e mapa sem sobrescrever |
| `audit` | discovery e drift somente leitura |
| `adopt analyze/apply/status/approve` | cria e confirma o baseline factual de projeto existente |
| `spec new/list/show/status` | cria e acompanha mudanças isoladas |
| `spec validate/analyze/sync/archive` | valida deltas/trace, faz preview e archive atômico |
| `spec request-approval` | marca a mudança L2/L3 como aguardando a resposta da pessoa ao plano no chat (ADR-0037) |
| `spec approve` | vincula aprovação humana e registro interno a L3, pelo terminal da pessoa |
| `intake status` | mostra decisões humanas e avaliações técnicas do agente |
| `intake approve` | persiste aprovação e atualiza propósito/mapa |
| `resolve build/check` | compila/verifica effective policy e profile lock |
| `map build/check` | compila/verifica PROJECT_MAP |
| `decision list` | mostra categorias, perguntas e alternativas globais + profiles ativos |
| `decision recommend` | pontua alternativas, expõe conflitos/dúvidas e opcionalmente persiste o caso |
| `decision approve` | exige humano + ADR e registra a escolha arquitetural aceita |
| `principle list` | mostra Clean Code, SOLID e princípios fundamentais com contexto e salvaguardas |
| `change classify` | explica L0–L3, artefatos e rota sugerida |
| `validate` | roda gates do nível informado |
| `route explain/status/eval` | indica a rota, avalia casos e mostra o estado; o roteamento fica sempre ligado |
| `impasse open/attempt/status/review/decide/revalidate` | registra tentativas de correção e congela mudanças ao atingir o limite |
| `intake set` | grava uma decisão no Charter; editar um Charter aprovado o reabre |
| `waiver add/list` | exceções humanas com prazo para gates e regras sobrescrevíveis |
| `break-glass grant/list` | permissões temporárias de incidente respeitadas pelo hook |
| `template list/copy` | cria documentos a partir dos templates |
| `secrets scan` | procura segredos nos arquivos do projeto (e no histórico do git com `--history`), sem mostrar os valores |
| `change assess`, `assess report/verdict` | avaliador de tarefas em modo sombra e seus vereditos |
| `assess eval` | roda uma suíte de `evals/assessment/` contra o modelo de decisão e mostra acertos e cortes |
| `runs show` | resume as sessões gravadas contra as regras do fluxo |
| `claude install/enable/check` | comando `/aifw`, ativação por projeto e diagnóstico da integração |
| `eval` | executa conformance cases contra traces |
| `doctor` | diagnostica Python/Git/Windows/WSL |

## Seleção de stack no `init`

O profile principal pode ser escolhido com um nome curto no próprio comando:

```powershell
aifw init --id app --name "Projeto" --flutter --existing
aifw init --id site --name "Site" --web
aifw init --id api --name "API" --python
```

`--flutter` ativa internamente `flutter-mobile`; `--web` ativa `web-ts`, que cobre React, JavaScript, TypeScript e outras stacks Web; `--python` ativa `python`. Os IDs internos permanecem estáveis para não quebrar manifests existentes.

Essas opções representam a stack primária. Informar mais de uma no mesmo `init` é um conflito e a CLI encerra antes de escrever qualquer arquivo. Sem uma delas, o projeto continua com `profiles: []` para que discovery e Project Intake recomendem a stack posteriormente.

`--json` oferece saída estável para adapters/CI. Código 0 significa operação válida; código 2 significa condição verificada mas não pronta/aprovada, como map stale, intake humano ou técnico incompleto ou gates bloqueados; código 1 representa erro de contrato/comando. Em `intake status`, `ready` se refere à aprovação humana do Charter e `complete` ao processo inteiro, incluindo `agentAssessments`.

## Segurança

- init recusa overwrite;
- init valida flags de stack conflitantes antes de escrever o manifesto;
- audit/check e `adopt analyze` sem `--write` não escrevem;
- descoberta brownfield nunca confirma semântica ou owner automaticamente;
- `spec sync` nunca muta current specs e `archive` exige readiness revalidado;
- gate commands são arrays executados sem shell;
- working directory não pode escapar da raiz;
- routing activation exige relatório e registro humano;
- decisões arquiteturais exigem caso íntegro, identidade `human:*` e ADR dentro do projeto;
- caminhos e políticas permanecem explícitos;
- a CLI não envia dados a serviços externos por conta própria.

## JavaScript/TypeScript versus Python

O executável distribuído é JavaScript gerado de TypeScript. Usuários não precisam de compilador no projeto consumidor, apenas Node compatível. Python continua possível para apps e profiles; consulte ADR-0001 e o guia Windows/WSL.
