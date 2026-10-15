# Referência gerada da CLI do AIFW

> Gerado por `python scripts/generate_cli_reference.py`. Guia: [HOW_TO_USE.md](../HOW_TO_USE.md).

Esta referência contém 57 comandos finais e suas opções.

## `aifw --help`

```text
usage: aifw [-h] [--version]
            {init,audit,intake,map,adopt,spec,decision,principle,resolve,change,route,waiver,break-glass,secrets,template,runs,claude,impasse,context,instructions,gates,doctor,eval,validate} ...

AI Software Engineering Framework control plane (Python)

positional arguments:
  {init,audit,intake,map,adopt,spec,decision,principle,resolve,change,route,waiver,break-glass,secrets,template,runs,claude,impasse,context,instructions,gates,doctor,eval,validate}
    init                initialize a project control plane
    audit               inspect a project without changing it
    intake              Manage intake
    map                 Manage map
    adopt               Manage adopt
    spec                Manage spec
    decision            Manage decision
    principle           Manage principle
    resolve             Manage resolve
    change              Manage change
    route               Manage route
    waiver              Manage waiver
    break-glass         Manage break-glass
    secrets             Manage secrets
    template            Manage template
    runs                Manage runs
    claude              Manage claude
    impasse             Manage impasse
    context             Manage context
    instructions        Manage instructions
    gates               Manage gates
    doctor              check Python, Git, Windows and WSL
    eval                evaluate agent behavioral conformance
    validate            run quality gates selected by impact, or for a spec
                        change

options:
  -h, --help            show this help message and exit
  --version, -V         show program's version number and exit
```

## `aifw init`

```text
usage: aifw init [-h] [--json] --id ID --name NAME [--existing] [--flutter]
                 [--web] [--python] [--locale LOCALE]
                 [--primary {windows,wsl,linux}] [--targets TARGETS]

initialize a project control plane

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --id ID               id
  --name NAME           name
  --existing            existing
  --flutter             flutter
  --web                 web
  --python              python
  --locale LOCALE       locale
  --primary {windows,wsl,linux}
                        primary
  --targets TARGETS     targets
```

## `aifw audit`

```text
usage: aifw audit [-h] [--json]

inspect a project without changing it

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw intake status`

```text
usage: aifw intake status [-h] [--json]

show missing human decisions and technical assessments

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw intake approve`

```text
usage: aifw intake approve [-h] [--json] --by BY [--at AT]

persist human approval of a ready charter

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --by BY     by
  --at AT     at
```

## `aifw intake set`

```text
usage: aifw intake set [-h] [--json] --field FIELD --value VALUE

record one Charter decision; editing an approved Charter reopens it

options:
  -h, --help     show this help message and exit
  --json         emit stable machine-readable JSON
  --field FIELD  field
  --value VALUE  value
```

## `aifw map build`

```text
usage: aifw map build [-h] [--json]

regenerate PROJECT_MAP.md

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw map check`

```text
usage: aifw map check [-h] [--json]

verify PROJECT_MAP.md freshness

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw adopt analyze`

```text
usage: aifw adopt analyze [-h] [--json] [--write] [--at AT]

discover factual brownfield references

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --write     write
  --at AT     at
```

## `aifw adopt apply`

```text
usage: aifw adopt apply [-h] [--json] [--at AT]

write factual discovery candidates for review

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --at AT     at
```

## `aifw adopt status`

```text
usage: aifw adopt status [-h] [--json]

show brownfield mapping review state

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw adopt approve`

```text
usage: aifw adopt approve [-h] [--json] --by BY [--at AT]

confirm mapping after human review

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --by BY     by
  --at AT     at
```

## `aifw spec new`

```text
usage: aifw spec new [-h] [--json] --title TITLE --summary SUMMARY
                     --level {L0,L1,L2,L3} [--at AT]
                     id

create a self-contained active spec change

positional arguments:
  id

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --title TITLE         title
  --summary SUMMARY     summary
  --level {L0,L1,L2,L3}
                        level
  --at AT               at
```

## `aifw spec list`

```text
usage: aifw spec list [-h] [--json]

list active and archived changes

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw spec show`

```text
usage: aifw spec show [-h] [--json] id

show a change summary

positional arguments:
  id

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw spec status`

