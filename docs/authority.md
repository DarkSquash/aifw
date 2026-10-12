# Hierarquia de autoridade

## Duas perguntas diferentes

1. **Quem pode decidir?** Humano, Constitution, Charter/ADR/contrato, regras do projeto.
2. **Qual default técnico prevalece?** Core invariant, preferência pessoal, capability profile, stack profile, projeto.

Misturar essas perguntas permitiria que um profile técnico substituísse uma decisão do produto. O AIFW não permite isso.

## Ordem normativa

```text
aprovação e intenção humana explícita
        ↓
Constitution + core invariants irrenunciáveis
        ↓
Project Charter + ADRs + contratos aprovados
        ↓
regras específicas do projeto
        ↓
stack profile
        ↓
capability profile
        ↓
preferências pessoais
        ↓
heurística temporária do agente
```

No resolver executável, core invariants não substituíveis são protegidos independentemente da precedência de defaults. Para rules substituíveis, project > stack > capability > personal. Conflitos diferentes na mesma camada bloqueiam.

## Regra bem formada

Toda regra possui ID estável, versão, palavra normativa (`MUST`, `MUST_NOT`, `SHOULD`, `MAY`), declaração, escopo, justificativa, owner, modo de enforcement, evidências, fonte e `overridable`.

## Overrides

Um override legítimo:

- referencia o mesmo rule ID;
- vem de camada com autoridade suficiente;
- explica por que o contexto exige a diferença;
- não enfraquece regra irrenunciável;
- é persistido e testado.

Exceção temporária usa Waiver, não override permanente. Mudança na Constitution/core é L3.

## Artefatos gerados

`aifw resolve build` produz `.aifw/effective-policy.json` e `.aifw/framework.lock.yaml`. `resolve check` detecta drift sem reescrever. Preferências pessoais podem ser fornecidas por caminho explícito e não precisam ser copiadas para o repositório.
