# Proposal — Orquestração em cascata pela complexidade

## Intent

A pessoa redefiniu como as tarefas são feitas: o caminho de execução sai da complexidade, não do risco, e cada nível tem uma cascata fixa de modelos. O Opus da conversa nunca implementa: orquestra, e em L3 planeja. O risco continua decidindo a governança (o "sim" ao plano, spec, ADR e os dois revisores) e cria uma exceção em L0/L1.

## Scope

- **Caminho pela complexidade** (`assessment.path_for`): trivial → L0 (`FAST`), simples → L1 (`WORK`), moderada → L2 (`PLANNED`), alta → L3 (`CRITICAL`). A importância deixa de mudar o caminho (continua avaliada e registrada). Os nomes dos caminhos não mudam, para não quebrar `assess verdict --path` nem os relatórios.
- **Cascata por nível** (texto do avaliador, skill e subagentes):
  - L0: `aifw-quick` (Haiku, low) planeja e executa sozinho; sem revisor.
  - L1: `aifw-executor` (Sonnet, medium) planeja e executa sozinho; sem revisor.
  - L2: `aifw-planner` (Sonnet, high, novo) planeja; depois do "sim", quando houver, distribui as partes a um ou mais `aifw-worker` (Haiku, medium, novo), revisa até ficar satisfeito e devolve só o resumo ao Opus, que chama `aifw-adversary` e depois `aifw-qa`.
  - L3: o Opus da conversa planeja e divide entre um ou mais `aifw-lead` (Sonnet, medium, novo); cada um quebra a sua parte em tarefas pequenas para `aifw-worker`, revisa até ficar satisfeito e devolve o resultado ao Opus, que chama os dois revisores.
- **Exceção de risco:** risco alto ou crítico (L2 ou L3 na nota de risco do avaliador) em complexidade L0 → um `aifw-executor` (Sonnet) sozinho; em complexidade L1 → um `aifw-senior` (Opus, high, novo) sozinho. Os dois revisores rodam depois, porque o risco pede.
- **Governança pelo risco, como hoje:** risco alto ou crítico pede o plano aprovado no chat, spec e ADR, e os dois revisores. O contexto do avaliador passa a mostrar o risco como baixo, médio, alto ou crítico.
- **Papéis novos** instalados pelo `aifw claude enable`: `aifw-planner` e `aifw-lead` com a ferramenta `Agent` (lançam os workers; até três níveis abaixo da conversa, o Claude Code permite), `aifw-worker` e `aifw-senior`. `aifw-explorer`, `aifw-quick`, `aifw-executor`, `aifw-adversary` e `aifw-qa` continuam.
- O núcleo vivo do hook continua com o Opus da conversa (`orchestration.sessionPaths`, ADR-0040).
- Testes, skill, `docs/claude-code.md`, `docs/routing.md`, CHANGELOG e ADR-0042.

## Non-goals

- Renomear os níveis de impacto no resto do framework (`aifw spec new --level L2`, `change.yaml`, gates, Constituição). Eles continuam sendo o risco, com os nomes de hoje; só o texto do avaliador e da skill usa baixo, médio, alto e crítico para o risco e L0–L3 para a complexidade. Renomear tudo é uma mudança à parte, se a pessoa quiser.
- Trocar o esforço da sessão principal: quem escolhe é a pessoa, no app.
- Mudar o roteamento FAST/WORK/BRAIN de `aifw route explain`.

## Acceptance

- `path_for` devolve FAST, WORK, PLANNED e CRITICAL para complexidade trivial, simples, moderada e alta, qualquer que seja a importância.
- O contexto do avaliador cita a cascata de cada nível, a exceção (Sonnet sozinho em L0, `aifw-senior` em L1) com risco L2/L3, e o pedido de aprovação e dos revisores quando o risco é alto ou crítico.
- `aifw claude enable` instala os quatro papéis novos com modelo, esforço e ferramentas do template, e `aifw claude check` os confere.
- A skill descreve a cascata, a exceção e a regra de que o Opus da conversa só orquestra.
- Suíte inteira passando e revisão em duas etapas aprovada.
