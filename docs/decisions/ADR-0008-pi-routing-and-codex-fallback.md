# ADR-0008: Roteamento executável do Pi e fallback manual para Codex

- Status: superseded by [ADR-0014](ADR-0014-claude-code-host.md)
- Date: 2026-08-23
- Impact: L3
- Approved by: human:DarkSquash
- Item 6 (handoff Codex) substituído pelo [ADR-0013](ADR-0013-skill-delegation.md)

## Contexto

O adapter do Pi já recomendava FAST/WORK/BRAIN, mas não chamava a API real de troca de modelo. O Pi instalado oferece Luna, Terra e Sol no provider `openai-codex` e expõe `pi.setModel()`. Também faltava uma saída estruturada quando o Pi não resolvesse o caso.

## Evidência de ativação

A suíte `evals/routing/cases.yaml` contém 32 casos revisáveis cobrindo L0–L3, arquitetura, alta incerteza, falhas repetidas, cross-domain e tentativas de downgrade. O relatório persistido em `evals/reports/routing-2026-08-23.json` registra 100% de aprovação e zero falhas críticas. O pedido explícito do usuário nesta mudança é a aprovação humana.

## Decisão

1. Distribuir a extensão Pi do AIFW (removida no ADR-0014) como recurso oficial do pacote Pi do AIFW.
2. Mapear FAST para `openai-codex/gpt-5.6-luna`, WORK para `gpt-5.6-terra` e BRAIN para `gpt-5.6-sol`.
3. O agente chama `aifw_route_task` antes de trabalho não trivial; a ferramenta classifica por metadados estruturados e só troca o modelo se a policy persistida estiver em modo automático.
4. Policy local do projeto vence a global. Projeto sem policy usa `~/.pi/agent/aifw-routing.yaml`.
5. Modelo indisponível ou sem autenticação preserva o modelo atual e informa a falha; nunca há downgrade silencioso de BRAIN.
6. `/codex-handoff` e `aifw_codex_handoff` geram um documento local, redigido e orientado a evidência. O humano transfere manualmente para Codex.
7. Novos projetos continuam nascendo em `recommendation-only`; ativação por projeto continua exigindo eval e aprovação.

## Consequências

- Pi pode começar barato em Luna e trocar para Terra/Sol dentro do loop antes de alterações.
- A classificação inicial ainda depende de o agente fornecer metadados corretos; conformance e auditoria continuam necessárias.
- Sol custa mais e deve ser reservado a BRAIN.
- O fallback não funciona se o Pi estiver totalmente incapaz de executar comandos; nesse caso o usuário pode fornecer ao Codex o último handoff existente, `PROJECT_MAP.md`, erro e evidências manualmente.

## Rollback

Definir `enabled: false` e `mode: recommendation-only` nas policies global/local, executar `/reload` no Pi e, se necessário, remover o pacote local do AIFW. O default do Pi permanece Luna e nenhum arquivo de projeto é apagado.
