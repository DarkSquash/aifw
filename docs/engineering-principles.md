# Princípios de engenharia contextuais

O AIFW separa arquitetura de princípios de design. Clean Architecture, Ports and Adapters ou Vertical Slice são alternativas arquiteturais comparadas em `decision-catalogs/`. Clean Code, SOLID, KISS, YAGNI e DRY são lentes de revisão que podem coexistir e por isso vivem em `principle-catalogs/`.

## Conteúdo inicial

### Clean Code

- nomes que comuniquem intenção;
- funções e módulos coesos, sem limite arbitrário de linhas;
- comportamento de erro explícito;
- comentários que registrem por que e restrições, não narrem sintaxe;
- testes legíveis que protejam comportamento;
- efeitos colaterais visíveis nas fronteiras.

### SOLID

- Single Responsibility Principle;
- Open-Closed Principle;
- Liskov Substitution Principle;
- Interface Segregation Principle;
- Dependency Inversion Principle.

### Fundamentos complementares

- KISS e simplicidade essencial;
- YAGNI baseado em evidência;
- DRY somente quando o conhecimento duplicado é realmente o mesmo e já estabilizou;
- Separation of Concerns;
- composição em vez de herança quando não existe uma relação substituível estável.

## Por que não são hard gates universais

Princípios são heurísticas, não algoritmos. Uma função grande pode ser mais legível que dez funções artificiais; DRY prematuro pode acoplar contextos independentes; OCP sem pressão real de extensão cria abstração especulativa; SRP por contagem de métodos fragmenta o sistema.

Cada princípio declara:

- sinais que tornam a revisão aplicável;
- perguntas que o agente deve responder;
- evidência esperada;
- riscos de mau uso;
- exceções legítimas;
- fontes.

Princípios sem `appliesWhen` são sempre revisados. Os demais ficam `deferred` até existir um sinal pertinente. `deferred` não significa violação.

## Uso

```powershell
aifw principle list
```

A revisão é feita pela skill `code-review`, no eixo Standards, sobre o diff da mudança. Informe `principle-catalogs/` como fonte de padrões documentados: para cada princípio aplicável ao diff, o revisor responde às perguntas do catálogo, respeita as exceções e aponta os riscos de mau uso. Findings devem citar arquivo, comportamento, impacto e evidência concreta. A policy core classifica essa revisão como auditoria contextual (`evidence: [code-review]`), não como aprovação automática. Consulte o [ADR-0013](decisions/ADR-0013-skill-delegation.md).