```text
usage: aifw spec status [-h] [--json] [--set {active,ready}] id

show or advance a change status

positional arguments:
  id

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --set {active,ready}  set
```

## `aifw spec validate`

```text
usage: aifw spec validate [-h] [--json] id

validate delta preconditions

positional arguments:
  id

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw spec analyze`

```text
usage: aifw spec analyze [-h] [--json] id

analyze requirement-to-evidence traceability

positional arguments:
  id

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw spec sync`

```text
usage: aifw spec sync [-h] [--json] [--dry-run] id

preview the capability merge without writing

positional arguments:
  id

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --dry-run   dry run
```

## `aifw spec approve`

```text
usage: aifw spec approve [-h] [--json] --by BY [--at AT] --record RECORD id

persist human approval for a change

positional arguments:
  id

options:
  -h, --help       show this help message and exit
  --json           emit stable machine-readable JSON
  --by BY          by
  --at AT          at
  --record RECORD  record
```

## `aifw spec archive`

```text
usage: aifw spec archive [-h] [--json] [--at AT] id

commit validated specs and archive context

positional arguments:
  id

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --at AT     at
```

## `aifw decision list`

```text
usage: aifw decision list [-h] [--json] [--category CATEGORY]

list decision categories and alternatives

options:
  -h, --help           show this help message and exit
  --json               emit stable machine-readable JSON
  --category CATEGORY  category
```

## `aifw decision recommend`

```text
usage: aifw decision recommend [-h] [--json] --category CATEGORY
                               --signals SIGNALS [--selected SELECTED]
                               [--write]

rank alternatives from explicit signals

options:
  -h, --help           show this help message and exit
  --json               emit stable machine-readable JSON
  --category CATEGORY  category
  --signals SIGNALS    signals
  --selected SELECTED  selected
  --write              write
```

## `aifw decision approve`

```text
usage: aifw decision approve [-h] [--json] --by BY [--at AT]
                             --category CATEGORY --option OPTION --adr ADR

approve an eligible decision with an ADR

options:
  -h, --help           show this help message and exit
  --json               emit stable machine-readable JSON
  --by BY              by
  --at AT              at
  --category CATEGORY  category
  --option OPTION      option
  --adr ADR            adr
```

## `aifw principle list`

```text
usage: aifw principle list [-h] [--json]
                           [--family {clean-code,solid,foundational}]

list engineering principles

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --family {clean-code,solid,foundational}
                        family
```

## `aifw resolve build`

```text
usage: aifw resolve build [-h] [--json] [--personal PERSONAL]

resolve authority layers and verify the pinned policy

options:
  -h, --help           show this help message and exit
  --json               emit stable machine-readable JSON
  --personal PERSONAL  personal
```

## `aifw resolve check`

```text
usage: aifw resolve check [-h] [--json] [--personal PERSONAL]

resolve authority layers and verify the pinned policy

options:
  -h, --help           show this help message and exit
  --json               emit stable machine-readable JSON
  --personal PERSONAL  personal
```

## `aifw change classify`

```text
usage: aifw change classify [-h] [--json] [--read-only] [--docs-only]
                            [--behavior-change] [--local-only] [--reversible]
                            [--cross-module] [--shared-contract]
                            [--sensitive-data] [--global-design-system]
                            [--external-cost] [--production] [--touches-auth]
                            [--framework-core] [--constitution]
                            [--security-boundary] [--destructive-migration]
                            [--breaking-contract] [--irreversible-production]
                            [--complexity {fast,work,brain}] [--diff]
                            [--base BASE]

classify change impact

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --read-only           read only
  --docs-only           docs only
  --behavior-change     behavior change
  --local-only          local only
  --reversible          reversible
  --cross-module        cross module
  --shared-contract     shared contract
  --sensitive-data      sensitive data
  --global-design-system
                        global design system
  --external-cost       external cost
  --production          production
  --touches-auth        touches auth
  --framework-core      framework core
  --constitution        constitution
  --security-boundary   security boundary
  --destructive-migration
                        destructive migration
  --breaking-contract   breaking contract
  --irreversible-production
                        irreversible production
  --complexity {fast,work,brain}
                        complexity
  --diff                diff
  --base BASE           base
```

