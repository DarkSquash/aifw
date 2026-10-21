# Aprovação L3 — judge-opaque

O que a pessoa aprova ao rodar `aifw spec approve judge-opaque`:

- Um segundo hook `PreToolUse`, assíncrono (`aifw assess judge --hook`), que pede ao Claude da assinatura, via `claude -p`, um julgamento dos comandos com código que o hook não lê. Ele **só registra** em `.aifw/assessments/judge.jsonl` e não muda nenhuma decisão do hook (ADR-0035).
- O recurso `judge` ligado em `aifw.yaml`. Comandos `opaque` e o texto dos scripts de código que eles citam vão mascarados à Anthropic, pela assinatura. Arquivos de segredo, de dados, com chave privada, binários ou grandes não são enviados.
- Para o futuro modo ativo, fica registrado que o caminho será o `aifw-hook` chamando o Haiku só para comandos `opaque`. A ativação em si é outra mudança.

Evidência:
- `evidence/tests.txt`: 2404 testes passando.
- `evidence/judge-eval-1.txt` e `judge-eval-2.txt`: duas rodadas reais da suíte de 40 casos. O gabarito ainda aguarda sua revisão.
- `independent-review.md`: segunda revisão independente, aprovado com ressalvas. As correções estão em `evidence/review-2-response.md`. A primeira revisão foi sobrescrita pela segunda; seus achados estão listados nela como "achados anteriores".
- `aifw validate --change judge-opaque`: todos os gates passam, exceto a aprovação humana.
