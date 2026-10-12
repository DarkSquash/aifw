# AIFW no Claude Code

O AIFW fica desligado até você habilitá-lo num projeto. Nada roda nas sessões de projetos que não o usam.

## Instalação (uma vez por máquina)

Requisitos: Python 3.11 ou superior, [uv](https://docs.astral.sh/uv/), [Git](https://git-scm.com/) e Claude Code.

```powershell
uv tool install C:\caminho\para\aifw
aifw claude install
```

- O primeiro comando instala os executáveis `aifw` e `aifw-hook` no PATH (`~/.local/bin`). Com `--editable`, mudanças na pasta do AIFW valem na hora, sem reinstalar.
- O segundo copia o comando `/aifw` para `~/.claude/skills/aifw/`. Esse comando só roda quando você o digita; o Claude não o aciona sozinho.

Confira com `aifw --version`. Se o uv avisar que a pasta de executáveis não está no PATH, rode `uv tool update-shell` e abra um terminal novo.

## Habilitar num projeto

Abra o Claude Code na pasta do projeto e digite:

- `/aifw new` — projeto do zero: inicializa o control plane e conduz a entrevista do intake.
- `/aifw adopt` — projeto que já existe: inicializa com `--existing`, faz o discovery e pede sua aprovação do que foi encontrado.

Os dois rodam `aifw claude enable`, que grava no próprio projeto:

- `.claude/settings.json`: o hook `aifw-hook`, mesclado com o que já existir no arquivo;
- `.claude/skills/aifw-workflow/SKILL.md`: o fluxo do AIFW para o Claude seguir neste projeto.

Abra uma nova sessão depois de habilitar, para o hook e a skill carregarem. Se o projeto usa git, versione a pasta `.claude/`: quem clonar o projeto recebe a mesma configuração.

Para desabilitar, remova a entrada `aifw-hook` de `.claude/settings.json` e a pasta `.claude/skills/aifw-workflow/`.

## O que os hooks fazem

| Evento | Ação |
| --- | --- |
| PreToolUse | aplica permissões, impasses, arquivos de controle, MCP, delegação, classificação dos dados e break-glass (detalhes abaixo); se o `aifw-hook` não puder rodar, a ação é bloqueada (`onFailure: block`) |
| PostToolUse | registra comandos e edições em `.aifw/runs/<sessão>.jsonl`, em segundo plano |
| PostToolUseFailure | registra a falha; se o mesmo comando de teste falhar duas vezes sem impasse aberto, sugere `aifw impasse open` |
| Stop | impede concluir com código alterado depois da última verificação bem-sucedida (testes ou `aifw validate`), uma vez por resposta |
| SessionStart | informa intake incompleto, mudanças ativas e impasses abertos |

Como o PreToolUse bloqueia quando falha, quem clonar um projeto habilitado precisa instalar o AIFW antes de usar o Claude Code nele. `aifw claude check` mostra o que falta: hooks, skill do projeto, `aifw-hook` no PATH, comando `/aifw` e skills obrigatórias.

### PreToolUse

`aifw-hook` aplica `.aifw/permissions.yaml` e os impasses abertos a cada ação do Claude Code. Ele nunca aprova sozinho: quando o AIFW não tem objeção, as regras de permissão do próprio Claude Code continuam valendo. Ele retorna:

- `deny` quando a política diz `denied`, quando o serviço externo de escrita não está na allowlist, ou quando um impasse congela edições e comandos destrutivos;
- `ask` quando a política exige aprovação humana, para leitura de serviço fora da allowlist, para comandos `aifw ... approve/decide/activate`, para comandos de shell durante um impasse `OPEN` e para edições nos arquivos de controle do AIFW (`aifw.yaml`, permissões, gates, roteamento, impasses, decisões, aprovação da adoção, specs aceitas, `evidence/validation.json`, `policies/` e `.claude/settings.json`);
- `ask` também quando a política não pode ser lida, para que a falha chegue ao humano em vez de liberar a ação.

Controles adicionais:

- **Serviços externos:** a allowlist vem de `spec.externalAllowlist` em `aifw.yaml`. Com `dataClassification: confidential`, leitura de serviço fora dela é negada; com `restricted`, escrita externa também é negada.
- **MCP:** `mcpServers.deny` e `mcpServers.ask` em `.aifw/permissions.yaml` listam servidores (o trecho entre `mcp__` e `__` no nome da ferramenta). Servidores fora das listas seguem as regras do Claude Code.
- **Subagentes:** delegar para `haiku` pede confirmação enquanto houver mudança L2 ou L3 ativa.
- **Break-glass:** `aifw break-glass grant --incident <id> --scope git-remote,deploy --reason ... --by human:<nome> --hours 4` libera esses tipos de ação até expirar, se `breakGlass.enabled` estiver ativo. Não libera arquivos de controle, impasses nem aprovações.

A classificação de comandos de shell é heurística (expressões regulares) e não detecta comandos ofuscados ou executados dentro de scripts. Consulte o [ADR-0015](decisions/ADR-0015-claude-code-hooks.md).

## Skills auxiliares

A skill `aifw-workflow` delega duas etapas a skills do host ([ADR-0013](decisions/ADR-0013-skill-delegation.md)):

- `grilling` (ou `grill-me`) conduz a entrevista do intake;
- `code-review` revisa o diff, usando `principle-catalogs/` como fonte de padrões.

Sem essas skills instaladas, o agente segue o mesmo método manualmente.

## Modelos

O Claude Code não troca o modelo da sessão por comando do AIFW. `aifw route explain` recomenda FAST/WORK/BRAIN (haiku/sonnet/opus), e a skill usa essa recomendação ao delegar trabalho a subagentes. Consulte [Roteamento](routing.md).
