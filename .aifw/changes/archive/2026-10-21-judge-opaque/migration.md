# Migração — Juiz do resíduo opaque

Não há migração de dados: o recurso só cria arquivos novos (`.aifw/assessments/judge.jsonl` e `judge-verdicts.jsonl`) e não muda nenhum formato existente.

- `aifw claude enable` passa a instalar uma segunda entrada no `PreToolUse` (`aifw assess judge --hook || true`, assíncrona). `aifw claude check` acusa a falta dela nos projetos já habilitados, até rodarem `aifw claude enable` de novo.
- A entrada não faz nada enquanto `judge` não estiver em `spec.assessment.features` com `mode: shadow`.
- Nenhuma decisão do hook muda, e nenhuma configuração precisa ser alterada.
