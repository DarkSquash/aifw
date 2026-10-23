# ADR-0037: mais autonomia para o agente

- Status: accepted
- Date: 2026-10-22
- Impact: L3
- Change: `agent-autonomy`
- Supersedes: em parte ADR-0003 e ADR-0032 (ativação do roteamento), ADR-0020 e ADR-0022 (assinatura na aprovação de spec), ADR-0025 e ADR-0030 (push, escrita externa, delegação), ADR-0035 (juiz, removido) e ADR-0036 (ativação do avaliador)

## Contexto

Mesmo depois dos ADRs 0025 e 0030, o trabalho parava muitas vezes à espera da pessoa: aprovação de L3 por comando no terminal e commit assinado, ativação manual do roteamento e do avaliador de tarefas, confirmação a cada push, a cada escrita em serviço externo, a cada delegação a Haiku em L3 e a cada código que o hook não lê. A pessoa pediu a lista completa do que exigia aprovação ou só ela podia digitar, revisou item por item e decidiu o que muda.

## Decisão

1. **Aprovação de L2/L3 pelo chat.** O agente apresenta o plano e roda `aifw spec request-approval <id>`. O hook `UserPromptSubmit` grava a próxima mensagem da pessoa como aprovação, em `approval.md`, quando ela começa por "sim", "aprovo", "ok", "bora", "fechado" ou "pode" (sozinho ou com "seguir", "fazer", "implementar"...) e não tem pergunta nem ressalva ("mas", "porém", "antes", "espera", "ainda não", "não faça", "só depois"; um "não" solto, como em "sim, não tenho objeções", não conta). Qualquer outra resposta cancela o pedido, e o hook avisa o agente para ajustar e pedir de novo; mensagens automáticas não contam; com dois pedidos pendentes, nenhum é aprovado. Enquanto o pedido espera, o agente daquela sessão fica congelado (o hook nega qualquer ferramenta), então a mensagem seguinte da pessoa é a resposta ao plano. Aprovada, a mudança não pede novas aprovações, salvo as ações que já pedem por conta própria.
2. **Sem assinatura na aprovação de mudança.** O pedido de aprovação vale só na sessão que o fez (o hook anota a sessão em `.aifw/runs/approvals/<id>.session`). Commitar o `change.yaml` aprovado não pede confirmação, porque a assinatura não conta mais para mudanças. Editar `change.yaml` ou `approval.md` (também por padrão de shell, como `chang?.yaml`) pede confirmação. Rodar o hook, `python -m aifw.hooks` ou `claude -p` pelo shell é negado. `requireSignedCommit` continua valendo para Charter, adoção, impasse, waiver e break-glass.
3. **Roteamento sempre ligado.** Sai `aifw route activate`. A suíte de roteamento passa a ser exigida só para mudar a tabela. Emendados o §11 da Constituição e a invariante `routing.eval-before-automation` (2.0.0).
4. **Avaliador de tarefas sempre ativo** com o recurso `tasks` ligado. Sai `aifw assess activate` e `.aifw/assessor.yaml`; o hook de pedidos roda sempre em primeiro plano.
5. **Push.** Novo valor `remoteMutation: branches`: push para branch de trabalho, `gh pr create` e comentários rodam (o PR, mesmo sem `github` na allowlist; com dados confidential o GitHub precisa estar nela, e com restricted a escrita é negada); push para a branch padrão (ou sem destino saindo dela), `--tags`, `--all`, `--mirror`, force push, apagar branch remota e `gh pr merge` pedem.
6. **Escrita externa.** Novo valor `externalServices.writes: allowlist`: escrever num serviço de `spec.externalAllowlist` roda; fora dela pede. Para um domínio novo que pareça parte do projeto, o agente pergunta uma vez e, com o sim, inclui.
7. **Publicação** (`npm publish`, `twine upload`, `uv publish`, `poetry publish`, `docker push`, `docker buildx build --push`, `dotnet nuget push`, `gh release create`, `gradle publish`, `mvn deploy` e afins) é um tipo próprio: sempre pede, e é negada com dados confidential ou restricted.
8. **Código opaco** liberado neste repositório e no scaffold (`opaqueCode: allow`). O que o código faz continua sob as regras: o agente não usa script para contornar uma confirmação.
9. **Segredos:** ler o conteúdo (ferramenta Read, `cat`, `grep`, `git diff`, `printenv`...) passa a ser negado, sem opção de confirmar. Um comando que só cita o arquivo (`echo .env >> .gitignore`, `cp .env.example .env > .env`) continua pedindo, e procurar o nome (`grep .env .gitignore`) roda.
10. **Delegação** a subagentes locais é escolha do agente; só a sessão na nuvem pede.
11. **Juiz removido** (ADR-0035): `aifw assess judge`, `judge.py`, o recurso `judge`, a suíte e a capability `opaque-judge`. `aifw claude enable` tira o hook antigo.
12. `spec archive` apaga a spec de uma capability que perde todos os requisitos.
13. **Commits livres no scaffold:** projetos novos nascem com `commits: allow` (ADR-0030), como este repositório.

Mantidos: instalações, deploy de produção, ações destrutivas e o que já era decisão humana.

## Consequências

- O agente trabalha sem interrupção numa mudança aprovada, faz commit, push da branch e abre PR. O merge na branch padrão continua da pessoa.
- A prova da aprovação é a mensagem da pessoa citada em `approval.md`, gravada pelo hook. Ela protege contra erro do agente e caminhos óbvios, não contra um agente decidido a forjá-la (ADR-0034).
- **Decisão da pessoa em 2026-10-23:** seis revisões independentes, instruídas a achar qualquer jeito de forjar a aprovação, acharam sempre um caminho novo (cópia de pasta, `git merge` de outra worktree, leitura da pasta pessoal...). Um selo HMAC com chave em `~/.aifw`, um piso de nível pelo diff, a exigência de aprovação em L2 e bloqueios de cópia, patch e extração chegaram a ser feitos, mas quebravam o uso normal (aprovação presa a uma máquina, falsos positivos em `cp`, `claude --model`, `grep`) e foram retirados. O hook não persegue um agente malicioso. Se essa proteção for desejada, ela vem de uma barreira estrutural (sandbox de arquivos do Claude Code ou commit assinado), não de listas de comandos.
- Dados podem ir sem confirmação para os domínios da allowlist; a pessoa controla a lista.
- O hook de pedidos síncrono pode atrasar uma mensagem em até 60 s se o serviço de decisão estiver fora.
- Rollback por projeto sem mudar código: `remoteMutation: human-approval`, `writes: human-approval`, `opaqueCode: ask`.
