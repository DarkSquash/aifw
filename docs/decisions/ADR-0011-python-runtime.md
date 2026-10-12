# ADR-0011: CLI e núcleo Python independentes de Node.js

- Status: accepted
- Date: 2026-09-06
- Impact: L3
- Authorized by: human:DarkSquash, nesta tarefa: "CLI e núcleo em Python, sem Node.js (recomendado)".
- Supersedes: escolha de runtime TypeScript/Node do ADR-0001 para o núcleo e CLI.

## Decisão

Migrar o CLI e todo o núcleo para Python 3.11+, mantendo os 35 comandos, códigos de saída 0/1/2, documentos YAML/JSON e as correções do ADR-0010. Publicar o pacote local `aifw-cli` v0.3.0 com entrada `aifw` e `python -m aifw`. Usar argparse, pathlib/subprocess, PyYAML e jsonschema; dependências e ferramentas de teste ficam declaradas em pyproject.toml e lock.

O núcleo não executará JavaScript nem iniciará Node para cumprir seus comandos. TypeScript anterior será preservado como referência histórica separada. A integração Pi é um adapter opcional executado no ambiente do Pi e deve consumir o CLI Python; não deve duplicar governança. Node pode continuar necessário a ferramentas da aplicação inspecionada, como um gate npm, mas não ao AIFW.

## Compatibilidade e alternativas

Um wrapper Python sobre Node foi explicitamente descartado pelo usuário. Reescrever somente os comandos principais deixaria funcionalidades existentes ausentes, portanto a migração inclui specs, brownfield, catálogos, resolução, permissões, impasse, roteamento, conformance e gates.

Preservar nomes e estrutura dos contratos. Mudanças inevitáveis do runtime, como o diagnóstico de Python e o formato de help do argparse, são documentadas. Comparações de contratos e fixtures da versão TypeScript permitem identificar divergências; evidência nova não é inferida de testes antigos.

## Migração e rollback

Criar checkpoint antes de substituir fontes, instalar o wheel em ambiente isolado e verificar execução fora do repositório sem Node no PATH. Atualizar documentação, mapa, CI e manifesto do próprio projeto apenas após validar os fluxos. Para rollback restaurar o checkpoint registrado na mudança `python-cli-core`, preservar dados/specs novos e reinstalar o runtime antigo separadamente.

## Riscos

Diferenças de parsing YAML, ordenação, hash, caminhos Windows e execução de gates podem alterar comportamento. Rejeitar chaves YAML duplicadas, respeitar schemas, manter serialização determinística, provar recuperação de archive e preservar aprovação humana. A identidade em registros continua declarativa; a migração não cria autenticação criptográfica.