## `aifw route explain`

```text
usage: aifw route explain [-h] [--json] --impact {L0,L1,L2,L3}
                          --operation {single-read,discovery,documentation,implementation,review,research,architecture-decision,incident-response}
                          --uncertainty {low,medium,high}
                          [--failed-attempts FAILED_ATTEMPTS] [--cross-domain]

explain deterministic cognitive routing

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --impact {L0,L1,L2,L3}
                        impact
  --operation {single-read,discovery,documentation,implementation,review,research,architecture-decision,incident-response}
                        operation
  --uncertainty {low,medium,high}
                        uncertainty
  --failed-attempts FAILED_ATTEMPTS
                        failed attempts
  --cross-domain        cross domain
```

## `aifw route status`

```text
usage: aifw route status [-h] [--json]

show persisted routing state

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw route eval`

```text
usage: aifw route eval [-h] [--json] [--cases CASES] [--output OUTPUT]

evaluate routing against reviewable cases

options:
  -h, --help       show this help message and exit
  --json           emit stable machine-readable JSON
  --cases CASES    cases
  --output OUTPUT  output
```

## `aifw route activate`

```text
usage: aifw route activate [-h] [--json] --report REPORT --by BY
                           --record RECORD

activate routing after evals and human approval

options:
  -h, --help       show this help message and exit
  --json           emit stable machine-readable JSON
  --report REPORT  report
  --by BY          by
  --record RECORD  record
```

## `aifw waiver add`

```text
usage: aifw waiver add [-h] [--json] --rule RULE --scope SCOPE --reason REASON
                       --expires EXPIRES [--requested-by REQUESTED_BY] --by BY
                       [--at AT]

record a time-bounded human exception for a gate or overridable rule

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --rule RULE           rule
  --scope SCOPE         scope
  --reason REASON       reason
  --expires EXPIRES     expires
  --requested-by REQUESTED_BY
                        requested by
  --by BY               by
  --at AT               at
```

## `aifw waiver list`

```text
usage: aifw waiver list [-h] [--json]

list waivers and whether they are active

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw break-glass grant`

```text
usage: aifw break-glass grant [-h] [--json] --incident INCIDENT --scope SCOPE
                              --reason REASON [--hours HOURS] --by BY
                              [--at AT]

grant temporary incident permissions honored by the Claude hook

options:
  -h, --help           show this help message and exit
  --json               emit stable machine-readable JSON
  --incident INCIDENT  incident
  --scope SCOPE        scope
  --reason REASON      reason
  --hours HOURS        hours
  --by BY              by
  --at AT              at
```

## `aifw break-glass list`

```text
usage: aifw break-glass list [-h] [--json]

list incident grants and whether they are active

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw secrets scan`

```text
usage: aifw secrets scan [-h] [--json] [--history]

find secrets in project files; reports locations, never values

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --history   history
```

## `aifw template list`

```text
usage: aifw template list [-h] [--json]

list document templates

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw template copy`

```text
usage: aifw template copy [-h] [--json] --name NAME [--change CHANGE]
                          [--output OUTPUT]

copy a template into a spec change or a project path

options:
  -h, --help       show this help message and exit
  --json           emit stable machine-readable JSON
  --name NAME      name
  --change CHANGE  change
  --output OUTPUT  output
```

## `aifw runs show`

```text
usage: aifw runs show [-h] [--json] [--session SESSION]

summarize recorded Claude sessions against the workflow rules

options:
  -h, --help         show this help message and exit
  --json             emit stable machine-readable JSON
  --session SESSION  session
```

## `aifw claude install`

```text
usage: aifw claude install [-h] [--json]

install the /aifw command in ~/.claude (it activates nothing by itself)

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw claude enable`

```text
usage: aifw claude enable [-h] [--json]

add the AIFW hooks and workflow skill to this project's .claude folder

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw claude check`

```text
usage: aifw claude check [-h] [--json]

report what Claude Code still needs to run AIFW in this project

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw impasse open`

```text
usage: aifw impasse open [-h] [--json] --id ID --impact {L0,L1,L2,L3}

start tracking correction attempts for a problem

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --id ID               id
  --impact {L0,L1,L2,L3}
                        impact
```

