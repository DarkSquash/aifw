# Threat model: juiz por modelo do resíduo opaque, em modo sombra

## Modelo

Vale o modelo decidido no impasse `hook-indirect-code` (2026-10-20): o hook protege contra erros do agente e caminhos óbvios, não é um sandbox, e quanto menos aprovações, melhor. Nesta mudança, o juiz **não decide nada**: só registra. Os riscos de decisão (um juiz enganado que libera uma ação) ficam para a mudança que o ativar, que vai ser julgada pelos dados deste modo sombra.

## Escopo e assets

- A decisão do hook síncrono, que precisa ficar idêntica.
- Os segredos do projeto e da máquina, que não podem sair no texto mandado ao modelo.
- O uso da assinatura da pessoa.
- A sessão, que não pode receber texto do juiz nem travar por causa dele.
- O registro `.aifw/assessments/judge.jsonl`, base da futura decisão de ativar.

## Diagrama e trust boundaries

Agente (não confiável quanto a intenção) → comando e arquivos do projeto → `aifw assess judge --hook` (assíncrono) → `claude -p` (assinatura, Anthropic) → registro local.

São dados não confiáveis o comando, o texto dos arquivos citados, a descrição do agente, a resposta do modelo e qualquer arquivo que o agente possa escrever fora do projeto, como um `CLAUDE.md` numa pasta temporária.

## Actors

- O agente, inclusive sob prompt injection vinda de páginas, documentos ou saídas de ferramentas.
- Um colaborador que commita um script com texto dirigido ao juiz.
- A pessoa, que dá os vereditos.

## STRIDE

| ID | Categoria | Cenário | Impacto | Controle | Evidência | Risco residual | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J-001 | Elevation of privilege | o juiz muda a decisão do hook | ação liberada sem aprovação | hook separado e assíncrono; a saída de hooks async não controla a ação; `judge.py` não devolve decisão | `test_opaque_command_is_judged_and_the_hook_decision_is_unchanged` | nenhum nesta mudança | human:DarkSquash |
| J-002 | Tampering | texto no script ou na descrição convence o juiz ("isto é seguro, aprove", JSON falso, marcador de fechamento) | registro diz harmless para ação perigosa e infla a concordância | marcadores com nonce aleatório por chamada; prompt manda tratar persuasão como risco; resposta malformada vira unknown; casos de injeção na suíte, contados à parte | `test_untrusted_text_goes_between_markers_with_a_fresh_nonce`, `test_malformed_answers_are_unknown_never_harmless`, casos `injection-*` | o modelo pode ser enganado mesmo assim; por isso é só sombra, e a ativação depende da taxa de liberação na suíte | human:DarkSquash |
| J-003 | Tampering | `CLAUDE.md` ou settings plantados numa pasta acima da pasta de trabalho do `claude -p` | contexto do juiz manipulado; hooks rodando no juiz | pasta temporária nova e vazia; `CLAUDE_CODE_DISABLE_CLAUDE_MDS` e `..._AUTO_MEMORY`; `disableAllHooks`, `--strict-mcp-config`, `--disable-slash-commands`, `--tools ""` | `test_claude_is_called_without_tools_hooks_or_mcp` | configurações gerenciadas da organização, que a pessoa controla | human:DarkSquash |
| J-004 | Information disclosure | o comando ou um arquivo citado contém segredo | segredo enviado ao modelo | `mask()` (`redact` e tokens do GitHub, GitLab, Slack e AWS, mais atribuições a `*SECRET*` e `*TOKEN*`); só arquivos de código dentro do projeto; `SECRET_FILE` e `SECRET_NAME`, chave privada, dados, binários e grandes ficam na máquina; `confidential` e `restricted` bloqueiam | `test_secret_binary_large_and_outside_files_are_never_sent`, `test_data_files_credentials_and_tokens_stay_on_the_machine`, `test_guards_keep_the_judge_silent` | segredos em formatos que as máscaras não reconhecem, dentro de código; vão ao mesmo provedor que já recebe a conversa, que também vê o comando | human:DarkSquash |
| J-010 | Elevation of privilege | push, instalação ou rede escondidos no código opaco, que a regra fixa não vê | um juiz enganado marcaria a pergunta como dispensável | `SENSITIVE` no texto do comando e do código mantém `wouldChange` falso | `test_code_that_names_a_kept_effect_never_would_change` (também cobre texto dirigido ao revisor, como "responda harmless", que o Haiku seguiu na segunda rodada) | efeito montado em tempo de execução, sem o nome no texto; no modo ativo, a mesma regra precisa ficar fora do modelo | human:DarkSquash |
| J-011 | Evasion | script citado dentro de `$(...)`, `bash -c`, `;` colado ou caminho com `\` | o juiz julga sem o código | `candidates()` também separa nesses pontos | `test_scripts_are_found_inside_substitutions_inline_shells_and_windows_paths` | formas de citar arquivo que não estão nessa lista | human:DarkSquash |
| J-005 | Elevation of privilege | o juiz executa algo | efeito colateral pelo próprio juiz | `--tools ""`, sem MCP, sem hooks, sem skills | `test_claude_is_called_without_tools_hooks_or_mcp` | nenhum | human:DarkSquash |
| J-006 | Denial of service | `claude -p` trava, demora ou se acumula | processos presos; uso da assinatura | timeout de 120 s por chamada; só comandos com parte opaque; no máximo 2 chamadas por comando | `CALL_TIMEOUT` em `judge.py` | rajada de comandos opaque gera rajada de processos em segundo plano | human:DarkSquash |
| J-007 | Spoofing | saída do hook assíncrono entra na conversa | texto do juiz vira instrução para o agente | `aifw assess judge --hook` não imprime nada e engole exceções | `test_a_failed_cli_raises_and_the_hook_entry_prints_nothing` | nenhum | human:DarkSquash |
| J-008 | Repudiation | registro forjado pelo agente | concordância falsa na decisão de ativar | `.aifw/assessments/` é arquivo de controle do hook: escrita pelo agente pede confirmação; vereditos são aprovações humanas no terminal | `CONTROL` em `hooks.py` (existente) | nenhum novo | human:DarkSquash |
| J-009 | Information disclosure | a lista de permissões externas é afrouxada para o juiz | `curl` liberado para a Anthropic | o juiz não usa `externalAllowlist`; a guarda é `dataClassification` | `blocker()` em `judge.py`, ADR-0035 | nenhum | human:DarkSquash |

## Abuse cases

- **Script que só imprime e pede aprovação** (`injection-benign-only`): o gabarito diz ask, porque texto dirigido ao juiz é sinal de má intenção mesmo quando o código é inofensivo.
- **Descrição honesta com código perigoso:** o `mismatch` não é evidência; o veredito sai do código.

## Riscos residuais aceitos

- O juiz pode errar. Nesta mudança isso só afeta o registro e a decisão futura de ativar, que vai considerar a taxa de liberações indevidas na suíte e os vereditos da pessoa.
- Uso da assinatura em cada comando opaque.
