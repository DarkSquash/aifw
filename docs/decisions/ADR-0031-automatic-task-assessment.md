# ADR-0031 — Avaliação automática das tarefas em modo sombra

- Status: accepted
- Date: 2026-10-19
- Impact: L2
- Approved by: human:DarkSquash

## Contexto

O avaliador de tarefas (ADR-0023) só registrava quando o agente lembrava de rodar `aifw change assess`. Em dias de uso, juntou 1 registro dos 50 necessários para decidir a ativação.

## Decisão

1. Novo hook `UserPromptSubmit`, assíncrono e com tempo limite de 60 s, instalado por `aifw claude enable`. Ele avalia cada pedido da pessoa com o mesmo `assess` do comando, sem piso de diff, e grava com `source: prompt`.
2. Não são avaliados:
   - comandos `/`;
   - pedidos com menos de 5 palavras, que costumam ser respostas como "pode subir";
   - nada, quando o recurso `tasks` está desligado ou falta alguma guarda (allowlist, chave, classificação de dados).
3. O pedido passa pelo `redact` do AIFW antes de sair da máquina e é cortado em 4000 caracteres.
4. Prompts de subagentes não disparam o hook; só os da pessoa.

## Consequências

- Cerca de US$ 0,00001 por pedido. Rodando em segundo plano, a sessão não espera a resposta.
- Pedidos que dependem da conversa ("pode começar pelo 1") são avaliados sem esse contexto e tendem a sair errados. O veredito da pessoa serve para marcá-los.
- O `redact` só reconhece alguns formatos de segredo (`sk-...`, `Bearer`, `api_key=`, `password=`, `secret=`). Um segredo colado em outro formato iria para o OpenRouter. Projetos `confidential` ou `restricted` nunca chamam o modelo.

## Rollback

Tirar `tasks` de `spec.assessment.features`, ou remover o hook `UserPromptSubmit` do `.claude/settings.json` e de `claude.HOOKS`.
