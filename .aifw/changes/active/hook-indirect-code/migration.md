# Migração — Hook lê código indireto

Não se aplica: a mudança não altera dados, schemas, arquivos persistidos nem a interface da CLI. O hook só passa a ler mais arquivos antes de decidir.

Efeito visível para quem usa: comandos que antes passavam em silêncio podem pedir confirmação quando o script que executam publica, instala, apaga ou envia dados, ou quando o hook não consegue ler o arquivo executado. Nenhuma configuração precisa mudar. Quem quiser liberar código ilegível continua usando `opaqueCode: allow` em `permissions.yaml`.
