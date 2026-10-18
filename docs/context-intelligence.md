# Contexto por tarefa e consistência das instruções

O AIFW inventaria documentação existente, seleciona referências por tarefa e detecta
referências quebradas e alterações desde um snapshot. Não executa comandos encontrados
nos documentos, não conecta a serviços e não considera texto importado como autorização.
Esses comandos funcionam também antes de `aifw init`.

## Importação sem reestruturar o projeto

```powershell
aifw context index --json
aifw context check --json
aifw context index --write --json
```

O índice lê Markdown em `docs/`, além de README.md, AGENTS.md e CLAUDE.md na raiz.
Dependências, saídas de build e históricos em `archive`/`_archive` ficam fora.
Diretórios de skills externos não são promovidos a regras. Frontmatter é opcional.
Na ausência de `scope`, o título principal serve como resumo pesquisável.
Nenhum texto original é modificado.

`--write` salva `.aifw/context-index.json` se não houver erros. O snapshot registra
hashes de documentos e fontes declaradas; **não é aprovação semântica**. Após revisar
mudanças reais, gere outro snapshot. Sem snapshot, `check` valida referências, mas
não detecta alterações anteriores.

Metadados opcionais, adaptáveis ao vocabulário do projeto:

```yaml
---
scope: autenticação login sessão
intents: [bugfix, security-review]
depends-on: [../schemas/auth.md, ../decisions/001-auth.md]
sources: [src/auth.ts]
required: false
---
```

`depends-on`, `sources` e `intents` aceitam listas ou strings separadas por vírgulas.
Dependências são documentos obrigatórios; fontes são arquivos cuja alteração exige
revisão. Fontes são comparadas por hash, sem inserir seus corpos na saída. Use caminhos
explícitos de arquivos, sem glob ou diretório.

Referências com `docs/`, `src/` ou `.aifw/` partem da raiz. Outros caminhos são relativos
ao documento, com fallback para `docs/` e raiz; `../` é sempre relativo ao documento.
Links externos não são acessados. Links Markdown, definições de links por referência
e caminhos literais em crases são conferidos. Blocos de código, padrões e placeholders
não são contratos. Fragmentos `#ancora` e Markdown complexo não são validados.

Arquivos `.env*`, chaves privadas, caminhos externos e links simbólicos são rejeitados.
Cada documento/fonte tem limite de 1 MB. A saída contém caminhos, metadados filtrados
e hashes, sem corpos de documentos. O filtro não substitui um scanner de segredos;
revise metadados antes de compartilhar um índice.

## Seleção e orçamento

```powershell
aifw context select --task "corrigir login" --intent bugfix --files src/auth.ts --budget 2500 --json
```

A seleção considera palavras da tarefa no caminho/scope, intenção explícita, arquivos
afetados e `required: true`. Inclui transitivamente `depends-on`, com proteção contra
ciclos. Informa os motivos de seleção e dependências fora do índice. A seleção em si não
usa rede, embeddings nem modelo para inferir responsabilidades.

Com `context` em `spec.assessment.features` (modo sombra, ADR-0026), o resultado ganha o
campo `assessment`. Nele o Decider aponta os documentos relevantes que as palavras não
acharam e os escolhidos só por uma palavra em comum. A avaliação usa só o caminho e o
assunto de cada documento, nunca o corpo, e a seleção não muda: o agente pode ler os
sugeridos. O relatório sai com `aifw assess report --feature context`. Um assunto
descritivo (`scope` nos metadados) melhora a avaliação.

O orçamento é informativo, estimado por caracteres/4 arredondados para cima. Não
confia em `tokens:` declarado. Documentos selecionados e dependências não são
descartados para caber: `overBudget` retorna aviso e código 2. Sem correspondência,
retorna aviso em vez de carregar tudo.

`check` detecta documentos adicionados/removidos/alterados e mudanças nas fontes e
dependências declaradas desde o snapshot. Mudanças pedem revisão, mas não provam erro
no conteúdo. Dependências não declaradas e contradições semânticas exigem revisão humana.

## Instruções comuns, mantendo o AGENTS universal

Crie `.aifw/project-instructions.md` com regras específicas e revisadas do projeto.
Use o [modelo](../templates/context/project-instructions.md) como ponto de partida.
Documentos encontrados não são promovidos automaticamente a regras.

```powershell
aifw instructions build --agent all
aifw instructions check --agent all
```

`codex` e `opencode` usam AGENTS.md; `claude` usa CLAUDE.md; `all` atualiza os dois.
Somente um bloco delimitado é gerado, referenciando a mesma fonte e seu hash. Bytes
fora dele são preservados, incluindo instruções universais. Nenhuma configuração
global é modificada. `--source` aceita outro Markdown local, exceto os arquivos gerados.

`check` detecta alterações na fonte/bloco, sem reinterpretar regras externas ao bloco.
Marcadores corrompidos/duplicados impedem a escrita. Destinos são verificados antes de
escrever; falhas de escrita provocam tentativa de restauração.

## Gates e CI

Acrescente estes gates opcionais ao conjunto existente quando fizerem sentido:

```yaml
- id: context-integrity
  enforcement: hard
  levels: [L1, L2, L3]
- id: instructions-integrity
  enforcement: hard
  levels: [L1, L2, L3]
```

O segundo exige fonte compartilhada e ambos os arquivos gerados. Para um único agente,
configure um gate com comando `aifw instructions check --agent codex`. O primeiro verifica
referências e o snapshot, quando presente. Versione o snapshot para detectar drift na CI.
Esses gates não são ativados automaticamente.

```powershell
aifw gates check --level L2 --json
```

Inspeciona configuração e referências literais em `run:` de GitHub Actions, distinguindo
referência automática, condicional, manual e ausente. Reconhece o comando completo ou
`aifw validate --level L2`, também via `python -m aifw` e com `--json` opcional. Reconhece
`uv run` com `--no-sync`, `--locked` ou `--frozen`, e equivalência entre executáveis
ruff/pytest/aifw e seus módulos Python. Outros wrappers,
scripts npm, matrizes e workflows reutilizáveis exigem revisão: ausência de correspondência
não prova ausência de CI.

Resultados mantêm `execution: not-run`: uma referência não prova execução, proteção de
branch ou bloqueio de deploy. Em `validate`, gates hard/human exigem status `pass`;
`skipped`, estados desconhecidos e avisos não aprovam.

Nos novos comandos, 0 indica verificação sem achados, 1 indica entrada/execução inválida
e 2 indica achados ou pendência. `gates check` retornando 0 certifica apenas correspondência
estática, nunca execução dos testes.
