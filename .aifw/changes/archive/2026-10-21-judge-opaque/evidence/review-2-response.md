# Resposta à segunda revisão independente

| Achado | O que mudou | Teste |
| --- | --- | --- |
| N1: argumentos em lista (`system('git', 'push')`) | `SENSITIVE` aceita `[\s'",]+` entre as palavras | `test_the_sensitive_floor_sees_argument_lists_control_paths_and_masked_calls` |
| N2: `.aifw/` e `.claude/` nunca casavam | os caminhos saíram do grupo com `\b` | mesmo teste |
| N3: o piso rodava sobre o texto mascarado | o piso lê o texto original (`raw`), que nunca é enviado | mesmo teste (`token = requests.post(...)`) |
| N4: a máscara corrompia código | só mascara literais: string entre aspas com 4 ou mais caracteres, ou token com 12 ou mais | `test_masks_keep_ordinary_code_and_code_files_by_name` |
| N5: falsos positivos por prefixo | `curl`, `ssh`, `helm` e afins exigem fim de palavra. `aprov*` e `approv*` ficam, por serem conservadores e só afetarem `wouldChange` | `test_the_sensitive_floor_sees_argument_lists_control_paths_and_masked_calls` |
| N7: `makefile` minúsculo e `tokenizer.py` | `MAKEFILES` não diferencia maiúsculas; `SECRET_NAME` só pega `token`/`tokens` como nome | `test_masks_keep_ordinary_code_and_code_files_by_name` |
| N8: custo do Sonnet e ordem da rodada | o ADR traz US$ 0,318 e diz que a rodada é anterior às correções do piso e das máscaras | — |

Ficam como risco aceito no modo sombra:
- **N6:** a suíte não mede o piso. Ele é coberto por testes unitários.
- **B1:** ids podem se repetir em `store` com hooks concorrentes. O código é compartilhado com as outras avaliações, e no pior caso um veredito vale para dois registros.
- **B4:** o teste de stdin conta `input=text` como entrada própria.
