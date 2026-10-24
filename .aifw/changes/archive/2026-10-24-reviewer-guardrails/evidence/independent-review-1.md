# Revisão independente — reviewer-guardrails

## Adversário

Rodada 1. Escopo: `git diff f419bd5..HEAD` (commit 9ac9cd1), a delta `specs/claude-subagents.delta.yaml`, a seção Acceptance de `proposal.md`, `design.md` e os itens 6 a 8 do ADR-0038. Fiz os experimentos numa pasta temporária fora do projeto, por arquivos de teste rodados com `python -m pytest` (`scratchpad/t/test_probe.py`, `test_stash.py` e `test_stash2.py`). Eles chamam `aifw.hooks.handle` com `agent_type` sobre um projeto criado por `test_workflows.init`, e o git roda num repositório temporário.

### Achado 1 — `git stash -a` passa pela trava dos revisores (severidade média)

- Arquivo: `python/aifw/shell.py:557`. A correção só trata o `git stash` sem argumentos. Com qualquer argumento de `LIST_ARGS`, o comando ainda conta como `read-only`. `git stash -a` é a forma curta de `git stash push --all`: guarda e desfaz as alterações rastreadas e apaga do disco os arquivos não rastreados e os ignorados (`.venv/`, por exemplo).
- Spec: a delta diz que o hook "deve negar a um subagente revisor ... o comando de shell que ... altera o repositório" (REQ-SUBAGENTS-REVIEWER-GUARD, `statement`) e cita `git stash` no `when` do SCN-SUBAGENTS-REVIEWER-GUARD. O critério de aceitação diz que o revisor "não consegue ... rodar ... `git stash`". O CHANGELOG diz que o `git stash` "que guarda e desfaz as alterações deixa de contar como leitura".
- Cenário: chamada `Bash` com `command="git stash -a"` e `agent_type` igual a `aifw-adversary` ou `aifw-qa`.
- Resultado esperado: `deny`, com o motivo "a reviewer subagent ...".
- Resultado obtido: `handle()` devolve `None`, ou seja, nenhuma objeção. `analyze("git stash -a")` classifica o comando como `['read-only']`. Para comparar, `git stash` é negado e `git stash -u` vira `git-local` e também é negado.
- Prova do efeito, num repositório temporário: depois de `git stash -a`, o `f.txt` editado voltou a `one`, o `new.txt` não rastreado deixou de existir e `git stash list` mostra `stash@{0}: WIP on master`.

### Achado 2 — outros comandos git que alteram o repositório passam como leitura (severidade baixa)

- `git tag -a v9 -m x`: `python/aifw/shell.py:557`, mesma linha do achado 1. O `-a` está em `LIST_ARGS` por causa do `git branch -a`, mas para `tag` ele cria uma tag anotada. O comando é classificado como `['read-only']`, `handle()` devolve `None` para os dois revisores, e no repositório temporário a tag `v9` foi criada.
- `git reflog expire --expire=now --all`: `reflog` está em `GIT_READ` (`python/aifw/shell.py:179`), então qualquer subcomando conta como leitura, inclusive `expire` e `delete`, que apagam entradas do reflog. `handle()` devolve `None` para os dois revisores.
- Spec: o mesmo `statement` do REQ-SUBAGENTS-REVIEWER-GUARD ("o comando de shell que ... altera o repositório"). A trava depende do classificador, e esses comandos chegam a ela como `read-only`.

### Ressalvas (sem prova de violação da spec)

1. Comandos `aifw` que gravam no projeto passam para o revisor, todos como `read-only`: `aifw spec archive x`, `aifw validate --write` e `aifw claude enable`. A spec libera "aifw" de forma explícita, então não reprovo. Mesmo assim, um revisor consegue arquivar a mudança ou reinstalar as definições.
2. `REVIEW_FILE` (`hooks.py:145`) aceita o `independent-review.md` de qualquer mudança ativa (`.aifw/changes/active/zz/independent-review.md` passa), e não só o da mudança em revisão, como diz a spec ("além do independent-review.md da mudança"). O hook não sabe qual mudança está em revisão. O risco é baixo.
3. Proteção de `.claude/agents/aifw-*` pelo shell: a busca por trecho do texto não pega `cp templates/claude/agents/aifw-qa.md .claude/agents/` nem `cd .claude/agents && sed -i s/a/b/ aifw-qa.md`. `evaluate()` devolve `None` para os dois no agente principal, sem pedir confirmação. A skill `aifw-workflow` tem a mesma lacuna (`cp -r templates/claude/skills/aifw-workflow .claude/skills/`) e o mecanismo é anterior à mudança. A spec pede "como a skill do AIFW" e o cenário cita só Edit e `sed -i` com o caminho completo, por isso fica como ressalva. O `cp` para a pasta é um caminho plausível por engano, para quem atualiza a cópia instalada à mão.
4. Falsos positivos contra "deixando seguir leitura":
   - `python --version` é classificado como `filesystem-write` e negado ao revisor. Para o agente principal o resultado é `None`.
   - Um script de sonda fora do projeto que importa `aifw.shell` ou `aifw.hooks` também foi negado, com a mensagem do revisor. Não isolei a causa; o `indirect` lê o script.
   - O caminho por `python -m pytest <arquivo fora do projeto>` funcionou.
5. Quando a trava se aplica, `reviewer_change` substitui o motivo de um `deny` que `evaluate` já tinha dado (por exemplo, o de forjar o hook), e o revisor vê só a mensagem genérica. Se `evaluate` lançar uma exceção, a trava não roda e o resultado fica `ask`, não `deny`. Não reproduzi esse segundo caso.
6. Esta rodada rodou com a definição antiga do `aifw-adversary`, carregada no início da sessão. O texto pedia "Use a skill `code-review`" e a ferramenta Skill estava disponível. Não invoquei a skill: ela lança subagentes e eu não tenho `Agent`. Fiz o eixo Spec diretamente. O critério "esta mudança revisada pelo fluxo de duas etapas" só vale com as definições novas depois que o Claude Code as recarregar.

Resultado: reprovado
