# ADR-0025 — Escopo das aprovações: instalações, commits e L3

- Status: accepted
- Date: 2026-10-18
- Impact: L3
- Approved by: human:DarkSquash

## Contexto

As confirmações do hook interrompiam trabalho rotineiro, como editar o código do próprio AIFW (`protectedPaths: [python/aifw/]`). Ao mesmo tempo, a instalação de programas fora da tabela (`winget`, `npx`, `uvx`, `git clone`) passava sem pergunta, e a de pacotes podia ser liberada pela allowlist (`package-registry`).

O usuário definiu, em 2026-10-18, o que precisa da aprovação dele:

- instalações de projetos novos, bibliotecas ou qualquer programa;
- mudanças L3;
- commits.

Todo o resto pode ser alterado, desde que fique registrado nos commits.

## Decisão

1. Novo tipo de ação `install`, que sempre pede confirmação, mesmo com o serviço na allowlist. Cobre:
   - gerenciadores de pacotes (`pip`, `uv add/pip/tool`, `npm/pnpm/yarn/bun install|add|create`, `cargo`, `go`, `gem`, `composer`, `conda`, `flutter/dart pub`);
   - gerenciadores de sistema (`winget`, `choco`, `scoop`, `apt`, `brew`, `snap`, `dnf`, `yum`, `pacman`);
   - quem baixa e roda pacotes (`npx`, `pnpx`, `bunx`, `uvx`, `pipx run`, `pnpm/yarn dlx`);
   - quem traz projetos (`git clone`, `gh repo clone`).

   `uv sync` continua liberado.
2. Novo tipo de ação `commit` para `git commit`, `merge`, `rebase`, `cherry-pick`, `revert` e `am`, que sempre pede confirmação. As demais operações locais do git continuam livres.
3. `python/aifw/` sai de `protectedPaths` neste repositório. Os arquivos de controle do AIFW (`aifw.yaml`, `.aifw/` e `.claude/settings`) continuam pedindo confirmação: são as mudanças de núcleo, que o próprio AIFW classifica como L3.
4. A skill `aifw-workflow` passa a exigir o "sim" do usuário antes de começar qualquer mudança L3.
5. Nova opção `opaqueCode: allow | ask` em `permissions.yaml` (padrão `ask`): com `allow`, código que o hook não consegue ler (`python -c`, scripts que chamam programas, `eval`) roda sem perguntar. Uma aprovação do AIFW escondida nesse código continua negada. Neste repositório a opção foi testada e voltou a `ask` em 2026-10-18; uma forma mais autônoma fica para depois.
6. Nova opção `trustedPackages` em `permissions.yaml`: pacotes que `npx`, `uvx` e afins podem baixar e rodar sem perguntar. Neste repositório: `ctx7`, usado pela regra global de documentação. Com `-p`, `--package` ou `--from`, o nome do comando não diz qual pacote é instalado, então volta a perguntar.
7. Continuam como estavam (ver Consequências):
   - push, deploy de produção e escrita externa;
   - comandos destrutivos;
   - código que o hook não consegue ler;
   - leitura de segredos.

## Consequências

- Comandos com `npx` passam a pedir confirmação a cada uso, exceto os pacotes em `trustedPackages`.
- Uma edição errada no código do hook pode bloquear todas as ações até ser corrigida. A recuperação é `git checkout` no arquivo, possível porque os commits guardam a versão anterior.
- Num projeto com `opaqueCode: allow`, um script pode instalar, fazer commit ou push sem que o hook veja, porque o hook só vê o que o comando mostra. A proteção passa a ser a revisão dos commits.
- Os itens do ponto 7 continuam pedindo confirmação. Eles não se enquadram nas três categorias da decisão, mas também não alteram arquivos que os commits protegem: publicam, apagam ou escondem o que fazem. Fica para o usuário decidir se mudam.

## Rollback

Recolocar `python/aifw/` em `protectedPaths` e desfazer as mudanças listadas.
