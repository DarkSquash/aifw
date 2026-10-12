import { spawnSync } from "node:child_process";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

const requiredArtifacts = [
  "README.md",
  "HOW_TO_USE.md",
  "CONSTITUTION.md",
  "LICENSE",
  ".github/workflows/ci.yml",
  "docs/architecture.md",
  "docs/authority.md",
  "docs/project-intake.md",
  "docs/change-lifecycle.md",
  "docs/impasse-prevention.md",
  "docs/project-map.md",
  "docs/quality-gates.md",
  "docs/agent-conformance.md",
  "docs/pi-adapter.md",
  "docs/tooling-and-mcps.md",
  "docs/security.md",
  "docs/observability-and-runbooks.md",
  "docs/windows-wsl.md",
  "docs/cli.md",
  "docs/cli-reference.generated.md",
  "docs/decision-catalogs.md",
  "docs/engineering-principles.md",
  "docs/existing-project-adoption.md",
  "docs/spec-lifecycle.md",
  "docs/traceability.md",
  "docs/pi-context-files.md",
  "docs/codex-fallback.md",
  "docs/gap-audit-2026-08-23.md",
  "docs/migrations.md",
  "docs/decisions/ADR-0001-typescript-cli.md",
  "docs/decisions/ADR-0002-agent-independent-core.md",
  "docs/decisions/ADR-0003-routing-disabled-default.md",
  "docs/decisions/ADR-0005-global-decision-catalogs.md",
  "docs/decisions/ADR-0006-short-stack-flags.md",
  "docs/decisions/ADR-0007-contextual-engineering-principles.md",
  "docs/decisions/ADR-0008-pi-routing-and-codex-fallback.md",
  "docs/decisions/ADR-0009-executable-spec-core-and-brownfield-adoption.md",
  "templates/adr.md",
  "templates/spec.md",
  "templates/technical-plan.md",
  "templates/change-case.yaml",
  "templates/c4.md",
  "templates/openapi.yaml",
  "templates/asyncapi.yaml",
  "templates/design-tokens.json",
  "templates/storybook.md",
  "templates/threat-model.md",
  "templates/observability.md",
  "templates/runbook.md",
  "templates/impasse.yaml",
  "templates/waiver.yaml",
  "templates/codex-handoff-input.json",
  "templates/capability-spec.yaml",
  "templates/capability-delta.yaml",
  "templates/change-tasks.yaml",
  "templates/traceability.yaml",
  "schemas/codex-handoff.schema.json",
  "schemas/spec-change.schema.json",
  "schemas/capability-spec.schema.json",
  "schemas/capability-delta.schema.json",
  "schemas/change-tasks.schema.json",
  "schemas/traceability.schema.json",
  "schemas/brownfield-discovery.schema.json",
  "schemas/brownfield-adoption.schema.json",
];

describe("framework documentation and delivery artifacts", () => {
  it("ships every required architecture, operations and contract artifact", async () => {
    for (const relativePath of requiredArtifacts) {
      await assert.doesNotReject(() => access(path.join(root, relativePath)), relativePath);
    }
  });

  it("persists the non-negotiable decisions outside AI conversations", async () => {
    const [constitution, intake, impasse, pi, tooling, windows, cli] = await Promise.all([
      readFile(path.join(root, "CONSTITUTION.md"), "utf8"),
      readFile(path.join(root, "docs", "project-intake.md"), "utf8"),
      readFile(path.join(root, "docs", "impasse-prevention.md"), "utf8"),
      readFile(path.join(root, "docs", "pi-adapter.md"), "utf8"),
      readFile(path.join(root, "docs", "tooling-and-mcps.md"), "utf8"),
      readFile(path.join(root, "docs", "windows-wsl.md"), "utf8"),
      readFile(path.join(root, "docs", "cli.md"), "utf8"),
    ]);

    assert.match(constitution, /conversa com (uma )?IA.*fonte de verdade/iu);
    assert.match(intake, /problema.*público.*resultado.*escopo/isu);
    assert.doesNotMatch(intake, /usuário (deve|precisa) escolher (a )?stack/iu);
    assert.match(impasse, /L0.*L1.*cinco/isu);
    assert.match(impasse, /L2.*L3.*duas/isu);
    assert.match(pi, /default.*(enabled: false|recommendation-only)/isu);
    assert.match(tooling, /Serena/);
    assert.match(tooling, /skills? específicas demais/iu);
    assert.match(windows, /WSL.*validação/isu);
    assert.match(windows, /TypeScript.*Python/isu);
    assert.match(cli, /plano de controle/iu);
  });

  it("keeps the generated CLI reference synchronized with real help output", () => {
    const result = spawnSync(
      process.execPath,
      [path.join(root, "scripts", "generate-cli-reference.mjs"), "--check"],
      { cwd: root, encoding: "utf8", env: { ...process.env, NO_COLOR: "1" } },
    );

    assert.equal(result.status, 0, result.stderr || result.stdout);
  });
});
