# Design — Context intelligence

## Approach

Optional CLI groups delegate to context.py and instructions.py. JSON Schema validates factual snapshots. Existing quality gates gain optional built-in context and instruction checks. Discovery supports conventional decisions directories.

## Decisions

See docs/decisions/ADR-0012-context-intelligence.md for user authorization and tradeoffs. Context metadata is advisory; source contents are not returned. All selected dependencies survive budget overflow. CI results remain not-run.

## Risks and rollback

Lexical matching is limited; hash drift does not certify semantic truth; literal CI matching cannot prove deployment protection. Failed instruction writes attempt restoration. Source checkpoint: .aifw/cache/checkpoints/before-context-intelligence. New commands are optional; no existing project is automatically migrated.
