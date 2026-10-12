# Design

Decisões, alternativas, consequências e limites: docs/decisions/ADR-0010-spec-archive-integrity.md.

Implementação: separar commit de cleanup; compartilhar validação de aprovação/arquivo real; rejeitar capabilities duplicadas; exigir arquivo para passed e sucesso dos compromissos checkedBy; validar título e saída.

Risco: validação mais rigorosa pode bloquear mudanças ativas antes aceitas indevidamente. Migração: revisar essas entradas, sem reescrever arquivos históricos. Rollback de código: checkpoint em evidence/checkpoint.json; preservar artefatos aceitos após a correção.
