# Lifecycle de mudanças L0–L3

Impacto e complexidade são eixos independentes. L0–L3 mede risco/raio de impacto; FAST/WORK/BRAIN mede raciocínio necessário. Uma descoberta somente leitura pode ser BRAIN, e uma edição simples em produção pode ser L3.

| Nível | Exemplos | Artefatos mínimos | Aprovação |
| --- | --- | --- | --- |
| L0 | leitura, discovery, inventário, docs sem comportamento | registro + evidência | nenhuma |
| L1 | comportamento local, reversível, baixo blast radius | Change Case, testes, rollback | normalmente workflow |
| L2 | cross-module, contrato compartilhado, auth, dados sensíveis, design system, custo ou produção reversível | spec, plano, testes, rollback, revisão independente | condicional/obrigatória pelo sinal |
| L3 | Constitution/core, security boundary, migração destrutiva, breaking contract, produção irreversível | RFC, spec, plano, ADR, threat model, migração, rollback, revisão, aprovação | humana obrigatória |

## Fluxo

```text
intenção → classificação → artefatos → aprovação → checkpoint
       → implementação → gates → auditoria → docs/map → conclusão
```

O classificador seleciona o nível mais alto indicado. Dúvida sobre reversibilidade, dados ou produção eleva a classe até haver evidência.

Mudanças L2 e L3 usam o ciclo executável em `docs/spec-lifecycle.md`: deltas ficam isolados em `.aifw/changes/active/`, são validados contra `.aifw/specs/current/` e só entram na verdade aceita durante archive validado. L3 também exige aprovação humana persistida em ADR ou registro equivalente dentro do repositório.

## Quality gates por risco

- L0 valida manifesto e evidência de leitura.
- L1 adiciona map freshness e testes do comportamento alterado.
- L2 adiciona contratos, integração, segurança/UX conforme o domínio e revisão independente.
- L3 adiciona aprovação, migração/rollback provados, threat model e regressão integral.

TDD é obrigatório para comportamento novo ou bugfix. Documentação pura usa validação de links/schemas/artefatos em vez de testes artificiais.

## Conclusão

“Concluído” significa que os gates selecionados rodaram agora, evidências foram preservadas, fontes de verdade foram atualizadas e não há aprovação pendente. Um comando que não rodou nunca é inferido como aprovado.
