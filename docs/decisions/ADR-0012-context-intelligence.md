# ADR-0012 — Contexto seletivo e integridade documental

Status: accepted

## Contexto

Projetos distribuem conhecimento entre documentos e instruções de agentes. Referências
quebradas, cópias divergentes e checks não executados podem parecer orientação confiável.
A descoberta também ignorava ADRs convencionais em docs/decisions.

## Decisão

Adicionar inventário, seleção e checagem local de contexto; comparar hashes de documentos
e fontes declaradas sem certificar semântica; gerar blocos delimitados para agentes a partir
de fonte comum; inspecionar referências de gates na CI separadamente da execução.

Dependências obrigatórias prevalecem sobre o orçamento informativo. Documentos importados
não viram autorização ou regras automaticamente. Preservar AGENTS universais e não executar
código durante descoberta. Gates hard/human exigem pass; skipped, warning e desconhecidos bloqueiam.

## Autorização e limites

Autorização do usuário nesta tarefa, em 2026-09-19:
“vamos aplicar essas melhorias no aifw então assim a gente deixa ele ainda mais completo”.

Escopo: melhorias propostas na análise anterior, incluindo ADRs, contexto por tarefa,
consistência de instruções, referências e gates. Nenhum conteúdo, segredo ou código
proprietário do projeto analisado é incorporado. Testes usam projetos sintéticos.
Nenhuma publicação ou alteração no projeto de origem.

Seleção lexical não interpreta intenção profunda. Hashes não provam correção documental.
Correspondência em GitHub Actions não prova execução ou proteção de produção. Auditoria
semântica continua responsabilidade do revisor.
