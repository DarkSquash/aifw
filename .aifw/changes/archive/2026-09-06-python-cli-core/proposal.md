# Proposta: CLI e núcleo Python

Migrar os 35 comandos e todo o núcleo para Python, conforme autorização explícita do usuário. Preservar YAML/JSON, classificação, permissões, gates, approvals e as garantias de archive do ADR-0010.

Aceitação: testes Python, paridade capturada do runtime anterior, wheel instalado fora do checkout sem Node no PATH, documentação e CI Python. Integração Pi deve chamar o núcleo Python.
