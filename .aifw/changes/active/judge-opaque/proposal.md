# Proposal — Juiz por modelo do resíduo opaque, em modo sombra

## Intent

O hook `PreToolUse` pede confirmação sempre que um comando roda código que ele não lê: Perl, Ruby, binários, `eval`, `python -c`, aliases e código passado por pipe para um shell. O impasse `hook-indirect-code` decidiu que regras fixas nunca cobrem tudo e que quanto menos aprovações, melhor. Esta mudança põe um modelo para julgar esse resíduo `opaque` pelo que o código realmente faz. Por enquanto ele só registra o veredito, a intenção provável do comando e a latência, sem mudar nenhuma decisão do hook.

## Scope

- Um hook assíncrono no `PreToolUse` (Bash e PowerShell), separado do hook síncrono: `aifw assess judge --hook`.
- O juiz roda só quando o comando tem um item `opaque` e o recurso `judge` está em `spec.assessment.features`.
- O acesso ao Claude é pela assinatura da pessoa, via `claude -p`, sem ferramentas, hooks, MCP nem skills: Haiku primeiro e Sonnet quando a confiança fica abaixo de 0,7 ou a resposta é `unknown`.
- A entrada é o comando mascarado e o texto dos arquivos que ele cita dentro do projeto. Esse texto vai mascarado, como dado não confiável, até 20 KB por arquivo e no máximo 5 arquivos, sem arquivos de segredo nem binários. A descrição do agente vai só como alegação a comparar.
- A saída tem veredito (`harmless`, `ask` ou `unknown`), confiança, intenção em uma frase e o sinal `mismatch`, quando a descrição do agente diverge do código.
- O registro vai para `.aifw/assessments/judge.jsonl`, com `aifw assess report` e `aifw assess verdict --feature judge`.
- A suíte `evals/assessment/judge-cases.yaml` mede Haiku, Sonnet e a escalada: acerto, liberações indevidas, latência e custo.

## Non-goals

- Mudar qualquer decisão do hook. O modo ativo é outra mudança, depois do critério de ativação.
- Julgar push, instalação, deploy, escrita externa, aprovações ou arquivos de controle: essas ações continuam só pela regra fixa.
- Usar o OpenRouter, o Decider ou uma chave de API.
- Ler imports ou seguir scripts chamados por scripts.

## Acceptance

- Um comando com parte `opaque` gera um registro com veredito, intenção, decisão da regra fixa e latência, e `hooks.evaluate` devolve a mesma decisão de antes.
- Comandos sem parte `opaque`, ferramentas que não são shell e projetos sem o recurso não chamam o modelo.
- `wouldChange` só é verdadeiro quando o único motivo da pergunta era o código opaco e o veredito é `harmless`.
- Texto do script e descrição do agente vão entre marcadores com nonce novo a cada chamada. Arquivos de segredo, binários, grandes ou fora do projeto não são enviados.
- Resposta malformada vira `unknown`, nunca `harmless`.
- O hook assíncrono não imprime nada e não falha a sessão.
- `dataClassification` `confidential` ou `restricted` impede a chamada.
- Testes com o `claude -p` simulado e a suíte completa de testes passam. A primeira rodada da suíte fica registrada em `evidence/`.
