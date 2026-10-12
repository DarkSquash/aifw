# Referência TypeScript v0.2.0

Fontes, testes e configurações anteriores à migração Python autorizada no ADR-0011. Esta árvore não participa da execução, build, descoberta ou distribuição v0.3.0.

Os scripts de captura produziram as fixtures de paridade que agora são consumidas diretamente pelos testes Python. A suíte anterior passou com 162 testes antes da separação.

Para reconstruir o ambiente anterior, use o checkpoint completo `.aifw/cache/checkpoints/before-python-migration/` numa pasta separada, incluindo os recursos compartilhados. Não execute estes scripts de captura sobre o projeto atual: a estrutura relativa antiga foi preservada apenas como referência histórica.
