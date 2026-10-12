# Migração para Python — v0.3.0

O CLI e o núcleo executam em Python 3.11 ou superior. O pacote local é `aifw-cli`, com os comandos `aifw` e `python -m aifw`. Nenhum comando do núcleo usa Node.js. Ferramentas de um projeto Web, quando configuradas como gates, continuam exigindo o runtime da própria aplicação.

## Instalação e desenvolvimento

Na raiz deste repositório:

```powershell
uv sync --locked --extra dev
uv run --no-sync aifw --version
uv run --no-sync python -m pytest -q
uv run --no-sync ruff check python tests_python scripts setup.py
uv run --no-sync python scripts/generate_cli_reference.py --check
uv run --no-sync python -m build --no-isolation
```

Para disponibilizar a ferramenta fora do repositório, `uv tool install .` cria um ambiente próprio. Alternativamente, com Python instalado: `python -m pip install .`. Não há publicação no PyPI nesta entrega.

O wheel em `dist/aifw_cli-0.3.0-py3-none-any.whl` inclui schemas, templates, políticas, profiles, catálogos e avaliações. Não depende do checkout de origem. O arquivo `uv.lock` fixa as dependências usadas no desenvolvimento e na CI.

## Compatibilidade

- Os 35 comandos finais e os códigos 0/1/2 permanecem disponíveis.
- Os documentos YAML/JSON existentes permanecem legíveis; a representação textual YAML pode mudar ao salvar. Datas são strings, booleanos seguem YAML Core e chaves duplicadas são rejeitadas.
- O `--help` passa a usar argparse. `doctor` verifica Python no lugar de Node.
- Projetos novos fixam `frameworkVersion: 0.3.0`. Um projeto existente não tem seu manifesto alterado só por instalar a CLI; a atualização do pin é explícita.
- APIs Python usam nomes `snake_case` e dicionários com as mesmas chaves dos contratos persistidos. Exemplo: `from aifw.routing import route_task` e `from aifw.specs import archive_change`.
- O resolver compara a definição de uma regra sem seu campo gerado `origin`, permitindo reapresentar a mesma definição sem confundi-la com um override. Invariantes continuam bloqueando definições diferentes.
- Gates Windows `.cmd`/`.bat` são iniciados com argumentos delimitados e rejeitam expansão `%`, aspas e quebras de linha nos argumentos.
- Gates Python usam o executável encontrado no PATH. Se Python não estiver no PATH, usam o ambiente que executa o AIFW; isso mantém funcional a instalação isolada. Ative o ambiente do projeto quando os gates dependerem de seus pacotes.

## Verificação e referência histórica

As fixtures `tests_python/fixtures/legacy-parity.json` e `cli-parity.json` foram capturadas da implementação TypeScript corrigida, antes da substituição. Os testes de Python não executam Node para consumir essas referências. Testes adicionais exercitam adoção, decisões, intake, gates, validação, instalação isolada e falhas de filesystem durante archive.

O código TypeScript original está em `.aifw/legacy/typescript/`, fora da execução e da distribuição Python. A evidência da migração está na mudança arquivada `python-cli-core`; o checkpoint local anterior foi descartado em 2026-10-11.

A decisão autorizada está no [ADR-0011](decisions/ADR-0011-python-runtime.md). A matriz de CI cobre Windows e Ubuntu com Python 3.11–3.13; resultados locais desta entrega não substituem uma execução remota dessa matriz.
