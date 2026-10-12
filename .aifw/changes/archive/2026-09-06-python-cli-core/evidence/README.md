# Evidências da migração Python

- verification.json: resultado consolidado.
- pytest.xml e python-tests.txt: 1902 testes Python aprovados.
- typescript-baseline.txt: baseline anterior de 162 testes.
- isolated-wheel.json e release-package.json: instalação independente, pacote sem JavaScript e digest.
- global-cli-validation.json e l3-gates.json: gates mecânicos aprovados; revisão independente permanece audit/not-run.
- pi-adapter-smoke.json: ponte real Python com loader/dependências do Pi e API do host simulada.
- global-launchers.json: comando global atualizado e backup.
- checkpoint.json: cópia anterior à migração.

A matriz remota de CI não foi executada nesta sessão. Nenhum modelo real do Pi foi alterado e nenhum handoff foi enviado.
