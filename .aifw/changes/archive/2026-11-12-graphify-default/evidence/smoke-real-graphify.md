# Smoke real com graphify 0.9.107

Fonte do AIFW: `PYTHONPATH=C:/Users/DarkSquash/Documents/Projetos/aifw/python python -m aifw ...`
(`aifw.__file__` = `...\Projetos\aifw\python\aifw\__init__.py`; `claude enable --help` lista `--no-graphify`).
Clones descartaveis (git clone do repo) em
`C:\Users\DARKSQ~1\AppData\Local\Temp\claude\f70c4826a486d420\31451809-735d-4dd2-985a-991c20809a6a\scratchpad\smoke-112443\{a,b,c,d,e}`.
Saidas JSON completas: `smoke-112443\s1.json`, `s2.json`, `s4.json`, `s5.json`, `s6.json`, `s7.json`.

## 1. Clone A, sem grafo: `python -m aifw claude enable --json`
- Codigo de saida 0; tempo 26 s.
- `"graphify": "graph built; git hooks installed"`.
- `.gitignore` termina com:
  ```
  # AIFW local files (not versioned)
  graphify-out/
  ```
- `graphify-out/graph.json` existe (4337437 bytes).
- `.git/hooks/`: post-checkout, post-commit, post-merge, post-rewrite.
- `.gitattributes` ganhou `graphify-out/graph.json merge=graphify`.
- `git status --short`: ` M .gitattributes`, ` M .gitignore` (sem `graphify-out/`).
- Resultado: PASSOU.

## 2. Repetir enable no clone A
- Codigo de saida 0; 1298 ms.
- `"graphify": "graph already exists; git hooks installed"`.
- `grep -c graphify-out .gitignore` = 1; cabecalho `AIFW local files` = 1.
- Blocos por hook (`grep -c 'graphify.*hook-start'`): post-commit 1, post-checkout 1, post-merge 1, post-rewrite 1.
  Nota: o marcador difere por hook (`graphify-hook-start`, `graphify-checkout-hook-start`,
  `graphify-merge-hook-start`, `graphify-rewrite-hook-start`); so o post-commit usa `graphify-hook-start`.
- `merge=graphify` em .gitattributes: 1 ocorrencia.
- Resultado: PASSOU.

## 3. Commit de teste no clone A
- Alteracao: `echo "# smoke" >> python/aifw/common.py`.
- Primeiro commit falhou (exit 128) por `commit.gpgsign` global (gpg cancelado), nao relacionado ao AIFW/graphify;
  repetido com `-c commit.gpgsign=false -c user.name=t -c user.email=t@t`, exit 0.
- Saida do commit: `[graphify hook] launching background rebuild (log: /c/Users/DarkSquash/.cache/graphify-rebuild.log)`.
- Em 60 s, mtime de `graphify-out/graph.json` NAO mudou (11:25:39).
- Observado: o hook rodou em segundo plano (log e `.graphify_build_state.json`/`manifest.json`/`cache` atualizados
  as 11:28:30, ~11 s apos o commit). Log:
  ```
  [graphify hook] 3 file(s) changed - rebuilding graph...
  ... AST cache: 0/1 files served from cache (0%); 1 to extract
  [graphify watch] No code-graph topology changes detected; outputs left untouched.
  ```
  Ou seja, o rebuild foi disparado pelo hook; graph.json nao foi regravado porque o graphify nao viu mudanca de topologia
  (a alteracao foi so um comentario).
- Resultado: o hook dispara e reconstroi em segundo plano (PASSOU); a atualizacao de graph.json nao foi observada
  por esta alteracao especifica (comportamento do graphify, nao testado com mudanca estrutural).

## 4. Clone B: `claude enable --no-graphify --json`
- Codigo de saida 0; `"graphify": "skipped (--no-graphify)"`.
- Sem `graphify-out/`; `grep -c graphify .gitignore` = 0; nenhum hook em `.git/hooks` (so *.sample);
  `git diff --stat .gitattributes` vazio; `git status --short` vazio.
- Resultado: PASSOU.

## 5. Clone C: PATH sem graphify
- `PATH=/c/Users/DarkSquash/AppData/Local/Python/bin:/usr/bin:/bin:/mingw64/bin:/cmd`;
  `command -v graphify` vazio, `python` e `git` achados.
- Codigo de saida 0; `"graphify": "graphify not found on PATH: skipped"`.
- Sem `graphify-out/`; `.gitignore` sem graphify (0); sem hooks; `git status --short` vazio.
- Demais chaves do JSON identicas as do cenario 4 (diff das linhas sem "graphify" vazio).
- Resultado: PASSOU.

## 6. Clone D: `core.hooksPath=.husky`
- Codigo de saida 0; 22 s.
- `"graphify": "graph built; core.hooksPath set: git hooks skipped (run `graphify hook install` if you want them)"`.
- `graphify-out/graph.json` existe; `.husky` vazio; `.git/hooks` sem hooks do graphify; `git status` so ` M .gitignore`.
- Resultado: PASSOU.

## 7. Clone E: post-commit preexistente com `echo mine`
- Codigo de saida 0; `"graphify": "graph built; git hooks installed"`.
- post-commit: linha 2 `echo mine` preservada, 1 bloco `graphify-hook-start`, arquivo executavel (15924 bytes).
- Resultado: PASSOU.

## 8. Desfazer no clone A: `graphify hook uninstall`
- Codigo de saida 0; removeu post-commit, post-checkout, post-merge, post-rewrite e
  `merge driver: removed from .gitattributes (other entries preserved)`.
- `.git/hooks` sem hooks do graphify.
- `git diff .gitattributes` (contra o indice) NAO e vazio: mostra a remocao da linha, porque o commit do cenario 3
  (`commit -a`) ja tinha incluido a linha adicionada pelo enable. Contra a base (`git diff HEAD~1 -- .gitattributes`):
  vazio, ou seja, o arquivo voltou ao original.
- Resultado: PASSOU (com a ressalva acima, causada pelo meu `commit -a`).

## Resumo de falhas / comportamentos inesperados
- Nenhuma falha do codigo do projeto.
- Observacoes: (a) `commit.gpgsign` global exigiu `-c commit.gpgsign=false` no commit de teste; (b) cenario 3: graph.json
  nao mudou de mtime porque o graphify decidiu "no topology changes" para um comentario; (c) `git commit -a` no clone
  tambem comitou `.gitignore`/`.gitattributes` alterados pelo enable (efeito do teste); (d) `git status` do clone nunca
  lista `graphify-out/`; as mudancas em `.claude` nao aparecem porque o repo ja as versiona/ignora (hooksChanged vazio).
- O graphify escreve o log de rebuild em `~/.cache/graphify-rebuild.log` (fora do clone).
