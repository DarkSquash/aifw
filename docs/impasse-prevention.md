# Prevenção de impasse e conflito com o framework

## Por que existe

Uma regra global pode ser inadequada a um contexto — por exemplo, um raio de botão muito grande em controles densos. Sem limite, um agente pode repetir ajustes cosméticos, acumular regressões ou mudar a regra silenciosamente.

## O que conta como tentativa distinta

Cada tentativa registra:

- hipótese falsificável;
- intervenção diferente, não apenas novos números;
- evidência antes/depois;
- resultado e instante.

Trocar `padding: 10px` por `9px`, depois `8px`, sem nova hipótese não são três estratégias. O fingerprint de hipótese + intervenção detecta repetição.

O fingerprint só pega texto idêntico depois de normalizado: reescrever a mesma ideia com outras palavras passa como tentativa nova. Com `impasse` em `spec.assessment.features` (modo sombra, ADR-0024), cada `aifw impasse attempt` também pergunta ao Decider, contra cada tentativa anterior, se a nova repete a estratégia.
- **Registro:** a probabilidade fica gravada em `.aifw/assessments/impasse.jsonl`, e o caso não muda.
- **Revisão:** você confere com `aifw assess report --feature impasse` e registra o veredito com `aifw assess verdict --feature impasse`.
- **Modo ativo, ainda não implementado:** com probabilidade de 0,7 ou mais, a tentativa contaria como repetição. O modelo só poderia antecipar o congelamento, nunca adiar.

## Limites

Mudanças seguras L0 e L1 permitem no máximo **cinco tentativas realmente distintas** sem sucesso. Mudanças arriscadas L2 e L3 permitem **duas tentativas realmente distintas**. Uma estratégia idêntica repetida abre o impasse imediatamente.

Esses números são tetos, não metas: evidência forte de conflito pode abrir o caso antes.

## Estados

```text
NORMAL → SUSPECTED → OPEN → HUMAN_REVIEW → HALF_OPEN → RESOLVED
                    ▲                         │
                    └──── falha na revalidação┘
```

- `NORMAL`: execução comum.
- `SUSPECTED`: primeira falha relevante; alterações destrutivas param.
- `OPEN`: limite/repetição atingido; novas mutações ficam congeladas.
- `HUMAN_REVIEW`: evidências, regra suspeita e proposta foram apresentadas.
- `HALF_OPEN`: humano aprovou mudança controlada; revalidação em andamento.
- `RESOLVED`: caso original e regressões passaram, artefatos foram atualizados.

## Comandos

```powershell
aifw impasse open --id login-radius --impact L2
aifw impasse attempt --id login-radius --hypothesis "..." --intervention "..." --evidence logs/run1.txt --outcome failure
aifw impasse status
aifw impasse review --id login-radius --rule ui.radius --explanation "..." --proposal "..."
aifw impasse decide --id login-radius --by human:proprietario --record docs/decisions/ADR-0016.md
aifw impasse revalidate --id login-radius --result passed --evidence logs/full.txt --artifacts policies/core.yaml
```

Os casos ficam em `.aifw/impasses/`. `impasse status` retorna código 2 enquanto algum caso estiver `OPEN` ou `HUMAN_REVIEW`. No Claude Code, o hook `aifw-hook` aplica o congelamento: nega edições e comandos destrutivos e pede confirmação para outros comandos de shell ([Claude Code](claude-code.md)).

## Protocolo de escalada

O agente deve preservar checkpoint, attempt ledger, testes, screenshots/logs sanitizados e comparação isolada. Depois explica ao usuário:

1. o resultado esperado;
2. as hipóteses e intervenções distintas tentadas;
3. o que a evidência eliminou;
4. qual rule ID/profile/contrato parece incompatível;
5. escopo e riscos da mudança proposta;
6. alternativas, rollback e validação.

Ele não muda o framework antes da aprovação. Se aprovada, a mudança é L3 e segue para BRAIN/opus ou modelo equivalente competente. A implementação atualiza ADR, policies/profiles, schemas, Constitution/docs quando aplicável, testes de conformidade, migração e `PROJECT_MAP`; em seguida revalida o cenário original e a suíte integral.

Rejeição humana mantém o impasse aberto ou encerra a feature sem fingir correção. Urgência não transforma repetição em estratégia.
