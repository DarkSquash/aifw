# Design: runtime Python

Pacote em python/aifw, argparse como CLI, PyYAML com regras YAML Core, jsonschema para contratos, subprocess para gates e pacote wheel com recursos incluídos.

A árvore TypeScript foi separada em .aifw/legacy/typescript. A extensão Pi usa uma ponte JSON por stdin/stdout com toda a governança em Python.

O catálogo conserva owners e relações existentes; referências de código, manifesto e runtime são atualizadas conforme a migração explícita. A renovação do baseline factual está coberta pela autorização da mudança, sem inferir novas responsabilidades de negócio.

Rollback: preservar novos documentos e restaurar o checkpoint pré-migração numa pasta separada. Ver ADR-0011 e evidence/checkpoint.json.
