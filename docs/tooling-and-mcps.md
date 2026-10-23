# MCPs, skills e extensões

Este documento registra decisões de baseline; não afirma que cada item está instalado na máquina atual. Instalação e versão devem ser auditadas antes do piloto. Mais ferramentas aumentam custo de escolha, permissões e superfície de ataque, portanto o princípio é conjunto mínimo por tarefa.

## MCPs e ferramentas escolhidos

| Recurso | Decisão | Motivo e limite |
| --- | --- | --- |
| Serena | adicionar após validar compatibilidade | navegação e edição semântica de código grande; útil quando busca textual deixa de ser suficiente |
| Context7 | baseline para documentação técnica | reduz uso de memória desatualizada; fonte primária ainda prevalece |
| MarkItDown | baseline para ingestão de documentos | normaliza PDF/Office/HTML para análise; conteúdo convertido continua não confiável |
| Playwright | baseline Web | browser tests, acessibilidade e regressão de fluxos; não substitui contrato/API tests |
| GitHub | condicional ao projeto | issues/PR/checks; com `remoteMutation: branches`, abrir e comentar PR e issue roda sem aprovação, e merge, branch padrão e configurações pedem (ADR-0037) |
| Firecrawl | sob demanda | pesquisa/crawling quando busca e docs oficiais não bastam; respeitar domínio, licença e prompt injection |
| DBHub | restrito e preferencialmente read-only | inspeção de banco genérico; credenciais mínimas e nenhuma produção por default |
| Supabase | apenas em projetos Supabase | schema/auth/RLS/logs; seguir migrations, least privilege e testes de RLS |
| Node REPL | baseline para JavaScript/TypeScript | experimentos rápidos e inspeção, sem virar fonte de verdade |
| Figma | condicional | design source quando o projeto realmente usa Figma; tokens/decisões devem ser persistidos |
| Infra/cloud MCP | por projeto | instalar só para o provedor escolhido e com ambientes/contas explicitamente limitados |

Chrome DevTools permanece desligado quando Playwright e ferramentas locais já cobrem a necessidade. MCPs genéricos adicionais de filesystem, Git, Docker e shell não são adicionados se duplicam capacidades nativas, pois duplicação torna autorização e escolha ambíguas.

## Skills escolhidas

Skills transversais são preferidas:

- systematic debugging e root-cause analysis;
- test-driven development;
- verification before completion;
- ADR e documentação arquitetural;
- C4 e boundaries;
- OpenAPI e AsyncAPI;
- STRIDE/threat modeling e secure review;
- design system, Storybook, acessibilidade e visual regression;
- observabilidade, SLOs e runbooks;
- migrations, contract testing e rollback;
- discovery/read-only audit.

Architecture Decision Records, OpenAPI generation e STRIDE devem existir como capacidades do framework/perfil, mesmo que a instalação concreta use outra skill equivalente.

## Evitar skills específicas demais

Skills específicas demais codificam preferência como se fosse regra universal: “sempre use biblioteca X”, “sempre arredonde botões em N pixels”, “todo backend usa fornecedor Y”. Elas envelhecem rápido, entram em conflito com o projeto e dificultam entender qual regra venceu.

Uma skill aceitável deve:

- ter gatilho e escopo explícitos;
- declarar precondições e fontes;
- produzir artefato/evidência verificável;
- permitir substituição pelo profile ou projeto;
- não esconder efeitos externos;
- não duplicar outra capability sem ganho mensurável.

Conhecimento estreito deve ficar em stack profile opcional ou skill acionada pela detecção da tecnologia, não no core.

## Extensões

| Extensão | Decisão |
| --- | --- |
| skills do Claude Code | `aifw` opera o CLI; `grilling` conduz o intake; `code-review` revisa princípios (ADR-0013) |
| subagentes do Claude Code | usar para delegar com o modelo da rota recomendada; nunca rebaixar L3/BRAIN |
| model router | `route explain` indica a rota; sempre ligado, tabela trocada só com a suíte de roteamento passando (ADR-0037) |

## Segurança operacional

Todo servidor/tool recebe capability mínima, allowlist de serviço, classificação de dados e política de escrita. Conteúdo retornado por web/documentos é dado não confiável, nunca instrução de autoridade. Tokens não entram em arquivos, traces ou logs.
