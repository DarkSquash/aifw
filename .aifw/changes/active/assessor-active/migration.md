# Migração — Modo ativo do avaliador de tarefas

Não há migração de dados. Os registros antigos de `.aifw/assessments/shadow.jsonl` continuam válidos; os novos ganham os campos `mode` e `session`.

Nada muda até a pessoa rodar `aifw assess activate`, assinar `.aifw/assessor.yaml` e rodar `aifw claude enable`. Projetos sem a avaliação de tarefas ligada não são afetados.