## `aifw impasse attempt`

```text
usage: aifw impasse attempt [-h] [--json] --id ID --hypothesis HYPOTHESIS
                            --intervention INTERVENTION --evidence EVIDENCE
                            --outcome {success,failure,inconclusive} [--at AT]

record a distinct correction attempt

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --id ID               id
  --hypothesis HYPOTHESIS
                        hypothesis
  --intervention INTERVENTION
                        intervention
  --evidence EVIDENCE   evidence
  --outcome {success,failure,inconclusive}
                        outcome
  --at AT               at
```

## `aifw impasse status`

```text
usage: aifw impasse status [-h] [--json] [--id ID]

show impasse cases and whether mutations are frozen

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --id ID     id
```

## `aifw impasse review`

```text
usage: aifw impasse review [-h] [--json] --id ID --rule RULE
                           --explanation EXPLANATION --proposal PROPOSAL

submit an open impasse with a framework proposal for human review

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --id ID               id
  --rule RULE           rule
  --explanation EXPLANATION
                        explanation
  --proposal PROPOSAL   proposal
```

## `aifw impasse decide`

```text
usage: aifw impasse decide [-h] [--json] --id ID --record RECORD --by BY
                           [--at AT]

persist the human decision approving the proposed change

options:
  -h, --help       show this help message and exit
  --json           emit stable machine-readable JSON
  --id ID          id
  --record RECORD  record
  --by BY          by
  --at AT          at
```

## `aifw impasse revalidate`

```text
usage: aifw impasse revalidate [-h] [--json] --id ID --result {passed,failed}
                               --evidence EVIDENCE --artifacts ARTIFACTS

record revalidation after an approved change

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --id ID               id
  --result {passed,failed}
                        result
  --evidence EVIDENCE   evidence
  --artifacts ARTIFACTS
                        artifacts
```

## `aifw context index`

```text
usage: aifw context index [-h] [--json] [--write]

inventory local documentation; optionally save a factual baseline

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
  --write     write
```

## `aifw context check`

```text
usage: aifw context check [-h] [--json]

check local references and drift against the saved baseline

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw context select`

```text
usage: aifw context select [-h] [--json] --task TASK [--intent INTENT]
                           [--files FILES] [--budget BUDGET]

select task context without dropping required dependencies

options:
  -h, --help       show this help message and exit
  --json           emit stable machine-readable JSON
  --task TASK      task
  --intent INTENT  intent
  --files FILES    files
  --budget BUDGET  budget
```

## `aifw instructions build`

```text
usage: aifw instructions build [-h] [--json]
                               [--agent {all,codex,claude,opencode}]
                               [--source SOURCE]

generate or check managed blocks from shared project instructions

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --agent {all,codex,claude,opencode}
                        agent
  --source SOURCE       source
```

## `aifw instructions check`

```text
usage: aifw instructions check [-h] [--json]
                               [--agent {all,codex,claude,opencode}]
                               [--source SOURCE]

generate or check managed blocks from shared project instructions

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --agent {all,codex,claude,opencode}
                        agent
  --source SOURCE       source
```

## `aifw gates check`

```text
usage: aifw gates check [-h] [--json] --level {L0,L1,L2,L3}

inspect gate configuration and static GitHub CI references without running
them

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --level {L0,L1,L2,L3}
                        level
```

## `aifw doctor`

```text
usage: aifw doctor [-h] [--json]

check Python, Git, Windows and WSL

options:
  -h, --help  show this help message and exit
  --json      emit stable machine-readable JSON
```

## `aifw eval`

```text
usage: aifw eval [-h] [--json] [--cases CASES] [--traces TRACES]

evaluate agent behavioral conformance

options:
  -h, --help       show this help message and exit
  --json           emit stable machine-readable JSON
  --cases CASES    cases
  --traces TRACES  traces
```

## `aifw validate`

```text
usage: aifw validate [-h] [--json] [--level {L0,L1,L2,L3}] [--change CHANGE]
                     [--write]

run quality gates selected by impact, or for a spec change

options:
  -h, --help            show this help message and exit
  --json                emit stable machine-readable JSON
  --level {L0,L1,L2,L3}
                        level
  --change CHANGE       change
  --write               write
```
