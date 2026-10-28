# Proposal — Backup só de cópia editada e status livre no plano aprovado

## Intent

Dois atritos que a pessoa viu várias vezes:

1. `aifw claude enable` grava `<arquivo>.bak` sempre que a cópia instalada difere do template, inclusive quando ela só é a versão anterior, sem edição. As cópias ficam em pastas protegidas, então apagar o `.bak` pede confirmação a cada atualização.
2. O `tasks.yaml` de uma mudança aprovada é arquivo de controle (ADR-0039), e por isso marcar uma tarefa como `done` pede confirmação, embora só a lista de `paths` precise de proteção.

## Scope

- **Backup:** a instalação passa a gravar, abaixo do carimbo de versão, o hash do conteúdo instalado (`<!-- aifw-sha256: ... -->`). Na próxima instalação:
  - a cópia cujo conteúdo ainda bate com o hash gravado não foi editada e é trocada sem `.bak`;
  - a cópia editada, ou sem hash (instalada antes desta mudança) e diferente do template, continua indo para `.bak`.
  - Vale para a skill e para os subagentes.
- **Status livre:** editar o `tasks.yaml` de uma mudança aprovada pelas ferramentas de edição (Edit, MultiEdit, Write) deixa de pedir confirmação quando os `paths` de cada tarefa ficam iguais. O hook aplica a edição ao arquivo atual e compara os `paths` antes e depois. Se mudam, se a edição não se aplica ou se o resultado não é YAML legível, continua pedindo. Pelo shell, como hoje, pede.
- Testes, skill (template e cópia), `docs/claude-code.md`, CHANGELOG e ADR-0041.

## Non-goals

- Apagar `.bak` já existentes.
- Ler o efeito de comandos de shell sobre o `tasks.yaml`.

## Acceptance

- Instalar, mudar o template e instalar de novo não cria `.bak`; editar a cópia instalada e instalar de novo cria; uma cópia sem hash e diferente do template cria.
- `aifw claude check` continua passando depois da instalação.
- Com uma mudança aprovada, trocar `status: pending` por `status: done` no `tasks.yaml` dela pelo Edit não pede; incluir um path, ou reescrever o arquivo com Write mudando os `paths`, pede; `sed -i` no arquivo pede.
- Suíte inteira passando e revisão em duas etapas aprovada.
